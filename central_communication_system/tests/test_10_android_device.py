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


def test_tap_emoji_execution():
    """Verify tap_emoji and type_gboard_emoji trigger Gboard universal emoji search gestures."""
    mgr = AndroidDeviceManager(adb_path=DEFAULT_ADB_PATH)
    commands_executed = []

    def mock_run(args, **kwargs):
        commands_executed.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with patch.object(mgr, "_run_adb", side_effect=mock_run):
        with patch.object(mgr, "_default_serial", return_value="fake_dev"):
            with patch.object(mgr, "find_element", return_value=None):
                res = mgr.tap_emoji("laugh")
                assert res["success"] is True
                assert res["emoji"] == "laugh"
                assert res["coordinate"] == (229, 1213)
                assert res["method"] == "gboard_emoji_search"
                # Verify Gboard long-press on ',' key [205, 2320] for 450ms
                assert any(["input", "swipe", "205", "2320", "205", "2320", "450"] == cmd[-7:] for cmd in commands_executed)
                # Verify Gboard Search pill [280, 1280] tapped
                assert any(["input", "tap", "280", "1280"] == cmd[-4:] for cmd in commands_executed)
                # Verify search query 'laugh' typed
                assert any(["input", "text", "laugh"] == cmd[-3:] for cmd in commands_executed)
                # Verify laughing emoji [229, 1213] tapped
                assert any(["input", "tap", "229", "1213"] == cmd[-4:] for cmd in commands_executed)
                # Verify back arrow [72, 1045] tapped
                assert any(["input", "tap", "72", "1045"] == cmd[-4:] for cmd in commands_executed)


def test_auto_rotate_status_and_locking():
    """Verify querying and toggling screen rotation lock settings."""
    mgr = AndroidDeviceManager(adb_path=DEFAULT_ADB_PATH)
    commands_executed = []

    def mock_run(args, **kwargs):
        commands_executed.append(args)
        cmd_str = " ".join(args)
        if "accelerometer_rotation" in cmd_str and "get" in cmd_str:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="0\n", stderr="")
        if "user_rotation" in cmd_str and "get" in cmd_str:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="0\n", stderr="")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with patch.object(mgr, "_run_adb", side_effect=mock_run):
        with patch.object(mgr, "_default_serial", return_value="fake_dev"):
            # 1. Query status
            status = mgr.get_auto_rotate_status()
            assert status["success"] is True
            assert status["auto_rotate"] is False
            assert status["is_portrait_locked"] is True

            # 2. Lock rotation (enabled=False)
            commands_executed.clear()
            set_res = mgr.set_auto_rotate(enabled=False)
            assert set_res["success"] is True
            assert any(["settings", "put", "system", "accelerometer_rotation", "0"] == cmd[-5:] for cmd in commands_executed)
            assert any(["settings", "put", "system", "user_rotation", "0"] == cmd[-5:] for cmd in commands_executed)


def test_call_phone_cellular_and_whatsapp():
    """Verify cellular call executes native CALL intent and WhatsApp call taps Voice call."""
    mgr = AndroidDeviceManager(adb_path=DEFAULT_ADB_PATH)
    commands_executed = []

    def mock_run(args, **kwargs):
        commands_executed.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with patch.object(mgr, "_run_adb", side_effect=mock_run):
        with patch.object(mgr, "_default_serial", return_value="fake_dev"):
            # 1. Cellular Call
            res_cell = mgr.call_phone("9876543210")
            assert res_cell["success"] is True
            assert res_cell["type"] == "cellular"
            assert any("android.intent.action.CALL" in str(cmd) for cmd in commands_executed)

            # 2. WhatsApp Audio Call
            commands_executed.clear()
            with patch.object(mgr, "dump_ui_hierarchy", return_value={"current_activity": "Conversation"}):
                with patch.object(mgr, "find_element", return_value={"center": [888, 191]}):
                    res_wa = mgr.call_phone("Diya BBA GEHU", app="whatsapp")
                    assert res_wa["success"] is True
                    assert res_wa["type"] == "whatsapp_voice_call"
                    assert any(["input", "tap", "888", "191"] == cmd[-4:] for cmd in commands_executed)


