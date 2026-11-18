from typing import Dict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # Maps client IDs (e.g., "kaalu", "faulkner", "david") to their WebSocket connections
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        """Accepts a new WebSocket connection and registers the client ID."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"[RGS Hub] Client connected: {client_id}")

    def disconnect(self, client_id: str):
        """Removes a client from active connections upon disconnection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            print(f"[RGS Hub] Client disconnected: {client_id}")

    async def route_message(self, sender_id: str, data: dict):
        """Routes a message based on a 'recipient' field inside the incoming JSON payload."""
        recipient = data.get("recipient")
        if recipient and recipient in self.active_connections:
            data["sender"] = sender_id
            await self.active_connections[recipient].send_json(data)
            print(f"[RGS Hub] Routed message from '{sender_id}' to '{recipient}'")
        else:
            print(f"[RGS Hub] Warning: Recipient '{recipient}' not found or offline.")
            if sender_id and sender_id in self.active_connections:
                error_reply = {
                    "recipient": sender_id,
                    "sender": "rgs_hub",
                    "action": f"{data.get('action', 'task')}_result",
                    "status": "error",
                    "error": f"Agent '{recipient}' is not connected or offline.",
                    "payload": {
                        "success": False,
                        "error": f"Agent '{recipient}' is offline."
                    }
                }
                await self.active_connections[sender_id].send_json(error_reply)