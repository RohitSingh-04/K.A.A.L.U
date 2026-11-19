import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from kaalu_orchestrator.prompts import KAALU_SYSTEM_PROMPT
from kaalu_orchestrator.core_agent import KaaluOrchestrator
from kaalu_orchestrator.rgs_llm_client import RGSLLMClient, RGSLMClient
from kaalu_orchestrator.ws_client import KaaluWSClient

def test_kaalu_prompt_definitions():
    """Verify that KAALU_SYSTEM_PROMPT includes required agent capabilities and protocols."""
    assert "faulkner" in KAALU_SYSTEM_PROMPT
    assert "david" in KAALU_SYSTEM_PROMPT
    assert "execute_terminal" in KAALU_SYSTEM_PROMPT
    assert "capture_screen" in KAALU_SYSTEM_PROMPT
    assert "scrape" in KAALU_SYSTEM_PROMPT
    assert "delegate" in KAALU_SYSTEM_PROMPT
    assert "finish" in KAALU_SYSTEM_PROMPT

def test_kaalu_extract_json():
    """Verify robust JSON extraction from pure JSON, markdown blocks, and surrounding prose."""
    # 1. Pure JSON
    pure = '{"thought": "test", "action": "finish", "final_answer": "Done"}'
    parsed_pure = KaaluOrchestrator._extract_json(pure)
    assert parsed_pure is not None
    assert parsed_pure["action"] == "finish"

    # 2. Markdown fenced JSON
    fenced = """Here is my plan:
```json
{
  "thought": "Delegate check",
  "action": "delegate",
  "recipient": "faulkner",
  "task_action": "execute_terminal",
  "payload": {"command": "dir"}
}
```
Let me know the result."""
    parsed_fenced = KaaluOrchestrator._extract_json(fenced)
    assert parsed_fenced is not None
    assert parsed_fenced["action"] == "delegate"
    assert parsed_fenced["recipient"] == "faulkner"
    assert parsed_fenced["payload"]["command"] == "dir"

    # 3. Invalid text returns None
    invalid = "I will check the directory now."
    assert KaaluOrchestrator._extract_json(invalid) is None

def test_kaalu_rgs_llm_client_sync():
    """Test synchronous generation method of RGSLLMClient."""
    client = RGSLLMClient(gateway_url="http://test-gateway/llm/generate")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"response": "Mocked sync response"}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.Client.post", return_value=mock_resp):
        res = client.generate(prompt="Hello")
        assert res == "Mocked sync response"

@pytest.mark.asyncio
async def test_kaalu_rgs_llm_client_async():
    """Test asynchronous generation method of RGSLLMClient."""
    client = RGSLLMClient(gateway_url="http://test-gateway/llm/generate")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"response": "Mocked async response"}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        res = await client.generate_async(messages=[{"role": "user", "content": "Hi"}])
        assert res == "Mocked async response"

@pytest.mark.asyncio
async def test_kaalu_full_orchestration_loop():
    """Test complete multi-step reasoning loop: Step 1 (delegate) -> Step 2 (finish)."""
    orchestrator = KaaluOrchestrator(max_steps=5)

    # Mock the WebSocket client
    orchestrator.ws_client.connect_server = AsyncMock(return_value=True)
    orchestrator.ws_client.send_task = AsyncMock()
    orchestrator.ws_client.receive_response = AsyncMock(return_value={
        "sender": "faulkner",
        "action": "execute_terminal_result",
        "payload": {"exit_code": 0, "stdout": "All systems operational", "success": True}
    })

    # Step 1: LLM decides to delegate to Faulkner
    step_1_llm = json.dumps({
        "thought": "I should run a status check via terminal.",
        "action": "delegate",
        "recipient": "faulkner",
        "task_action": "execute_terminal",
        "payload": {"command": "systeminfo"}
    })

    # Step 2: LLM evaluates observation and concludes with final answer
    step_2_llm = json.dumps({
        "thought": "All checks passed based on Faulkner's output.",
        "action": "finish",
        "final_answer": "System verified. Status: All systems operational."
    })

    # Mock LLM calls in sequence
    orchestrator.llm_client.generate_async = AsyncMock(side_effect=[step_1_llm, step_2_llm])

    # Run the user goal
    result = await orchestrator.process_user_goal("Check system operational status")

    # Assertions
    assert result["status"] == "completed"
    assert "All systems operational" in result["final_answer"]
    assert result["steps_taken"] == 2
    orchestrator.ws_client.send_task.assert_awaited_once_with(
        recipient="faulkner",
        action="execute_terminal",
        payload={"command": "systeminfo"}
    )

