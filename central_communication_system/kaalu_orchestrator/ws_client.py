import asyncio
import json
from websockets import connect

class KaaluWSClient:
    def __init__(self, uri="ws://localhost:8000/ws/kaalu"):
        self.uri = uri
        self.websocket = None

    async def connect_server(self):
        """Establish a persistent WebSocket connection to the RGS Hub."""
        if not self.websocket:
            self.websocket = await connect(self.uri)
            print("[Kaalu WS] Connected to RGS Hub successfully.")

    async def send_task(self, recipient: str, action: str, payload: dict):
        """Dispatch a structured task payload to a target agent (faulkner or david)."""
        if not self.websocket:
            await self.connect_server()
            
        message = {
            "recipient": recipient,
            "action": action,
            "payload": payload
        }
        await self.websocket.send(json.dumps(message))
        print(f"[Kaalu WS] Dispatched task -> Recipient: '{recipient}' | Action: '{action}'")

    async def listen_response(self):
        """Listen for incoming execution feedback or verification states from agents."""
        try:
            if self.websocket:
                response = await self.websocket.recv()
                data = json.loads(response)
                print(f"[Kaalu WS] Received data: {data}")
                return data
        except Exception as e:
            print(f"[Kaalu WS Error] Failed to receive message: {e}")
            return None