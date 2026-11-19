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
