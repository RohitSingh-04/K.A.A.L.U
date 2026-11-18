import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Search for .env in project root or current directory
root_env = Path(__file__).resolve().parent.parent.parent / ".env"
if root_env.exists():
    load_dotenv(dotenv_path=root_env)
else:
    load_dotenv()

# Prevent LiteLLM from making slow blocking network calls for pricing on import
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import yaml
import litellm
from litellm import completion

# Drop unsupported params (e.g. temperature on models that do not accept it like Gemini)
litellm.drop_params = True

class LLMGateway:
    def __init__(self, settings_path: str = None):
        if settings_path is not None:
            self.settings_path = Path(settings_path)
        else:
            # Prefer settings.yaml next to this file, fallback to current dir
            local_yaml = Path(__file__).parent / "settings.yaml"
            self.settings_path = local_yaml if local_yaml.exists() else Path("rgs_hub/settings.yaml")
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
                "default_model": "qwen2.5:3b",
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
        kwargs = {"timeout": 45}
        if temperature is not None and active_provider != "gemini":
            kwargs["temperature"] = temperature

        if active_provider == "ollama":
            model_string = f"ollama/{active_model}" if not active_model.startswith("ollama/") else active_model
            kwargs["api_base"] = llm_conf.get("providers", {}).get("ollama", {}).get("base_url", "http://localhost:11434")
        elif active_provider == "openai":
            model_string = active_model
        elif active_provider == "anthropic":
            model_string = f"anthropic/{active_model}" if not active_model.startswith("anthropic/") else active_model
        elif active_provider == "gemini":
            model_string = f"gemini/{active_model}" if not active_model.startswith("gemini/") else active_model
        else:
            model_string = active_model

        max_retries = 3
        last_exception = None

        for attempt in range(max_retries):
            try:
                # Execute completion request via LiteLLM gateway in a thread to keep event loop free
                response = await asyncio.to_thread(
                    completion,
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
                last_exception = e
                err_str = str(e).lower()
                is_transient = any(phrase in err_str for phrase in [
                    "503", "high demand", "unavailable", "429", "rate limit", "temporarily", "timeout"
                ])
                if is_transient and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"[LLM Gateway] Transient error from provider ({e}). Retrying attempt {attempt + 2}/{max_retries} in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue

                # Auto fallback for Gemini high-demand / unavailability
                if active_provider == "gemini" and "gemini-3.1-flash-lite" not in model_string:
                    print(f"[LLM Gateway] Model '{active_model}' unavailable. Falling back to 'gemini-3.1-flash-lite'...")
                    try:
                        fallback_resp = await asyncio.to_thread(
                            completion,
                            model="gemini/gemini-3.1-flash-lite",
                            messages=formatted_messages,
                            **kwargs
                        )
                        return {
                            "provider": active_provider,
                            "model": "gemini-3.1-flash-lite",
                            "response": fallback_resp.choices[0].message.content,
                            "usage": dict(fallback_resp.usage) if hasattr(fallback_resp, "usage") else {}
                        }
                    except Exception as fb_err:
                        print(f"[LLM Gateway] Fallback also failed: {fb_err}")

                print(f"[LLM Gateway Error] Failed to generate completion: {e}")
                raise RuntimeError(f"LLM Gateway Generation Error: {str(e)}") from e