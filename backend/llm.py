from groq import AsyncGroq

from config import GROQ_API_KEY, MODEL, TOOL_MAX_COMPLETION_TOKENS, TOOL_MODEL


client = AsyncGroq(api_key=GROQ_API_KEY)


async def create_chat_completion(
    *,
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str | None = None,
):
    payload = {
        "model": model or (TOOL_MODEL if tools else MODEL),
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
        payload["temperature"] = 0.2
        payload["max_completion_tokens"] = TOOL_MAX_COMPLETION_TOKENS

    return await client.chat.completions.create(**payload)


async def call_llm(prompt: str, system_prompt: str | None = None) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    response = await create_chat_completion(messages=messages)
    return response.choices[0].message.content
