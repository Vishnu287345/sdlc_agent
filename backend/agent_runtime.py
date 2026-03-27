import inspect
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from llm import create_chat_completion


ToolHandler = Callable[..., Any] | Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class LocalTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _preview(value: Any, limit: int = 240) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=True)
    return text if len(text) <= limit else f"{text[:limit]}..."


def _is_request_too_large(error: Exception) -> bool:
    text = str(error)
    return (
        "Request too large" in text
        or "rate_limit_exceeded" in text
        or "tokens per minute" in text
    )


async def emit_event(state: dict[str, Any], payload: dict[str, Any]) -> None:
    callback = state.get("_event_sink")
    if callback is None:
        return
    result = callback(payload)
    if inspect.isawaitable(result):
        await result


async def _invoke_tool(tool: LocalTool, arguments: dict[str, Any], state: dict[str, Any]) -> Any:
    result = tool.handler(state=state, **arguments)
    if inspect.isawaitable(result):
        return await result
    return result


async def run_agent(
    *,
    role: str,
    system_prompt: str,
    user_prompt: str,
    state: dict[str, Any],
    tools: list[LocalTool] | None = None,
    next_role: str | None = None,
    max_turns: int = 4,
) -> dict[str, Any]:
    available_tools = tools or []
    use_tools = bool(available_tools)
    tool_map = {tool.name: tool for tool in available_tools}
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    tool_history: list[dict[str, Any]] = []

    await emit_event(
        state,
        {
            "event": "agent_started",
            "agent": role,
        },
    )

    for _ in range(max_turns):
        try:
            response = await create_chat_completion(
                messages=messages,
                tools=[tool.schema for tool in available_tools] if use_tools else None,
            )
        except Exception as error:
            if use_tools and _is_request_too_large(error):
                use_tools = False
                await emit_event(
                    state,
                    {
                        "event": "tool_mode_fallback",
                        "agent": role,
                        "reason": "request_too_large",
                    },
                )
                response = await create_chat_completion(messages=messages, tools=None)
            else:
                raise

        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []

        if not use_tools or not tool_calls:
            await emit_event(
                state,
                {
                    "event": "agent_completed",
                    "agent": role,
                },
            )
            if next_role:
                await emit_event(
                    state,
                    {
                        "event": "handoff",
                        "from_agent": role,
                        "to_agent": next_role,
                    },
                )
            return {
                "content": message.content or "",
                "tool_history": tool_history,
            }

        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in tool_calls
                ],
            }
        )

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            if tool_name not in tool_map:
                raise ValueError(f"Unknown tool requested by {role}: {tool_name}")

            raw_arguments = tool_call.function.arguments or "{}"
            arguments = json.loads(raw_arguments)
            await emit_event(
                state,
                {
                    "event": "tool_called",
                    "agent": role,
                    "tool": tool_name,
                },
            )
            result = await _invoke_tool(tool_map[tool_name], arguments, state)
            tool_history.append(
                {
                    "agent": role,
                    "tool": tool_name,
                    "arguments": arguments,
                    "result_preview": _preview(result),
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": _preview(result, limit=800),
                }
            )
            await emit_event(
                state,
                {
                    "event": "tool_result",
                    "agent": role,
                    "tool": tool_name,
                    "result_preview": _preview(result, limit=120),
                },
            )

    raise RuntimeError(f"{role} exceeded the maximum tool-calling turns ({max_turns})")
