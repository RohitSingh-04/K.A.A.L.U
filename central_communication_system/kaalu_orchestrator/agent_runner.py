import asyncio
import sys
from kaalu_orchestrator.core_agent import KaaluOrchestrator

if __name__ == "__main__":
    orchestrator = KaaluOrchestrator()
    print("[Kaalu Orchestrator] Starting User-Facing Agent...")
    try:
        if len(sys.argv) > 1:
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
