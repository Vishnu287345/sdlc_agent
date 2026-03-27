from agent_runtime import run_agent
from prompts import render_prompt
from tools import get_tools_for_role


async def coder_agent(state):
    result = await run_agent(
        role="coder",
        system_prompt=render_prompt("coder_system.txt"),
        user_prompt=render_prompt("coder_user.txt", architecture=state["architecture"]),
        state=state,
        tools=get_tools_for_role("coder"),
        next_role="executor",
    )
    return {
        **state,
        "code": result["content"],
        "tool_history": state.get("tool_history", []) + result["tool_history"],
    }
