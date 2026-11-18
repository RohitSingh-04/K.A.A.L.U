# Project Kaalu V2

Project Kaalu V2 is an autonomous multi-agent desktop and browser orchestration system designed for local task execution, dynamic web interactions, and neural voice synthesis.

---

## Architecture Overview

Project Kaalu is built on a hub-and-spoke multi-agent architecture connected via high-speed WebSockets and an asynchronous LLM gateway:

```
                      +-----------------------------+
                      |   RGS Central Hub (:8000)   |
                      |  - FastAPI WebSocket Bus    |
                      |  - LiteLLM Unified Gateway  |
                      +--------------+--------------+
                                     |
         +---------------------------+---------------------------+
         |                           |                           |
         v                           v                           v
+------------------+       +-------------------+       +-------------------+
|      Kaalu       |       |     Faulkner      |       |       David       |
|   Orchestrator   |       |   System Agent    |       |   Browser Agent   |
| (ReAct Engine &  |       | (Terminal, Shell, |       | (Chrome Ext V3,   |
|   Voice Synth)   |       |  Screen Capture)  |       |   Semantic DOM)   |
+------------------+       +-------------------+       +-------------------+
```

### Components

1. **RGS Central Hub (`rgs_hub`)**:
   - Central FastAPI communication router running on port `8000`.
   - Manages live agent WebSocket sessions (`/ws/kaalu`, `/ws/faulkner`, `/ws/david`).
   - Hosts the unified LLM Gateway (`/llm/generate`), abstracting providers (Google Gemini, OpenAI, Claude) via LiteLLM with automatic fallback and parameter normalization.

2. **Kaalu Master Orchestrator (`kaalu_orchestrator`)**:
   - The user-facing intelligence operating in an autonomous step-by-step ReAct loop.
   - Maintains cross-turn conversational context for continuous workflows.
   - Produces dual-stream responses: comprehensive visual output for the console and natural, conversational text for voice playback.

3. **Faulkner System Agent (`faulkner_system`)**:
   - Local OS execution agent handling shell commands, process control, and desktop screen capture.
   - Built-in safeguards preventing termination of essential OS desktop shells.

4. **David Browser Agent (`david_browser_agent`)**:
   - Chrome Manifest V3 browser automation extension.
   - Features smart semantic element resolution (matches buttons, labels, and inputs by intuitive text without requiring minified CSS classes).
   - Automatically extracts search results, direct answer cards, and page snapshots upon navigation.
   - Full support for standard inputs and rich-text editors (`contenteditable`).

5. **Voice Engine (`voice_system`)**:
   - Offline neural Text-to-Speech (TTS) engine powered by Piper ONNX models.
   - Automatic text sanitization pipeline that strips markdown formatting, bullet symbols, raw paths, and URLs before audio synthesis.
   - Voice profile customization supporting multiple models.

---

## Installation & Setup

### Prerequisites
- Windows 10/11
- Python 3.10+
- Google Chrome

### 1. Environment Setup
Clone the repository and create a Python virtual environment:

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configuration
Copy or edit `central_communication_system/rgs_hub/settings.yaml` and configure your API keys (or export `GEMINI_API_KEY` in your environment / `.env`):

```yaml
llm:
  default_model: "gemini/gemini-2.5-flash"
  timeout: 30
```

### 3. Install David Chrome Extension
1. Open Google Chrome and navigate to `chrome://extensions`.
2. Toggle on **Developer mode** in the top right.
3. Click **Load unpacked** and select the folder:
   ```
   central_communication_system\david_browser_agent
   ```

---

## Running the System

To launch all agents, hub, and the interactive terminal at once, run:

```cmd
.\start.bat
```

> **Note**: To grant Faulkner full process management permissions (such as closing elevated applications), right-click `start.bat` and choose **Run as administrator**.

---

## Running Automated Tests

Run the comprehensive pytest test suite to verify all subsystem contracts:

```cmd
.venv\Scripts\pytest
```

---

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
