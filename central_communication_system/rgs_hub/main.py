import asyncio
import json
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Request, Query, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from rgs_hub.ws_manager import ConnectionManager
from rgs_hub.schemas import AgentMessage, LLMGenerationRequest, LLMGenerationResponse
from rgs_hub.llm_gateway import LLMGateway
from rgs_hub.gui_ui import render_gui_page
from user_profile import (
    ProfileManager,
    ProfileGenerator,
    Project,
    render_upload_page,
    render_edit_page,
    render_settings_page,
    build_user_profile_from_dict,
)
from job_tracker import (
    JobTrackerManager,
    JobApplicationRecord,
    ResumeSnapshot,
)

try:
    from android_controller.manager import AndroidDeviceManager
except (ImportError, ValueError):
    try:
        from ..android_controller.manager import AndroidDeviceManager
    except (ImportError, ValueError):
        AndroidDeviceManager = None

try:
    from voice_system.tts import Speaker, VoiceEngine
except (ImportError, ValueError):
    try:
        from ..voice_system.tts import Speaker, VoiceEngine
    except (ImportError, ValueError):
        Speaker = None
        VoiceEngine = None

app = FastAPI(title="RGS Central Gateway & Communication Hub", version="2.0.0")

# Enable CORS for external agents and UI connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()
llm_gateway = LLMGateway()

# ----------------- Animation Assets & Storage -----------------
ANIMATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "Animations"
ANIMATION_CONFIG_FILE = Path(__file__).resolve().parent.parent / "data" / "animation_settings.json"
kaalu_runner_ws: Optional[WebSocket] = None

def get_available_animations() -> List[str]:
    """Scans Animations/ directory for available .mp4 animations."""
    if not ANIMATIONS_DIR.exists():
        return []
    return sorted([f.name for f in ANIMATIONS_DIR.glob("*.mp4") if f.is_file()])

def get_configured_animation() -> str:
    """Reads configured animation name, defaulting to jarvis-30-fps-1600x1600.mp4 or first available."""
    avail = get_available_animations()
    if ANIMATION_CONFIG_FILE.exists():
        try:
            with open(ANIMATION_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                anim = data.get("active_animation")
                if anim and anim in avail:
                    return anim
        except Exception:
            pass
    for preferred in ["jarvis-30-fps-1600x1600.mp4", "jarvis-blue.mp4"]:
        if preferred in avail:
            return preferred
    return avail[0] if avail else ""

def save_configured_animation(anim_name: str) -> None:
    """Persists active animation setting."""
    ANIMATION_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ANIMATION_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"active_animation": anim_name.strip()}, f, indent=2)

# Mount /animations static directory
if ANIMATIONS_DIR.exists():
    app.mount("/animations", StaticFiles(directory=str(ANIMATIONS_DIR)), name="animations")

def get_available_voices() -> List[str]:
    """Scans voice models directory for available ONNX voice models."""
    if not Speaker or not hasattr(Speaker, "models_dir") or not Speaker.models_dir.exists():
        return ["jarvis"]
    voices = []
    try:
        for item in Speaker.models_dir.iterdir():
            if item.is_dir() and list(item.glob("*.onnx")):
                voices.append(item.name)
    except Exception:
        pass
    return sorted(voices) if voices else ["jarvis"]


async def check_resume_builder_status(url: str = "http://localhost:5173/") -> Dict[str, Any]:
    """Probes the standalone Resume Builder web application across IPv4 and localhost concurrently."""
    start_ts = time.time()
    candidates = [
        url,
        "http://127.0.0.1:5173/",
        "http://localhost:5173/",
        "http://127.0.0.1:5174/",
        "http://localhost:5174/",
        "http://127.0.0.1:8005/",
        "http://localhost:8005/"
    ]
    seen = set()
    unique_candidates = [c for c in candidates if not (c in seen or seen.add(c))]

    async def _probe_target(target: str):
        try:
            async with httpx.AsyncClient(timeout=0.4) as client:
                resp = await client.get(target)
                if resp.status_code < 500:
                    return {
                        "online": True,
                        "status_code": resp.status_code,
                        "url": target,
                        "error": None
                    }
        except Exception as exc:
            return {
                "online": False,
                "status_code": None,
                "url": target,
                "error": str(exc)
            }
        return {"online": False, "status_code": resp.status_code, "url": target, "error": f"HTTP {resp.status_code}"}

    results = await asyncio.gather(*[_probe_target(c) for c in unique_candidates])
    elapsed = round((time.time() - start_ts) * 1000, 1)

    for res in results:
        if res.get("online"):
            res["latency_ms"] = elapsed
            return res

    last_err = results[0].get("error") if results else "Connection refused"
    return {
        "online": False,
        "status_code": None,
        "latency_ms": elapsed,
        "url": url,
        "error": last_err or "Connection refused"
    }


