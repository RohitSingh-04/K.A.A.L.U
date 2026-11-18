import asyncio
import json
from websockets import connect
from faulkner_system.terminal_executor import TerminalExecutor
from faulkner_system.screen_capture import ScreenCapture

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