@pytest.mark.asyncio
async def test_kaalu_delegates_to_david_browser():
    """Test Kaalu delegating a web scraping action to David browser agent."""
    orchestrator = KaaluOrchestrator(max_steps=3)

    orchestrator.ws_client.connect_server = AsyncMock(return_value=True)
    orchestrator.ws_client.send_task = AsyncMock()
    orchestrator.ws_client.receive_response = AsyncMock(return_value={
        "sender": "david",
        "action": "scrape_result",
        "payload": {"content": "<html><body>Dashboard Loaded</body></html>"}
    })

    step_1 = json.dumps({
        "thought": "Need to scrape the dashboard using David.",
        "action": "delegate",
        "recipient": "david",
        "task_action": "scrape",
        "payload": {"selector": "body"}
    })
    step_2 = json.dumps({
        "thought": "Dashboard content acquired successfully.",
        "action": "finish",
        "final_answer": "Dashboard loaded with valid HTML."
    })

    orchestrator.llm_client.generate_async = AsyncMock(side_effect=[step_1, step_2])

    result = await orchestrator.process_user_goal("Scrape the active web dashboard")

    assert result["status"] == "completed"
    assert "Dashboard loaded" in result["final_answer"]
    orchestrator.ws_client.send_task.assert_awaited_once_with(
        recipient="david",
        action="scrape",
        payload={"selector": "body"}
    )

@pytest.mark.asyncio
async def test_kaalu_max_steps_exceeded():
    """Verify Kaalu safely terminates when the maximum reasoning limit is reached."""
    orchestrator = KaaluOrchestrator(max_steps=2)

    orchestrator.ws_client.connect_server = AsyncMock(return_value=True)
    orchestrator.ws_client.send_task = AsyncMock()
    orchestrator.ws_client.receive_response = AsyncMock(return_value={"status": "ok"})

    # Always return a delegate action to trigger max_steps limit
    never_ending = json.dumps({
        "thought": "Keep going",
        "action": "delegate",
        "recipient": "faulkner",
        "task_action": "execute_terminal",
        "payload": {"command": "echo loop"}
    })
    orchestrator.llm_client.generate_async = AsyncMock(return_value=never_ending)

    result = await orchestrator.process_user_goal("Run endless tasks")
    assert result["status"] == "max_steps_exceeded"
    assert result["steps_taken"] == 2

