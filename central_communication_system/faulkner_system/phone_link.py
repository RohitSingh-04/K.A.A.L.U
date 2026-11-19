import os
import re
import subprocess
import time
from typing import Optional, Dict, Any, List

try:
    from android_controller.manager import AndroidDeviceManager
except (ImportError, ValueError):
    try:
        from ..android_controller.manager import AndroidDeviceManager
    except (ImportError, ValueError):
        AndroidDeviceManager = None


class PhoneLinkController:
    """
    Controls Microsoft Phone Link (formerly Your Phone) on Windows 10/11.
    Handles placing calls, opening the dialer, and sending SMS via Windows Phone Link
    connected to the user's paired Android/OnePlus mobile device.
    """

    PHONE_LINK_APP_ID = "Microsoft.YourPhone_8wekyb3d8bbwe!App"
    TEL_PROTOCOL_PREFIX = "tel:"
    MS_PHONE_PROTOCOL = "ms-phone://"

    @classmethod
    def resolve_contact_number(cls, target: str) -> Optional[Dict[str, str]]:
        """
        Attempts to resolve a contact name (e.g. 'Mom', 'Diya') to a phone number
        using the AndroidDeviceManager contacts database if connected.
        """
        if not AndroidDeviceManager:
            return None
        try:
            mgr = AndroidDeviceManager.get_instance()
            contacts = mgr.search_contacts(target)
            if contacts:
                return contacts[0]
        except Exception as e:
            print(f"[PhoneLink Warning] Contact resolution failed for '{target}': {e}")
        return None

    @classmethod
    def open_app(cls) -> Dict[str, Any]:
        """
        Launches or brings Microsoft Phone Link to the foreground on Windows desktop.
        """
        success = False
        method_used = "unknown"

        # Try os.startfile with shell:AppsFolder
        if hasattr(os, "startfile"):
            try:
                os.startfile(f"shell:AppsFolder\\{cls.PHONE_LINK_APP_ID}")
                success = True
                method_used = "os.startfile(AppsFolder)"
            except Exception:
                try:
                    os.startfile(cls.MS_PHONE_PROTOCOL)
                    success = True
                    method_used = "os.startfile(ms-phone)"
                except Exception:
                    pass

        # Fallback to subprocess explorer / cmd
        if not success:
            try:
                cmd = f'explorer.exe "shell:AppsFolder\\{cls.PHONE_LINK_APP_ID}"'
                subprocess.Popen(cmd, shell=True)
                success = True
                method_used = "subprocess(explorer)"
            except Exception as e:
                return {
                    "success": False,
                    "action": "open_phone_link",
                    "app": "Microsoft Phone Link",
                    "error": str(e)
                }

        return {
            "success": True,
            "action": "open_phone_link",
            "app": "Microsoft Phone Link",
            "app_id": cls.PHONE_LINK_APP_ID,
            "method": method_used,
            "message": "Microsoft Phone Link launched on Windows desktop."
        }

    @classmethod
    def close_app(cls) -> Dict[str, Any]:
        """
        Gracefully closes the Microsoft Phone Link window (simulating clicking the 'X' close button),
        removing it from the taskbar without force-killing or terminating the background process from Task Manager.
        """
        closed = False
        methods_tried = []

        # Method 1: Win32 WM_CLOSE via EnumWindows and PostMessage
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            WM_CLOSE = 0x0010

            def enum_cb(hwnd, lparam):
                nonlocal closed
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        val = buf.value.lower()
                        if "phone link" in val or "your phone" in val:
                            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                            closed = True
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
            if closed:
                methods_tried.append("Win32 PostMessage(WM_CLOSE)")
        except Exception as e:
            print(f"[PhoneLink Warning] Win32 WM_CLOSE failed: {e}")

        # Method 2: PowerShell CloseMainWindow() on PhoneExperienceHost & ApplicationFrameHost
        try:
            ps_script = (
                "$procs = Get-Process PhoneExperienceHost, ApplicationFrameHost -ErrorAction SilentlyContinue | "
                "Where-Object { $_.MainWindowTitle -like '*Phone Link*' -or $_.MainWindowTitle -like '*Your Phone*' -or $_.ProcessName -eq 'PhoneExperienceHost' }; "
                "$closed = $false; "
                "foreach ($p in $procs) { if ($p.CloseMainWindow()) { $closed = $true } }; "
                "if ($closed) { 'SUCCESS' } else { 'NONE' }"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=10
            )
            if "SUCCESS" in res.stdout:
                closed = True
                methods_tried.append("Process.CloseMainWindow()")
        except Exception as e:
            print(f"[PhoneLink Warning] PowerShell CloseMainWindow failed: {e}")

        # Method 3: Windows UI Automation WindowPattern.Close()
        if not closed:
            try:
                uia_script = (
                    "Add-Type -AssemblyName UIAutomationClient -ErrorAction SilentlyContinue; "
                    "$root = [System.Windows.Automation.AutomationElement]::RootElement; "
                    "$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, 'Phone Link'); "
                    "$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond); "
                    "if ($win) { $pattern = $win.GetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern); $pattern.Close(); 'SUCCESS' }"
                )
                res_uia = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", uia_script],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if "SUCCESS" in res_uia.stdout:
                    closed = True
                    methods_tried.append("UIAutomation WindowPattern.Close()")
            except Exception as e:
                print(f"[PhoneLink Warning] UIAutomation close failed: {e}")

        return {
            "success": True,
            "action": "close_phone_link",
            "app": "Microsoft Phone Link",
            "closed": closed,
            "methods_tried": methods_tried or ["Graceful Close Dispatch"],
            "message": "Sent graceful close request (WM_CLOSE / Close button) to Microsoft Phone Link window, removing it from taskbar without terminating background processes."
        }

    @classmethod
    def dial(cls, target: str, phone_number: Optional[str] = None) -> Dict[str, Any]:
        """
        Initiates a phone call via Microsoft Phone Link on Windows.
        Automatically resolves contact names (e.g. 'Mom', 'Diya') to their phone numbers,
        then invokes Windows 'tel:<number>' handler to dial via Phone Link through the connected device.
        """
        if not target and not phone_number:
            return {
                "success": False,
                "action": "phone_link_call",
                "error": "Missing required field: provide 'target' or 'phone_number'."
            }

        contact_name = target or ""
        resolved_number = phone_number

        # Check if target is already a phone number
        clean_target = re.sub(r"[^\d+]", "", target) if target else ""
        if not resolved_number:
            if clean_target and len(clean_target) >= 7 and (target.strip().startswith("+") or target.strip()[0].isdigit()):
                resolved_number = target.strip()
            else:
                # Target is a contact name (e.g. 'Mom', 'Diya') - resolve from contacts database
                contact_match = cls.resolve_contact_number(target)
                if contact_match:
                    resolved_number = contact_match["clean_number"]
                    contact_name = contact_match["name"]
                else:
                    resolved_number = clean_target if clean_target else target

        # Clean dial digits for the URI
        dial_digits = re.sub(r"[^\d+]", "", resolved_number) if resolved_number else resolved_number
        uri = f"{cls.TEL_PROTOCOL_PREFIX}{dial_digits}"

        print(f"[PhoneLink] Placing call to '{contact_name}' ({dial_digits}) via Microsoft Phone Link URI '{uri}'...")

        # Ensure Phone Link is active on desktop
        cls.open_app()
        time.sleep(0.3)

        # Trigger dial via Windows tel: protocol handler
        success = False
        method_used = "unknown"

        if hasattr(os, "startfile"):
            try:
                os.startfile(uri)
                success = True
                method_used = "os.startfile"
            except Exception as e:
                print(f"[PhoneLink Warning] os.startfile('{uri}') failed: {e}")

        if not success:
            try:
                # Use Windows shell start
                subprocess.Popen(f'cmd.exe /c start "" "{uri}"', shell=True)
                success = True
                method_used = "cmd_start"
            except Exception:
                try:
                    subprocess.Popen(["explorer.exe", uri], shell=False)
                    success = True
                    method_used = "explorer_uri"
                except Exception as e:
                    return {
                        "success": False,
                        "action": "phone_link_call",
                        "app": "Microsoft Phone Link",
                        "target": target,
                        "contact": contact_name,
                        "phone_number": dial_digits,
                        "error": f"Failed to invoke tel protocol handler: {e}"
                    }

        return {
            "success": True,
            "action": "phone_link_call",
            "app": "Microsoft Phone Link",
            "target": target,
            "contact": contact_name,
            "phone_number": dial_digits,
            "protocol_uri": uri,
            "method": method_used,
            "message": f"Successfully initiated call to {contact_name or dial_digits} ({dial_digits}) through Microsoft Phone Link on Windows."
        }

    @classmethod
    def send_sms(cls, target: str, message: str, phone_number: Optional[str] = None) -> Dict[str, Any]:
        """
        Opens SMS thread or composes a message in Microsoft Phone Link on Windows.
        """
        contact_name = target or ""
        resolved_number = phone_number

        clean_target = re.sub(r"[^\d+]", "", target) if target else ""
        if not resolved_number:
            if clean_target and len(clean_target) >= 7 and (target.strip().startswith("+") or target.strip()[0].isdigit()):
                resolved_number = target.strip()
            else:
                contact_match = cls.resolve_contact_number(target)
                if contact_match:
                    resolved_number = contact_match["clean_number"]
                    contact_name = contact_match["name"]
                else:
                    resolved_number = clean_target if clean_target else target

        dial_digits = re.sub(r"[^\d+]", "", resolved_number) if resolved_number else resolved_number
        uri = f"sms:{dial_digits}?body={message}"

        cls.open_app()
        time.sleep(0.3)

        success = False
        if hasattr(os, "startfile"):
            try:
                os.startfile(uri)
                success = True
            except Exception:
                pass

        if not success:
            try:
                subprocess.Popen(f'cmd.exe /c start "" "{uri}"', shell=True)
                success = True
            except Exception as e:
                return {
                    "success": False,
                    "action": "phone_link_sms",
                    "error": str(e)
                }

        return {
            "success": True,
            "action": "phone_link_sms",
            "app": "Microsoft Phone Link",
            "target": target,
            "contact": contact_name,
            "phone_number": dial_digits,
            "message": message
        }
