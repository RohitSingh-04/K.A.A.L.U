from typing import Dict, List, Any
from datetime import datetime
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # Maps client IDs (e.g., "kaalu", "faulkner", "david") to their WebSocket connections
        self.active_connections: Dict[str, WebSocket] = {}
        # Active GUI terminal stream subscribers
        self.terminal_subscribers: List[WebSocket] = []

    async def connect(self, client_id: str, websocket: WebSocket):
        """Accepts a new WebSocket connection and registers the client ID."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"[RGS Hub] Client connected: {client_id}")
        await self.broadcast_terminal({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "source": "rgs_hub",
            "type": "connect",
            "message": f"Client connected: '{client_id}'"
        })

    def disconnect(self, client_id: str):
        """Removes a client from active connections upon disconnection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            print(f"[RGS Hub] Client disconnected: {client_id}")

    async def subscribe_terminal(self, websocket: WebSocket):
        """Registers a GUI terminal subscriber for live system streaming."""
        await websocket.accept()
        if websocket not in self.terminal_subscribers:
            self.terminal_subscribers.append(websocket)
        print(f"[RGS Hub] Terminal subscriber attached (Total: {len(self.terminal_subscribers)})")

    def unsubscribe_terminal(self, websocket: WebSocket):
        """Removes a GUI terminal subscriber upon disconnection."""
        if websocket in self.terminal_subscribers:
            self.terminal_subscribers.remove(websocket)
            print(f"[RGS Hub] Terminal subscriber detached (Total: {len(self.terminal_subscribers)})")

    async def broadcast_terminal(self, log_entry: Dict[str, Any]):
        """Broadcasts a live log or step event to all active GUI terminal clients."""
        if not self.terminal_subscribers:
            return
        dead = []
        for ws in self.terminal_subscribers:
            try:
                await ws.send_json(log_entry)
            except Exception:
                dead.append(ws)
        for d in dead:
            if d in self.terminal_subscribers:
                self.terminal_subscribers.remove(d)

    async def route_message(self, sender_id: str, data: dict):
        """Routes a message based on a 'recipient' field inside the incoming JSON payload."""
        recipient = data.get("recipient")
        action = data.get("action", "unknown")
        
        # Broadcast routing activity to live GUI terminal
        await self.broadcast_terminal({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "source": sender_id,
            "recipient": recipient,
            "type": "route",
            "action": action,
            "message": f"[{sender_id} -> {recipient}] Action: {action}"
        })

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