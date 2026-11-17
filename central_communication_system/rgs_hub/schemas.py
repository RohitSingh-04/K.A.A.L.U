from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class AgentMessage(BaseModel):
    """
    Standard schema for all WebSocket messages routed through the RGS Hub.
    
    Example JSON Payload:
    {
        "recipient": "faulkner",
        "action": "execute_terminal",
        "payload": {
            "command": "ls -la"
        }
    }
    """
    recipient: str = Field(..., description="The target client ID (e.g., 'kaalu', 'faulkner', 'david')")
    sender: Optional[str] = Field(None, description="The origin client ID (automatically injected by the RGS Hub)")
    action: str = Field(..., description="The specific action or instruction identifier (e.g., 'execute_command', 'click_element')")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Dictionary containing action-specific arguments and data")
    status: Optional[str] = Field(None, description="Optional status field for responses (e.g., 'success', 'failed', 'pending')")
    error: Optional[str] = Field(None, description="Optional error description if an action execution fails")