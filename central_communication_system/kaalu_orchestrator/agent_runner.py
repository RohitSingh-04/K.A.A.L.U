import asyncio
import os
import sys
from kaalu_orchestrator.core_agent import KaaluOrchestrator

if __name__ == "__main__":
    orchestrator = KaaluOrchestrator()
    print("[Kaalu Orchestrator] Starting User-Facing Agent...")
    try:
        # Check if GUI mode was requested via flag or GUI_KAALU.bat environment variable
        is_gui_mode = ("--gui" in sys.argv or "-g" in sys.argv or os.environ.get("KAALU_GUI_MODE") == "1")

        if is_gui_mode:
            print("[Kaalu Orchestrator] GUI Mode active: Listening for Voice & GUI Terminal objectives.")
            asyncio.run(orchestrator.run_gui_listener())
        elif len(sys.argv) > 1:
            goal = " ".join(sys.argv[1:])
            asyncio.run(orchestrator.process_user_goal(goal))
        else:
            asyncio.run(orchestrator.run_interactive())
    except KeyboardInterrupt:
        print("\n[Kaalu Orchestrator] Shutting down gracefully.")
    finally:
        try:
            asyncio.run(orchestrator.close())
        except Exception:
            pass