def test_send_whatsapp_macro():
    """Verify send_whatsapp macro executes end-to-end send without multiple reasoning loops."""
    mgr = AndroidDeviceManager(adb_path=DEFAULT_ADB_PATH)
    commands_executed = []

    def mock_run(args, **kwargs):
        commands_executed.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with patch.object(mgr, "_run_adb", side_effect=mock_run):
        with patch.object(mgr, "_default_serial", return_value="fake_dev"):
            with patch.object(mgr, "open_app") as mock_open:
                with patch.object(mgr, "dump_ui_hierarchy", return_value={"current_activity": "Conversation"}):
                    with patch.object(mgr, "find_element") as mock_find:
                        # find_element returns Send button when checked
                        mock_find.side_effect = lambda t, **kwargs: {"center": [1000, 2210]} if t == "Send" else None
                        with patch.object(mgr, "type_text") as mock_type:
                            with patch.object(mgr, "type_gboard_emoji") as mock_emoji:
                                res = mgr.send_whatsapp("Diya BBA GEHU", message="hello", emoji="laugh")
                                assert res["success"] is True
                                assert res["action"] == "send_whatsapp"
                                assert res["verified"] is True
                                assert mock_open.called
                                assert mock_type.called
                                assert mock_emoji.called


def test_send_whatsapp_prevents_voice_recording():
    """Verify send_whatsapp explicitly DOES NOT tap if Voice message button is active."""
    mgr = AndroidDeviceManager(adb_path=DEFAULT_ADB_PATH)
    commands_executed = []

    def mock_run(args, **kwargs):
        commands_executed.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with patch.object(mgr, "_run_adb", side_effect=mock_run):
        with patch.object(mgr, "_default_serial", return_value="fake_dev"):
            with patch.object(mgr, "open_app"):
                with patch.object(mgr, "dump_ui_hierarchy", return_value={"current_activity": "Conversation"}):
                    with patch.object(mgr, "find_element") as mock_find:
                        def fake_find(target, **kwargs):
                            if target in ("Voice message", "voice_note_btn"):
                                return {"center": [980, 2218]}
                            if target == "Send":
                                return None
                            return None
                        mock_find.side_effect = fake_find

                        res = mgr.send_whatsapp("Project X", emoji="laugh")
                        assert res["success"] is True
                        # Verify NO tap was issued at [980, 2218] (which would activate voice recording)
                        assert not any(["input", "tap", "980", "2218"] == cmd[-4:] for cmd in commands_executed)


def test_kaalu_macro_helper_methods():
    """Verify Kaalu exposes android_send_whatsapp, android_call, and android_tap_emoji."""
    mock_mgr = MagicMock()
    mock_mgr.send_whatsapp.return_value = {"success": True, "action": "send_whatsapp"}
    mock_mgr.call_phone.return_value = {"success": True, "action": "call_phone"}
    mock_mgr.tap_emoji.return_value = {"success": True, "action": "tap_emoji"}

    kaalu = KaaluOrchestrator(android_manager=mock_mgr)
    assert kaalu.android_send_whatsapp("Diya", message="hi")["success"] is True
    assert kaalu.android_call("Diya", app="whatsapp")["success"] is True
    assert kaalu.android_tap_emoji("laugh")["success"] is True


@pytest.mark.asyncio
async def test_kaalu_delegates_to_send_whatsapp_macro():
    """Verify Kaalu completes WhatsApp send in 1 step using the send_whatsapp macro."""
    mock_mgr = MagicMock()
    mock_mgr.list_devices_details.return_value = [{
        "serial": "fake_dev",
        "market_name": "OnePlus Phone",
        "model": "IV2201",
        "brand": "OnePlus"
    }]
    mock_mgr.send_whatsapp.return_value = {
        "success": True,
        "action": "send_whatsapp",
        "contact": "Diya BBA GEHU",
        "message": "hello",
        "verified": True
    }

    kaalu = KaaluOrchestrator(android_manager=mock_mgr)

    step1_response = json.dumps({
        "thought": "The user wants to send 'hello' to Diya BBA GEHU on WhatsApp. I will use the ultra-efficient send_whatsapp macro to complete this in one action.",
        "action": "delegate",
        "recipient": "android",
        "task_action": "send_whatsapp",
        "payload": {
            "contact": "Diya BBA GEHU",
            "message": "hello"
        }
    })

    step2_response = json.dumps({
        "thought": "Message has been verified sent on WhatsApp.",
        "action": "finish",
        "final_answer": "Successfully sent 'hello' to Diya BBA GEHU on WhatsApp.",
        "voice_response": "I have sent hello to Diya on WhatsApp."
    })

    with patch.object(kaalu.ws_client, "connect_server", new_callable=AsyncMock):
        with patch.object(kaalu.llm_client, "generate_async", new_callable=AsyncMock, side_effect=[step1_response, step2_response]):
            res = await kaalu.process_user_goal('send "hello" to Diya BBA GEHU on whatsapp using my phone')
            assert res["status"] == "completed"
            assert mock_mgr.send_whatsapp.called
            assert res["steps_taken"] == 2


