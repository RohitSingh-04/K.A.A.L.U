import subprocess

class TerminalExecutor:
    @staticmethod
    def run_command(command: str) -> dict:
        """
        Executes a shell command locally and returns stdout, stderr, and exit status.
        """
        print(f"[Faulkner Terminal] Executing command: {command}")
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": "Command execution timed out after 60 seconds.",
                "success": False
            }
        except Exception as e:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False
            }