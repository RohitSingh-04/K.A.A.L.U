# Central Communication System

Core backend services, multi-agent communication hub, and voice engine for Project Kaalu V2.

## Components

1. **`rgs_hub`**: Central FastAPI WebSocket routing gateway (`:8000`) and LiteLLM proxy.
2. **`user_profile`**: Centralized user profile schemas, resume generator, web management interface (`/profile/edit`), and GitHub repo importer.
3. **`voice_system`**: Neural Text-to-Speech (TTS) engine using Piper ONNX models with Tensor Core GPU training optimization.
4. **`kaalu_orchestrator`**: Master autonomous agent loop with ReAct reasoning and voice output.
5. **`faulkner_system`**: Local desktop process, terminal, and screen control agent.
6. **`david_browser_agent`**: Manifest V3 Chrome browser automation extension.

## Voice Training GPU Optimization (RTX 3050 / 6GB VRAM)

```python
from voice_system.tts import Speaker

# Train with optimized 6GB VRAM saturation and Ampere Tensor Cores:
Speaker.train_voice("tony", batch_size=12, precision="16-mixed", checkpoint_epochs=25)

# Export directly from existing checkpoint without retraining:
Speaker.export_voice("tony")
```

For full documentation and hardware benchmarks, see the main [README.md](../README.md).
