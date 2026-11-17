import asyncio
import json
from websockets import connect

async def simulate_agents():
    # 1. Connect 'kaalu' client
    async with connect("ws://localhost:8000/ws/kaalu") as kaalu_ws:
        # 2. Connect 'faulkner' client in parallel or sequence
        async with connect("ws://localhost:8000/ws/faulkner") as faulkner_ws:
            
            print("[Test] Both agents connected successfully to RGS.")
            
            # 3. Kaalu sends a message intended for Faulkner via the hub
            test_payload = {
                "recipient": "faulkner",
                "action": "execute_terminal",
                "payload": {"command": "echo 'RGS Test Successful'"}
            }
            
            await kaalu_ws.send(json.dumps(test_payload))
            print("[Test] Kaalu sent payload to RGS hub.")
            
            # 4. Faulkner receives the routed message
            response = await faulkner_ws.recv()
            print(f"[Test] Faulkner received raw data: {response}")
            
            parsed = json.loads(response)
            assert parsed["sender"] == "kaalu"
            assert parsed["action"] == "execute_terminal"
            print("[Test Verification Passed]: Message successfully routed from Kaalu to Faulkner!")

if __name__ == "__main__":
    asyncio.run(simulate_agents())