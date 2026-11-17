from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from rgs_hub.ws_manager import ConnectionManager
from rgs_hub.schemas import AgentMessage

# ... (keep your app initialization, CORS middleware, and manager definition) ...

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint where agents register and communicate.
    """
    await manager.connect(client_id, websocket)
    try:
        while True:
            # Receive raw JSON from the client
            raw_data = await websocket.receive_json()
            
            try:
                # Validate and parse incoming data using the Pydantic schema
                message = AgentMessage(**raw_data)
                
                # Convert back to dict for routing (or pass the model object)
                await manager.route_message(client_id, message.model_dump())
                
            except Exception as validation_error:
                # Send a validation error back to the sender if the schema is malformed
                await websocket.send_json({
                    "sender": "rgs_hub",
                    "status": "error",
                    "error": f"Invalid message schema: {str(validation_error)}"
                })
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)