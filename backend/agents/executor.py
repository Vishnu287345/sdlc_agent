import os
import subprocess
import sys
import tempfile

from agent_runtime import emit_event


MAX_RETRIES = 3


async def execution_agent(state):
    tmp_path = None
    await emit_event(state, {"event": "agent_started", "agent": "executor"})
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(state["code"])
            tmp_path = f.name

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            next_role = "debugger" if state.get("retries", 0) < MAX_RETRIES else "pipeline_end"
            await emit_event(state, {"event": "agent_completed", "agent": "executor"})
            await emit_event(
                state,
                {"event": "handoff", "from_agent": "executor", "to_agent": next_role},
            )
            return {
                **state,
                "errors": state.get("errors", []) + [result.stderr],
            }

        await emit_event(state, {"event": "agent_completed", "agent": "executor"})
        await emit_event(
            state,
            {"event": "handoff", "from_agent": "executor", "to_agent": "evaluator"},
        )
        return {**state, "execution_result": result.stdout, "errors": []}

    except subprocess.TimeoutExpired:
        next_role = "debugger" if state.get("retries", 0) < MAX_RETRIES else "pipeline_end"
        await emit_event(state, {"event": "agent_completed", "agent": "executor"})
        await emit_event(
            state,
            {"event": "handoff", "from_agent": "executor", "to_agent": next_role},
        )
        return {
            **state,
            "errors": state.get("errors", []) + ["Execution timed out after 30 seconds."],
        }
    except Exception as e:
        next_role = "debugger" if state.get("retries", 0) < MAX_RETRIES else "pipeline_end"
        await emit_event(state, {"event": "agent_completed", "agent": "executor"})
        await emit_event(
            state,
            {"event": "handoff", "from_agent": "executor", "to_agent": next_role},
        )
        return {
            **state,
            "errors": state.get("errors", []) + [str(e)],
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