async def build_system_status() -> Dict[str, Any]:
    """Builds comprehensive live system status telemetry."""
    # 1. Probe Resume Builder
    rb_status = await check_resume_builder_status()

    # 2. Connected Agents
    active_client_ids = list(manager.active_connections.keys())
    known_agents = {
        "kaalu": {
            "name": "Kaalu",
            "role": "Master Orchestrator & Reasoning Engine",
            "connected": "kaalu" in active_client_ids,
            "channel": "WebSocket /ws/kaalu"
        },
        "faulkner": {
            "name": "Faulkner",
            "role": "Local System & Terminal Execution",
            "connected": "faulkner" in active_client_ids,
            "channel": "WebSocket /ws/faulkner"
        },
        "david": {
            "name": "David",
            "role": "Chrome Extension Browser Agent",
            "connected": "david" in active_client_ids,
            "channel": "WebSocket /ws/david"
        }
    }
    other_clients = [c for c in active_client_ids if c not in known_agents]

    # 3. Voice Engine Status
    voice_info = {
        "active_voice": getattr(Speaker, "voice_name", "none") if Speaker else "none",
        "available_voices": get_available_voices(),
        "use_cuda": getattr(Speaker, "use_cuda", False) if Speaker else False,
        "status": "ready" if (Speaker and getattr(Speaker, "voice", None)) else "not_loaded"
    }

    # 4. LLM Gateway & Gemini Configuration
    llm_cfg = llm_gateway.config.get("llm", {})
    gemini_key = bool(os.environ.get("GEMINI_API_KEY"))
    openai_key = bool(os.environ.get("OPENAI_API_KEY"))
    anthropic_key = bool(os.environ.get("ANTHROPIC_API_KEY"))

    llm_info = {
        "default_provider": llm_cfg.get("default_provider", "gemini"),
        "default_model": llm_cfg.get("default_model", "gemini-3.1-flash-lite"),
        "configured_providers": list(llm_cfg.get("providers", {}).keys()),
        "api_keys": {
            "gemini": gemini_key,
            "openai": openai_key,
            "anthropic": anthropic_key,
        },
        "status": "configured"
    }

    # 5. Services & Storage
    profile_mgr = ProfileManager.get_instance()
    user_prof = profile_mgr.load_profile()
    job_mgr = JobTrackerManager.get_instance()
    apps = job_mgr.list_applications()

    total_resumes = 0
    if job_mgr.resumes_root.exists():
        total_resumes = sum(1 for _ in job_mgr.resumes_root.rglob("*.pdf")) + sum(1 for _ in job_mgr.resumes_root.rglob("*.docx"))

    services_info = {
        "resume_builder": rb_status,
        "rgs_hub": {
            "name": "RGS Central Communication Gateway",
            "port": 8000,
            "status": "online",
            "version": "2.0.0"
        },
        "job_tracker": {
            "name": "Job Application Tracker",
            "status": "online",
            "tracked_applications": len(apps),
            "stored_resumes": total_resumes,
            "resumes_directory": str(job_mgr.resumes_root)
        },
        "user_profile": {
            "name": "Centralized User Profile",
            "status": "online",
            "profile_loaded": bool(user_prof),
            "candidate_name": user_prof.basic_details.name if user_prof else None,
            "resume_path": user_prof.resume_path if user_prof else None
        }
    }

    # 6. Connected Android Devices (e.g. OnePlus Phone)
    android_devices = []
    android_credentials = {"configured": False}
    if AndroidDeviceManager:
        try:
            android_devices = AndroidDeviceManager.get_instance().list_devices_details()
            android_credentials = AndroidDeviceManager.get_instance().get_credentials_status()
        except Exception as e:
            print(f"[RGS Hub Warning] Error querying Android devices/credentials: {e}")

    anim_info = {
        "active_animation": get_configured_animation(),
        "available_animations": get_available_animations(),
        "gui_mode": os.environ.get("KAALU_GUI_MODE") == "1"
    }

    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "connected_agents": {
            "total_active": len(active_client_ids),
            "active_clients": active_client_ids,
            "agents": known_agents,
            "other_clients": other_clients
        },
        "connected_devices": android_devices,
        "android_devices": android_devices,
        "android_credentials": android_credentials,
        "services": services_info,
        "voice": voice_info,
        "animations": anim_info,
        "llm": llm_info
    }

@app.get("/gui", response_class=HTMLResponse)
async def get_gui_page():
    """Renders the 2-Tab Interactive GUI (Live Terminal + Hologram Avatar & Voice Ears)."""
    anim = get_configured_animation()
    voice = getattr(Speaker, "voice_name", "jarvis-gb") if Speaker else "jarvis-gb"
    return HTMLResponse(content=render_gui_page(active_animation=anim, active_voice=voice))

@app.get("/api/animations")
async def get_animations_endpoint():
    """Lists available animations in the Animations/ folder and active selection."""
    return {
        "status": "success",
        "animations": get_available_animations(),
        "active": get_configured_animation(),
        "gui_mode": os.environ.get("KAALU_GUI_MODE") == "1"
    }

@app.post("/api/animations/select")
async def select_animation_endpoint(payload: Dict[str, Any]):
    """Switches the active animation avatar."""
    anim_name = payload.get("animation")
    if not anim_name:
        raise HTTPException(status_code=400, detail="Missing required field 'animation'.")
    avail = get_available_animations()
    if anim_name not in avail:
        raise HTTPException(status_code=404, detail=f"Animation '{anim_name}' not found in Animations folder.")
    save_configured_animation(anim_name)
    return {
        "status": "success",
        "message": f"Active animation switched to '{anim_name}'.",
        "active": anim_name
    }

@app.post("/voice/stop")
@app.post("/api/voice/stop")
async def stop_voice_endpoint():
    """Halts active neural TTS voice output immediately (e.g. when user speaks)."""
    if Speaker:
        Speaker.stop()
    global kaalu_runner_ws
    if kaalu_runner_ws is not None:
        try:
            await kaalu_runner_ws.send_json({"action": "stop_voice"})
        except Exception:
            pass
    return {"status": "success", "message": "Voice playback stopped."}

@app.get("/settings", response_class=HTMLResponse)
async def get_settings_page():
    """Renders the System Settings & Agent Fleet Monitoring dashboard."""
    return HTMLResponse(content=render_settings_page())

@app.get("/system/status")
@app.get("/api/status")
async def get_system_status_endpoint():
    """Returns real-time telemetry: Resume Builder online check, connected agents, voice, LLM, and services."""
    return await build_system_status()

@app.get("/api/probe/resumebuilder")
@app.post("/api/probe/resumebuilder")
async def probe_resume_builder_endpoint():
    """Explicitly probes the Resume Builder ports across IPv4/localhost and returns real-time status."""
    return await check_resume_builder_status()

