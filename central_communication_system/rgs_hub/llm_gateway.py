import os
import yaml
from pathlib import Path
from litellm import completion
from dotenv import load_dotenv

load_dotenv()

class LLMGateway:
    def __init__(self, settings_path: str = "rgs_hub/settings.yaml"):
        self.settings_path = Path(settings_path)
        self.config = self._load_settings()

    def _load_settings(self) -> dict:
        """Load gateway settings from YAML configuration file."""
        if self.settings_path.exists():
            with open(self.settings_path, "r") as f:
                return yaml.safe_load(f)
        # Fallback default configuration if yaml is missing
        return {
            "llm": {
                "default_provider": "ollama",
                "default_model": "qwen2.5",
                "providers": {"ollama": {"base_url": "http://localhost:11434"}}
            }
        }

    async def generate(self, prompt: str = None, messages: list = None, provider: str = None, model: str = None, temperature: float = 0.0) -> dict:
        """
        Centralized generation method handling routing to Ollama, OpenAI, Anthropic, or Gemini.
        """
        llm_conf = self.config.get("llm", {})
        active_provider = provider or llm_conf.get("default_provider", "ollama")
        active_model = model or llm_conf.get("default_model", "qwen2.5")

        # Format messages for LiteLLM standard
        if messages:
            formatted_messages = messages
        elif prompt:
            formatted_messages = [{"role": "user", "content": prompt}]
        else:
            raise ValueError("Either 'prompt' or 'messages' must be provided.")

        # Configure provider-specific environment variables or endpoints
        kwargs = {"temperature": temperature}
        
        if active_provider == "ollama":
            # Prefix model with 'ollama/' for LiteLLM routing
            model_string = f"ollama/{active_model}"
            kwargs["api_base"] = llm_conf.get("providers", {}).get("ollama", {}).get("base_url", "http://localhost:11434")
        elif active_provider == "openai":
            model_string = active_model
        elif active_provider == "anthropic":
            model_string = f"anthropic/{active_model}"
        elif active_provider == "gemini":
            model_string = f"gemini/{active_model}"
        else:
            model_string = active_model

        try:
            # Execute completion request via LiteLLM gateway
            response = completion(
                model=model_string,
                messages=formatted_messages,
                **kwargs
            )
            
            content = response.choices[0].message.content
            usage = dict(response.usage) if hasattr(response, "usage") else {}

            return {
                "provider": active_provider,
                "model": active_model,
                "response": content,
                "usage": usage
            }
        except Exception as e:
            print(f"[LLM Gateway Error] Failed to generate completion: {e}")
            raise RuntimeError(f"LLM Gateway Generation Error: {str(e)}")