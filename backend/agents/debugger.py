from agent_runtime import run_agent
from prompts import render_prompt
from tools import get_tools_for_role


async def debug_agent(state):
    all_errors = "\n---\n".join(state.get("errors", []))
    result = await run_agent(
        role="debugger",
        system_prompt=render_prompt("debugger_system.txt"),
        user_prompt=render_prompt(
            "debugger_user.txt",
            code=state["code"],
            errors=all_errors,
        ),
        state=state,
        tools=get_tools_for_role("debugger"),
        next_role="executor",
    )
    return {
        **state,
        "code": result["content"],
        "retries": state["retries"] + 1,
        "tool_history": state.get("tool_history", []) + result["tool_history"],
    }