@pytest.mark.asyncio
async def test_kaalu_multi_turn_history():
    """Verify that Kaalu retains previous chat context across consecutive goals."""
    orchestrator = KaaluOrchestrator(max_steps=3)
    orchestrator.ws_client.connect_server = AsyncMock(return_value=True)

    # Goal 1: Check pictures folder
    g1_finish = json.dumps({
        "thought": "Found pictures",
        "action": "finish",
        "final_answer": "Pictures folder contains sign.jpg at C:\\OneDrive\\Pictures"
    })
    orchestrator.llm_client.generate_async = AsyncMock(return_value=g1_finish)
    res1 = await orchestrator.process_user_goal("list files in Pictures")
    assert res1["status"] == "completed"

    # Verify history has both user prompt and assistant reply
    assert len(orchestrator.conversation_history) == 2
    assert orchestrator.conversation_history[0]["content"] == "list files in Pictures"
    assert "sign.jpg" in orchestrator.conversation_history[1]["content"]

    # Goal 2: Open sign.jpg
    g2_finish = json.dumps({
        "thought": "Using path from previous turn",
        "action": "finish",
        "final_answer": "Opened sign.jpg from C:\\OneDrive\\Pictures"
    })
    orchestrator.llm_client.generate_async = AsyncMock(return_value=g2_finish)
    res2 = await orchestrator.process_user_goal("open sign.jpg")
    assert res2["status"] == "completed"

    # Verify history was forwarded to LLM on the second call
    call_args = orchestrator.llm_client.generate_async.call_args[1]
    messages_passed = call_args["messages"]
    
    # Must include system prompt, turn 1 user, turn 1 assistant, and turn 2 user
    assert len(messages_passed) >= 4
    assert any("sign.jpg at C:\\OneDrive\\Pictures" in m["content"] for m in messages_passed)

    # Test reset
    orchestrator.reset_session()
    assert len(orchestrator.conversation_history) == 0

@pytest.mark.asyncio
async def test_kaalu_dual_voice_and_text_response():
    """Verify that Kaalu extracts both rich final_answer and voice_response from finish payload."""
    orchestrator = KaaluOrchestrator(max_steps=2)
    orchestrator.ws_client.connect_server = AsyncMock(return_value=True)

    finish_payload = json.dumps({
        "thought": "All files listed",
        "action": "finish",
        "final_answer": "Desktop contains:\n- file1.pdf\n- file2.docx\n- file3.jpg",
        "voice_response": "I found three files on your Desktop."
    })
    orchestrator.llm_client.generate_async = AsyncMock(return_value=finish_payload)

    result = await orchestrator.process_user_goal("list files")
    assert result["status"] == "completed"
    assert "file1.pdf" in result["final_answer"]
    assert result["voice_response"] == "I found three files on your Desktop."


def test_kaalu_identity_and_creator_prompt_definitions():
    """Verify that Kaalu system prompt includes creator Rohit, purpose, and active model."""
    from kaalu_orchestrator.prompts import get_kaalu_system_prompt

    prompt = get_kaalu_system_prompt("gemini-2.5-pro")
    assert "KAALU" in prompt
    assert "Master named Rohit" in prompt
    assert "System AI Automation for Fun" in prompt
    assert "gemini-2.5-pro" in prompt


@pytest.mark.asyncio
async def test_kaalu_identity_inquiry_goal():
    """Verify Kaalu responds to 'who are you?' acknowledging creator Rohit and active cloud model."""
    orchestrator = KaaluOrchestrator(max_steps=2)
    orchestrator.ws_client.connect_server = AsyncMock(return_value=True)

    captured_messages = []

    async def mock_generate(messages):
        captured_messages.extend(messages)
        return json.dumps({
            "thought": "The user is asking about my identity. I will explain that I am KAALU, created by Master Rohit for System AI Automation for Fun, currently powered by gemini-3.1-flash-lite.",
            "action": "finish",
            "final_answer": "I am KAALU, an autonomous system orchestrator created by my Master Rohit for System AI Automation for Fun! I am currently powered by the gemini-3.1-flash-lite cloud model to be smart, plan, and execute tasks across your desktop, browser, and phone.",
            "voice_response": "I am Kaalu, created by Rohit for System AI Automation for Fun, currently powered by the Gemini cloud model."
        })

    orchestrator.llm_client.generate_async = mock_generate

    result = await orchestrator.process_user_goal("who are you and who created you?")
    assert result["status"] == "completed"
    assert "KAALU" in result["final_answer"]
    assert "Rohit" in result["final_answer"]
    assert "gemini-3.1-flash-lite" in result["final_answer"]

    # Verify system prompt given to LLM contained the creator and active model
    sys_content = captured_messages[0]["content"]
    assert "Rohit" in sys_content
    assert "System AI Automation for Fun" in sys_content
    assert "gemini-3.1-flash-lite" in sys_content


