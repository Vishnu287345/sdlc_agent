import os
import subprocess
import sys
import tempfile
from typing import Any

from agent_runtime import LocalTool
from memory import load_state


def _get_pipeline_context(*, state: dict[str, Any], section: str | None = None, include_empty: bool = False) -> dict[str, Any]:
    allowed = {
        "task_id": state.get("task_id"),
        "prd": state.get("prd"),
        "plan": state.get("plan"),
        "architecture": state.get("architecture"),
        "code": state.get("code"),
        "execution_result": state.get("execution_result"),
        "evaluation": state.get("evaluation"),
        "errors": state.get("errors", []),
        "retries": state.get("retries", 0),
    }
    if section:
        if section not in allowed:
            return {"error": f"Unknown section '{section}'", "available_sections": sorted(allowed)}
        return {section: allowed.get(section)}

    if include_empty:
        return allowed
    return {key: value for key, value in allowed.items() if value not in ("", [], None)}


def _load_saved_task(*, state: dict[str, Any], task_id: str) -> dict[str, Any]:
    saved = load_state(task_id)
    if saved is None:
        return {"error": f"Task '{task_id}' not found"}
    return {
        "task_id": saved.get("task_id"),
        "prd": saved.get("prd"),
        "plan": saved.get("plan"),
        "architecture": saved.get("architecture"),
        "evaluation": saved.get("evaluation"),
        "errors": saved.get("errors", []),
    }


def _run_python_snippet(*, state: dict[str, Any], code: str, timeout_seconds: int = 10) -> dict[str, Any]:
    tmp_path = None
    effective_timeout = min(max(timeout_seconds, 1), 20)
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as handle:
            handle.write(code)
            tmp_path = handle.name

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=effective_timeout,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout[:4000],
            "stderr": result.stderr[:4000],
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Execution timed out after {effective_timeout} seconds.",
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def get_tools_for_role(role: str) -> list[LocalTool]:
    shared_tools = [
        LocalTool(
            name="get_pipeline_context",
            description=(
                "Read the current pipeline state, including the requirement, prior agent outputs, "
                "execution results, retry count, and errors. Use this before making assumptions."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "description": "Optional specific state section to fetch, such as prd, plan, architecture, code, execution_result, evaluation, errors, or retries.",
                    },
                    "include_empty": {
                        "type": "boolean",
                        "description": "Set true to include empty fields in the response.",
                    },
                },
            },
            handler=_get_pipeline_context,
        ),
        LocalTool(
            name="load_saved_task",
            description=(
                "Load a previously saved task from Redis by task_id. Use this only when prior task output would help compare or reuse earlier work."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task identifier to load from persisted memory.",
                    },
                },
                "required": ["task_id"],
            },
            handler=_load_saved_task,
        ),
    ]

    if role in {"coder", "debugger"}:
        return shared_tools + [
            LocalTool(
                name="run_python_snippet",
                description=(
                    "Execute a short Python snippet locally to validate syntax, logic, or a fix before returning final code. "
                    "Use this for quick checks, not for long-running programs."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The Python snippet to execute.",
                        },
                        "timeout_seconds": {
                            "type": "integer",
                            "description": "Optional timeout in seconds between 1 and 20.",
                        },
                    },
                    "required": ["code"],
                },
                handler=_run_python_snippet,
            )
        ]

    return shared_tools