@pytest.mark.asyncio
async def test_dynamic_context_filtering_skips_apps_context_on_mobile():
    """Verify mobile tasks omit job tracker applications context to avoid TPM rate limits."""
    mock_mgr = MagicMock()
    mock_mgr.list_devices_details.return_value = []
    mock_job_tracker = MagicMock()
    mock_job_tracker.to_prompt_context.return_value = "HUGE APPLICATION LIST" * 200

    kaalu = KaaluOrchestrator(android_manager=mock_mgr, job_tracker=mock_job_tracker)

    captured_messages = []

    async def mock_generate(messages):
        captured_messages.extend(messages)
        return json.dumps({
            "thought": "Done",
            "action": "finish",
            "final_answer": "Done",
            "voice_response": "Done"
        })

    with patch.object(kaalu.ws_client, "connect_server", new_callable=AsyncMock):
        with patch.object(kaalu.llm_client, "generate_async", side_effect=mock_generate):
            # 1. Mobile Task: should NOT contain apps_context
            await kaalu.process_user_goal("call Diya on my phone")
            all_content = " ".join(m["content"] for m in captured_messages)
            assert "HUGE APPLICATION LIST" not in all_content

            # 2. Job Task: SHOULD contain apps_context
            captured_messages.clear()
            await kaalu.process_user_goal("what jobs have I applied to?")
            all_content_job = " ".join(m["content"] for m in captured_messages)
            assert "HUGE APPLICATION LIST" in all_content_job


@pytest.mark.asyncio
async def test_kaalu_delegates_to_gboard_emoji_and_rotation_control():
    """Verify Kaalu handles delegating gboard_emoji and set_auto_rotate to AndroidDeviceManager."""
    mock_mgr = MagicMock()
    mock_mgr.list_devices_details.return_value = []
    mock_mgr.type_gboard_emoji.return_value = {
        "success": True,
        "action": "type_gboard_emoji",
        "emoji": "laugh",
        "coordinate": [450, 1680],
        "method": "gboard_universal"
    }
    mock_mgr.set_auto_rotate.return_value = {
        "success": True,
        "action": "set_auto_rotate",
        "enabled": False,
        "status": {"auto_rotate": False, "is_portrait_locked": True}
    }

    kaalu = KaaluOrchestrator(android_manager=mock_mgr)

    # 1. Test gboard_emoji delegation
    step1_emoji = json.dumps({
        "thought": "Typing laughing emoji via Gboard.",
        "action": "delegate",
        "recipient": "android",
        "task_action": "gboard_emoji",
        "payload": {"emoji": "laugh"}
    })
    step2_finish = json.dumps({
        "thought": "Emoji entered.",
        "action": "finish",
        "final_answer": "Sent laughing emoji.",
        "voice_response": "Emoji sent."
    })

    with patch.object(kaalu.ws_client, "connect_server", new_callable=AsyncMock):
        with patch.object(kaalu.llm_client, "generate_async", side_effect=[step1_emoji, step2_finish]):
            res = await kaalu.process_user_goal("type laughing emoji")
            assert res["status"] == "completed"
            assert mock_mgr.type_gboard_emoji.called

    # 2. Test set_auto_rotate delegation
    step1_rotate = json.dumps({
        "thought": "Locking screen rotation to portrait mode.",
        "action": "delegate",
        "recipient": "android",
        "task_action": "set_auto_rotate",
        "payload": {"enabled": False}
    })

    with patch.object(kaalu.ws_client, "connect_server", new_callable=AsyncMock):
        with patch.object(kaalu.llm_client, "generate_async", side_effect=[step1_rotate, step2_finish]):
            res = await kaalu.process_user_goal("lock phone rotation to portrait")
            assert res["status"] == "completed"
            assert mock_mgr.set_auto_rotate.called


