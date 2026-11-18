from faulkner_system.terminal_executor import TerminalExecutor

def test_faulkner_terminal_executor():
    """Directly test Faulkner's terminal execution logic without WebSocket overhead."""
    result = TerminalExecutor.run_command("echo 'Faulkner Unit Test'")
    
    assert result["success"] is True
    assert result["exit_code"] == 0
    assert "Faulkner Unit Test" in result["stdout"]