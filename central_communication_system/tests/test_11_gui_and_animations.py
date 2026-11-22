import os
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from rgs_hub.main import (
    app,
    get_available_animations,
    get_configured_animation,
    save_configured_animation,
)
from user_profile.web_ui import render_settings_page


@pytest.fixture
def client():
    return TestClient(app)


def test_animations_discovery():
    """Verify that available .mp4 animations in Animations/ folder are discovered."""
    anims = get_available_animations()
    assert isinstance(anims, list)
    # Both jarvis animations should be present
    assert "jarvis-30-fps-1600x1600.mp4" in anims
    assert "jarvis-blue.mp4" in anims


def test_get_and_save_configured_animation():
    """Verify reading and persisting animation configuration."""
    orig = get_configured_animation()
    try:
        save_configured_animation("jarvis-blue.mp4")
        assert get_configured_animation() == "jarvis-blue.mp4"
    finally:
        save_configured_animation(orig)


def test_api_animations_endpoints(client):
    """Test GET /api/animations and POST /api/animations/select endpoints."""
    # GET /api/animations
    resp = client.get("/api/animations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "animations" in data
    assert "jarvis-blue.mp4" in data["animations"]
    assert "active" in data
    assert "gui_mode" in data

    # POST /api/animations/select with valid animation
    orig = data["active"]
    try:
        post_resp = client.post("/api/animations/select", json={"animation": "jarvis-blue.mp4"})
        assert post_resp.status_code == 200
        pdata = post_resp.json()
        assert pdata["status"] == "success"
        assert pdata["active"] == "jarvis-blue.mp4"

        # Verify active setting changed
        get_again = client.get("/api/animations").json()
        assert get_again["active"] == "jarvis-blue.mp4"
    finally:
        client.post("/api/animations/select", json={"animation": orig})

    # POST with missing field -> 400
    bad_resp = client.post("/api/animations/select", json={})
    assert bad_resp.status_code == 400

    # POST with non-existent animation -> 404
    not_found_resp = client.post("/api/animations/select", json={"animation": "non_existent.mp4"})
    assert not_found_resp.status_code == 404


def test_voice_stop_endpoint(client):
    """Test POST /voice/stop and /api/voice/stop."""
    with patch("rgs_hub.main.Speaker") as mock_speaker:
        resp = client.post("/voice/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        mock_speaker.stop.assert_called_once()

    with patch("rgs_hub.main.Speaker") as mock_speaker:
        resp = client.post("/api/voice/stop")
        assert resp.status_code == 200
        mock_speaker.stop.assert_called_once()


def test_get_gui_page(client):
    """Test GET /gui renders the 2-Tab GUI interface with live terminal and hologram avatar."""
    resp = client.get("/gui")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    html = resp.text

    # Header & 2 Tabs
    assert "Project Kaalu" in html
    assert "Live Terminal" in html
    assert "Visual Assistant" in html

    # Tab 1: Live Terminal elements
    assert "terminal-container" in html
    assert "terminal-screen" in html
    assert "terminal-input" in html
    assert "Kaalu&gt;" in html
    assert "submitTerminalCommand" in html

    # Tab 2: Visual Assistant & Voice Ears elements
    assert "avatar-video" in html
    assert "hologram-wrapper" in html
    assert "voice-indicator" in html
    assert "stopActiveVoice" in html
    assert "markdownOutput" in html
    assert "voiceResponseText" in html
    assert "/animations/" in html

    # Tab 2: Live Step Status & Simultaneous Dual Streaming elements
    assert "stepStatusBar" in html
    assert "stepBadge" in html
    assert "stepDots" in html
    assert "streamVoiceSubtitles" in html
    assert "streamMarkdownOutput" in html
    assert "processing-placeholder" in html
    assert "fadeInUp" in html
    assert 'target="_blank"' in html


def test_british_jarvis_prompt_selection():
    """Verify that voice models in SIR_VOICE_MODELS switch to the British JARVIS Butler prompt."""
    from kaalu_orchestrator.prompts import get_kaalu_system_prompt, SIR_VOICE_MODELS

    assert "jarvis-gb" in SIR_VOICE_MODELS
    assert "tony" in SIR_VOICE_MODELS

    # Prompt with jarvis-gb should have British JARVIS persona and mandate 'Sir, '
    prompt_gb = get_kaalu_system_prompt(voice_model="jarvis-gb")
    assert "British AI butler" in prompt_gb or "BRITISH JARVIS" in prompt_gb
    assert "Always address Master Rohit respectfully as 'Sir'" in prompt_gb
    assert "MUST ALWAYS START WITH 'Sir, '" in prompt_gb

    # Prompt with Tony should also have British JARVIS persona
    prompt_tony = get_kaalu_system_prompt(voice_model="tony")
    assert "Always address Master Rohit respectfully as 'Sir'" in prompt_tony

    # Prompt with unknown voice should use standard Kaalu prompt
    prompt_std = get_kaalu_system_prompt(voice_model="standard-us")
    assert "British AI butler" not in prompt_std


def test_resume_builder_probe_endpoint_and_settings_button(client):
    """Verify GET /api/probe/resumebuilder endpoint and Settings probe button."""
    resp = client.get("/api/probe/resumebuilder")
    assert resp.status_code == 200
    data = resp.json()
    assert "online" in data
    assert "url" in data
    assert "latency_ms" in data

    # Verify settings page has probeRbBtn and probeResumeBuilder
    settings_html = render_settings_page()
    assert 'id="probeRbBtn"' in settings_html
    assert 'onclick="probeResumeBuilder()"' in settings_html


def test_settings_page_animations_gui_mode_flags():
    """
    Test /settings rendering under CLI mode (KAALU_GUI_MODE not set)
    vs GUI mode (KAALU_GUI_MODE=1).
    """
    # 1. When KAALU_GUI_MODE is NOT 1 (normal CLI start.bat)
    with patch.dict(os.environ, {"KAALU_GUI_MODE": "0"}):
        html_cli = render_settings_page()
        assert "Assistant Video Animations" in html_cli
        assert "Disabled (Active in GUI mode via GUI_KAALU.bat)" in html_cli
        # Buttons should have disabled attribute
        assert "disabled" in html_cli

    # 2. When KAALU_GUI_MODE IS 1 (GUI_KAALU.bat)
    with patch.dict(os.environ, {"KAALU_GUI_MODE": "1"}):
        html_gui = render_settings_page()
        assert "Assistant Video Animations" in html_gui
        assert "⚡ GUI Mode Active" in html_gui


def test_system_status_includes_animations_telemetry(client):
    """Verify /system/status includes animations and gui_mode in telemetry payload."""
    resp = client.get("/system/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "animations" in data
    anim_data = data["animations"]
    assert "active_animation" in anim_data
    assert "available_animations" in anim_data
    assert isinstance(anim_data["available_animations"], list)
    assert "gui_mode" in anim_data