@pytest.mark.asyncio
async def test_kaalu_routes_phone_link_call_to_faulkner():
    """Verify that when user specifies calling via Phone Link, Kaalu delegates to faulkner, NOT android."""
    orchestrator = KaaluOrchestrator(max_steps=5)
    orchestrator.ws_client.connect_server = AsyncMock(return_value=True)
    orchestrator.ws_client.send_task = AsyncMock()
    orchestrator.ws_client.receive_response = AsyncMock(return_value={
        "sender": "faulkner",
        "action": "phone_link_call_result",
        "payload": {
            "success": True,
            "action": "phone_link_call",
            "app": "Microsoft Phone Link",
            "contact": "Mom",
            "phone_number": "+918477873189"
        }
    })

    # Step 1: LLM recognizes 'call her using phone link' means delegating to faulkner
    step_1 = json.dumps({
        "thought": "The user explicitly asked to call using phone link. According to my routing protocols, Microsoft Phone Link calls on Windows must be delegated to faulkner, not android. From context, 'her' refers to 'Mom'.",
        "action": "delegate",
        "recipient": "faulkner",
        "task_action": "phone_link_call",
        "payload": {"target": "Mom"}
    })

    # Step 2: LLM finishes
    step_2 = json.dumps({
        "thought": "The call has been initiated through Microsoft Phone Link via Faulkner.",
        "action": "finish",
        "final_answer": "Initiated call to Mom through Microsoft Phone Link on your Windows desktop.",
        "voice_response": "I have initiated the call to your mom using Microsoft Phone Link."
    })

    orchestrator.llm_client.generate_async = AsyncMock(side_effect=[step_1, step_2])

    result = await orchestrator.process_user_goal("call her using phone link")
    assert result["status"] == "completed"
    orchestrator.ws_client.send_task.assert_called_once_with(
        recipient="faulkner",
        action="phone_link_call",
        payload={"target": "Mom"}
    )
    assert "Microsoft Phone Link" in result["final_answer"]


@pytest.mark.asyncio
async def test_kaalu_routes_close_phone_link_to_faulkner():
    """Verify Kaalu closes Phone Link window via faulkner close_phone_link without terminating process."""
    orchestrator = KaaluOrchestrator(max_steps=5)
    orchestrator.ws_client.connect_server = AsyncMock(return_value=True)
    orchestrator.ws_client.send_task = AsyncMock()
    orchestrator.ws_client.receive_response = AsyncMock(return_value={
        "sender": "faulkner",
        "action": "close_phone_link_result",
        "payload": {
            "success": True,
            "action": "close_phone_link",
            "app": "Microsoft Phone Link",
            "closed": True,
            "message": "Closed window without terminating process."
        }
    })

    # Step 1: LLM decides to delegate close_phone_link to faulkner
    step_1 = json.dumps({
        "thought": "The user wants to close Phone Link window by pressing the close button without terminating it from Task Manager. I will delegate to faulkner with action close_phone_link.",
        "action": "delegate",
        "recipient": "faulkner",
        "task_action": "close_phone_link",
        "payload": {}
    })

    # Step 2: LLM finishes
    step_2 = json.dumps({
        "thought": "The Phone Link window has been closed and removed from taskbar.",
        "action": "finish",
        "final_answer": "I have closed the Microsoft Phone Link window and removed it from your taskbar without terminating the background process.",
        "voice_response": "I have closed the Phone Link window for you."
    })

    orchestrator.llm_client.generate_async = AsyncMock(side_effect=[step_1, step_2])

    user_goal = "close the phone link don't terminate it from the task manager just remove it from taskbar by pressing close button"
    result = await orchestrator.process_user_goal(user_goal)
    assert result["status"] == "completed"
    orchestrator.ws_client.send_task.assert_called_once_with(
        recipient="faulkner",
        action="close_phone_link",
        payload={}
    )
    assert "closed" in result["final_answer"].lower()


