central_communication_system/
│
├── .venv                           # Central API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, etc.)
├── .gitignore
├── pyproject.toml                 # Dependencies (fastapi, uvicorn, pydantic, websockets, litellm / provider sdks)
├── requirements.txt
├── README.md
│
├── rgs_hub/                       # Central Control, LLM Gateway, & Routing Hub
│   ├── __init__.py
│   ├── main.py                    # FastAPI server (WebSocket router + Central LLM REST/WS API)
│   ├── ws_manager.py              # WebSocket connection manager for all active agents
│   ├── schemas.py                 # Pydantic schemas for messages, task requests, & LLM payloads
│   ├── llm_gateway.py             # Central LLM client manager (switches between Ollama, OpenAI, Claude, Gemini)
│   └── settings.yaml              # Configuration file specifying active LLM provider, default models, and fallbacks
│
├── kaalu_orchestrator/            # Priority 1 User-Facing Agent & Operator
│   ├── __init__.py
│   ├── core_agent.py              # Main user-facing interaction and reasoning loop
│   ├── prompts.py                 # System instructions and operational rules for Kaalu
│   └── ws_client.py               # Communicates with RGS Hub for LLM inference requests and task dispatch
│
├── faulkner_system/               # System Execution Agent (Terminal & GUI)
│   ├── __init__.py
│   ├── terminal_executor.py       # Handles local bash/terminal execution
│   ├── gui_controller.py          # PyAutoGUI desktop automation controls
│   └── ws_client.py               # Connects to RGS Hub to receive system execution tasks
│
├── david_browser_agent/           # Manifest V3 Chrome Extension (Web Agent)
│   ├── manifest.json
│   ├── background.js              # WebSocket background worker connecting to RGS Hub
│   ├── content.js                 # Injected script for DOM manipulation and web scraping
│   └── popup/
│       ├── popup.html
│       └── popup.js
│
└── tests/                         # Automated test suite
    ├── __init__.py
    ├── test_rgs.py                # Integration tests for WebSocket message routing
    └── test_llm_gateway.py        # Tests for verifying central LLM provider switching (Ollama vs Cloud LLMs)