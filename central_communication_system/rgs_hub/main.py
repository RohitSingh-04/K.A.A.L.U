from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from rgs_hub.ws_manager import ConnectionManager
from rgs_hub.schemas import AgentMessage, LLMGenerationRequest, LLMGenerationResponse
from rgs_hub.llm_gateway import LLMGateway

app = FastAPI(title="RGS Central Gateway & Communication Hub", version="2.0.0")

# Enable CORS for external agents and UI connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()
llm_gateway = LLMGateway()

@app.get("/")
async def root():
    """Health check endpoint showing active WebSocket clients and default LLM configuration."""
    return {
        "status": "RGS Central Gateway is active",
        "active_clients": list(manager.active_connections.keys()),
        "default_llm_provider": llm_gateway.config.get("llm", {}).get("default_provider"),
        "default_model": llm_gateway.config.get("llm", {}).get("default_model")
    }

@app.post("/llm/generate", response_model=LLMGenerationResponse)
async def generate_llm_completion(request: LLMGenerationRequest):
    """
    Centralized LLM inference endpoint. 
    Agents (like Kaalu) send their prompts here instead of connecting to local models directly.
    """
    try:
        result = await llm_gateway.generate(
            prompt=request.prompt,
            messages=[m.model_dump() for m in request.messages] if request.messages else None,
            provider=request.provider,
            model=request.model,
            temperature=request.temperature
        )
        return LLMGenerationResponse(**result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint where agents (Kaalu, Faulkner, David) register and communicate.
    """
    await manager.connect(client_id, websocket)
    try:
        while True:
            raw_data = await websocket.receive_json()
            if raw_data.get("action") == "ping":
                await websocket.send_json({
                    "recipient": client_id,
                    "sender": "rgs_hub",
                    "action": "pong",
                    "payload": {}
                })
                continue

            try:
                message = AgentMessage(**raw_data)
                await manager.route_message(client_id, message.model_dump())
            except Exception as validation_error:
                await websocket.send_json({
                    "sender": "rgs_hub",
                    "status": "error",
                    "error": f"Invalid message schema: {str(validation_error)}"
                })
    except WebSocketDisconnect:
        manager.disconnect(client_id)