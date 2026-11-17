from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class AgentMessage(BaseModel):
    """Standard schema for WebSocket messages routed through the RGS Hub."""
    recipient: str = Field(..., description="Target client ID (e.g., 'kaalu', 'faulkner', 'david')")
    sender: Optional[str] = Field(None, description="Origin client ID (injected by RGS)")
    action: str = Field(..., description="Action/instruction identifier")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Action-specific arguments")
    status: Optional[str] = Field(None, description="Optional status field")
    error: Optional[str] = Field(None, description="Optional error description")

class LLMMessage(BaseModel):
    role: str = Field(..., description="Role of the speaker: 'system', 'user', or 'assistant'")
    content: str = Field(..., description="Text content of the prompt or response")

class LLMGenerationRequest(BaseModel):
    """Schema for agents requesting centralized LLM inference via RGS."""
    prompt: Optional[str] = Field(None, description="Direct prompt string")
    messages: Optional[List[LLMMessage]] = Field(None, description="Chat message history array")
    provider: Optional[str] = Field(None, description="Override provider ('ollama', 'openai', etc.)")
    model: Optional[str] = Field(None, description="Override specific model name")
    temperature: float = Field(0.0, description="Sampling temperature")

class LLMGenerationResponse(BaseModel):
    """Schema for the returned LLM text output."""
    provider: str
    model: str
    response: str
    usage: Optional[Dict[str, Any]] = None