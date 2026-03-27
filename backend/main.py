import logging
import os
import tempfile
import textwrap
import uuid
import zipfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import validate_config
from graph import build_graph
from memory import load_state, save_state


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_config()
    global pipeline
    pipeline = build_graph()
    logger.info("Pipeline ready.")
    yield


app = FastAPI(lifespan=lifespan)
pipeline = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

connections: list[WebSocket] = []


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    connections.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if ws in connections:
            connections.remove(ws)


async def broadcast(msg: dict):
    disconnected = []
    for conn in connections:
        try:
            await conn.send_json(msg)
        except Exception:
            disconnected.append(conn)
    for conn in disconnected:
        connections.remove(conn)


def _strip_runtime_state(state: dict):
    return {
        key: value
        for key, value in state.items()
        if not str(key).startswith("_")
    }


class RunRequest(BaseModel):
    prd: str


@app.post("/run")
async def run_task(req: RunRequest):
    task_id = str(uuid.uuid4())

    async def emit_runtime_event(payload: dict):
        await broadcast({"task_id": task_id, **payload})

    state = {
        "task_id": task_id,
        "prd": req.prd,
        "plan": "",
        "architecture": "",
        "code": "",
        "execution_result": "",
        "evaluation": "",
        "errors": [],
        "retries": 0,
        "logs": [],
        "tool_history": [],
        "_event_sink": emit_runtime_event,
    }

    await broadcast({"status": "started", "event": "task_started", "task_id": task_id})
    result = await pipeline.ainvoke(state)
    clean_result = _strip_runtime_state(result)

    save_state(clean_result.get("task_id", task_id), clean_result)

    await broadcast(
        {
            "status": "done",
            "event": "task_completed",
            "task_id": clean_result.get("task_id", task_id),
        }
    )
    return clean_result


@app.get("/task/{task_id}")
async def get_task(task_id: str):
    state = load_state(task_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return state


def _build_zip(state: dict) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()

    prd = state.get("prd", "")
    code = state.get("code", "")

    if code.startswith("```"):
        lines = code.splitlines()
        code = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()

    readme = textwrap.dedent(f"""
        # Generated Project

        ## Original Requirement
        {prd}

        ## How to Run
        ```bash
        python generated_code.py
        ```

        ## Task ID
        {state.get("task_id", "")}
    """).strip()

    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("generated_code.py", code)
        zf.writestr("plan.md", state.get("plan", ""))
        zf.writestr("architecture.md", state.get("architecture", ""))
        zf.writestr("evaluation.md", state.get("evaluation", ""))
        zf.writestr("execution_output.txt", state.get("execution_result", ""))
        zf.writestr("README.md", readme)

    return tmp.name


@app.get("/download/{task_id}")
async def download_task(task_id: str):
    state = load_state(task_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Task not found")

    zip_path = _build_zip(state)

    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in state.get("prd", "project")[:40]
    ).strip("_")
    filename = f"{safe_name}.zip"

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=filename,
        background=None,
    )
