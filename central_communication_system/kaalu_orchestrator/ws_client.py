import asyncio
import json
from typing import Any, Dict, Optional
from websockets import connect
from websockets.protocol import State

class KaaluWSClient:
    """
    WebSocket client for Kaalu Orchestrator.
    Connects to the RGS Hub router at /ws/kaalu to dispatch tasks and receive agent feedback.
    Features robust connection state checking and automatic reconnection.
    """
    def __init__(self, uri: str = "ws://localhost:8000/ws/kaalu"):
        self.uri = uri
        self.websocket = None

    @property
    def is_connected(self) -> bool:
        """Returns True if WebSocket connection is open and ready to transmit."""
        if self.websocket is None:
            return False
        # WebSockets 13+ State check
        state = getattr(self.websocket, "state", None)
        if state is not None:
            return state == State.OPEN
        return not getattr(self.websocket, "closed", True)

    async def connect_server(self, timeout: float = 5.0) -> bool:
        """Establish a persistent WebSocket connection to the RGS Hub."""
        if self.is_connected:
            return True

        # Clean up stale connection reference if any
        if self.websocket is not None:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None

        try:
            # ping_interval=None prevents unwanted 1011 keepalive ping timeouts on local loops
            self.websocket = await connect(self.uri, open_timeout=timeout, ping_interval=None)
            print(f"[Kaalu WS] Connected to RGS Hub successfully at {self.uri}.")
            return True
        except Exception as e:
            print(f"[Kaalu WS Error] Failed to connect to RGS Hub at {self.uri}: {e}")
            self.websocket = None
            raise ConnectionError(
                f"Could not connect to RGS Hub at {self.uri}. Ensure the RGS Hub server is running."
            ) from e

    async def send_task(self, recipient: str, action: str, payload: Optional[Dict[str, Any]] = None):
        """Dispatch a structured task payload to a target agent with auto-reconnect retry."""
        if not self.is_connected:
            await self.connect_server()

        message = {
            "recipient": recipient,
            "action": action,
            "payload": payload if payload is not None else {}
        }
        raw_msg = json.dumps(message)

        try:
            await self.websocket.send(raw_msg)
            print(f"[Kaalu WS] Dispatched task -> Recipient: '{recipient}' | Action: '{action}'")
        except Exception as send_err:
            print(f"[Kaalu WS Warning] Send failed ({send_err}). Attempting reconnect & retry...")
            self.websocket = None
            await self.connect_server()
            await self.websocket.send(raw_msg)
            print(f"[Kaalu WS] Reconnected and dispatched task -> Recipient: '{recipient}' | Action: '{action}'")

    async def receive_response(self, timeout: float = 60.0) -> Optional[Dict[str, Any]]:
        """
        Listen for incoming execution feedback from agents with a safety timeout.
        Returns parsed JSON dictionary.
        """
        if not self.is_connected:
            print("[Kaalu WS Error] Cannot receive response: WebSocket is not connected.")
            return {
                "sender": "system",
                "action": "error",
                "status": "error",
                "payload": {"error": "WebSocket connection lost.", "success": False}
            }

        try:
            raw_response = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
            data = json.loads(raw_response)
            sender = data.get("sender", "unknown")
            action = data.get("action", "unknown")
            print(f"[Kaalu WS] Received response from '{sender}' (action: '{action}')")
            return data
        except asyncio.TimeoutError:
            print(f"[Kaalu WS Warning] Timed out waiting for response after {timeout}s.")
            return {
                "sender": "system",
                "action": "timeout",
                "status": "error",
                "payload": {"error": f"Timed out waiting for response from agent after {timeout} seconds.", "success": False}
            }
        except Exception as e:
            print(f"[Kaalu WS Error] Connection error during receive: {e}")
            self.websocket = None
            return {
                "sender": "system",
                "action": "error",
                "status": "error",
                "payload": {"error": str(e), "success": False}
            }

    async def close(self):
        """Close the WebSocket connection cleanly."""
        if self.websocket:
            try:
                await self.websocket.close()
                print("[Kaalu WS] Connection closed.")
            except Exception:
                pass
            finally:
                self.websocket = None
