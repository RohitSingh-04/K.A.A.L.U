import json
import pytest
from websockets import connect

@pytest.mark.asyncio
async def test_rgs_websocket_routing():
    """Integration test verifying RGS WebSocket connection and message routing between agents."""
    # Ensure your FastAPI server is running on port 8000 before executing pytest
    async with connect("ws://localhost:8000/ws/kaalu") as kaalu_ws:
        async with connect("ws://localhost:8000/ws/faulkner") as faulkner_ws:
            
            # Kaalu sends a message intended for Faulkner via the RGS Hub
            test_payload = {
                "recipient": "faulkner",
                "action": "execute_terminal",
                "payload": {"command": "echo 'RGS Gateway Test Successful'"}
            }
            
            await kaalu_ws.send(json.dumps(test_payload))
            
            # Faulkner receives the routed message
            response = await faulkner_ws.recv()
            parsed = json.loads(response)
            
            # Assertions
            assert parsed["sender"] == "kaalu"
            assert parsed["action"] == "execute_terminal"
            assert parsed["payload"]["command"] == "echo 'RGS Gateway Test Successful'"