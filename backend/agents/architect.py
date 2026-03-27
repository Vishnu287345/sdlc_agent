from agent_runtime import run_agent
from prompts import render_prompt
from tools import get_tools_for_role


async def architect_agent(state):
    result = await run_agent(
        role="architect",
        system_prompt=render_prompt("architect_system.txt"),
        user_prompt=render_prompt("architect_user.txt", plan=state["plan"]),
        state=state,
        tools=get_tools_for_role("architect"),
        next_role="coder",
    )
    return {
        **state,
        "architecture": result["content"],
        "tool_history": state.get("tool_history", []) + result["tool_history"],
    }
