import json
import time

import redis


_client = None
_local_cache: dict[str, dict] = {}


def get_client():
    global _client
    if _client is None:
        for attempt in range(5):
            try:
                _client = redis.Redis(
                    host="redis",
                    port=6379,
                    decode_responses=True,
                    socket_connect_timeout=3,
                )
                _client.ping()
                break
            except redis.exceptions.ConnectionError:
                if attempt == 4:
                    raise RuntimeError("Could not connect to Redis after 5 attempts")
                time.sleep(1)
    return _client


def save_state(task_id: str, state: dict):
    _local_cache[task_id] = state
    try:
        get_client().set(task_id, json.dumps(state))
    except Exception as e:
        print(f"[memory] Failed to save state for {task_id}: {e}")


def load_state(task_id: str):
    try:
        data = get_client().get(task_id)
        if data:
            return json.loads(data)
    except Exception as e:
        print(f"[memory] Failed to load state for {task_id}: {e}")

    return _local_cache.get(task_id)
