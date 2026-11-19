import asyncio
import json
from websockets import connect
from faulkner_system.terminal_executor import TerminalExecutor
from faulkner_system.screen_capture import ScreenCapture
from faulkner_system.phone_link import PhoneLinkController

class FaulknerWSClient:
    def __init__(self, uri="ws://localhost:8000/ws/faulkner"):
        self.uri = uri

    async def start_listening(self):
        """Main persistent loop connecting Faulkner to RGS Hub and processing incoming jobs."""
        while True:
            try:
                print(f"[Faulkner WS] Connecting to RGS Hub at {self.uri}...")
                async with connect(self.uri, ping_interval=None) as websocket:
                    print("[Faulkner WS] Connected successfully. Awaiting tasks...")
                    
                    async for raw_message in websocket:
                        data = json.loads(raw_message)
                        sender = data.get("sender", "unknown")
                        action = data.get("action")
                        payload = data.get("payload", {})
                        
                        print(f"[Faulkner WS] Received task from '{sender}' | Action: '{action}'")
                        
                        # Handle specific actions
                        result_payload = {}
                        if action == "execute_terminal":
                            command = payload.get("command", "")
                            result_payload = TerminalExecutor.run_command(command)
                        elif action == "capture_screen":
                            screenshot_b64 = ScreenCapture.capture_screen_base64()
                            result_payload = {"screenshot_base64": screenshot_b64}
                        elif action in ("phone_link_call", "call_phone_link", "phone_link_dial"):
                            target = payload.get("target") or payload.get("contact") or payload.get("phone_number") or payload.get("number", "")
                            phone_number = payload.get("phone_number") or payload.get("number")
                            result_payload = PhoneLinkController.dial(
                                target=str(target),
                                phone_number=str(phone_number) if phone_number else None
                            )
                        elif action in ("open_phone_link", "launch_phone_link"):
                            result_payload = PhoneLinkController.open_app()
                        elif action in ("close_phone_link", "close_phone_link_window", "dismiss_phone_link"):
                            result_payload = PhoneLinkController.close_app()
                        elif action in ("phone_link_sms", "send_phone_link_sms"):
                            target = payload.get("target") or payload.get("contact") or payload.get("phone_number", "")
                            message = payload.get("message") or payload.get("text", "")
                            phone_number = payload.get("phone_number") or payload.get("number")
                            result_payload = PhoneLinkController.send_sms(
                                target=str(target),
                                message=str(message),
                                phone_number=str(phone_number) if phone_number else None
                            )
                        else:
                            result_payload = {"error": f"Unknown action '{action}' requested."}

                        # Send execution results back through RGS to the sender
                        response_message = {
                            "recipient": sender,
                            "action": f"{action}_result",
                            "payload": result_payload
                        }
                        await websocket.send(json.dumps(response_message))
                        print(f"[Faulkner WS] Sent result back to '{sender}'.")
                        
            except Exception as e:
                print(f"[Faulkner WS Error] Connection lost: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)