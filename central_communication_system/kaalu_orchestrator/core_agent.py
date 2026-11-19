import asyncio
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional
try:
    from voice_system.tts import Speaker
except (ImportError, ValueError):
    try:
        from ..voice_system.tts import Speaker
    except (ImportError, ValueError):
        try:
            from central_communication_system.voice_system.tts import Speaker
        except (ImportError, ValueError):
            Speaker = None

try:
    from user_profile.profile_manager import ProfileManager
except (ImportError, ValueError):
    try:
        from ..user_profile.profile_manager import ProfileManager
    except (ImportError, ValueError):
        try:
            from central_communication_system.user_profile.profile_manager import ProfileManager
        except (ImportError, ValueError):
            ProfileManager = None

try:
    from job_tracker.manager import JobTrackerManager
except (ImportError, ValueError):
    try:
        from ..job_tracker.manager import JobTrackerManager
    except (ImportError, ValueError):
        try:
            from central_communication_system.job_tracker.manager import JobTrackerManager
        except (ImportError, ValueError):
            JobTrackerManager = None

try:
    from android_controller.manager import AndroidDeviceManager
except (ImportError, ValueError):
    try:
        from ..android_controller.manager import AndroidDeviceManager
    except (ImportError, ValueError):
        try:
            from central_communication_system.android_controller.manager import AndroidDeviceManager
        except (ImportError, ValueError):
            AndroidDeviceManager = None

from kaalu_orchestrator.prompts import KAALU_SYSTEM_PROMPT, get_kaalu_system_prompt
from kaalu_orchestrator.ws_client import KaaluWSClient
from kaalu_orchestrator.rgs_llm_client import RGSLLMClient