@app.post("/voice/change")
@app.post("/api/settings/voice")
async def change_active_voice(payload: Dict[str, Any]):
    """Switches the active Piper neural voice model (e.g. 'tony', 'jarvis')."""
    voice_name = payload.get("voice")
    if not voice_name:
        raise HTTPException(status_code=400, detail="Missing required field 'voice'.")

    if not Speaker:
        raise HTTPException(status_code=503, detail="Voice engine is not initialized on this host.")

    try:
        Speaker.set_voice(voice_name.strip().lower())
        return {
            "status": "success",
            "message": f"Active voice successfully switched to '{voice_name}'.",
            "active_voice": Speaker.voice_name
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to switch voice: {str(e)}")

@app.post("/voice/test")
async def test_voice_endpoint(payload: Optional[Dict[str, Any]] = None):
    """Synthesizes a short phrase on the host using the active voice model."""
    if not Speaker or not getattr(Speaker, "voice", None):
        raise HTTPException(status_code=503, detail="Voice model not loaded.")

    text = (payload or {}).get("text", "Sir, neural voice synthesis is online and fully operational.")
    try:
        Speaker.speak(text)
        return {
            "status": "success",
            "message": "Voice test audio synthesized successfully.",
            "voice": Speaker.voice_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice synthesis failed: {str(e)}")

@app.post("/llm/change")
@app.post("/api/settings/llm")
async def change_llm_model(payload: Dict[str, Any]):
    """Dynamically updates the default LLM model and provider."""
    model = payload.get("model")
    provider = payload.get("provider", "gemini")
    if not model:
        raise HTTPException(status_code=400, detail="Missing required field 'model'.")

    llm_gateway.config.setdefault("llm", {})
    llm_gateway.config["llm"]["default_model"] = model
    llm_gateway.config["llm"]["default_provider"] = provider

    return {
        "status": "success",
        "message": f"Updated default LLM to {provider}/{model}",
        "default_provider": provider,
        "default_model": model
    }

# ----------------- Android Automation Endpoints -----------------

@app.get("/android/devices")
async def get_android_devices():
    """Lists connected Android devices with detailed telemetry (e.g. OnePlus Phone)."""
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    devices = mgr.list_devices_details()
    return {
        "status": "success",
        "count": len(devices),
        "devices": devices
    }

@app.get("/android/screenshot")
async def get_android_screenshot(raw: bool = False, serial: Optional[str] = None):
    """Captures a screenshot from the connected OnePlus phone / Android device."""
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    res = mgr.capture_screenshot(serial=serial)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error", "Failed to capture screenshot."))

    if raw and res.get("saved_path") and os.path.exists(res["saved_path"]):
        with open(res["saved_path"], "rb") as f:
            return Response(content=f.read(), media_type="image/png")

    return res

@app.get("/android/inspect")
@app.get("/android/elements")
async def get_android_inspect(serial: Optional[str] = None):
    """Dumps the active screen UI hierarchy, visible text labels, and interactive elements."""
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    return mgr.inspect_screen(serial=serial)

@app.post("/android/tap")
async def post_android_tap(payload: Dict[str, Any]):
    """Performs a touch tap at screen coordinate (x, y) or at target element label."""
    x = payload.get("x")
    y = payload.get("y")
    target = payload.get("target")
    if target is None and (x is None or y is None):
        raise HTTPException(status_code=400, detail="Missing required fields: provide 'target' or both 'x' and 'y'.")

    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    res = mgr.tap(x=int(x) if x is not None else None, y=int(y) if y is not None else None, target=target, serial=payload.get("serial"))
    return res

@app.post("/android/type")
async def post_android_type(payload: Dict[str, Any]):
    """Types text into the focused field or focuses the target input element first."""
    text = payload.get("text")
    if text is None:
        raise HTTPException(status_code=400, detail="Missing required field 'text'.")

    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    res = mgr.type_text(
        text=str(text),
        target=payload.get("target"),
        clear=bool(payload.get("clear", False)),
        press_enter=bool(payload.get("press_enter", False)),
        serial=payload.get("serial")
    )
    return res

@app.post("/android/swipe")
async def post_android_swipe(payload: Dict[str, Any]):
    """Performs a swipe gesture on the Android device."""
    for f in ("x1", "y1", "x2", "y2"):
        if payload.get(f) is None:
            raise HTTPException(status_code=400, detail=f"Missing required field '{f}'.")

    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    res = mgr.swipe(
        x1=int(payload["x1"]),
        y1=int(payload["y1"]),
        x2=int(payload["x2"]),
        y2=int(payload["y2"]),
        duration_ms=int(payload.get("duration_ms", 300)),
        serial=payload.get("serial")
    )
    return res

@app.post("/android/key")
async def post_android_key(payload: Dict[str, Any]):
    """Presses a key (HOME, BACK, ENTER, APP_SWITCH) on the Android device."""
    key = payload.get("key")
    if key is None:
        raise HTTPException(status_code=400, detail="Missing required field 'key'.")

    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    res = mgr.press_key(key=key, serial=payload.get("serial"))
    return res

@app.post("/android/app/open")
async def post_android_open_app(payload: Dict[str, Any]):
    """Launches an application package on the Android device."""
    pkg = payload.get("package")
    if not pkg:
        raise HTTPException(status_code=400, detail="Missing required field 'package'.")

    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    res = mgr.open_app(package=pkg, serial=payload.get("serial"))
    return res

@app.post("/android/shell")
async def post_android_shell(payload: Dict[str, Any]):
    """Executes an arbitrary shell command on the Android device."""
    cmd = payload.get("command")
    if not cmd:
        raise HTTPException(status_code=400, detail="Missing required field 'command'.")

    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    res = mgr.shell(command=cmd, serial=payload.get("serial"))
    return res

@app.post("/android/whatsapp/send")
async def post_android_send_whatsapp(payload: Dict[str, Any]):
    """High-efficiency macro: opens WhatsApp, navigates to contact, types text/emoji, and sends."""
    contact = payload.get("contact")
    if not contact:
        raise HTTPException(status_code=400, detail="Missing required field 'contact'.")
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    res = mgr.send_whatsapp(
        contact=str(contact),
        message=payload.get("message", ""),
        emoji=payload.get("emoji"),
        serial=payload.get("serial")
    )
    return res

@app.post("/android/call")
async def post_android_call(payload: Dict[str, Any]):
    """High-efficiency macro: places a direct cellular or WhatsApp voice call to a number or contact."""
    target = payload.get("target") or payload.get("number") or payload.get("contact")
    if not target:
        raise HTTPException(status_code=400, detail="Missing required field 'target'.")
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    res = mgr.call_phone(
        target=str(target),
        app=payload.get("app", "phone"),
        serial=payload.get("serial")
    )
    return res

@app.post("/android/emoji")
async def post_android_emoji(payload: Dict[str, Any]):
    """Taps an emoji from the active keyboard panel (e.g. 'laugh', '😂', 'heart')."""
    emoji = payload.get("emoji", "laugh")
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    res = mgr.tap_emoji(emoji=str(emoji), serial=payload.get("serial"))
    return res

@app.get("/android/rotation")
async def get_android_rotation(serial: Optional[str] = None):
    """Queries screen auto-rotation and orientation lock status."""
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    return mgr.get_auto_rotate_status(serial=serial)

@app.post("/android/rotation")
async def post_android_rotation(payload: Dict[str, Any]):
    """Toggles or locks screen orientation (enabled=False locks portrait mode)."""
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    enabled = bool(payload.get("enabled", False))
    return mgr.set_auto_rotate(enabled=enabled, serial=payload.get("serial"))

@app.post("/android/call/answer")
async def post_android_call_answer(payload: Optional[Dict[str, Any]] = None):
    """Answers an incoming phone or WhatsApp call."""
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    serial = (payload or {}).get("serial")
    return mgr.answer_call(serial=serial)

@app.post("/android/call/end")
async def post_android_call_end(payload: Optional[Dict[str, Any]] = None):
    """Ends or hangs up an active phone call."""
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    serial = (payload or {}).get("serial")
    return mgr.end_call(serial=serial)

@app.get("/android/contacts")
async def get_android_contacts(query: str = "", serial: Optional[str] = None):
    """Searches Android contacts by name or queries all saved contacts."""
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    contacts = mgr.search_contacts(query=query, serial=serial)
    return {
        "status": "success",
        "query": query,
        "count": len(contacts),
        "contacts": contacts
    }

@app.post("/android/sms/send")
async def post_android_sms_send(payload: Dict[str, Any]):
    """Sends an SMS message to a contact name or phone number."""
    target = payload.get("target") or payload.get("contact") or payload.get("number")
    message = payload.get("message") or payload.get("text")
    if not target or message is None:
        raise HTTPException(status_code=400, detail="Missing required fields 'target' and 'message'.")
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    return mgr.send_sms(
        target=str(target),
        message=str(message),
        auto_send=bool(payload.get("auto_send", True)),
        serial=payload.get("serial")
    )

@app.get("/android/sms")
async def get_android_sms(limit: int = 10, serial: Optional[str] = None):
    """Reads recent incoming SMS messages from the phone inbox."""
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    return mgr.read_sms(limit=limit, serial=serial)

@app.get("/android/bluetooth")
async def get_android_bluetooth(serial: Optional[str] = None):
    """Queries Bluetooth adapter state and lists bonded devices."""
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    return mgr.get_bluetooth_status(serial=serial)

@app.post("/android/bluetooth")
async def post_android_bluetooth(payload: Dict[str, Any]):
    """Enables or disables Bluetooth on the Android device."""
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    enabled = bool(payload.get("enabled", True))
    return mgr.set_bluetooth(enabled=enabled, serial=payload.get("serial"))

@app.post("/android/bluetooth/connect")
async def post_android_bluetooth_connect(payload: Dict[str, Any]):
    """Connects to a paired Bluetooth device (earbuds, headphones, watch)."""
    device = payload.get("device") or payload.get("name") or payload.get("address")
    if not device:
        raise HTTPException(status_code=400, detail="Missing required field 'device'.")
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    return mgr.connect_bluetooth_device(device_name_or_address=str(device), serial=payload.get("serial"))

# ----------------- Phone Security & Unlock Credentials Endpoints -----------------

@app.get("/android/credentials")
@app.get("/api/settings/android/credentials")
async def get_android_credentials(serial: Optional[str] = None):
    """Returns phone PIN configuration status without exposing plaintext or ciphertext."""
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    return mgr.get_credentials_status(serial=serial)

@app.post("/android/credentials")
@app.post("/api/settings/android/credentials")
async def post_android_credentials(payload: Dict[str, Any]):
    """Safely encrypts and stores phone unlock PIN/password using machine-bound encryption (Windows DPAPI)."""
    pin = payload.get("pin") or payload.get("password")
    if not pin or not str(pin).strip():
        raise HTTPException(status_code=400, detail="Missing required field 'pin'.")
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    return mgr.save_phone_pin(pin=str(pin).strip(), serial=payload.get("serial"))

@app.delete("/android/credentials")
@app.delete("/api/settings/android/credentials")
async def delete_android_credentials(serial: Optional[str] = None):
    """Clears stored phone unlock credentials."""
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    return mgr.clear_phone_pin(serial=serial)

@app.post("/android/unlock")
async def post_android_unlock(payload: Optional[Dict[str, Any]] = None):
    """Executes phone unlock sequence using stored encrypted credentials (or optional one-time pin)."""
    if not AndroidDeviceManager:
        raise HTTPException(status_code=503, detail="Android controller module not loaded.")
    mgr = AndroidDeviceManager.get_instance()
    p = payload or {}
    return mgr.unlock_device(pin=p.get("pin"), serial=p.get("serial"))

# ----------------- Windows Phone Link Automation Endpoints -----------------

@app.post("/faulkner/phonelink/call")
@app.post("/system/phonelink/call")
async def post_faulkner_phonelink_call(payload: Dict[str, Any]):
    """Initiates a phone call through Microsoft Phone Link on Windows."""
    target = payload.get("target") or payload.get("contact") or payload.get("phone_number")
    if not target:
        raise HTTPException(status_code=400, detail="Missing required field 'target'.")
    try:
        from faulkner_system.phone_link import PhoneLinkController
        return PhoneLinkController.dial(
            target=str(target),
            phone_number=payload.get("phone_number")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/faulkner/phonelink/open")
@app.post("/system/phonelink/open")
async def post_faulkner_phonelink_open():
    """Opens or activates Microsoft Phone Link on Windows desktop."""
    try:
        from faulkner_system.phone_link import PhoneLinkController
        return PhoneLinkController.open_app()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/faulkner/phonelink/close")
@app.post("/system/phonelink/close")
async def post_faulkner_phonelink_close():
    """Gracefully closes Microsoft Phone Link window (simulating clicking the 'X' button)."""
    try:
        from faulkner_system.phone_link import PhoneLinkController
        return PhoneLinkController.close_app()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Health check endpoint showing active WebSocket clients and default LLM configuration."""
    return {
        "status": "RGS Central Gateway is active",
        "active_clients": list(manager.active_connections.keys()),
        "default_llm_provider": llm_gateway.config.get("llm", {}).get("default_provider"),
        "default_model": llm_gateway.config.get("llm", {}).get("default_model")
    }

@app.post("/llm/generate", response_model=LLMGenerationResponse)
async def generate_llm_completion(request: LLMGenerationRequest):
    """
    Centralized LLM inference endpoint. 
    Agents (like Kaalu) send their prompts here instead of connecting to local models directly.
    """
    try:
        result = await llm_gateway.generate(
            prompt=request.prompt,
            messages=[m.model_dump() for m in request.messages] if request.messages else None,
            provider=request.provider,
            model=request.model,
            temperature=request.temperature
        )
        return LLMGenerationResponse(**result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/profile")
async def get_user_profile():
    """Returns the current user profile JSON for agents or UI."""
    mgr = ProfileManager.get_instance()
    profile = mgr.load_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="No user profile found. Upload a resume to generate one.")
    return profile.model_dump()

@app.get("/profile/upload", response_class=HTMLResponse)
async def get_upload_page():
    """Renders the HTML form for uploading resume files."""
    return HTMLResponse(content=render_upload_page())

@app.post("/profile/upload")
async def upload_resume(file: UploadFile = File(...), request: Request = None):
    """Uploads a resume file (PDF, TXT, MD, JSON) and triggers profile generation."""
    upload_dir = Path(__file__).resolve().parent.parent / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / file.filename
    with open(saved_path, "wb") as f:
        content = await file.read()
        f.write(content)

    generator = ProfileGenerator()
    profile = generator.generate_profile(resume_source=saved_path)

    if request:
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header and not ("application/json" in accept_header or "*/*" in accept_header):
            return HTMLResponse(content=render_upload_page(message=f"Successfully extracted profile from {file.filename}"))

    return {
        "status": "success",
        "message": f"Successfully parsed profile from {file.filename}",
        "profile": profile.model_dump()
    }

@app.get("/profile/edit", response_class=HTMLResponse)
async def get_edit_page():
    """Renders the HTML form for inspecting and editing the user profile."""
    mgr = ProfileManager.get_instance()
    profile = mgr.load_profile()
    return HTMLResponse(content=render_edit_page(profile=profile))

@app.post("/profile/edit")
async def save_profile_edit(request: Request):
    """
    Saves profile updates submitted either via JSON (API/AJAX)
    or standard form submission from the edit HTML interface.
    """
    mgr = ProfileManager.get_instance()
    current_profile = mgr.load_profile()

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
    else:
        form_data = await request.form()
        payload = dict(form_data)

    if not payload:
        raise HTTPException(status_code=400, detail="No profile data provided.")

    try:
        updated_profile = build_user_profile_from_dict(payload, existing_profile=current_profile)
        mgr.save_profile(updated_profile)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to validate profile data: {str(e)}")

    accept_header = request.headers.get("accept", "")
    if "text/html" in accept_header and not ("application/json" in accept_header or "*/*" in accept_header):
        return HTMLResponse(content=render_edit_page(profile=updated_profile, message="Profile successfully updated!"))

    return {
        "status": "success",
        "message": "Profile updated successfully",
        "profile": updated_profile.model_dump()
    }

async def _fetch_github_repositories(username: str) -> List[Dict[str, Any]]:
    """Helper to fetch public repositories for a given GitHub username."""
    headers = {
        "User-Agent": "Project-Kaalu-Agent",
        "Accept": "application/vnd.github.v3+json",
    }
    url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=100"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to GitHub API: {str(exc)}"
        )

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"GitHub user '{username}' not found.")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"GitHub API error: {resp.text}")

    data = resp.json()
    if not isinstance(data, list):
        return []

    repos = []
    for r in data:
        lang = r.get("language")
        topics = r.get("topics") or []
        techs = []
        if lang:
            techs.append(lang)
        for t in topics:
            if t not in techs:
                techs.append(t)

        repos.append({
            "name": r.get("name") or "Unnamed Repo",
            "description": r.get("description") or "",
            "url": r.get("html_url") or "",
            "stars": r.get("stargazers_count", 0),
            "language": lang,
            "technologies": techs,
            "fork": r.get("fork", False)
        })
    return repos

@app.get("/profile/github/repos")
async def get_github_repos(username: Optional[str] = Query(None)):
    """
    Fetch public repositories for a GitHub user.
    If username is omitted, extracts it from the existing user profile's GitHub URL.
    """
    if not username:
        mgr = ProfileManager.get_instance()
        profile = mgr.load_profile()
        if profile and profile.urls and profile.urls.github:
            m = re.search(r"github\.com/([a-zA-Z0-9_\-]+)", profile.urls.github)
            if m:
                username = m.group(1)

    if not username:
        raise HTTPException(
            status_code=400,
            detail="GitHub username not provided and not found in existing user profile."
        )

    repos = await _fetch_github_repositories(username)
    return {
        "status": "success",
        "username": username,
        "count": len(repos),
        "repositories": repos
    }

@app.post("/profile/github/import")
async def import_github_repos(payload: Optional[Dict[str, Any]] = None):
    """
    Imports GitHub repositories as projects into the user's profile.
    Accepts either an explicit list of repository dicts or fetches them
    using `username` or profile URL.
    """
    payload = payload or {}
    mgr = ProfileManager.get_instance()
    profile = mgr.load_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="No user profile found. Please create one first.")

    repos_to_import = payload.get("repositories")
    username = payload.get("username")

    if not repos_to_import:
        if not username and profile.urls and profile.urls.github:
            m = re.search(r"github\.com/([a-zA-Z0-9_\-]+)", profile.urls.github)
            if m:
                username = m.group(1)

        if not username:
            raise HTTPException(
                status_code=400,
                detail="No repositories provided and no GitHub username found to fetch from."
            )

        repos_to_import = await _fetch_github_repositories(username)
        allowed_names = payload.get("repo_names")
        if allowed_names:
            allowed_set = {n.lower() for n in allowed_names}
            repos_to_import = [r for r in repos_to_import if r.get("name", "").lower() in allowed_set]

    existing_names = {p.name.strip().lower() for p in profile.projects}
    existing_urls = {p.url.strip().lower() for p in profile.projects if p.url}

    newly_added = []
    for item in repos_to_import:
        name = item.get("name", "").strip()
        url = item.get("url", "").strip() or item.get("html_url", "").strip()
        if not name:
            continue
        # Skip duplicates by name or URL
        if name.lower() in existing_names or (url and url.lower() in existing_urls):
            continue

        desc = item.get("description") or ""
        techs = item.get("technologies") or []
        if not techs and item.get("language"):
            techs = [item["language"]]

        proj = Project(
            name=name,
            description=desc,
            technologies=techs,
            url=url or None,
            highlights=[desc] if desc else [],
            stars=item.get("stars", 0) or item.get("stargazers_count", 0),
            language=item.get("language")
        )
        profile.projects.append(proj)
        existing_names.add(name.lower())
        if url:
            existing_urls.add(url.lower())
        newly_added.append(proj)

    if newly_added:
        mgr.save_profile(profile)

    return {
        "status": "success",
        "message": f"Successfully imported {len(newly_added)} project(s) from GitHub.",
        "imported_count": len(newly_added),
        "total_projects": len(profile.projects),
        "projects": [p.model_dump() for p in profile.projects]
    }

@app.delete("/profile/skills/category/{category_name}")
async def delete_skill_category(category_name: str):
    """
    Deletes a specific skill category by name (case-insensitive) from the user profile.
    Supports standard categories ('Soft Skills', 'Spoken Languages', etc.)
    and custom categories ('AI & LLMs', 'Cloud & DevOps', etc.).
    """
    mgr = ProfileManager.get_instance()
    profile = mgr.load_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="No user profile found.")

    removed = profile.skills.remove_category(category_name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Skill category '{category_name}' not found in profile.")

    mgr.save_profile(profile)
    return {
        "status": "success",
        "message": f"Successfully removed skill category '{category_name}'.",
        "remaining_categories": list(profile.skills.all_categories().keys()),
        "profile": profile.model_dump()
    }

@app.post("/profile/skills/category/remove")
async def remove_skill_category_via_post(payload: Dict[str, Any]):
    """Alternative POST endpoint to remove a skill category by name."""
    cat_name = payload.get("category_name") or payload.get("name")
    if not cat_name:
        raise HTTPException(status_code=400, detail="Missing 'category_name' in payload.")
    return await delete_skill_category(cat_name)

@app.post("/job/resume/save")
async def save_job_resume(payload: Dict[str, Any]):
    """
    Saves a generated/downloaded resume file into the structured date folder:
    data/resumes/YYYY-MM-DD/<Company>_<Position>_Resume_<timestamp>.pdf
    and automatically updates user_profile.json's resume_path.
    """
    company = payload.get("company")
    position = payload.get("position")
    if not company or not position:
        raise HTTPException(status_code=400, detail="Missing required fields: 'company' and 'position'.")

    source_path = payload.get("source_path")
    move = bool(payload.get("move", False))

    tracker = JobTrackerManager.get_instance()
    try:
        dest_path, dest_filename = tracker.save_downloaded_resume(
            company=company,
            position=position,
            source_path=source_path,
            move=move
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save resume: {str(e)}")

    return {
        "status": "success",
        "message": f"Resume successfully stored under date directory for {company} - {position}",
        "resume_path": str(dest_path),
        "resume_filename": dest_filename,
        "date_folder": dest_path.parent.name
    }

@app.post("/job/applied")
async def record_job_application(payload: Dict[str, Any]):
    """
    Records a job application or marks an existing one as applied,
    storing the target job metadata, applied date, and linking the exact resume file and snapshot.
    """
    tracker = JobTrackerManager.get_instance()

    identifier = payload.get("application_id") or payload.get("identifier")
    if identifier:
        rec = tracker.mark_as_applied(
            identifier=identifier,
            job_url=payload.get("job_url"),
            notes=payload.get("notes")
        )
        if rec:
            return {
                "status": "success",
                "message": f"Job application '{rec.company} - {rec.position}' marked as applied.",
                "application": rec.model_dump()
            }

    company = payload.get("company")
    position = payload.get("position")
    if not company or not position:
        raise HTTPException(status_code=400, detail="Missing required fields: 'company' and 'position'.")

    rec = tracker.record_job_application(
        company=company,
        position=position,
        job_description=payload.get("job_description"),
        job_url=payload.get("job_url"),
        location=payload.get("location"),
        resume_path=payload.get("resume_path"),
        resume_snapshot=payload.get("resume_snapshot"),
        status=payload.get("status", "applied"),
        applied_date=payload.get("applied_date"),
        notes=payload.get("notes"),
        metadata=payload.get("metadata")
    )
    return {
        "status": "success",
        "message": f"Job application recorded for {company} - {position}.",
        "application": rec.model_dump()
    }

@app.get("/job/applications")
async def list_job_applications(
    status: Optional[str] = Query(None),
    company: Optional[str] = Query(None)
):
    """Lists all tracked job applications with optional status and company filtering."""
    tracker = JobTrackerManager.get_instance()
    records = tracker.list_applications(status=status, company=company)
    return {
        "status": "success",
        "count": len(records),
        "applications": [r.model_dump() for r in records]
    }

@app.get("/job/applications/{application_id}")
async def get_job_application(application_id: str):
    """Retrieves a single job application record by application_id."""
    tracker = JobTrackerManager.get_instance()
    rec = tracker.get_application(application_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Job application '{application_id}' not found.")
    return {
        "status": "success",
        "application": rec.model_dump()
    }

active_hub_goal_id: int = 0

async def _run_kaalu_goal_background(goal: str, query_id: Optional[int] = None):
    global active_hub_goal_id
    active_hub_goal_id += 1
    my_goal_id = query_id if query_id is not None else active_hub_goal_id
    active_hub_goal_id = max(active_hub_goal_id, my_goal_id)

    # Silence any previous voice
    if Speaker:
        Speaker.stop()

    try:
        from kaalu_orchestrator.core_agent import KaaluOrchestrator
        orchestrator = KaaluOrchestrator()
        async def _cb(evt):
            if query_id is not None:
                evt["query_id"] = query_id
            await manager.broadcast_terminal(evt)
        res = await orchestrator.process_user_goal(goal, step_callback=_cb)
        final_answer = res.get("final_answer", str(res)) if isinstance(res, dict) else str(res)
        voice_text = res.get("voice_response") if isinstance(res, dict) else None
        if not voice_text:
            voice_text = final_answer

        is_latest = (my_goal_id == active_hub_goal_id)
        finish_payload = {
            "type": "finish",
            "source": "kaalu",
            "final_answer": final_answer,
            "voice_response": voice_text,
            "is_latest": is_latest,
            "superseded": not is_latest
        }
        if query_id is not None:
            finish_payload["query_id"] = query_id
        await manager.broadcast_terminal(finish_payload)

        # Only speak if this is still the active, latest goal
        if is_latest and Speaker:
            try:
                speak_text = voice_text if voice_text.strip().lower().startswith("sir,") else f"Sir, {voice_text}"
                threading.Thread(target=Speaker.speak, args=(speak_text,), kwargs={"speech_id": my_goal_id}, daemon=True).start()
            except Exception:
                pass
        await orchestrator.close()
    except Exception as e:
        await manager.broadcast_terminal({
            "type": "error",
            "source": "system",
            "message": f"Kaalu background execution error: {e}",
            "query_id": query_id
        })

@app.post("/api/kaalu/goal")
async def post_kaalu_goal_endpoint(payload: Dict[str, Any]):
    """Dispatches user goal (from voice ears or terminal) to Kaalu."""
    global active_hub_goal_id
    goal = payload.get("goal")
    query_id = payload.get("query_id")
    if not goal or not str(goal).strip():
        raise HTTPException(status_code=400, detail="Missing required field 'goal'.")

    active_hub_goal_id += 1
    my_goal_id = query_id if query_id is not None else active_hub_goal_id
    active_hub_goal_id = max(active_hub_goal_id, my_goal_id)

    # Immediately silence previous voice on hub and runner
    if Speaker:
        Speaker.stop()
    global kaalu_runner_ws
    if kaalu_runner_ws is not None:
        try:
            await kaalu_runner_ws.send_json({"action": "stop_voice"})
        except Exception:
            pass

    goal_str = str(goal).strip()
    await manager.broadcast_terminal({
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "source": "user",
        "type": "start",
        "message": f"User Objective: {goal_str}",
        "query_id": my_goal_id
    })

    if kaalu_runner_ws is not None:
        try:
            await kaalu_runner_ws.send_json({
                "action": "user_goal",
                "goal": goal_str,
                "query_id": my_goal_id,
                "active_goal_id": active_hub_goal_id
            })
            return {"status": "dispatched", "message": f"Objective dispatched: {goal_str}", "query_id": my_goal_id}
        except Exception as ws_err:
            print(f"[RGS Hub Warning] WS dispatch failed: {ws_err}")
            kaalu_runner_ws = None

    # Fallback to direct execution
    try:
        from kaalu_orchestrator.core_agent import KaaluOrchestrator
        orchestrator = KaaluOrchestrator()
        async def _cb(evt):
            if query_id is not None:
                evt["query_id"] = query_id
            await manager.broadcast_terminal(evt)
        res = await orchestrator.process_user_goal(goal_str, step_callback=_cb)
        final_answer = res.get("final_answer", str(res)) if isinstance(res, dict) else str(res)
        voice_text = res.get("voice_response") if isinstance(res, dict) else None
        if not voice_text:
            voice_text = final_answer

        is_latest = (my_goal_id == active_hub_goal_id)
        # Only speak if this is still the active latest goal (newer query has not superseded it)
        if is_latest and Speaker:
            try:
                speak_text = voice_text if voice_text.strip().lower().startswith("sir,") else f"Sir, {voice_text}"
                threading.Thread(target=Speaker.speak, args=(speak_text,), kwargs={"speech_id": my_goal_id}, daemon=True).start()
            except Exception:
                pass
        await orchestrator.close()
        return {
            "status": "completed",
            "final_answer": final_answer,
            "voice_response": voice_text,
            "query_id": my_goal_id,
            "is_latest": is_latest
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Execution failed: {exc}")

@app.websocket("/ws/terminal")
async def websocket_terminal_endpoint(websocket: WebSocket):
    """GUI Live Terminal stream: broadcasts all multi-agent events, steps, and system logs."""
    await manager.subscribe_terminal(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            if action in ("user_goal", "execute_goal"):
                goal = data.get("goal") or data.get("payload", {}).get("goal", "")
                if goal:
                    global kaalu_runner_ws
                    if kaalu_runner_ws:
                        await kaalu_runner_ws.send_json({"action": "user_goal", "goal": goal})
                    else:
                        asyncio.create_task(_run_kaalu_goal_background(str(goal)))
            elif action == "stop_voice":
                if Speaker:
                    Speaker.stop()
                if kaalu_runner_ws is not None:
                    try:
                        await kaalu_runner_ws.send_json({"action": "stop_voice"})
                    except Exception:
                        pass
    except WebSocketDisconnect:
        manager.unsubscribe_terminal(websocket)

@app.websocket("/ws/kaalu_dispatch")
async def websocket_kaalu_dispatch(websocket: WebSocket):
    """Direct WebSocket dispatcher between Kaalu Agent Runner and RGS Hub / GUI."""
    global kaalu_runner_ws
    await websocket.accept()
    kaalu_runner_ws = websocket
    print("[RGS Hub] Kaalu Orchestrator connected to GUI Dispatcher.")
    await manager.broadcast_terminal({
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "source": "kaalu",
        "type": "connect",
        "message": "Kaalu Orchestrator registered on GUI Dispatcher."
    })
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "finish":
                q_id = data.get("query_id")
                if q_id is not None and q_id < active_hub_goal_id:
                    data["is_latest"] = False
                    data["superseded"] = True
                else:
                    data["is_latest"] = True
                    data["superseded"] = False
            await manager.broadcast_terminal(data)
    except WebSocketDisconnect:
        print("[RGS Hub] Kaalu Orchestrator disconnected from GUI Dispatcher.")
        if kaalu_runner_ws == websocket:
            kaalu_runner_ws = None

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint where agents (Kaalu, Faulkner, David) register and communicate.
    """
    await manager.connect(client_id, websocket)
    try:
        while True:
            raw_data = await websocket.receive_json()
            if raw_data.get("action") == "ping":
                await websocket.send_json({
                    "recipient": client_id,
                    "sender": "rgs_hub",
                    "action": "pong",
                    "payload": {}
                })
                continue

            if raw_data.get("action") == "get_user_profile":
                mgr = ProfileManager.get_instance()
                profile = mgr.load_profile()
                await websocket.send_json({
                    "recipient": client_id,
                    "sender": "rgs_hub",
                    "action": "user_profile_data",
                    "payload": profile.model_dump() if profile else None
                })
                continue

            if raw_data.get("action") == "save_job_resume":
                payload = raw_data.get("payload", {})
                company = payload.get("company", "")
                position = payload.get("position", "")
                src_path = payload.get("source_path")
                tracker = JobTrackerManager.get_instance()
                try:
                    dest_p, dest_name = tracker.save_downloaded_resume(
                        company=company,
                        position=position,
                        source_path=src_path
                    )
                    await websocket.send_json({
                        "recipient": client_id,
                        "sender": "rgs_hub",
                        "action": "job_resume_saved",
                        "payload": {
                            "status": "success",
                            "resume_path": str(dest_p),
                            "resume_filename": dest_name
                        }
                    })
                except Exception as save_err:
                    await websocket.send_json({
                        "recipient": client_id,
                        "sender": "rgs_hub",
                        "action": "job_resume_saved",
                        "payload": {
                            "status": "error",
                            "error": str(save_err)
                        }
                    })
                continue

            if raw_data.get("action") == "record_job_application":
                payload = raw_data.get("payload", {})
                tracker = JobTrackerManager.get_instance()
                try:
                    rec = tracker.record_job_application(
                        company=payload.get("company", ""),
                        position=payload.get("position", ""),
                        job_description=payload.get("job_description"),
                        job_url=payload.get("job_url"),
                        location=payload.get("location"),
                        resume_path=payload.get("resume_path"),
                        resume_snapshot=payload.get("resume_snapshot"),
                        status=payload.get("status", "applied"),
                        notes=payload.get("notes"),
                        metadata=payload.get("metadata")
                    )
                    await websocket.send_json({
                        "recipient": client_id,
                        "sender": "rgs_hub",
                        "action": "job_application_recorded",
                        "payload": {
                            "status": "success",
                            "application": rec.model_dump()
                        }
                    })
                except Exception as rec_err:
                    await websocket.send_json({
                        "recipient": client_id,
                        "sender": "rgs_hub",
                        "action": "job_application_recorded",
                        "payload": {
                            "status": "error",
                            "error": str(rec_err)
                        }
                    })
                continue

            if raw_data.get("action") == "get_job_applications":
                payload = raw_data.get("payload", {})
                tracker = JobTrackerManager.get_instance()
                apps = tracker.list_applications(
                    status=payload.get("status"),
                    company=payload.get("company")
                )
                await websocket.send_json({
                    "recipient": client_id,
                    "sender": "rgs_hub",
                    "action": "job_applications_data",
                    "payload": {
                        "status": "success",
                        "count": len(apps),
                        "applications": [a.model_dump() for a in apps]
                    }
                })
                continue

            if raw_data.get("action") == "get_system_status":
                status_payload = await build_system_status()
                await websocket.send_json({
                    "recipient": client_id,
                    "sender": "rgs_hub",
                    "action": "system_status_data",
                    "payload": status_payload
                })
                continue

            if raw_data.get("action") == "change_voice":
                voice_name = raw_data.get("payload", {}).get("voice", "")
                if Speaker and voice_name:
                    try:
                        Speaker.set_voice(voice_name.strip().lower())
                        await websocket.send_json({
                            "recipient": client_id,
                            "sender": "rgs_hub",
                            "action": "voice_changed",
                            "payload": {"status": "success", "active_voice": Speaker.voice_name}
                        })
                    except Exception as ve:
                        await websocket.send_json({
                            "recipient": client_id,
                            "sender": "rgs_hub",
                            "action": "voice_changed",
                            "payload": {"status": "error", "error": str(ve)}
                        })
                continue

            if raw_data.get("action") == "android_action":
                sub_action = raw_data.get("task_action") or raw_data.get("payload", {}).get("action")
                payload = raw_data.get("payload", {})
                if not AndroidDeviceManager:
                    await websocket.send_json({
                        "recipient": client_id,
                        "sender": "rgs_hub",
                        "action": "android_action_result",
                        "payload": {"success": False, "error": "Android controller not loaded."}
                    })
                    continue

                mgr = AndroidDeviceManager.get_instance()
                res = {"success": False, "error": f"Unknown android action: {sub_action}"}
                serial = payload.get("serial")
                try:
                    if sub_action == "capture_screenshot":
                        res = mgr.capture_screenshot(serial=serial)
                    elif sub_action == "tap":
                        res = mgr.tap(
                            x=int(payload.get("x", 0)) if payload.get("x") is not None else None,
                            y=int(payload.get("y", 0)) if payload.get("y") is not None else None,
                            target=payload.get("target"),
                            serial=serial
                        )
                    elif sub_action == "type":
                        res = mgr.type_text(
                            text=str(payload.get("text", "")),
                            target=payload.get("target"),
                            clear=bool(payload.get("clear", False)),
                            press_enter=bool(payload.get("press_enter", False)),
                            serial=serial
                        )
                    elif sub_action == "swipe":
                        res = mgr.swipe(
                            x1=int(payload.get("x1", 0)),
                            y1=int(payload.get("y1", 0)),
                            x2=int(payload.get("x2", 0)),
                            y2=int(payload.get("y2", 0)),
                            duration_ms=int(payload.get("duration_ms", 300)),
                            serial=serial
                        )
                    elif sub_action in ("press_key", "key"):
                        res = mgr.press_key(key=payload.get("key", "HOME"), serial=serial)
                    elif sub_action in ("open_app", "launch_app"):
                        res = mgr.open_app(package=payload.get("package", ""), serial=serial)
                    elif sub_action in ("execute_shell", "shell"):
                        res = mgr.shell(command=payload.get("command", ""), serial=serial)
                    elif sub_action in ("get_device_info", "list_devices"):
                        res = {"success": True, "devices": mgr.list_devices_details()}
                    elif sub_action in ("call_phone", "call"):
                        res = mgr.call_phone(
                            target=str(payload.get("target") or payload.get("contact") or payload.get("number", "")),
                            app=str(payload.get("app", "phone")),
                            serial=serial
                        )
                    elif sub_action in ("answer_call", "accept_call"):
                        res = mgr.answer_call(serial=serial)
                    elif sub_action in ("end_call", "hangup"):
                        res = mgr.end_call(serial=serial)
                    elif sub_action in ("send_sms", "sms"):
                        res = mgr.send_sms(
                            target=str(payload.get("target") or payload.get("contact") or payload.get("number", "")),
                            message=str(payload.get("message") or payload.get("text", "")),
                            auto_send=bool(payload.get("auto_send", True)),
                            serial=serial
                        )
                    elif sub_action in ("read_sms", "get_sms"):
                        res = mgr.read_sms(limit=int(payload.get("limit", 10)), serial=serial)
                    elif sub_action in ("search_contacts", "contacts"):
                        res = {
                            "success": True,
                            "contacts": mgr.search_contacts(query=str(payload.get("query") or payload.get("name", "")), serial=serial)
                        }
                    elif sub_action in ("get_bluetooth_status", "bluetooth_status", "bluetooth"):
                        res = mgr.get_bluetooth_status(serial=serial)
                    elif sub_action in ("set_bluetooth", "toggle_bluetooth"):
                        res = mgr.set_bluetooth(enabled=bool(payload.get("enabled", True)), serial=serial)
                    elif sub_action in ("connect_bluetooth", "connect_bluetooth_device"):
                        res = mgr.connect_bluetooth_device(
                            device_name_or_address=str(payload.get("device") or payload.get("name") or payload.get("address", "")),
                            serial=serial
                        )
                    elif sub_action in ("send_whatsapp", "whatsapp"):
                        res = mgr.send_whatsapp(
                            contact=str(payload.get("contact") or payload.get("target", "")),
                            message=str(payload.get("message", "")),
                            emoji=payload.get("emoji"),
                            auto_send=bool(payload.get("auto_send", True)),
                            serial=serial
                        )
                    elif sub_action in ("tap_emoji", "emoji", "gboard_emoji"):
                        res = mgr.tap_emoji(emoji=str(payload.get("emoji", "laugh")), serial=serial)
                    elif sub_action in ("set_auto_rotate", "auto_rotate"):
                        res = mgr.set_auto_rotate(enabled=bool(payload.get("enabled", False)), serial=serial)
                    elif sub_action in ("get_rotation_status", "rotation_status"):
                        res = mgr.get_auto_rotate_status(serial=serial)
                    elif sub_action in ("unlock_device", "unlock", "unlock_phone"):
                        res = mgr.unlock_device(pin=payload.get("pin"), serial=serial)
                    elif sub_action in ("get_credentials_status", "credentials_status", "credentials"):
                        res = mgr.get_credentials_status(serial=serial)
                    elif sub_action in ("save_credentials", "save_pin"):
                        res = mgr.save_phone_pin(pin=str(payload.get("pin", "")), serial=serial)
                    elif sub_action in ("clear_credentials", "clear_pin"):
                        res = mgr.clear_phone_pin(serial=serial)
                except Exception as a_err:
                    res = {"success": False, "error": str(a_err)}

                await websocket.send_json({
                    "recipient": client_id,
                    "sender": "rgs_hub",
                    "action": "android_action_result",
                    "payload": res
                })
                continue

            try:
                message = AgentMessage(**raw_data)
                await manager.route_message(client_id, message.model_dump())
            except Exception as validation_error:
                await websocket.send_json({
                    "sender": "rgs_hub",
                    "status": "error",
                    "error": f"Invalid message schema: {str(validation_error)}"
                })
    except WebSocketDisconnect:
        manager.disconnect(client_id)