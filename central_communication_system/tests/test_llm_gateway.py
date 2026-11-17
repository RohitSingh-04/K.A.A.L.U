from fastapi.testclient import TestClient
from unittest.mock import patch
from rgs_hub.main import app

client = TestClient(app)

def test_rgs_root_health_check():
    """Test the root endpoint to confirm gateway status and configuration loading."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "RGS Central Gateway is active"
    assert "default_llm_provider" in data
    assert "default_model" in data

@patch("rgs_hub.llm_gateway.completion")
def test_llm_generate_endpoint_mocked(mock_completion):
    """Test the centralized /llm/generate endpoint using a mocked LLM response."""
    
    # Mock the LiteLLM response structure
    class MockMessage:
        content = "Mocked AI response from RGS Central Gateway"

    class MockChoice:
        message = MockMessage()

    class MockResponse:
        choices = [MockChoice()]
        usage = {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20}

    mock_completion.return_value = MockResponse()

    # Send POST request to RGS Hub LLM Gateway
    response = client.post("/llm/generate", json={
        "prompt": "Hello Kaalu, test the gateway",
        "provider": "ollama",
        "model": "qwen2.5",
        "temperature": 0.0
    })

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "ollama"
    assert data["model"] == "qwen2.5"
    assert data["response"] == "Mocked AI response from RGS Central Gateway"
    assert data["usage"]["total_tokens"] == 20