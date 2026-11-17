import asyncio
from langchain_community.chat_models import ChatOllama
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from kaalu_orchestrator.prompts import KAALU_SYSTEM_PROMPT
from kaalu_orchestrator.tools import dispatch_to_faulkner, dispatch_to_david, ws_client

async def run_kaalu_orchestrator(goal: str):
    """Initializes the local Ollama reasoning engine and runs the autonomous agent loop."""
    # 1. Ensure WebSocket connection to RGS Hub is open
    await ws_client.connect_server()

    # 2. Initialize local model via Ollama (ensure Ollama is running locally)
    llm = ChatOllama(model="qwen2.5", temperature=0)

    # 3. Register tools available to Kaalu
    tools = [dispatch_to_faulkner, dispatch_to_david]

    # 4. Build chat prompt structure with system instructions and workspace memory
    prompt = ChatPromptTemplate.from_messages([
        ("system", KAALU_SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    # 5. Create tool-calling agent and executor
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    print(f"\n[Kaalu Brain] Initialized goal execution: '{goal}'")
    
    try:
        # Run the agent execution loop asynchronously
        response = await agent_executor.ainvoke({"input": goal})
        print(f"\n[Kaalu Brain] Goal execution finished.\nResult: {response['output']}")
    except Exception as e:
        print(f"\n[Kaalu Error] Execution failed: {e}")

if __name__ == "__main__":
    # Example execution entry point
    test_goal = "Check local directory contents via system terminal and open dashboard in browser."
    asyncio.run(run_kaalu_orchestrator(test_goal))