import asyncio
from faulkner_system.ws_client import FaulknerWSClient

if __name__ == "__main__":
    client = FaulknerWSClient()
    print("[Faulkner Agent] Starting system execution agent...")
    try:
        asyncio.run(client.start_listening())
    except KeyboardInterrupt:
        print("[Faulkner Agent] Shutting down gracefully.")