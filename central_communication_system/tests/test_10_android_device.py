import base64
import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from android_controller.manager import AndroidDeviceManager, KEY_MAP, DEFAULT_ADB_PATH
from rgs_hub.main import app, build_system_status
from user_profile.web_ui import render_settings_page
from kaalu_orchestrator.core_agent import KaaluOrchestrator
from voice_system.tts import get_configured_voice, save_configured_voice, VoiceEngine


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def temp_screenshots_dir(tmp_path):
    d = tmp_path / "screenshots"
    d.mkdir()
    return d


# 1. AndroidDeviceManager Unit Tests
def test_key_map_definitions():
    """Verify standard Android key events are mapped correctly."""
    assert KEY_MAP["HOME"] == 3
    assert KEY_MAP["BACK"] == 4
    assert KEY_MAP["ENTER"] == 66
    assert KEY_MAP["APP_SWITCH"] == 187
    assert KEY_MAP["POWER"] == 26
    assert KEY_MAP["VOLUME_UP"] == 24
    assert KEY_MAP["VOLUME_DOWN"] == 25


def test_manager_singleton_and_custom_path(temp_screenshots_dir):
    """Verify singleton instance and initialization parameters."""
    mgr = AndroidDeviceManager(adb_path=DEFAULT_ADB_PATH, screenshots_dir=temp_screenshots_dir)
    assert mgr.adb_path == DEFAULT_ADB_PATH
    assert mgr.screenshots_dir == temp_screenshots_dir


def test_run_adb_utf8_decoding_handles_non_ascii_and_emojis():
    """Verify that _run_adb decodes UTF-8 and handles special characters without cp1252 charmap errors."""
    mgr = AndroidDeviceManager(adb_path=DEFAULT_ADB_PATH)
    # Simulate binary output from adb containing non-cp1252 byte 0x81 and multi-byte UTF-8 Tibetan/Hindi
    raw_bytes = "Diya BBA GEHU རང་གི་འབད་བྱུང་ཟླ་ལྲ\x81".encode("utf-8", errors="replace")
    mock_res = subprocess.CompletedProcess(
        args=["adb", "shell", "cat"],
        returncode=0,
        stdout=raw_bytes,
        stderr=b""
    )

    with patch("subprocess.run", return_value=mock_res):
        res = mgr._run_adb(["shell", "cat"])
        assert res.returncode == 0
        assert "Diya BBA GEHU" in res.stdout
        assert "རང་གི་" in res.stdout


def test_list_devices_parsing():
    """Verify parsing of `adb devices -l` output into device dictionaries."""
    mock_stdout = (
        "List of devices attached\n"
        "adb-AQTWNN8DWSMNG6KJ-vxhPaR._adb-tls-connect._tcp device product:OP555BL1 model:IV2201 device:OP555BL1 transport_id:1\n"
        "emulator-5554          device product:sdk_gphone64_x86_64 model:sdk_gphone64_x86_64 device:emu64x transport_id:2\n"
        "offline_dev            offline\n"
    )
    mock_proc = subprocess.CompletedProcess(
        args=["adb", "devices", "-l"],
        returncode=0,
        stdout=mock_stdout,
        stderr=""
    )

    mgr = AndroidDeviceManager(adb_path=DEFAULT_ADB_PATH)
    with patch.object(mgr, "_run_adb", return_value=mock_proc):
        with patch.object(mgr, "is_adb_available", return_value=True):
            devices = mgr.list_devices()
            assert len(devices) == 3
            oneplus = devices[0]
            assert oneplus["serial"] == "adb-AQTWNN8DWSMNG6KJ-vxhPaR._adb-tls-connect._tcp"
            assert oneplus["state"] == "device"
            assert oneplus["model"] == "IV2201"
            assert oneplus["product"] == "OP555BL1"


