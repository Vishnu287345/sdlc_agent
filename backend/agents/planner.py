from agent_runtime import run_agent
from prompts import render_prompt
from tools import get_tools_for_role


async def planner_agent(state):
    result = await run_agent(
        role="planner",
        system_prompt=render_prompt("planner_system.txt"),
        user_prompt=render_prompt("planner_user.txt", prd=state["prd"]),
        state=state,
        tools=get_tools_for_role("planner"),
        next_role="architect",
    )
    return {
        **state,
        "plan": result["content"],
        "tool_history": state.get("tool_history", []) + result["tool_history"],
    }
