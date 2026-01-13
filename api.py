# api.py
import os
from fastapi import FastAPI
from pydantic import BaseModel

from plugins.task_store import TaskStore

DATA_DIR = os.environ.get("AETHER_DATA_DIR", "/tmp/aether")
TASK_DB = os.path.join(DATA_DIR, "tasks.db")
store = TaskStore(TASK_DB)

app = FastAPI(title="AETHER API")

class EnqueueReq(BaseModel):
    task_type: str
    payload: dict
    priority: int = 20
    timeout_s: int = 30
    max_attempts: int = 3

@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/status")
def status():
    return {"ok": True, "recent": store.list_recent(10)}

@app.post("/api/enqueue")
def enqueue(req: EnqueueReq):
    import uuid
    from datetime import datetime, timezone
    tid = f"task-{uuid.uuid4().hex}"
    run_after = datetime.now(timezone.utc).isoformat()
    store.enqueue(
        tid,
        req.task_type,
        req.payload,
        priority=req.priority,
        max_attempts=req.max_attempts,
        timeout_s=req.timeout_s,
        run_after=run_after,
    )
    return {"ok": True, "task_id": tid}

@app.get("/api/task/{task_id}")
def get_task(task_id: str):
    return {"ok": True, "task": store.get_task(task_id)}
