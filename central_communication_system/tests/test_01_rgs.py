import json
from fastapi.testclient import TestClient
from rgs_hub.main import app

def test_rgs_websocket_routing():
    """Integration test verifying RGS WebSocket connection and message routing between agents."""
    client = TestClient(app)
    
    with client.websocket_connect("/ws/kaalu") as kaalu_ws:
        with client.websocket_connect("/ws/faulkner") as faulkner_ws:
            # Kaalu sends a message intended for Faulkner via the RGS Hub
            test_payload = {
                "recipient": "faulkner",
                "action": "execute_terminal",
                "payload": {"command": "echo 'RGS Gateway Test Successful'"}
            }
            
            kaalu_ws.send_json(test_payload)
            
            # Faulkner receives the routed message
            parsed = faulkner_ws.receive_json()
            
            # Assertions
            assert parsed["sender"] == "kaalu"
            assert parsed["action"] == "execute_terminal"
            assert parsed["payload"]["command"] == "echo 'RGS Gateway Test Successful'"
