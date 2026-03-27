from typing import Any, Dict, List, TypedDict


class SDLCState(TypedDict):
    task_id: str
    prd: str
    plan: str
    architecture: str
    code: str
    execution_result: str
    evaluation: str
    errors: List[str]
    retries: int
    logs: List[Dict[str, Any]]
    tool_history: List[Dict[str, Any]]
