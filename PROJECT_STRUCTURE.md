central_communication_system/
│
├── .gitignore
├── pyproject.toml                 # uv workspace/project configuration
├── README.md
│
├── rgs_hub/                       # Central FastAPI Communication Hub
│   ├── __init__.py
│   ├── main.py                    # FastAPI app initialization and Uvicorn runner
│   ├── ws_manager.py              # WebSocket connection manager (handles agent routing)
│   └── schemas.py                 # Pydantic models for TaskRequest, ActionResult, etc.
│
├── kaalu_orchestrator/            # The Brain (LangChain + Ollama)
│   ├── __init__.py
│   ├── core_agent.py              # Main reasoning loop (Plan -> Act -> Observe)
│   ├── prompts.py                 # System instructions for goal breakdown and verification
│   ├── tools.py                   # Definitions of tools available to the LLM
│   └── ws_client.py               # Connects to RGS Hub to dispatch commands via WebSockets
│
├── faulkner_system/               # The System Execution Agent
│   ├── __init__.py
│   ├── terminal_executor.py       # Handles subprocess bash script/command execution
│   ├── gui_controller.py          # PyAutoGUI scripts for raw desktop control
│   ├── screen_capture.py          # Captures local desktop state for verification
│   └── ws_client.py               # Connects to RGS Hub to receive terminal/GUI tasks
│
└── david_browser_agent/           # Manifest V3 Chrome Extension
    ├── manifest.json              # Extension config (permissions: activeTab, scripting, etc.)
    ├── background.js              # Service worker managing the WebSocket connection to RGS
    ├── content.js                 # Injected script for DOM manipulation and clicking
    ├── popup/
    │   ├── popup.html             # Basic UI to toggle the agent on/off manually
    │   └── popup.js
    ├── icons/
    │   └── icon128.png
    └── utils/
        └── dom_parser.js          # Helper to serialize webpage structure for Kaalu