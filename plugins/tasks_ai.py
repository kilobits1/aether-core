# plugins/tasks_ai.py
import os
import uuid
import threading
from datetime import datetime, timezone

from plugins.task_store import TaskStore
from plugins.adapters import Adapters
from plugins.task_runner import TaskRunner

def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()

DATA_DIR = os.environ.get("AETHER_DATA_DIR", "/tmp/aether")
os.makedirs(DATA_DIR, exist_ok=True)

TASK_DB = os.path.join(DATA_DIR, "tasks.db")
WORK_DIR = os.path.join(DATA_DIR, "workspace")
os.makedirs(WORK_DIR, exist_ok=True)

_store = TaskStore(TASK_DB)
_adapters = Adapters(
    base_dir=WORK_DIR,
    allowed_shell_cmds=["python", "pip"],
    allowed_http_domains=[],
)
_runner = TaskRunner(_store, _adapters, poll_interval_s=0.5)
_runner_thread = None
_runner_lock = threading.Lock()

def _ensure_runner():
    global _runner_thread
    with _runner_lock:
        if _runner_thread and _runner_thread.is_alive():
            return
        _runner_thread = threading.Thread(target=_runner.start_loop, daemon=True)
        _runner_thread.start()

def can_handle(command: str) -> bool:
    c = (command or "").lower().strip()
    return c.startswith("task ")

def run(command: str):
    """
    Comandos:
      task a        -> crea /tmp/aether/workspace/test/hello.txt
      task b        -> lista /tmp/aether/workspace
      task c        -> ejecuta python -c "print('runner ok')"
      task last     -> lista tareas recientes
      task show <id>
    """
    _ensure_runner()
    c = (command or "").strip()
    cl = c.lower().strip()

    # task a: write file
    if cl == "task a":
        tid = f"task-{uuid.uuid4().hex}"
        _store.enqueue(
            tid,
            "files.write_text",
            {"path": "test/hello.txt", "text": "AETHER v26 OK (real)\n"},
            priority=10,
            max_attempts=3,
            timeout_s=30,
            run_after=_utc_now_iso(),
        )
        return {"ok": True, "msg": f"Encolada TASK A real", "task_id": tid, "file": "workspace/test/hello.txt"}

    # task b: list dir
    if cl == "task b":
        tid = f"task-{uuid.uuid4().hex}"
        _store.enqueue(
            tid,
            "files.list_dir",
            {"path": ""},
            priority=20,
            max_attempts=3,
            timeout_s=30,
            run_after=_utc_now_iso(),
        )
        return {"ok": True, "msg": "Encolada TASK B real", "task_id": tid}

    # task c: shell exec
    if cl == "task c":
        tid = f"task-{uuid.uuid4().hex}"
        _store.enqueue(
            tid,
            "shell.exec",
            {"cmd": ["python", "-c", "print('runner ok')"]},
            priority=5,
            max_attempts=2,
            timeout_s=30,
            run_after=_utc_now_iso(),
        )
        return {"ok": True, "msg": "Encolada TASK C real", "task_id": tid}

    if cl in ("task last", "task recent"):
        return {"ok": True, "recent": _store.list_recent(10)}

    if cl.startswith("task show "):
        tid = c.split(" ", 2)[2].strip()
        return {"ok": True, "task": _store.get_task(tid)}

    return {
        "ok": False,
        "error": "Comando no reconocido",
        "help": ["task a", "task b", "task c", "task last", "task show <id>"],
    }
