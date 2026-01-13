# plugins/tasks_ai.py
import os
import re
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

def _enqueue(task_type: str, payload: dict, priority=20, timeout_s=30, max_attempts=3):
    _ensure_runner()
    tid = f"task-{uuid.uuid4().hex}"
    _store.enqueue(
        tid, task_type, payload,
        priority=int(priority),
        max_attempts=int(max_attempts),
        timeout_s=int(timeout_s),
        run_after=_utc_now_iso(),
    )
    return tid

# --------- NLP simple (reglas) ---------
def _nlp_to_task(text: str):
    t = (text or "").strip()
    tl = t.lower()

    # crear archivo: "crea un archivo <path> con <texto>"
    m = re.search(r"(crea|crear|escribe|guardar)\s+(un\s+)?archivo\s+([^\s]+)\s+(con|texto)\s+(.+)$", tl, re.IGNORECASE)
    if m:
        # ojo: path en el texto original para respetar mayúsculas
        path = t.split()[t.lower().split().index("archivo") + 1]
        # texto: todo después de " con " o " texto "
        if " con " in t.lower():
            content = t.split(" con ", 1)[1]
        elif " texto " in t.lower():
            content = t.split(" texto ", 1)[1]
        else:
            content = ""
        return ("files.write_text", {"path": path, "text": content})

    # leer archivo: "lee <path>" o "leer archivo <path>"
    m = re.search(r"^(lee|leer)\s+(archivo\s+)?(.+)$", tl, re.IGNORECASE)
    if m:
        path = t.split()[-1]
        return ("files.read_text", {"path": path, "max_bytes": 200000})

    # listar: "lista archivos" / "listar" / "muestra archivos"
    if any(k in tl for k in ["lista archivos", "listar archivos", "muestra archivos", "listar", "lista directorio", "lista carpeta"]):
        return ("files.list_dir", {"path": ""})

    # ejecutar python: "ejecuta python <codigo>" o "python: <codigo>"
    if tl.startswith("ejecuta python "):
        code = t[len("ejecuta python "):]
        return ("shell.exec", {"cmd": ["python", "-c", code]})
    if tl.startswith("python:"):
        code = t.split(":", 1)[1].strip()
        return ("shell.exec", {"cmd": ["python", "-c", code]})

    return (None, None)

def can_handle(command: str) -> bool:
    c = (command or "").strip().lower()
    if c.startswith("task "):
        return True
    # lenguaje natural (keywords)
    return any(k in c for k in ["crea", "crear", "escribe", "guardar", "lee", "leer", "lista", "listar", "muestra", "ejecuta python", "python:"])

def run(command: str):
    _ensure_runner()
    c = (command or "").strip()
    cl = c.lower().strip()

    # --- comandos clásicos ---
    if cl == "task a":
        tid = _enqueue("files.write_text", {"path": "test/hello.txt", "text": "AETHER v26 OK (real)\n"}, priority=10)
        return {"ok": True, "msg": "Encolada TASK A", "task_id": tid}

    if cl == "task b":
        tid = _enqueue("files.list_dir", {"path": ""}, priority=20)
        return {"ok": True, "msg": "Encolada TASK B", "task_id": tid}

    if cl == "task c":
        tid = _enqueue("shell.exec", {"cmd": ["python", "-c", "print('runner ok')"]}, priority=5)
        return {"ok": True, "msg": "Encolada TASK C", "task_id": tid}

    if cl in ("task last", "task recent"):
        return {"ok": True, "recent": _store.list_recent(10)}

    if cl.startswith("task show "):
        tid = c.split(" ", 2)[2].strip()
        return {"ok": True, "task": _store.get_task(tid)}

    # --- lenguaje natural ---
    task_type, payload = _nlp_to_task(c)
    if task_type:
        tid = _enqueue(task_type, payload, priority=15)
        return {"ok": True, "msg": f"Encolada (NL): {task_type}", "task_id": tid, "payload": payload}

    return {"ok": False, "error": "No entendí el comando", "help": ["task a", "task last", "crea un archivo X con Y", "lee X", "lista archivos", "ejecuta python <code>"]}
def _wait_task_done(task_id: str, max_wait_s: int = 4):
    import time
    t0 = time.time()
    while time.time() - t0 < max_wait_s:
        t = _store.get_task(task_id)
        if not t:
            time.sleep(0.2)
            continue
        if t.get("status") in ("success", "failed"):
            return t
        time.sleep(0.2)
    return None
