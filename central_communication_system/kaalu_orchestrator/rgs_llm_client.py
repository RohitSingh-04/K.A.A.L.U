from typing import Any, Dict, List, Optional
import httpx

class RGSLLMClient:
    """
    Centralized LLM client for Kaalu.
    Communicates with the RGS Hub /llm/generate endpoint instead of local models directly.
    """
    def __init__(self, gateway_url: str = "http://localhost:8000/llm/generate"):
        self.gateway_url = gateway_url

    def _build_payload(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        if not prompt and not messages:
            raise ValueError("Either 'prompt' or 'messages' must be provided.")
        payload: Dict[str, Any] = {"temperature": temperature}
        if prompt:
            payload["prompt"] = prompt
        if messages:
            payload["messages"] = messages
        if provider:
            payload["provider"] = provider
        if model:
            payload["model"] = model
        return payload

    def generate(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0
    ) -> str:
        """
        Synchronously requests LLM completion via RGS Hub gateway endpoint.
        """
        payload = self._build_payload(prompt, messages, provider, model, temperature)
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(self.gateway_url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", e.response.text)
            except Exception:
                detail = e.response.text
            err_msg = f"RGS Gateway returned status {e.response.status_code}: {detail}"
            print(f"[Kaalu LLM Client Error] {err_msg}")
            raise RuntimeError(err_msg) from e
        except httpx.RequestError as e:
            err_msg = f"Failed to connect to RGS Gateway at {self.gateway_url}: {e}"
            print(f"[Kaalu LLM Client Error] {err_msg}")
            raise RuntimeError(err_msg) from e

    async def generate_async(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0
    ) -> str:
        """
        Asynchronously requests LLM completion via RGS Hub gateway endpoint.
        """
        payload = self._build_payload(prompt, messages, provider, model, temperature)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.gateway_url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", e.response.text)
            except Exception:
                detail = e.response.text
            err_msg = f"RGS Gateway returned status {e.response.status_code}: {detail}"
            print(f"[Kaalu LLM Client Error] {err_msg}")
            raise RuntimeError(err_msg) from e
        except httpx.RequestError as e:
            err_msg = f"Failed to connect to RGS Gateway at {self.gateway_url}: {e}"
            print(f"[Kaalu LLM Client Error] {err_msg}")
            raise RuntimeError(err_msg) from e

# Alias for backward compatibility with previous typos
RGSLMClient = RGSLLMClient