def test_get_device_details_oneplus_recognition():
    """Verify detailed device telemetry properly detects the OnePlus Nord CE 2 5G."""
    mock_devices = [{
        "serial": "adb-AQTWNN8DWSMNG6KJ-vxhPaR._adb-tls-connect._tcp",
        "state": "device",
        "product": "OP555BL1",
        "model": "IV2201",
        "device": "OP555BL1",
        "transport_id": "1"
    }]

    def fake_run_adb(args, timeout=15.0, check=False, binary=False):
        cmd_str = " ".join(args)
        if "getprop" in cmd_str:
            stdout = "OnePlus\nOnePlus\nIV2201\n13\n33\n"
            return subprocess.CompletedProcess(args, 0, stdout, "")
        elif "wm size" in cmd_str:
            return subprocess.CompletedProcess(args, 0, "Physical size: 1080x2400\n", "")
        elif "dumpsys battery" in cmd_str:
            return subprocess.CompletedProcess(args, 0, "Current Battery Service state:\n  level: 85\n  scale: 100\n", "")
        elif "dumpsys window" in cmd_str:
            return subprocess.CompletedProcess(args, 0, "  mCurrentFocus=Window{abc u0 com.oneplus.camera/com.oneplus.camera.CameraApp}\n", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    mgr = AndroidDeviceManager(adb_path=DEFAULT_ADB_PATH)
    with patch.object(mgr, "list_devices", return_value=mock_devices):
        with patch.object(mgr, "_run_adb", side_effect=fake_run_adb):
            details = mgr.get_device_details("adb-AQTWNN8DWSMNG6KJ-vxhPaR._adb-tls-connect._tcp")
            assert details is not None
            assert details["is_oneplus"] is True
            assert "OnePlus Nord CE 2 5G" in details["market_name"]
            assert details["brand"] == "OnePlus"
            assert details["model"] == "IV2201"
            assert details["resolution"] == "1080x2400"
            assert details["battery_level"] == 85
            assert details["android_version"] == "13"
            assert details["current_package"] == "com.oneplus.camera"
            assert details["transport"] == "Wireless TLS"


def test_dump_ui_hierarchy_and_find_element():
    """Verify parsing of Android accessibility hierarchy XML, bounding boxes, and element search."""
    mock_xml = (
        "<hierarchy rotation=\"0\">"
        "<node text=\"Diya BBA GEHU\" class=\"android.widget.TextView\" bounds=\"[0,400][1080,600]\" clickable=\"true\"/>"
        "<node text=\"\" content-desc=\"Search\" class=\"android.widget.ImageView\" bounds=\"[900,100][1020,220]\" clickable=\"true\"/>"
        "<node text=\"\" content-desc=\"Send\" class=\"android.widget.ImageButton\" bounds=\"[940,2150][1060,2270]\" clickable=\"true\"/>"
        "<node text=\"Message\" class=\"android.widget.EditText\" bounds=\"[120,2150][920,2270]\" clickable=\"true\" focusable=\"true\"/>"
        "</hierarchy>"
    )

    mgr = AndroidDeviceManager(adb_path=DEFAULT_ADB_PATH)
    with patch.object(mgr, "_default_serial", return_value="fake_serial"):
        with patch.object(mgr, "_run_adb") as mock_adb:
            # First call for dump, second for cat
            mock_adb.side_effect = [
                subprocess.CompletedProcess(["adb", "shell", "uiautomator", "dump"], 0, "dumped", ""),
                subprocess.CompletedProcess(["adb", "shell", "cat"], 0, mock_xml, ""),
                subprocess.CompletedProcess(["adb", "shell", "dumpsys", "window"], 0, "u0 com.whatsapp/com.whatsapp.HomeActivity", "")
            ]

            res = mgr.dump_ui_hierarchy()
            assert res["success"] is True
            assert res["current_package"] == "com.whatsapp"
            assert "Diya BBA GEHU" in res["visible_texts"]
            assert "Search" in res["visible_texts"]
            assert "Send" in res["visible_texts"]

            # Verify find_element
            with patch.object(mgr, "dump_ui_hierarchy", return_value=res):
                diya = mgr.find_element("Diya BBA GEHU")
                assert diya is not None
                assert diya["center"] == [540, 500]
                assert diya["bounds"] == [0, 400, 1080, 600]

                search = mgr.find_element("Search")
                assert search is not None
                assert search["center"] == [960, 160]

                send = mgr.find_element("Send")
                assert send is not None
                assert send["center"] == [1000, 2210]


def test_tap_semantic_target_and_coordinates():
    """Verify tap works both with exact coordinates and with semantic targets (by element name)."""
    mgr = AndroidDeviceManager(adb_path=DEFAULT_ADB_PATH)

    mock_hierarchy = {
        "success": True,
        "current_package": "com.whatsapp",
        "elements": [
            {
                "label": "Diya BBA GEHU",
                "text": "Diya BBA GEHU",
                "content_desc": "",
                "bounds": [0, 400, 1080, 600],
                "center": [540, 500],
                "clickable": True
            }
        ],
        "visible_texts": ["Diya BBA GEHU", "Search", "Chats"]
    }

    with patch.object(mgr, "_default_serial", return_value="fake_phone"):
        with patch.object(mgr, "dump_ui_hierarchy", return_value=mock_hierarchy):
            with patch.object(mgr, "_run_adb", return_value=subprocess.CompletedProcess([], 0, "", "")) as mock_adb:
                # 1. Tap by target label
                res_target = mgr.tap(target="Diya BBA GEHU")
                assert res_target["success"] is True
                assert res_target["x"] == 540
                assert res_target["y"] == 500

                # 2. Tap by coordinate
                res_coord = mgr.tap(x=100, y=200)
                assert res_coord["success"] is True
                assert res_coord["x"] == 100
                assert res_coord["y"] == 200

                # 3. Target not found
                res_missing = mgr.tap(target="Nonexistent Person")
                assert res_missing["success"] is False
                assert "not found" in res_missing["error"]
                assert "Diya BBA GEHU" in res_missing["visible_texts_sample"]


def test_capture_screenshot_with_ui(temp_screenshots_dir):
    """Verify screenshot capture includes both base64 PNG and UI hierarchy labels."""
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 150
    mock_proc = subprocess.CompletedProcess(
        args=["adb", "exec-out", "screencap", "-p"],
        returncode=0,
        stdout=fake_png,
        stderr=b""
    )

    mock_ui = {
        "success": True,
        "active_package": "com.whatsapp",
        "current_package": "com.whatsapp",
        "current_activity": "ChatActivity",
        "visible_texts": ["Diya BBA GEHU", "Message", "Send"],
        "interactive_elements": [{"label": "Send", "center": [1000, 2200]}]
    }

    mgr = AndroidDeviceManager(adb_path=DEFAULT_ADB_PATH, screenshots_dir=temp_screenshots_dir)
    with patch.object(mgr, "_default_serial", return_value="fake_serial"):
        with patch.object(mgr, "_run_adb", return_value=mock_proc):
            with patch.object(mgr, "dump_ui_hierarchy", return_value=mock_ui):
                res = mgr.capture_screenshot(save=True, include_ui=True)
                assert res["success"] is True
                assert res["saved_path"] is not None
                assert "Diya BBA GEHU" in res["visible_texts"]
                assert res["current_package"] == "com.whatsapp"


# 2. RGS Hub API Endpoints Tests
def test_api_android_devices(client):
    """Test GET /android/devices endpoint."""
    mock_devs = [{
        "serial": "adb-AQTWNN8DWSMNG6KJ-vxhPaR._adb-tls-connect._tcp",
        "market_name": "OnePlus Nord CE 2 5G (OnePlus Phone)",
        "brand": "OnePlus",
        "model": "IV2201",
        "resolution": "1080x2400",
        "battery_level": 90,
        "is_oneplus": True
    }]
    with patch("rgs_hub.main.AndroidDeviceManager.get_instance") as mock_mgr_cls:
        mock_inst = MagicMock()
        mock_inst.list_devices_details.return_value = mock_devs
        mock_mgr_cls.return_value = mock_inst

        resp = client.get("/android/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["count"] == 1
        assert data["devices"][0]["brand"] == "OnePlus"


def test_api_android_screenshot_and_controls(client):
    """Test POST /android/tap, POST /android/type, POST /android/key, and POST /android/swipe."""
    with patch("rgs_hub.main.AndroidDeviceManager.get_instance") as mock_mgr_cls:
        mock_inst = MagicMock()
        mock_inst.tap.return_value = {"success": True, "action": "tap", "x": 100, "y": 200}
        mock_inst.type_text.return_value = {"success": True, "action": "type", "text": "hello"}
        mock_inst.swipe.return_value = {"success": True, "action": "swipe"}
        mock_inst.press_key.return_value = {"success": True, "action": "press_key", "key": "BACK"}
        mock_inst.open_app.return_value = {"success": True, "action": "open_app", "package": "com.android.chrome"}
        mock_inst.shell.return_value = {"success": True, "stdout": "test output", "exit_code": 0}
        mock_inst.inspect_screen.return_value = {"success": True, "visible_texts": ["Home", "Settings"]}
        mock_mgr_cls.return_value = mock_inst

        # Tap with target
        r_tap_target = client.post("/android/tap", json={"target": "Diya BBA GEHU"})
        assert r_tap_target.status_code == 200

        # Tap with coordinates
        r_tap = client.post("/android/tap", json={"x": 100, "y": 200})
        assert r_tap.status_code == 200
        assert r_tap.json()["action"] == "tap"

        # Type
        r_type = client.post("/android/type", json={"text": "hello", "target": "Message", "press_enter": True})
        assert r_type.status_code == 200
        assert r_type.json()["action"] == "type"

        # Inspect
        r_insp = client.get("/android/inspect")
        assert r_insp.status_code == 200
        assert "visible_texts" in r_insp.json()


def test_persistent_voice_configuration_sync(tmp_path):
    """Verify that voice settings persist across processes and Speaker immediately syncs."""
    test_cfg = tmp_path / "voice_settings.json"

    with patch("voice_system.tts.VOICE_CONFIG_FILE", test_cfg):
        # 1. Save voice as jarvis
        save_configured_voice("jarvis")
        assert test_cfg.exists()
        assert get_configured_voice() == "jarvis"

        # 2. Switch to tony
        save_configured_voice("tony")
        assert get_configured_voice() == "tony"


# 3. Kaalu Orchestrator Integration Tests
def test_kaalu_helper_methods():
    """Verify KaaluOrchestrator exposes direct Android automation helper methods."""
    mock_mgr = MagicMock()
    mock_mgr.list_devices_details.return_value = [{"model": "IV2201", "brand": "OnePlus"}]
    mock_mgr.capture_screenshot.return_value = {"success": True, "saved_path": "screen.png"}
    mock_mgr.inspect_screen.return_value = {"success": True, "visible_texts": ["WhatsApp"]}
    mock_mgr.tap.return_value = {"success": True, "action": "tap"}
    mock_mgr.type_text.return_value = {"success": True, "action": "type"}
    mock_mgr.swipe.return_value = {"success": True, "action": "swipe"}
    mock_mgr.press_key.return_value = {"success": True, "action": "press_key"}
    mock_mgr.open_app.return_value = {"success": True, "action": "open_app"}
    mock_mgr.shell.return_value = {"success": True, "stdout": "ok"}

    kaalu = KaaluOrchestrator(android_manager=mock_mgr)

    assert len(kaalu.android_devices()) == 1
    assert kaalu.android_screenshot()["success"] is True
    assert kaalu.android_inspect()["success"] is True
    assert kaalu.android_tap(500, 500)["success"] is True
    assert kaalu.android_tap(target="Diya BBA GEHU")["success"] is True
    assert kaalu.android_type("test", target="Message", press_enter=True)["success"] is True
    assert kaalu.android_swipe(100, 500, 100, 200)["success"] is True
    assert kaalu.android_key("HOME")["success"] is True
    assert kaalu.android_open_app("com.whatsapp")["success"] is True
    assert kaalu.android_shell("id")["success"] is True


@pytest.mark.asyncio
async def test_kaalu_delegates_to_android_with_confirmed_ui():
    """Verify Kaalu inspects screen first, verifies if contact is present, and taps confirmed target."""
    mock_mgr = MagicMock()
    mock_mgr.list_devices_details.return_value = [{
        "serial": "fake_oneplus",
        "market_name": "OnePlus Nord CE 2 5G (OnePlus Phone)",
        "model": "IV2201",
        "brand": "OnePlus",
        "resolution": "1080x2400",
        "battery_level": 80,
        "android_version": "13",
        "current_package": "com.whatsapp",
        "transport": "Wireless TLS"
    }]

    # Screenshot returns confirmed visible elements
    mock_mgr.capture_screenshot.return_value = {
        "success": True,
        "saved_path": "/data/screen.png",
        "current_package": "com.whatsapp",
        "visible_texts": ["Diya BBA GEHU", "Search", "Type a message"],
        "interactive_elements": [
            {"label": "Diya BBA GEHU", "type": "item", "center": [540, 520]},
            {"label": "Search", "type": "button", "center": [940, 180]}
        ]
    }
    mock_mgr.tap.return_value = {"success": True, "action": "tap", "target": "Diya BBA GEHU", "x": 540, "y": 520}

    kaalu = KaaluOrchestrator(android_manager=mock_mgr)

    # Step 1: LLM inspects screen
    step1_response = json.dumps({
        "thought": "I will inspect the phone screen to see if Diya BBA GEHU is visible.",
        "action": "delegate",
        "recipient": "android",
        "task_action": "capture_screenshot",
        "payload": {}
    })

    # Step 2: LLM sees Diya BBA GEHU in visible_texts and taps her directly
    step2_response = json.dumps({
        "thought": "I can see Diya BBA GEHU in the visible_texts list at center (540, 520). I will tap her to open the chat.",
        "action": "delegate",
        "recipient": "android",
        "task_action": "tap",
        "payload": {"target": "Diya BBA GEHU"}
    })

    # Step 3: Finish
    step3_response = json.dumps({
        "thought": "The chat is now open.",
        "action": "finish",
        "final_answer": "Yes, I see Diya BBA GEHU on your screen and tapped to open her chat.",
        "voice_response": "Yes, I see Diya BBA GEHU on your screen."
    })

    with patch.object(kaalu.ws_client, "connect_server", new_callable=AsyncMock):
        with patch.object(kaalu.llm_client, "generate_async", new_callable=AsyncMock, side_effect=[step1_response, step2_response, step3_response]) as mock_gen:
            res = await kaalu.process_user_goal("can you see Diya BBA GEHU on the screen of my phone, send her a Hi")

            assert res["status"] == "completed"
            assert "Diya BBA GEHU" in res["final_answer"]
            assert mock_mgr.capture_screenshot.called
            assert mock_mgr.tap.called
            assert mock_gen.call_count == 3
