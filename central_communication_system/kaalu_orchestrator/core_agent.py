import asyncio
import json
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

from kaalu_orchestrator.prompts import KAALU_SYSTEM_PROMPT
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
        job_tracker: Optional[Any] = None
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

        # 2. Build conversation context including system prompt and prior chat history
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": KAALU_SYSTEM_PROMPT}
        ]

        # Inject verified User Profile if available
        if self.profile_manager:
            user_profile = self.profile_manager.load_profile()
            if user_profile:
                profile_context = user_profile.to_prompt_context()
                messages.append({
                    "role": "system",
                    "content": (
                        f"Current Verified User Information:\n{profile_context}\n\n"
                        "CRITICAL: Use this profile data to personalize all searches, job filtering, "
                        "career guidance, education/upskilling advice, and form filling actions."
                    )
                })

        # Inject Tracked Job Applications & Resumes if available
        if self.job_tracker:
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

                elif recipient not in ("faulkner", "david"):
                    print(f"[Kaalu Error] Unknown agent recipient: '{recipient}'")
                    observation = {
                        "success": False,
                        "error": f"Unknown recipient agent '{recipient}'. Allowed agents are 'faulkner', 'david', and 'job_tracker'."
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

                # Update conversation history with the action and observation for next reasoning turn
                messages.append({"role": "assistant", "content": llm_response})
                messages.append({
                    "role": "user",
                    "content": (
                        f"Observation from '{recipient}' for action '{task_action}':\n"
                        f"{json.dumps(observation, indent=2)}\n\n"
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
