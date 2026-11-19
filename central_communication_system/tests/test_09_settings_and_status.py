import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from rgs_hub.main import app, check_resume_builder_status, build_system_status, get_available_voices
from user_profile.web_ui import render_upload_page, render_edit_page, render_settings_page


@pytest.fixture
def client():
    return TestClient(app)


def test_navbar_contains_settings_tab_across_pages():
    """Verify that the gear icon / Settings tab is present on upload, edit, and settings pages."""
    upload_html = render_upload_page()
    assert 'href="/settings"' in upload_html
    assert '⚙️ Settings' in upload_html
    assert 'title="Settings"' in upload_html

    edit_html = render_edit_page()
    assert 'href="/settings"' in edit_html
    assert '⚙️ Settings' in edit_html
    assert 'title="Settings"' in edit_html

    settings_html = render_settings_page()
    assert 'href="/settings"' in settings_html
    assert '⚙️ Settings' in settings_html
    assert 'class="active"' in settings_html


def test_get_settings_html_page(client):
    """Test GET /settings endpoint renders HTML dashboard with all required sections."""
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    html = resp.text

    # Title & Header
    assert "System Settings & Fleet Monitor" in html
    assert "Resume Builder Web App" in html
    assert "http://localhost:5173/" in html

    # Connected Agents
    assert "Kaalu" in html
    assert "Faulkner" in html
    assert "David" in html

    # Voice Engine & LLM
    assert "Neural Voice Engine" in html
    assert "Central LLM Gateway & Gemini Model" in html
    assert "gemini-3.1-flash-lite" in html
    # Dynamic Voice Pills
    assert 'data-voice="jarvis-gb"' in html
    assert 'data-voice="tony"' in html
    assert 'data-voice="jarvis"' in html


@pytest.mark.asyncio
async def test_check_resume_builder_status_probe():
    """Verify Resume Builder status probe handles online and offline conditions."""
    # 1. Mock Online response
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        status = await check_resume_builder_status("http://localhost:5173/")
        assert status["online"] is True
        assert status["status_code"] == 200
        assert status["error"] is None
        assert "latency_ms" in status

    # 2. Mock Offline connection error
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=Exception("Connection refused")):
        status = await check_resume_builder_status("http://localhost:5173/")
        assert status["online"] is False
        assert status["status_code"] is None
        assert "Connection refused" in status["error"]


def test_system_status_endpoint(client):
    """Test GET /system/status and GET /api/status return full telemetry JSON."""
    # Test both endpoints
    for endpoint in ["/system/status", "/api/status"]:
        resp = client.get(endpoint)
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "success"
        assert "timestamp" in data

        # Check Services
        assert "services" in data
        assert "resume_builder" in data["services"]
        assert "rgs_hub" in data["services"]
        assert data["services"]["rgs_hub"]["port"] == 8000
        assert "job_tracker" in data["services"]
        assert "user_profile" in data["services"]

        # Check Connected Agents
        assert "connected_agents" in data
        assert "total_active" in data["connected_agents"]
        agents = data["connected_agents"]["agents"]
        assert "kaalu" in agents
        assert "faulkner" in agents
        assert "david" in agents

        # Check Voice Engine
        assert "voice" in data
        assert "active_voice" in data["voice"]
        assert "available_voices" in data["voice"]

        # Check LLM / Gemini Model
        assert "llm" in data
        assert "default_provider" in data["llm"]
        assert "default_model" in data["llm"]
        assert "api_keys" in data["llm"]
        assert "gemini" in data["llm"]["api_keys"]


def test_voice_change_endpoint(client):
    """Test POST /voice/change and POST /api/settings/voice switches active voice."""
    # 1. Missing voice field returns 400
    bad_resp = client.post("/voice/change", json={})
    assert bad_resp.status_code == 400

    # 2. Mock voice change
    with patch("rgs_hub.main.Speaker") as mock_speaker:
        mock_speaker.voice_name = "jarvis"
        mock_speaker.set_voice = MagicMock()

        resp = client.post("/voice/change", json={"voice": "jarvis"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["active_voice"] == "jarvis"
        mock_speaker.set_voice.assert_called_with("jarvis")

        # Test alias endpoint /api/settings/voice
        mock_speaker.voice_name = "tony"
        alias_resp = client.post("/api/settings/voice", json={"voice": "tony"})
        assert alias_resp.status_code == 200
        assert alias_resp.json()["active_voice"] == "tony"


def test_voice_test_endpoint(client):
    """Test POST /voice/test synthesizes audio sample."""
    with patch("rgs_hub.main.Speaker") as mock_speaker:
        mock_speaker.voice = MagicMock()
        mock_speaker.voice_name = "tony"
        mock_speaker.speak = MagicMock()

        resp = client.post("/voice/test", json={"text": "Test speech."})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        mock_speaker.speak.assert_called_with("Test speech.")


def test_llm_change_endpoint(client):
    """Test POST /llm/change updates active default model and provider."""
    # 1. Missing model returns 400
    bad_resp = client.post("/llm/change", json={})
    assert bad_resp.status_code == 400

    # 2. Valid update
    resp = client.post("/llm/change", json={"model": "gemini-2.5-pro", "provider": "gemini"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["default_model"] == "gemini-2.5-pro"
    assert data["default_provider"] == "gemini"

    # Verify status endpoint reflects updated model
    status_resp = client.get("/system/status")
    assert status_resp.json()["llm"]["default_model"] == "gemini-2.5-pro"
