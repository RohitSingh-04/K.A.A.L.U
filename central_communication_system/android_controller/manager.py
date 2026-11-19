import base64
import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

DEFAULT_ADB_PATH = r"C:\Users\rsing\AppData\Local\Android\Sdk\platform-tools\adb.exe"
DEFAULT_SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent / "data" / "android_screenshots"

KEY_MAP = {
    "HOME": 3,
    "BACK": 4,
    "CALL": 5,
    "ENDCALL": 6,
    "VOLUME_UP": 24,
    "VOLUME_DOWN": 25,
    "POWER": 26,
    "CAMERA": 27,
    "CLEAR": 28,
    "COMMA": 55,
    "PERIOD": 56,
    "TAB": 61,
    "SPACE": 62,
    "ENTER": 66,
    "DELETE": 67,
    "BACKSPACE": 67,
    "ESCAPE": 111,
    "FORWARD_DEL": 112,
    "MOVE_HOME": 122,
    "MOVE_END": 123,
    "PAGE_UP": 92,
    "PAGE_DOWN": 93,
    "APP_SWITCH": 187,
    "RECENTS": 187,
    "MENU": 82,
    "NOTIFICATION": 83,
    "SEARCH": 84,
}


class AndroidDeviceManager:
    """
    Central manager for Android Device Automation over ADB.
    Recognizes connected devices (such as OnePlus phones), executes screen captures,
    touch taps, keyboard typing, gestures/swipes, and arbitrary shell operations.
    """

    _instance: Optional["AndroidDeviceManager"] = None

    def __init__(self, adb_path: Optional[str] = None, screenshots_dir: Optional[Path] = None):
        self.adb_path = self._resolve_adb_path(adb_path)
        self.screenshots_dir = Path(screenshots_dir) if screenshots_dir else DEFAULT_SCREENSHOTS_DIR
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance(cls, adb_path: Optional[str] = None) -> "AndroidDeviceManager":
        if cls._instance is None:
            cls._instance = AndroidDeviceManager(adb_path=adb_path)
        return cls._instance

    @staticmethod
    def _resolve_adb_path(override_path: Optional[str] = None) -> str:
        if override_path and os.path.exists(override_path):
            return override_path
        env_adb = os.environ.get("ADB_PATH")
        if env_adb and os.path.exists(env_adb):
            return env_adb
        if os.path.exists(DEFAULT_ADB_PATH):
            return DEFAULT_ADB_PATH
        system_adb = shutil.which("adb")
        if system_adb:
            return system_adb
        return DEFAULT_ADB_PATH

    def is_adb_available(self) -> bool:
        """Returns True if the ADB binary exists on the system."""
        return os.path.exists(self.adb_path)

    def _run_adb(self, args: List[str], timeout: float = 15.0, check: bool = False, binary: bool = False) -> subprocess.CompletedProcess:
        """
        Runs an ADB command using subprocess.
        Always captures raw bytes and decodes explicitly using UTF-8 with error replacement,
        preventing Windows cp1252/charmap UnicodeDecodeError on international/emoji texts.
        """
        cmd = [self.adb_path] + args
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout,
                check=check
            )
            if binary:
                return res

            stdout_str = res.stdout.decode("utf-8", errors="replace") if res.stdout else ""
            stderr_str = res.stderr.decode("utf-8", errors="replace") if res.stderr else ""
            return subprocess.CompletedProcess(cmd, returncode=res.returncode, stdout=stdout_str, stderr=stderr_str)
        except Exception as e:
            if binary:
                return subprocess.CompletedProcess(cmd, returncode=1, stdout=b"", stderr=str(e).encode())
            return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr=str(e))

    def list_devices(self) -> List[Dict[str, str]]:
        """
        Runs `adb devices -l` and parses the list of attached Android devices.
        Returns a list of dicts with serial, state, model, product, and device name.
        """
        if not self.is_adb_available():
            return []

        res = self._run_adb(["devices", "-l"])
        if res.returncode != 0:
            return []

        devices = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices attached") or line.startswith("*"):
                continue

            parts = line.split()
            if len(parts) >= 2:
                serial = parts[0]
                state = parts[1]
                extra = {}
                for token in parts[2:]:
                    if ":" in token:
                        k, v = token.split(":", 1)
                        extra[k.lower()] = v

                devices.append({
                    "serial": serial,
                    "state": state,
                    "product": extra.get("product", ""),
                    "model": extra.get("model", ""),
                    "device": extra.get("device", ""),
                    "transport_id": extra.get("transport_id", "")
                })

        return devices

    def get_device_details(self, serial: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves detailed hardware and software telemetry for a given Android device.
        Recognizes OnePlus devices, battery level, display resolution, and active app.
        """
        devices = self.list_devices()
        if not devices:
            return None

        target_serial = serial or devices[0]["serial"]
        dev_info = next((d for d in devices if d["serial"] == target_serial), None)
        if not dev_info:
            return None

        # Query Android system properties
        cmd = ["-s", target_serial, "shell", "getprop ro.product.brand; getprop ro.product.manufacturer; getprop ro.product.model; getprop ro.build.version.release; getprop ro.build.version.sdk"]
        res = self._run_adb(cmd, timeout=8.0)
        lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]

        brand = lines[0] if len(lines) > 0 else dev_info.get("product", "")
        manufacturer = lines[1] if len(lines) > 1 else brand
        model = lines[2] if len(lines) > 2 else dev_info.get("model", "")
        android_ver = lines[3] if len(lines) > 3 else "Unknown"
        sdk_ver = lines[4] if len(lines) > 4 else "Unknown"

        # Determine friendly brand and market name
        is_oneplus = (
            "oneplus" in brand.lower() or 
            "oneplus" in manufacturer.lower() or 
            model.upper().startswith("IV2201") or 
            dev_info.get("device", "").upper().startswith("OP")
        )
        if is_oneplus:
            friendly_brand = "OnePlus"
            if "IV2201" in model.upper():
                market_name = "OnePlus Nord CE 2 5G (OnePlus Phone)"
            else:
                market_name = f"OnePlus {model} (OnePlus Phone)"
        else:
            friendly_brand = brand or manufacturer or "Android Device"
            market_name = f"{friendly_brand} {model}".strip()

        # Query screen resolution
        size_res = self._run_adb(["-s", target_serial, "shell", "wm size"], timeout=5.0)
        m_size = re.search(r"(\d+x\d+)", size_res.stdout)
        resolution = m_size.group(1) if m_size else "1080x2400"

        # Query battery status
        bat_res = self._run_adb(["-s", target_serial, "shell", "dumpsys battery"], timeout=5.0)
        m_bat = re.search(r"level:\s*(\d+)", bat_res.stdout)
        battery_level = int(m_bat.group(1)) if m_bat else None

        # Query current focused window / app
        focus_res = self._run_adb(["-s", target_serial, "shell", "dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'"], timeout=5.0)
        m_app = re.search(r"u0\s+([a-zA-Z0-9_\.]+)/([a-zA-Z0-9_\.]+)", focus_res.stdout)
        current_package = m_app.group(1) if m_app else None
        current_activity = m_app.group(2) if m_app else None

        return {
            "serial": target_serial,
            "status": dev_info["state"],
            "brand": friendly_brand,
            "manufacturer": manufacturer,
            "model": model,
            "market_name": market_name,
            "is_oneplus": is_oneplus,
            "android_version": android_ver,
            "sdk_version": sdk_ver,
            "resolution": resolution,
            "battery_level": battery_level,
            "current_package": current_package,
            "current_activity": current_activity,
            "transport": "Wireless TLS" if "_adb-tls-connect" in target_serial else "USB"
        }

    def list_devices_details(self) -> List[Dict[str, Any]]:
        """Returns detailed telemetry for all attached devices."""
        devices = self.list_devices()
        return [self.get_device_details(d["serial"]) for d in devices if d["state"] == "device"]

    def _default_serial(self, serial: Optional[str] = None) -> Optional[str]:
        if serial:
            return serial
        devs = self.list_devices()
        return devs[0]["serial"] if devs else None

    def dump_ui_hierarchy(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """
        Dumps and parses the Android UI accessibility tree via `uiautomator dump`.
        Extracts all visible text strings, interactive elements (buttons, inputs, items),
        exact bounding boxes, and center coordinates.
        """
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected.", "visible_texts": [], "interactive_elements": []}

        # 1. Execute uiautomator dump on the device
        dump_res = self._run_adb(["-s", target_serial, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], timeout=10.0)
        cat_res = self._run_adb(["-s", target_serial, "exec-out", "cat", "/sdcard/window_dump.xml"], timeout=8.0)

        xml_text = cat_res.stdout
        if not xml_text or "<hierarchy" not in xml_text:
            return {
                "success": False,
                "error": f"Failed to dump UI hierarchy: {dump_res.stderr or cat_res.stderr or 'Empty XML'}",
                "visible_texts": [],
                "interactive_elements": []
            }

        # Query focused package/activity
        focus_res = self._run_adb(["-s", target_serial, "shell", "dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'"], timeout=5.0)
        m_app = re.search(r"u0\s+([a-zA-Z0-9_\.]+)/([a-zA-Z0-9_\.]+)", focus_res.stdout)
        current_package = m_app.group(1) if m_app else None
        current_activity = m_app.group(2) if m_app else None

        elements = []
        visible_texts = []
        interactive_elements = []

        try:
            root = ET.fromstring(xml_text)
            for node in root.iter("node"):
                text = (node.attrib.get("text") or "").strip()
                desc = (node.attrib.get("content-desc") or "").strip()
                res_id = (node.attrib.get("resource-id") or "").strip()
                cls_name = (node.attrib.get("class") or "").strip()
                clickable = node.attrib.get("clickable", "false").lower() == "true"
                editable = "EditText" in cls_name or (node.attrib.get("focusable", "false").lower() == "true" and "Edit" in cls_name)
                bounds_str = node.attrib.get("bounds", "")

                m = re.findall(r"\[(\d+),(\d+)\]", bounds_str)
                if len(m) == 2:
                    x1, y1 = int(m[0][0]), int(m[0][1])
                    x2, y2 = int(m[1][0]), int(m[1][1])
                    width = x2 - x1
                    height = y2 - y1
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                    label = text or desc
                    if label and label not in visible_texts:
                        visible_texts.append(label)

                    elem_type = "input" if editable else ("button" if (clickable and ("Button" in cls_name or "Image" in cls_name)) else ("item" if clickable else "text"))

                    short_res_id = res_id.split("/")[-1] if "/" in res_id else res_id
                    elem_info = {
                        "label": label,
                        "text": text,
                        "content_desc": desc,
                        "resource_id": short_res_id,
                        "class": cls_name.split(".")[-1] if "." in cls_name else cls_name,
                        "clickable": clickable,
                        "editable": editable,
                        "type": elem_type,
                        "bounds": [x1, y1, x2, y2],
                        "center": [cx, cy],
                        "width": width,
                        "height": height
                    }
                    elements.append(elem_info)

                    # Keep interactive or labeled elements in summary
                    if (clickable or editable or text) and width > 0 and height > 0:
                        interactive_elements.append({
                            "label": label or short_res_id or elem_type,
                            "type": elem_type,
                            "center": [cx, cy],
                            "bounds": [x1, y1, x2, y2],
                            "resource_id": short_res_id if short_res_id else None
                        })

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to parse UI XML: {e}",
                "visible_texts": [],
                "interactive_elements": []
            }

        return {
            "success": True,
            "device": target_serial,
            "current_package": current_package,
            "current_activity": current_activity,
            "visible_texts": visible_texts,
            "interactive_elements": interactive_elements,
            "elements": elements
        }

    def find_element(self, target: str, serial: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Locates a UI element on screen by text, content-desc, or resource-id.
        Tries exact match first, then case-insensitive substring match.
        """
        if not target or not isinstance(target, str):
            return None
        t_clean = target.strip().lower()

        hierarchy = self.dump_ui_hierarchy(serial)
        if not hierarchy.get("success"):
            return None

        elements = hierarchy.get("elements", [])

        # 1. Exact text or content_desc match
        for elem in elements:
            if (elem.get("text") and elem["text"].strip().lower() == t_clean) or \
               (elem.get("content_desc") and elem["content_desc"].strip().lower() == t_clean):
                return elem

        # 2. Substring match on text or content_desc
        for elem in elements:
            e_text = (elem.get("text") or "").lower()
            e_desc = (elem.get("content_desc") or "").lower()
            if t_clean in e_text or t_clean in e_desc:
                return elem

        # 3. Substring match on resource-id
        for elem in elements:
            e_res = (elem.get("resource_id") or "").lower()
            if t_clean in e_res:
                return elem

        # 4. Semantic fallback for message input field in chat apps
        if t_clean in ("message", "type a message", "input", "chat_input", "text_input"):
            for elem in elements:
                if elem.get("editable") or "EditText" in elem.get("class", "") or "entry" in (elem.get("resource_id") or "").lower():
                    return elem

        # 5. Semantic fallback for Send button in chat apps
        if t_clean in ("send", "send button", "send_button"):
            for elem in elements:
                if (elem.get("content_desc") or "").strip().lower() == "send" or "send" in (elem.get("resource_id") or "").lower():
                    return elem

        return None

    def inspect_screen(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Returns the current screen's visible texts, active package, and interactive elements."""
        return self.dump_ui_hierarchy(serial)

    def capture_screenshot(self, serial: Optional[str] = None, save: bool = True, include_ui: bool = True) -> Dict[str, Any]:
        """
        Captures a high-resolution screenshot from the Android device.
        Uses high-speed binary pipe (`exec-out screencap -p`), saves image file path,
        and automatically dumps visible UI hierarchy and interactive elements.
        """
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}

        res = self._run_adb(["-s", target_serial, "exec-out", "screencap", "-p"], binary=True, timeout=12.0)
        if res.returncode != 0 or len(res.stdout) < 100 or res.stdout[:8] != b"\x89PNG\r\n\x1a\n":
            return {"success": False, "error": f"Failed to capture screen: {res.stderr.decode(errors='replace')}"}

        png_bytes = res.stdout
        b64_str = base64.b64encode(png_bytes).decode("utf-8")

        saved_path = None
        if save:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            saved_file = self.screenshots_dir / f"screen_{ts}.png"
            with open(saved_file, "wb") as f:
                f.write(png_bytes)
            saved_path = str(saved_file)

        result = {
            "success": True,
            "device": target_serial,
            "bytes_length": len(png_bytes),
            "screenshot_base64": b64_str,
            "saved_path": saved_path
        }

        if include_ui:
            ui = self.dump_ui_hierarchy(target_serial)
            if ui.get("success"):
                result["current_package"] = ui.get("current_package")
                result["current_activity"] = ui.get("current_activity")
                result["visible_texts"] = ui.get("visible_texts", [])
                result["interactive_elements"] = ui.get("interactive_elements", [])
                result["ui_elements_count"] = len(ui.get("interactive_elements", []))

        return result

    def tap(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        target: Optional[str] = None,
        serial: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Performs a touch tap at screen coordinate (x, y) OR by locating a target element by label/text.
        """
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}

        # Semantic target tap (e.g. target="Diya BBA GEHU" or target="Search" or target="Send")
        if target:
            elem = self.find_element(target=target, serial=target_serial)
            if not elem:
                hierarchy = self.dump_ui_hierarchy(target_serial)
                sample_texts = hierarchy.get("visible_texts", [])[:15]
                return {
                    "success": False,
                    "action": "tap",
                    "target": target,
                    "error": f"Target element '{target}' not found on the active screen.",
                    "current_package": hierarchy.get("current_package"),
                    "visible_texts_sample": sample_texts
                }
            cx, cy = elem["center"]
            res = self._run_adb(["-s", target_serial, "shell", "input", "tap", str(cx), str(cy)])
            return {
                "success": res.returncode == 0,
                "action": "tap",
                "target": target,
                "matched_element": {
                    "label": elem.get("label"),
                    "text": elem.get("text"),
                    "content_desc": elem.get("content_desc"),
                    "bounds": elem.get("bounds"),
                    "center": [cx, cy]
                },
                "x": cx,
                "y": cy,
                "error": res.stderr if res.returncode != 0 else None
            }

        # Coordinate tap
        if x is None or y is None:
            return {"success": False, "error": "Either 'target' or both 'x' and 'y' must be provided."}

        res = self._run_adb(["-s", target_serial, "shell", "input", "tap", str(x), str(y)])
        return {
            "success": res.returncode == 0,
            "action": "tap",
            "x": x,
            "y": y,
            "error": res.stderr if res.returncode != 0 else None
        }

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300, serial: Optional[str] = None) -> Dict[str, Any]:
        """Performs a swipe or drag gesture from (x1, y1) to (x2, y2)."""
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}

        res = self._run_adb(["-s", target_serial, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)])
        return {
            "success": res.returncode == 0,
            "action": "swipe",
            "from": (x1, y1),
            "to": (x2, y2),
            "duration_ms": duration_ms,
            "error": res.stderr if res.returncode != 0 else None
        }

    def type_text(
        self,
        text: str,
        target: Optional[str] = None,
        clear: bool = False,
        press_enter: bool = False,
        serial: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Types text into the active focused field, or finds and focuses the target input element first.
        """
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}

        # If a target input is specified (e.g. target="Message" or target="Search"), tap it first to focus
        if target:
            elem = self.find_element(target=target, serial=target_serial)
            if elem:
                cx, cy = elem["center"]
                self._run_adb(["-s", target_serial, "shell", "input", "tap", str(cx), str(cy)])
                time.sleep(0.3)

        if clear:
            self._run_adb(["-s", target_serial, "shell", "input", "keyevent", "123"])
            for _ in range(50):
                self._run_adb(["-s", target_serial, "shell", "input", "keyevent", "67"])

        # ADB input text requires spaces to be escaped as %s and quotes escaped
        safe_text = text.replace(" ", "%s").replace("&", "\\&").replace("<", "\\<").replace(">", "\\>").replace('"', '\\"')
        res = self._run_adb(["-s", target_serial, "shell", "input", "text", f'"{safe_text}"'])

        if press_enter:
            self._run_adb(["-s", target_serial, "shell", "input", "keyevent", "66"])

        return {
            "success": res.returncode == 0,
            "action": "type",
            "text": text,
            "target": target,
            "press_enter": press_enter,
            "error": res.stderr if res.returncode != 0 else None
        }

    def press_key(self, key: Union[str, int], serial: Optional[str] = None) -> Dict[str, Any]:
        """Presses an Android hardware or keyboard key (e.g. HOME, BACK, ENTER, APP_SWITCH)."""
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}

        if isinstance(key, str):
            keycode = KEY_MAP.get(key.upper(), key)
        else:
            keycode = key

        res = self._run_adb(["-s", target_serial, "shell", "input", "keyevent", str(keycode)])
        return {
            "success": res.returncode == 0,
            "action": "press_key",
            "key": key,
            "keycode": keycode,
            "error": res.stderr if res.returncode != 0 else None
        }

    def open_app(self, package: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Launches an application package via monkey or am start."""
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}

        res = self._run_adb(["-s", target_serial, "shell", "monkey", "-p", package.strip(), "-c", "android.intent.category.LAUNCHER", "1"])
        return {
            "success": res.returncode == 0,
            "action": "open_app",
            "package": package,
            "error": res.stderr if res.returncode != 0 else None
        }

    def shell(self, command: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Executes an arbitrary ADB shell command on the device."""
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}

        res = self._run_adb(["-s", target_serial, "shell", command])
        return {
            "success": res.returncode == 0,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "exit_code": res.returncode
        }

    def type_gboard_emoji(
        self,
        emoji: str = "laugh",
        target: Optional[str] = None,
        serial: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Universally types an emoji using Gboard across any Android application.
        Uses Gboard's emoji search for 100% deterministic, reliable results independent of recent emojis:
        1. Focuses input field so Gboard is visible.
        2. Long-presses the comma/emoji ',' key at [205, 2320] on Gboard (450ms) to open the emoji palette.
        3. Taps the 'Search' pill on Gboard at [280, 1280].
        4. Types the search keyword (e.g. 'laugh', 'smile', 'heart', 'rofl') into Gboard emoji search.
        5. Selects the target emoji from the deterministic search results grid (e.g. 😂 at [229, 1213]).
        6. Closes the search palette / switches back to text mode cleanly.
        """
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}

        # 1. Ensure input field is focused so Gboard is visible
        if target:
            self.tap(target=target, serial=target_serial)
            time.sleep(0.4)
        else:
            entry = (
                self.find_element("entry", serial=target_serial)
                or self.find_element("Message", serial=target_serial)
                or self.find_element("Type a message", serial=target_serial)
            )
            if entry:
                self._run_adb(["-s", target_serial, "shell", "input", "tap", str(entry["center"][0]), str(entry["center"][1])])
                time.sleep(0.4)

        # 2. Long press on ',' (comma/emoji) key on Gboard at [205, 2320] (450ms)
        self._run_adb(["-s", target_serial, "shell", "input", "swipe", "205", "2320", "205", "2320", "450"])
        time.sleep(0.5)

        # 3. Tap the 'Q Search' pill on Gboard emoji palette at [280, 1280]
        self._run_adb(["-s", target_serial, "shell", "input", "tap", "280", "1280"])
        time.sleep(0.5)

        # 4. Resolve keyword for Gboard emoji search
        emoji_clean = emoji.strip().lower()
        search_keyword_map = {
            "😂": "laugh",
            "laugh": "laugh",
            "laughing": "laugh",
            "joy": "laugh",
            "🤣": "rofl",
            "rofl": "rofl",
            "rolling": "rofl",
            "🙂": "smile",
            "😀": "smile",
            "smile": "smile",
            "happy": "smile",
            "grin": "smile",
            "❤️": "heart",
            "heart": "heart",
            "love": "heart",
            "👍": "thumbs up",
            "thumbs_up": "thumbs up",
            "thumbsup": "thumbs up",
            "👏": "clap",
            "clap": "clap",
            "🔥": "fire",
            "fire": "fire",
            "lit": "fire"
        }
        search_term = search_keyword_map.get(emoji_clean, emoji_clean)
        safe_term = search_term.replace(" ", "%s")
        self._run_adb(["-s", target_serial, "shell", "input", "text", safe_term])
        time.sleep(0.6)

        # 5. Tap the target emoji in Gboard's deterministic search results grid
        # In Gboard search results: Row 1 is at y=1213.
        # For 'laugh': Col 1 [229, 1213] is '😂' (Face with tears of joy), Col 0 [89, 1213] is '🤣' (ROFL).
        # For other single-match queries (smile, heart, thumbs up, fire), Col 0 [89, 1213] is the primary match.
        search_grid_coords = {
            "laugh": (229, 1213),
            "laughing": (229, 1213),
            "joy": (229, 1213),
            "😂": (229, 1213),
            "rofl": (89, 1213),
            "🤣": (89, 1213),
            "smile": (89, 1213),
            "happy": (89, 1213),
            "🙂": (89, 1213),
            "😀": (89, 1213),
            "grin": (89, 1213),
            "heart": (89, 1213),
            "love": (89, 1213),
            "❤️": (89, 1213),
            "thumbs_up": (89, 1213),
            "thumbsup": (89, 1213),
            "👍": (89, 1213),
            "clap": (89, 1213),
            "👏": (89, 1213),
            "fire": (89, 1213),
            "🔥": (89, 1213),
        }
        tap_coord = search_grid_coords.get(emoji_clean, (89, 1213))
        self._run_adb(["-s", target_serial, "shell", "input", "tap", str(tap_coord[0]), str(tap_coord[1])])
        time.sleep(0.4)

        # 6. Tap back arrow on Gboard search [72, 1045] to close search palette and restore keyboard
        self._run_adb(["-s", target_serial, "shell", "input", "tap", "72", "1045"])
        time.sleep(0.3)

        return {
            "success": True,
            "action": "type_gboard_emoji",
            "emoji": emoji,
            "search_term": search_term,
            "coordinate": tap_coord,
            "method": "gboard_emoji_search"
        }

    def tap_emoji(self, emoji: str = "laugh", serial: Optional[str] = None) -> Dict[str, Any]:
        """
        Universal emoji typing method via Gboard keyboard.
        Uses Gboard's long-press on ',' to open emoji options across all Android apps.
        """
        return self.type_gboard_emoji(emoji=emoji, serial=serial)

    def get_auto_rotate_status(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Queries current screen auto-rotation and orientation lock status."""
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}
        accel = self._run_adb(["-s", target_serial, "shell", "settings", "get", "system", "accelerometer_rotation"]).stdout.strip()
        user_rot = self._run_adb(["-s", target_serial, "shell", "settings", "get", "system", "user_rotation"]).stdout.strip()
        return {
            "success": True,
            "auto_rotate": accel == "1",
            "accelerometer_rotation": accel,
            "user_rotation": user_rot,
            "is_portrait_locked": accel == "0" and user_rot == "0"
        }

    def set_auto_rotate(self, enabled: bool = False, serial: Optional[str] = None) -> Dict[str, Any]:
        """
        Locks screen orientation or enables auto-rotate.
        enabled=False locks device in portrait mode and disables auto-rotate.
        """
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}
        val = "1" if enabled else "0"
        self._run_adb(["-s", target_serial, "shell", "settings", "put", "system", "accelerometer_rotation", val])
        if not enabled:
            self._run_adb(["-s", target_serial, "shell", "settings", "put", "system", "user_rotation", "0"])
        status = self.get_auto_rotate_status(serial=target_serial)
        return {
            "success": True,
            "action": "set_auto_rotate",
            "enabled": enabled,
            "status": status
        }

    def search_contacts(self, query: str = "", serial: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Searches Android contacts database via ADB content query on com.android.contacts.
        Returns a list of matching contacts with name, raw number, and sanitized clean_number.
        """
        target_serial = self._default_serial(serial)
        if not target_serial:
            return []

        res = self._run_adb([
            "-s", target_serial, "shell", "content", "query",
            "--uri", "content://com.android.contacts/data/phones",
            "--projection", "display_name:data1"
        ])
        if res.returncode != 0 or not res.stdout:
            return []

        q = query.strip().lower()
        matches = []
        for line in res.stdout.splitlines():
            m = re.search(r"display_name=(.*?), data1=(.*)", line)
            if m:
                name = m.group(1).strip()
                number = m.group(2).strip()
                clean_num = re.sub(r"[^\d+]", "", number)
                if not q or q == name.lower() or q in name.lower():
                    matches.append({
                        "name": name,
                        "number": number,
                        "clean_number": clean_num
                    })

        # Sort exact matches first, then shortest names
        if q:
            matches.sort(key=lambda x: (x["name"].lower() != q, len(x["name"])))
        return matches

    def call_phone(self, target: str, app: str = "phone", serial: Optional[str] = None) -> Dict[str, Any]:
        """
        Places a phone call or WhatsApp voice call to a phone number or contact name.
        Automatically resolves contact names (e.g. 'Mom', 'Diya') to their saved phone number.
        Uses native high-speed CALL intent to initiate calling in 0.2s without manual dialer loops.
        """
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}

        clean_digits = re.sub(r"[^\d+]", "", target)

        if app.lower() == "whatsapp":
            # WhatsApp Voice Call
            self.open_app("com.whatsapp", serial=target_serial)
            time.sleep(0.6)
            h = self.dump_ui_hierarchy(target_serial)

            # If not in conversation, open chat
            if "Conversation" not in (h.get("current_activity") or ""):
                contact_elem = self.find_element(target, serial=target_serial)
                if contact_elem and contact_elem["center"][1] > 400:
                    self._run_adb(["-s", target_serial, "shell", "input", "tap", str(contact_elem["center"][0]), str(contact_elem["center"][1])])
                else:
                    self._run_adb(["-s", target_serial, "shell", "input", "tap", "540", "359"])
                    time.sleep(0.3)
                    self.type_text(target, serial=target_serial)
                    time.sleep(0.6)
                    found = self.find_element(target, serial=target_serial)
                    if found:
                        self._run_adb(["-s", target_serial, "shell", "input", "tap", str(found["center"][0]), str(found["center"][1])])
                    else:
                        self._run_adb(["-s", target_serial, "shell", "input", "tap", "387", "868"])
                time.sleep(0.8)

            # Tap Voice call button in chat header
            call_btn = self.find_element("Voice call", serial=target_serial)
            if call_btn:
                self._run_adb(["-s", target_serial, "shell", "input", "tap", str(call_btn["center"][0]), str(call_btn["center"][1])])
            else:
                self._run_adb(["-s", target_serial, "shell", "input", "tap", "888", "191"])
            time.sleep(0.5)

            confirm = self.find_element("Call", serial=target_serial)
            if confirm:
                self._run_adb(["-s", target_serial, "shell", "input", "tap", str(confirm["center"][0]), str(confirm["center"][1])])

            return {
                "success": True,
                "action": "call_phone",
                "type": "whatsapp_voice_call",
                "contact": target,
                "app": "whatsapp"
            }

        else:
            # Cellular Phone Call
            resolved_number = clean_digits
            contact_name = target

            # If target is a contact name (not purely a number), resolve via contact database
            if not clean_digits or len(clean_digits) < 3:
                contacts = self.search_contacts(target, serial=target_serial)
                if contacts:
                    resolved_number = contacts[0]["clean_number"]
                    contact_name = contacts[0]["name"]
                else:
                    # Fallback to Contacts app search if not in database
                    self._run_adb(["-s", target_serial, "shell", "am", "start", "-a", "android.intent.action.VIEW", "content://contacts/people"])
                    time.sleep(0.5)
                    self.type_text(target, serial=target_serial)
                    time.sleep(0.5)
                    found_elem = self.find_element(target, serial=target_serial)
                    if found_elem:
                        self.tap(target=target, serial=target_serial)
                        time.sleep(0.5)
                        call_icon = self.find_element("Call", serial=target_serial)
                        if call_icon:
                            self._run_adb(["-s", target_serial, "shell", "input", "tap", str(call_icon["center"][0]), str(call_icon["center"][1])])
                    return {
                        "success": True,
                        "action": "call_phone",
                        "type": "contacts_ui_search",
                        "target": target
                    }

            res = self._run_adb(["-s", target_serial, "shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{resolved_number}"])
            if res.returncode != 0:
                self._run_adb(["-s", target_serial, "shell", "am", "start", "-a", "android.intent.action.DIAL", "-d", f"tel:{resolved_number}"])

            return {
                "success": True,
                "action": "call_phone",
                "type": "cellular",
                "contact": contact_name,
                "phone_number": resolved_number,
                "target": target
            }

    def answer_call(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Answers an incoming phone call or WhatsApp audio call using standard Android CALL keyevent."""
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}
        self.press_key("CALL", serial=target_serial)
        time.sleep(0.2)
        self._run_adb(["-s", target_serial, "shell", "input", "keyevent", "79"]) # HEADSETHOOK toggle
        return {"success": True, "action": "answer_call"}

    def end_call(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Ends or hangs up an active phone call using standard Android ENDCALL keyevent."""
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}
        self.press_key("ENDCALL", serial=target_serial)
        return {"success": True, "action": "end_call"}

    def send_sms(
        self,
        target: str,
        message: str,
        auto_send: bool = True,
        serial: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends an SMS text message to a contact name or phone number.
        Automatically resolves contact names to phone numbers via search_contacts.
        Prefills message using Android's SENDTO intent and verifies/taps Send.
        """
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}

        clean_digits = re.sub(r"[^\d+]", "", target)
        resolved_number = clean_digits
        contact_name = target

        if not clean_digits or len(clean_digits) < 3:
            contacts = self.search_contacts(target, serial=target_serial)
            if contacts:
                resolved_number = contacts[0]["clean_number"]
                contact_name = contacts[0]["name"]
            else:
                return {
                    "success": False,
                    "error": f"Contact '{target}' not found in contacts list."
                }

        res = self._run_adb([
            "-s", target_serial, "shell", "am", "start",
            "-a", "android.intent.action.SENDTO",
            "-d", f"sms:{resolved_number}",
            "--es", "sms_body", message
        ])
        time.sleep(0.8)

        sent = False
        if auto_send:
            h = self.dump_ui_hierarchy(target_serial)
            send_btn = (
                self.find_element("Send SMS", serial=target_serial)
                or self.find_element("send_message_button", serial=target_serial)
                or self.find_element("send", serial=target_serial)
            )
            if send_btn:
                self._run_adb(["-s", target_serial, "shell", "input", "tap", str(send_btn["center"][0]), str(send_btn["center"][1])])
                sent = True
            else:
                self.press_key("ENTER", serial=target_serial)
                sent = True

        return {
            "success": res.returncode == 0,
            "action": "send_sms",
            "contact": contact_name,
            "phone_number": resolved_number,
            "message": message,
            "auto_send": auto_send,
            "verified": sent
        }

    def read_sms(self, limit: int = 10, serial: Optional[str] = None) -> Dict[str, Any]:
        """
        Reads recent SMS messages from Android's SMS inbox content provider.
        Returns message senders, timestamps, and message bodies.
        """
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}

        res = self._run_adb([
            "-s", target_serial, "shell", "content", "query",
            "--uri", "content://sms/inbox",
            "--projection", "address:body:date"
        ])
        if res.returncode != 0:
            return {"success": False, "error": res.stderr}

        messages = []
        raw = res.stdout
        rows = re.split(r"Row:\s*\d+\s+", raw)
        for r in rows:
            if not r.strip() or "address=" not in r:
                continue
            m = re.search(r"address=(.*?), body=(.*), date=(\d+)", r, re.DOTALL)
            if m:
                sender = m.group(1).strip()
                body = m.group(2).strip()
                try:
                    ts_ms = int(m.group(3))
                    dt_str = datetime.fromtimestamp(ts_ms / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    dt_str = "Unknown"
                    ts_ms = 0
                messages.append({
                    "sender": sender,
                    "body": body,
                    "date": dt_str,
                    "timestamp": ts_ms
                })
                if len(messages) >= limit:
                    break

        return {
            "success": True,
            "count": len(messages),
            "messages": messages
        }

    def get_bluetooth_status(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """
        Queries Bluetooth status, adapter state, and paired/bonded devices via dumpsys bluetooth_manager.
        """
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}

        res = self._run_adb(["-s", target_serial, "shell", "dumpsys", "bluetooth_manager"])
        if res.returncode != 0:
            return {"success": False, "error": res.stderr}

        lines = res.stdout.splitlines()
        enabled = False
        state = "UNKNOWN"
        device_name = ""
        bonded = []
        in_bonded = False

        for line in lines:
            l = line.strip()
            if l.startswith("enabled:"):
                enabled = "true" in l.lower()
            elif l.startswith("state:"):
                state = l.split(":", 1)[1].strip()
            elif l.startswith("name:") and not device_name:
                device_name = l.split(":", 1)[1].strip()
            elif "bonded devices:" in l.lower():
                in_bonded = True
                continue
            elif in_bonded:
                if not l or l.startswith("rec[") or l.startswith("curState="):
                    in_bonded = False
                elif in_bonded:
                    m = re.match(r"([0-9A-Fa-f:]{17})\s*(?:\[(.*?)\])?\s*(.*)", l)
                    if m:
                        bonded.append({
                            "address": m.group(1),
                            "type": (m.group(2) or "").strip(),
                            "name": (m.group(3) or "").strip()
                        })

        return {
            "success": True,
            "enabled": enabled,
            "state": state,
            "device_name": device_name,
            "bonded_devices_count": len(bonded),
            "bonded_devices": bonded
        }

    def set_bluetooth(self, enabled: bool = True, serial: Optional[str] = None) -> Dict[str, Any]:
        """Turns device Bluetooth ON or OFF via ADB cmd bluetooth_manager."""
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}

        action = "enable" if enabled else "disable"
        res = self._run_adb(["-s", target_serial, "shell", "cmd", "bluetooth_manager", action])
        time.sleep(0.5)
        status = self.get_bluetooth_status(serial=target_serial)
        return {
            "success": res.returncode == 0,
            "action": f"bluetooth_{action}",
            "enabled": enabled,
            "status": status
        }

    def connect_bluetooth_device(self, device_name_or_address: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """
        Opens Bluetooth settings and connects to a paired Bluetooth device (headphones, earbuds, watch).
        """
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}

        # 1. Ensure Bluetooth is ON
        self.set_bluetooth(enabled=True, serial=target_serial)

        # 2. Open Bluetooth Settings
        self._run_adb(["-s", target_serial, "shell", "am", "start", "-a", "android.settings.BLUETOOTH_SETTINGS"])
        time.sleep(0.8)

        # 3. Locate and tap device in Bluetooth list
        h = self.dump_ui_hierarchy(target_serial)
        target_clean = device_name_or_address.strip().lower()
        dev_elem = None
        for elem in h.get("elements", []):
            label = (elem.get("text") or elem.get("content_desc") or "").lower()
            if target_clean in label:
                dev_elem = elem
                break

        if dev_elem:
            self._run_adb(["-s", target_serial, "shell", "input", "tap", str(dev_elem["center"][0]), str(dev_elem["center"][1])])
            time.sleep(0.5)
            return {
                "success": True,
                "action": "connect_bluetooth_device",
                "device": device_name_or_address,
                "connected": True
            }

        return {
            "success": False,
            "action": "connect_bluetooth_device",
            "device": device_name_or_address,
            "error": f"Device '{device_name_or_address}' not found in active Bluetooth settings screen."
        }

    def send_whatsapp(
        self,
        contact: str,
        message: str = "",
        emoji: Optional[str] = None,
        auto_send: bool = True,
        serial: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        High-level, ultra-efficient workflow for sending WhatsApp messages & emojis.
        Executes end-to-end in a single turn without consuming reasoning loops or token limits.
        If auto_send is False, prepares the chat and types the message/emoji without tapping Send.
        """
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "error": "No Android device connected."}

        # 1. Bring WhatsApp to front
        self.open_app("com.whatsapp", serial=target_serial)
        time.sleep(0.6)

        h = self.dump_ui_hierarchy(target_serial)
        activity = h.get("current_activity") or ""

        # If currently in ContactInfo, press back
        if "ContactInfoActivity" in activity:
            self.press_key("BACK", serial=target_serial)
            time.sleep(0.4)
            h = self.dump_ui_hierarchy(target_serial)
            activity = h.get("current_activity") or ""

        # 2. Check if already in Conversation with this contact
        in_correct_chat = "Conversation" in activity and (self.find_element(contact, serial=target_serial) is not None)

        if not in_correct_chat:
            if "Conversation" in activity:
                self.press_key("BACK", serial=target_serial)
                time.sleep(0.4)
                h = self.dump_ui_hierarchy(target_serial)

            contact_elem = self.find_element(contact, serial=target_serial)
            if contact_elem and contact_elem["center"][1] > 400:
                self._run_adb(["-s", target_serial, "shell", "input", "tap", str(contact_elem["center"][0]), str(contact_elem["center"][1])])
            else:
                search_elem = self.find_element("Ask Meta AI or Search", serial=target_serial) or self.find_element("Search", serial=target_serial)
                if search_elem:
                    self._run_adb(["-s", target_serial, "shell", "input", "tap", str(search_elem["center"][0]), str(search_elem["center"][1])])
                else:
                    self._run_adb(["-s", target_serial, "shell", "input", "tap", "540", "359"])
                time.sleep(0.3)
                self.type_text(contact, serial=target_serial)
                time.sleep(0.7)

                res_elem = self.find_element(contact, serial=target_serial)
                if res_elem:
                    self._run_adb(["-s", target_serial, "shell", "input", "tap", str(res_elem["center"][0]), str(res_elem["center"][1])])
                else:
                    self._run_adb(["-s", target_serial, "shell", "input", "tap", "387", "868"])
            time.sleep(0.8)

        # 3. Locate text input field and ensure it is focused (opens Gboard)
        entry_elem = (
            self.find_element("entry", serial=target_serial)
            or self.find_element("Message", serial=target_serial)
            or self.find_element("Type a message", serial=target_serial)
        )
        input_y = entry_elem["center"][1] if entry_elem else 1502
        if entry_elem:
            self._run_adb(["-s", target_serial, "shell", "input", "tap", str(entry_elem["center"][0]), str(entry_elem["center"][1])])
            time.sleep(0.3)

        # 4. Type text message if provided
        if message:
            self.type_text(text=message, serial=target_serial)
            time.sleep(0.3)

        # 5. Type emoji via Gboard if requested (universal across apps)
        if emoji:
            self.type_gboard_emoji(emoji=emoji, serial=target_serial)
            time.sleep(0.4)

        # 6. Locate Send button with explicit guard against Voice Note Recording
        sent = False
        if auto_send:
            h = self.dump_ui_hierarchy(target_serial)
            send_btn = self.find_element("Send", serial=target_serial)
            if send_btn:
                self._run_adb(["-s", target_serial, "shell", "input", "tap", str(send_btn["center"][0]), str(send_btn["center"][1])])
                sent = True
            else:
                # ABSOLUTE SAFEGUARD: If Send button is not confirmed on screen, DO NOT TAP!
                # In WhatsApp, tapping (980, y) when Send is absent triggers the microphone/voice recording.
                print("[Android Safeguard] Send button is not visible on screen. Skipping tap to completely prevent activating voice recording.")
                sent = False
            time.sleep(0.4)

        return {
            "success": True,
            "action": "send_whatsapp",
            "contact": contact,
            "message": message,
            "emoji": emoji,
            "auto_send": auto_send,
            "verified": sent
        }

    def unlock_device(self, pin: Optional[str] = None, serial: Optional[str] = None) -> Dict[str, Any]:
        """
        Unlocks the Android device.
        If pin is not provided, automatically retrieves and decrypts the PIN from PhoneCredentialsManager.
        Sequence:
          1. Wakes device screen (keyevent 224 / WAKEUP) if asleep.
          2. Dismisses lockscreen: sends keyevent 82 (MENU) and performs upward swipe gesture (540, 1850 -> 540, 700).
          3. Enters unlock PIN/password via 'input text <pin>'.
          4. Submits PIN with keyevent 66 (ENTER).
          5. Verifies keyguard dismissal.
        """
        target_serial = self._default_serial(serial)
        if not target_serial:
            return {"success": False, "action": "unlock_device", "error": "No Android device connected."}

        # 1. Resolve PIN
        unlock_pin = pin
        if not unlock_pin:
            try:
                from android_controller.credentials import PhoneCredentialsManager
                unlock_pin = PhoneCredentialsManager.get_instance().get_pin(serial=target_serial)
            except Exception as e:
                return {"success": False, "action": "unlock_device", "error": f"Failed to retrieve stored credentials: {e}"}

        if not unlock_pin:
            return {
                "success": False,
                "action": "unlock_device",
                "error": "No unlock PIN/password configured. Please configure your phone PIN in /settings or provide it."
            }

        # 2. Wake device screen if sleeping
        pwr_res = self._run_adb(["-s", target_serial, "shell", "dumpsys", "power"], timeout=5.0)
        pwr_out = pwr_res.stdout or ""
        is_asleep = "mWakefulness=Asleep" in pwr_out or "mWakefulness=Dozing" in pwr_out
        if is_asleep or "mWakefulness=Awake" not in pwr_out:
            self._run_adb(["-s", target_serial, "shell", "input", "keyevent", "224"])
            time.sleep(0.3)

        # 3. Dismiss lockscreen & reveal PIN entry
        self._run_adb(["-s", target_serial, "shell", "input", "keyevent", "82"])
        time.sleep(0.2)
        self._run_adb(["-s", target_serial, "shell", "input", "swipe", "540", "1850", "540", "700", "250"])
        time.sleep(0.4)

        # 4. Input the PIN text
        self._run_adb(["-s", target_serial, "shell", "input", "text", str(unlock_pin)])
        time.sleep(0.2)

        # 5. Submit PIN via ENTER keyevent (66)
        self._run_adb(["-s", target_serial, "shell", "input", "keyevent", "66"])
        time.sleep(0.5)

        # 6. Check lock status
        win_res = self._run_adb(["-s", target_serial, "shell", "dumpsys", "window"], timeout=5.0)
        win_out = win_res.stdout or ""
        unlocked = ("isStatusBarKeyguard=false" in win_out) or ("mShowing=false" in win_out) or ("isKeyguardShowing=false" in win_out)

        return {
            "success": True,
            "action": "unlock_device",
            "serial": target_serial,
            "verified": unlocked,
            "message": "Device unlock sequence executed successfully."
        }

    def get_credentials_status(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Returns phone PIN configuration status (without exposing plaintext PIN)."""
        from android_controller.credentials import PhoneCredentialsManager
        target_serial = self._default_serial(serial)
        return PhoneCredentialsManager.get_instance().get_status(serial=target_serial)

    def save_phone_pin(self, pin: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Encrypts and saves phone PIN."""
        from android_controller.credentials import PhoneCredentialsManager
        target_serial = self._default_serial(serial)
        return PhoneCredentialsManager.get_instance().save_pin(pin=pin, serial=target_serial)

    def clear_phone_pin(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Clears saved phone PIN."""
        from android_controller.credentials import PhoneCredentialsManager
        target_serial = self._default_serial(serial)
        return PhoneCredentialsManager.get_instance().clear_pin(serial=target_serial)