class KaaluOrchestrator:
    """
    Main user-facing orchestrator agent for Project Kaalu.
    Coordinates multi-step objectives by consulting the RGS Central LLM Gateway
    and delegating concrete actions to Faulkner (system/terminal) and David (browser).
    Maintains cross-turn conversation memory for multi-goal contextual continuity.
    """
    def __init__(
        self,
        ws_uri: str = "ws://localhost:8000/ws/kaalu",
        gateway_url: str = "http://localhost:8000/llm/generate",
        max_steps: int = 15,
        max_history_turns: int = 10,
        profile_manager: Optional[Any] = None,
        job_tracker: Optional[Any] = None,
        android_manager: Optional[Any] = None
    ):
        self.llm_client = RGSLLMClient(gateway_url=gateway_url)
        self.ws_client = KaaluWSClient(uri=ws_uri)
        self.max_steps = max_steps
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history_turns = max_history_turns
        if profile_manager is not None:
            self.profile_manager = profile_manager
        elif ProfileManager is not None:
            self.profile_manager = ProfileManager.get_instance()
        else:
            self.profile_manager = None

        if job_tracker is not None:
            self.job_tracker = job_tracker
        elif JobTrackerManager is not None:
            self.job_tracker = JobTrackerManager.get_instance()
        else:
            self.job_tracker = None

        if android_manager is not None:
            self.android_mgr = android_manager
        elif AndroidDeviceManager is not None:
            self.android_mgr = AndroidDeviceManager.get_instance()
        else:
            self.android_mgr = None

    def save_downloaded_resume(
        self,
        company: str,
        position: str,
        source_path: Optional[str] = None,
        move: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Saves a downloaded resume file to date-structured storage (data/resumes/YYYY-MM-DD/),
        and automatically synchronizes the user profile's resume_path.
        """
        if not self.job_tracker:
            print("[Kaalu Warning] JobTrackerManager not initialized.")
            return None
        dest_path, dest_filename = self.job_tracker.save_downloaded_resume(
            company=company,
            position=position,
            source_path=source_path,
            move=move
        )
        return {
            "status": "success",
            "resume_path": str(dest_path),
            "resume_filename": dest_filename,
            "date_folder": dest_path.parent.name
        }

    def record_applied_job(
        self,
        company: str,
        position: str,
        job_description: Optional[str] = None,
        job_url: Optional[str] = None,
        location: Optional[str] = None,
        resume_path: Optional[str] = None,
        resume_snapshot: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Records a job application record and saves its snapshot to central storage."""
        if not self.job_tracker:
            print("[Kaalu Warning] JobTrackerManager not initialized.")
            return None
        rec = self.job_tracker.record_job_application(
            company=company,
            position=position,
            job_description=job_description,
            job_url=job_url,
            location=location,
            resume_path=resume_path,
            resume_snapshot=resume_snapshot,
            status="applied",
            notes=notes
        )
        return rec.model_dump()

    def mark_job_applied(
        self,
        identifier: str,
        job_url: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Marks an existing tracked job application as applied."""
        if not self.job_tracker:
            print("[Kaalu Warning] JobTrackerManager not initialized.")
            return None
        rec = self.job_tracker.mark_as_applied(
            identifier=identifier,
            job_url=job_url,
            notes=notes
        )
        return rec.model_dump() if rec else None

    def android_devices(self) -> List[Dict[str, Any]]:
        """Returns details of all connected Android devices (e.g. OnePlus Phone)."""
        if not self.android_mgr:
            return []
        return self.android_mgr.list_devices_details()

    def android_screenshot(self, serial: Optional[str] = None, save: bool = True) -> Dict[str, Any]:
        """Captures a screenshot from the connected OnePlus phone or Android device."""
        if not self.android_mgr:
            return {"success": False, "error": "AndroidDeviceManager not initialized."}
        return self.android_mgr.capture_screenshot(serial=serial, save=save)

    def android_inspect(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Inspects the active screen UI hierarchy, returning visible texts and interactive elements."""
        if not self.android_mgr:
            return {"success": False, "error": "AndroidDeviceManager not initialized."}
        return self.android_mgr.inspect_screen(serial=serial)

    def android_tap(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        target: Optional[str] = None,
        serial: Optional[str] = None
    ) -> Dict[str, Any]:
        """Performs a touch tap at screen coordinate (x, y) OR by locating target text/button label."""
        if not self.android_mgr:
            return {"success": False, "error": "AndroidDeviceManager not initialized."}
        return self.android_mgr.tap(x=x, y=y, target=target, serial=serial)

    def android_type(
        self,
        text: str,
        target: Optional[str] = None,
        clear: bool = False,
        press_enter: bool = False,
        serial: Optional[str] = None
    ) -> Dict[str, Any]:
        """Types text into the active input field or focuses target input field first."""
        if not self.android_mgr:
            return {"success": False, "error": "AndroidDeviceManager not initialized."}
        return self.android_mgr.type_text(
            text=text,
            target=target,
            clear=clear,
            press_enter=press_enter,
            serial=serial
        )

    def android_swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300, serial: Optional[str] = None) -> Dict[str, Any]:
        """Performs a swipe or scroll gesture from (x1, y1) to (x2, y2)."""
        if not self.android_mgr:
            return {"success": False, "error": "AndroidDeviceManager not initialized."}
        return self.android_mgr.swipe(x1=x1, y1=y1, x2=x2, y2=y2, duration_ms=duration_ms, serial=serial)

    def android_key(self, key: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Presses an Android key (HOME, BACK, ENTER, APP_SWITCH, etc.)."""
        if not self.android_mgr:
            return {"success": False, "error": "AndroidDeviceManager not initialized."}
        return self.android_mgr.press_key(key=key, serial=serial)

    def android_open_app(self, package: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Launches an app package on the Android device."""
        if not self.android_mgr:
            return {"success": False, "error": "AndroidDeviceManager not initialized."}
        return self.android_mgr.open_app(package=package, serial=serial)

    def android_shell(self, command: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Executes an arbitrary ADB shell command on the Android device."""
        if not self.android_mgr:
            return {"success": False, "error": "AndroidDeviceManager not initialized."}
        return self.android_mgr.shell(command=command, serial=serial)

    def android_send_whatsapp(
        self,
        contact: str,
        message: str = "",
        emoji: Optional[str] = None,
        serial: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sends a WhatsApp message or emoji in a single high-speed macro action."""
        if not self.android_mgr:
            return {"success": False, "error": "AndroidDeviceManager not initialized."}
        return self.android_mgr.send_whatsapp(contact=contact, message=message, emoji=emoji, serial=serial)

    def android_call(self, target: str, app: str = "phone", serial: Optional[str] = None) -> Dict[str, Any]:
        """Places a phone call or WhatsApp voice call in a single high-speed action."""
        if not self.android_mgr:
            return {"success": False, "error": "AndroidDeviceManager not initialized."}
        return self.android_mgr.call_phone(target=target, app=app, serial=serial)

    def android_tap_emoji(self, emoji: str = "laugh", serial: Optional[str] = None) -> Dict[str, Any]:
        """Taps an emoji directly via Gboard's universal emoji palette."""
        if not self.android_mgr:
            return {"success": False, "error": "AndroidDeviceManager not initialized."}
        return self.android_mgr.tap_emoji(emoji=emoji, serial=serial)

    def android_gboard_emoji(self, emoji: str = "laugh", target: Optional[str] = None, serial: Optional[str] = None) -> Dict[str, Any]:
        """Universally types an emoji using Gboard across any Android app."""
        if not self.android_mgr:
            return {"success": False, "error": "AndroidDeviceManager not initialized."}
        return self.android_mgr.type_gboard_emoji(emoji=emoji, target=target, serial=serial)

    def android_set_auto_rotate(self, enabled: bool = False, serial: Optional[str] = None) -> Dict[str, Any]:
        """Locks screen orientation in portrait or enables auto-rotate."""
        if not self.android_mgr:
            return {"success": False, "error": "AndroidDeviceManager not initialized."}
        return self.android_mgr.set_auto_rotate(enabled=enabled, serial=serial)

    def android_rotation_status(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Queries current screen auto-rotation setting."""
        if not self.android_mgr:
            return {"success": False, "error": "AndroidDeviceManager not initialized."}
        return self.android_mgr.get_auto_rotate_status(serial=serial)

    def _detect_active_model(self) -> str:
        """Determines the current cloud LLM model configured in the RGS Gateway settings."""
        settings_path = Path(__file__).resolve().parent.parent / "rgs_hub" / "settings.yaml"
        if settings_path.exists():
            try:
                import yaml
                with open(settings_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                    model = cfg.get("llm", {}).get("default_model")
                    if model:
                        return str(model)
            except Exception:
                pass
        return "gemini-3.1-flash-lite"

    def reset_session(self):
        """Clear multi-turn session history."""
        self.conversation_history.clear()
        print("[Kaalu] Session memory cleared.")

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """
        Robustly extracts and parses a JSON object from raw LLM output,
        handling markdown fences and surrounding conversational prose.
        """
        if not text:
            return None

        clean_text = text.strip()

        # 1. Check for markdown code fences (```json ... ``` or ``` ... ```)
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_text, re.IGNORECASE)
        if fence_match:
            candidate = fence_match.group(1).strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        # 2. Try direct json.loads
        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
            pass

        # 3. Locate outer-most curly braces { ... }
        start_idx = clean_text.find("{")
        end_idx = clean_text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidate = clean_text[start_idx:end_idx + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        return None

    async def process_user_goal(self, goal: str) -> Dict[str, Any]:
        """
        Processes a high-level user goal using the RGS Central Intelligence
        and agent delegation ReAct loop (Think -> Act -> Observe).
        Maintains awareness of previous goals, directory listings, and file locations.
        """
        print(f"\n[Kaalu] Initiating User Objective: '{goal}'")

        # 1. Ensure WebSocket connection to RGS Hub is established
        await self.ws_client.connect_server()

        # 2. Build conversation context with active cloud model injected into the system prompt
        active_model = self._detect_active_model()
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": get_kaalu_system_prompt(active_model)}
        ]

        # Determine task type to dynamically optimize context and prevent TPM limit exhaustion
        mobile_keywords = (
            "phone", "mobile", "whatsapp", "call", "sms", "tap", "swipe",
            "screen", "oneplus", "android", "device", "dial", "emoji"
        )
        is_mobile_task = any(kw in goal.lower() for kw in mobile_keywords)

        # Inject verified User Profile if available
        if self.profile_manager:
            user_profile = self.profile_manager.load_profile()
            if user_profile:
                if is_mobile_task:
                    # For mobile operations, inject only minimal user info to conserve tokens
                    b_details = getattr(user_profile, "basic_details", None)
                    u_name = getattr(b_details, "name", "") if b_details else getattr(user_profile, "name", "User")
                    u_phone = getattr(b_details, "phone", "") if b_details else getattr(user_profile, "phone", "")
                    u_email = getattr(b_details, "email", "") if b_details else getattr(user_profile, "email", "")
                    profile_context = (
                        f"User Name: {u_name}\n"
                        f"Contact Phone: {u_phone}\n"
                        f"Contact Email: {u_email}"
                    )
                else:
                    profile_context = user_profile.to_prompt_context()
                messages.append({
                    "role": "system",
                    "content": (
                        f"Current Verified User Information:\n{profile_context}\n\n"
                        "CRITICAL: Use this profile data to personalize all searches, job filtering, "
                        "career guidance, education/upskilling advice, and form filling actions."
                    )
                })

        # Inject Tracked Job Applications & Resumes only if not a mobile task or if job-related
        job_keywords = ("job", "resume", "apply", "application", "interview", "career", "tracker", "position")
        needs_job_context = any(kw in goal.lower() for kw in job_keywords)

        if self.job_tracker and (needs_job_context or not is_mobile_task):
            apps_context = self.job_tracker.to_prompt_context()
            if apps_context:
                messages.append({
                    "role": "system",
                    "content": (
                        f"Current Verified Tracked Job Applications & Resumes:\n{apps_context}\n\n"
                        "CRITICAL: When the user asks about applied jobs, application status, history, "
                        "companies applied to, which resume was used, or follow-up interview prep, "
                        "use this verified tracking data to give direct, detailed, and accurate responses."
                    )
                })

        # Inject Connected Hardware & Mobile Devices (OnePlus Phone) if available
        if self.android_mgr:
            try:
                android_devices = self.android_mgr.list_devices_details()
                if android_devices:
                    lines = ["[CONNECTED HARDWARE / ANDROID DEVICES (ONEPLUS PHONE)]"]
                    for d in android_devices:
                        lines.append(
                            f"- Device: {d.get('market_name', 'Android Phone')} | "
                            f"Model: {d.get('model')} ({d.get('brand', 'Android')}) | "
                            f"Serial: {d.get('serial')} | "
                            f"Display: {d.get('resolution', '1080x2400')} | "
                            f"Battery: {d.get('battery_level', 'unknown')}% | "
                            f"OS: Android {d.get('android_version', 'unknown')} | "
                            f"Active App: {d.get('current_package', 'None')} | "
                            f"Transport: {d.get('transport', 'Wireless TLS')}"
                        )
                    android_context = "\n".join(lines)
                    messages.append({
                        "role": "system",
                        "content": (
                            f"{android_context}\n\n"
                            "CRITICAL: When the user asks to see, interact with, take screenshot of, tap, type, swipe, "
                            "open an app, or control their mobile phone (OnePlus Phone), delegate to the 'android' agent."
                        )
                    })
            except Exception as adb_err:
                print(f"[Kaalu Warning] Could not query Android devices: {adb_err}")

        # Inject previous conversation turns so Kaalu remembers discovered files, folders, and outputs
        for prev_turn in self.conversation_history:
            messages.append(prev_turn)

        # Append current user objective
        messages.append({
            "role": "user",
            "content": (
                f"User Objective: {goal}\n\n"
                "Analyze this objective, plan the sequence of actions, and take the first step. "
                "CRITICAL: Use context, files, paths, and information from previous turns if relevant. "
                "Respond with a single valid JSON object following the specified protocol."
            )
        })

        steps_taken = 0

        # 3. Autonomous Execution Loop
        while steps_taken < self.max_steps:
            steps_taken += 1
            print(f"\n[Kaalu Step {steps_taken}/{self.max_steps}] Requesting reasoning from RGS Central LLM...")

            try:
                llm_response = await self.llm_client.generate_async(messages=messages)
            except Exception as llm_err:
                print(f"[Kaalu Error] LLM generation failed: {llm_err}")
                return {
                    "status": "error",
                    "error": f"LLM Gateway communication failed: {str(llm_err)}",
                    "steps_taken": steps_taken,
                    "final_answer": "Failed to communicate with RGS Central LLM Gateway."
                }

            print(f"[Kaalu Reasoning Output]:\n{llm_response}\n")

            # Parse the structured decision
            decision = self._extract_json(llm_response)

            if not decision:
                print("[Kaalu Warning] Could not parse valid JSON from LLM response. Requesting correction...")
                messages.append({"role": "assistant", "content": llm_response})
                messages.append({
                    "role": "user",
                    "content": (
                        "Your previous response was not a valid JSON object. "
                        "Please provide your decision strictly in JSON format as specified: "
                        "{\"thought\": \"...\", \"action\": \"delegate\" | \"finish\", ...}"
                    )
                })
                continue

            action_type = decision.get("action")
            thought = decision.get("thought", "")

            # A. Goal Completion
            if action_type == "finish":
                final_answer = decision.get("final_answer", "Objective accomplished.")
                voice_response = decision.get("voice_response") or final_answer
                print(f"[Kaalu Finish] Objective successfully achieved:\n{final_answer}")
                if decision.get("voice_response"):
                    print(f"[Kaalu Voice Response]: {voice_response}")

                # Persist this turn in conversation history for future turns
                self.conversation_history.append({"role": "user", "content": goal})
                self.conversation_history.append({"role": "assistant", "content": final_answer})

                # Maintain history within bounded size
                max_msgs = self.max_history_turns * 2
                if len(self.conversation_history) > max_msgs:
                    self.conversation_history = self.conversation_history[-max_msgs:]

                return {
                    "status": "completed",
                    "thought": thought,
                    "final_answer": final_answer,
                    "voice_response": voice_response,
                    "steps_taken": steps_taken
                }

            # B. Sub-Agent Task Delegation
            elif action_type == "delegate":
                recipient = decision.get("recipient")
                task_action = decision.get("task_action")
                payload = decision.get("payload", {})

                # If delegating fill_form to David without fields specified, autofill from profile
                if recipient == "david" and task_action == "fill_form" and not payload.get("fields") and self.profile_manager:
                    prof = self.profile_manager.load_profile()
                    if prof:
                        payload["fields"] = prof.get_form_fill_map()

                if recipient == "job_tracker":
                    if not self.job_tracker:
                        observation = {"success": False, "error": "JobTrackerManager is not available."}
                    else:
                        try:
                            if task_action == "record_application":
                                rec = self.job_tracker.record_job_application(
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
                                observation = {"success": True, "application": rec.model_dump()}
                            elif task_action == "mark_applied":
                                rec = self.job_tracker.mark_as_applied(
                                    identifier=payload.get("identifier") or payload.get("application_id") or payload.get("company", ""),
                                    job_url=payload.get("job_url"),
                                    notes=payload.get("notes")
                                )
                                observation = {"success": bool(rec), "application": rec.model_dump() if rec else None}
                            elif task_action == "save_resume":
                                dest_path, dest_fn = self.job_tracker.save_downloaded_resume(
                                    company=payload.get("company", ""),
                                    position=payload.get("position", ""),
                                    source_path=payload.get("source_path"),
                                    move=payload.get("move", False)
                                )
                                observation = {"success": True, "resume_path": str(dest_path), "resume_filename": dest_fn}
                            elif task_action == "list_applications":
                                apps = self.job_tracker.list_applications(
                                    status=payload.get("status"),
                                    company=payload.get("company")
                                )
                                observation = {"success": True, "count": len(apps), "applications": [a.model_dump() for a in apps]}
                            else:
                                observation = {"success": False, "error": f"Unknown job_tracker action: '{task_action}'"}
                        except Exception as jt_err:
                            observation = {"success": False, "error": str(jt_err)}

                elif recipient == "android":
                    if not self.android_mgr:
                        observation = {"success": False, "error": "AndroidDeviceManager is not available."}
                    else:
                        try:
                            serial = payload.get("serial") or payload.get("device_serial")
                            if task_action in ("capture_screenshot", "screenshot"):
                                save_img = payload.get("save", True)
                                res = self.android_mgr.capture_screenshot(serial=serial, save=save_img, include_ui=True)
                                obs = dict(res)
                                if "screenshot_base64" in obs:
                                    b64_val = obs.pop("screenshot_base64")
                                    obs["screenshot_base64_length"] = len(b64_val)
                                    obs["has_screenshot"] = True
                                observation = obs
                            elif task_action in ("inspect_screen", "get_ui_elements", "get_elements", "dump_hierarchy"):
                                observation = self.android_mgr.inspect_screen(serial=serial)
                            elif task_action in ("tap", "click"):
                                observation = self.android_mgr.tap(
                                    x=int(payload.get("x")) if payload.get("x") is not None else None,
                                    y=int(payload.get("y")) if payload.get("y") is not None else None,
                                    target=payload.get("target") or payload.get("text") or payload.get("label"),
                                    serial=serial
                                )
                            elif task_action in ("type", "type_text", "input_text"):
                                observation = self.android_mgr.type_text(
                                    text=str(payload.get("text", "")),
                                    target=payload.get("target"),
                                    clear=bool(payload.get("clear", False)),
                                    press_enter=bool(payload.get("press_enter", False)),
                                    serial=serial
                                )
                            elif task_action in ("swipe", "scroll"):
                                observation = self.android_mgr.swipe(
                                    x1=int(payload.get("x1", 0)),
                                    y1=int(payload.get("y1", 0)),
                                    x2=int(payload.get("x2", 0)),
                                    y2=int(payload.get("y2", 0)),
                                    duration_ms=int(payload.get("duration_ms", 300)),
                                    serial=serial
                                )
                            elif task_action in ("press_key", "key", "keyevent"):
                                observation = self.android_mgr.press_key(
                                    key=payload.get("key", "HOME"),
                                    serial=serial
                                )
                            elif task_action in ("open_app", "launch_app"):
                                observation = self.android_mgr.open_app(
                                    package=payload.get("package") or payload.get("package_name", ""),
                                    serial=serial
                                )
                            elif task_action in ("execute_shell", "shell"):
                                observation = self.android_mgr.shell(
                                    command=str(payload.get("command", "")),
                                    serial=serial
                                )
                            elif task_action in ("send_whatsapp", "whatsapp_send", "whatsapp_message"):
                                observation = self.android_mgr.send_whatsapp(
                                    contact=str(payload.get("contact") or payload.get("target") or payload.get("to", "")),
                                    message=str(payload.get("message") or payload.get("text", "")),
                                    emoji=payload.get("emoji"),
                                    auto_send=bool(payload.get("auto_send", payload.get("send", True))),
                                    serial=serial
                                )
                            elif task_action in ("call_phone", "call", "make_call", "voice_call"):
                                observation = self.android_mgr.call_phone(
                                    target=str(payload.get("target") or payload.get("contact") or payload.get("number") or payload.get("phone", "")),
                                    app=str(payload.get("app", "phone")),
                                    serial=serial
                                )
                            elif task_action in ("tap_emoji", "emoji", "gboard_emoji", "type_gboard_emoji"):
                                observation = self.android_mgr.type_gboard_emoji(
                                    emoji=str(payload.get("emoji") or payload.get("type", "laugh")),
                                    target=payload.get("target"),
                                    serial=serial
                                )
                            elif task_action in ("set_auto_rotate", "auto_rotate", "lock_rotation"):
                                observation = self.android_mgr.set_auto_rotate(
                                    enabled=bool(payload.get("enabled", False)),
                                    serial=serial
                                )
                            elif task_action in ("get_rotation_status", "rotation_status"):
                                observation = self.android_mgr.get_auto_rotate_status(serial=serial)
                            elif task_action in ("get_device_info", "list_devices", "status"):
                                devs = self.android_mgr.list_devices_details()
                                observation = {"success": True, "count": len(devs), "devices": devs}
                            else:
                                observation = {"success": False, "error": f"Unknown android action: '{task_action}'"}
                        except Exception as android_err:
                            observation = {"success": False, "error": str(android_err)}

                elif recipient not in ("faulkner", "david"):
                    print(f"[Kaalu Error] Unknown agent recipient: '{recipient}'")
                    observation = {
                        "success": False,
                        "error": f"Unknown recipient agent '{recipient}'. Allowed agents are 'faulkner', 'david', 'job_tracker', and 'android'."
                    }
                else:
                    print(f"[Kaalu] Delegating task to '{recipient}' -> action: '{task_action}'...")
                    try:
                        await self.ws_client.send_task(
                            recipient=recipient,
                            action=task_action,
                            payload=payload
                        )

                        print(f"[Kaalu] Awaiting response from '{recipient}'...")
                        observation = await self.ws_client.receive_response(timeout=60.0)
                    except Exception as comm_err:
                        print(f"[Kaalu Error] Communication with '{recipient}' failed: {comm_err}")
                        observation = {
                            "success": False,
                            "error": f"Failed to communicate with agent '{recipient}': {str(comm_err)}"
                        }

                print(f"[Kaalu] Observation from '{recipient}': {observation}")

                # Compact observation data before injecting into LLM context to prevent TPM rate limits
                obs_for_llm = dict(observation) if isinstance(observation, dict) else {"result": observation}
                obs_for_llm.pop("screenshot_base64", None)

                # Cap visible_texts to max 15 items
                if "visible_texts" in obs_for_llm and isinstance(obs_for_llm["visible_texts"], list):
                    obs_for_llm["visible_texts"] = [t for t in obs_for_llm["visible_texts"] if str(t).strip()][:15]

                # Cap and simplify interactive_elements to max 10 labeled items
                if "interactive_elements" in obs_for_llm and isinstance(obs_for_llm["interactive_elements"], list):
                    compact_elems = []
                    for el in obs_for_llm["interactive_elements"][:10]:
                        item = {"center": el.get("center")}
                        if el.get("label"):
                            item["label"] = el.get("label")
                        elif el.get("text"):
                            item["text"] = el.get("text")
                        if el.get("type"):
                            item["type"] = el.get("type")
                        compact_elems.append(item)
                    obs_for_llm["interactive_elements"] = compact_elems

                # Compress intermediate turns if context is growing large (>10 messages)
                if len(messages) > 10:
                    for midx in range(3, len(messages) - 2):
                        m = messages[midx]
                        if m.get("role") == "user" and len(m.get("content", "")) > 250:
                            first_line = m["content"].split("\n")[0]
                            messages[midx] = {
                                "role": "user",
                                "content": f"{first_line} -> (completed successfully)"
                            }

                # Update conversation history with the action and observation for next reasoning turn
                messages.append({"role": "assistant", "content": llm_response})
                messages.append({
                    "role": "user",
                    "content": (
                        f"Observation from '{recipient}' for action '{task_action}':\n"
                        f"{json.dumps(obs_for_llm, indent=2)}\n\n"
                        "Evaluate this observation. If the objective is complete, respond with action 'finish'. "
                        "Otherwise, take the next delegated action. Output JSON only."
                    )
                })

            else:
                print(f"[Kaalu Warning] Unknown action type '{action_type}'. Requesting valid action...")
                messages.append({"role": "assistant", "content": llm_response})
                messages.append({
                    "role": "user",
                    "content": (
                        f"The action '{action_type}' is invalid. The 'action' field must be either "
                        "'delegate' or 'finish'. Please provide a valid JSON decision."
                    )
                })

        # Max steps exceeded
        print(f"[Kaalu Warning] Maximum step count ({self.max_steps}) reached.")
        return {
            "status": "max_steps_exceeded",
            "final_answer": f"Task stopped: reached maximum allowed reasoning steps ({self.max_steps}).",
            "steps_taken": steps_taken
        }

    async def run_interactive(self):
        """Interactive REPL mode for continuous user interaction with Kaalu."""
        print("=" * 60)
        print("          KAALU MASTER ORCHESTRATOR ACTIVE")
        print("  Type your task/objective, or type 'exit' / 'quit' to stop.")
        print("  Type 'clear' to reset chat memory, or 'history' to view.")
        print("=" * 60)

        while True:
            try:
                user_input = input("\nKaalu> ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit"):
                    print("\n[Kaalu] Shutting down orchestrator session. Goodbye.")
                    break
                if user_input.lower() in ("clear", "reset"):
                    self.reset_session()
                    continue
                if user_input.lower() in ("history", "context"):
                    if not self.conversation_history:
                        print("[Kaalu] No previous session history.")
                    else:
                        print("\n=== Session History ===")
                        for i, msg in enumerate(self.conversation_history, 1):
                            role = "User" if msg["role"] == "user" else "Kaalu"
                            preview = msg["content"][:100].replace("\n", " ")
                            print(f"{i}. [{role}]: {preview}...")
                        print("=" * 23)
                    continue

                result = await self.process_user_goal(user_input)
                final_answer_text = result.get('final_answer', str(result)) if isinstance(result, dict) else str(result)
                voice_text = result.get('voice_response') if isinstance(result, dict) else None
                if not voice_text:
                    voice_text = final_answer_text

                print("\n" + "=" * 40)
                if Speaker is not None:
                    try:
                        Speaker.speak(f"Sir, {voice_text}")
                    except Exception as tts_err:
                        print(f"[Voice Warning] TTS playback failed: {tts_err}")
                print(f"[Kaalu Final Result]:\n{final_answer_text}")
                print("=" * 40)

            except (KeyboardInterrupt, EOFError):
                print("\n[Kaalu] Session aborted by user.")
                break
            except Exception as e:
                print(f"\n[Kaalu Error encountered]: {e}")

    async def close(self):
        """Clean up WebSocket client connection."""
        await self.ws_client.close()

if __name__ == "__main__":
    orchestrator = KaaluOrchestrator()
    try:
        if len(sys.argv) > 1:
            sample_goal = " ".join(sys.argv[1:])
            asyncio.run(orchestrator.process_user_goal(sample_goal))
        else:
            asyncio.run(orchestrator.run_interactive())
    finally:
        asyncio.run(orchestrator.close())
