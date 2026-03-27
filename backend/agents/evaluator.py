from agent_runtime import run_agent
from prompts import render_prompt
from tools import get_tools_for_role


async def evaluator_agent(state):
    result = await run_agent(
        role="evaluator",
        system_prompt=render_prompt("evaluator_system.txt"),
        user_prompt=render_prompt(
            "evaluator_user.txt",
            execution_result=state["execution_result"],
            prd=state["prd"],
        ),
        state=state,
        tools=get_tools_for_role("evaluator"),
    )
    return {
        **state,
        "evaluation": result["content"],
        "tool_history": state.get("tool_history", []) + result["tool_history"],
    }
