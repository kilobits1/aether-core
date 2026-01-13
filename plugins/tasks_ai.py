# plugins/tasks_ai.py
import os
import re
import uuid
import threading
import time
from datetime import datetime, timezone

from plugins.task_store import TaskStore
from plugins.adapters import Adapters
from plugins.task_runner import TaskRunner

# -----------------------------
# Base config
# -----------------------------
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

def _wait_task_done(task_id: str, max_wait_s: int = 4):
    """
    Espera breve para devolver resultado sin que el usuario use task show.
    """
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

# -----------------------------
# Parsing helpers
# -----------------------------
def _strip_quotes(s: str) -> str:
    s = (s or "").strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s

def _extract_path_and_text(original: str):
    """
    Soporta:
      crea un archivo test/a.txt con hola
      crea un archivo "test/a b.txt" con "hola mundo"
    """
    t = (original or "").strip()

    # buscar "archivo <path> con <text>"
    m = re.search(r"archivo\s+(.+?)\s+(con|texto)\s+(.+)$", t, flags=re.IGNORECASE)
    if not m:
        return None, None
    path = _strip_quotes(m.group(1).strip())
    content = m.group(3)
    # si el contenido viene entre comillas, se respeta
    content = _strip_quotes(content.strip())
    return path, content

# --------- NLP simple (reglas) ---------
def _nlp_to_task(text: str):
    t = (text or "").strip()
    tl = t.lower()

    # crear archivo (varias formas)
    if any(k in tl for k in ["crea", "crear", "escribe", "guardar"]) and "archivo" in tl and (" con " in tl or " texto " in tl):
        path, content = _extract_path_and_text(t)
        if path:
            return ("files.write_text", {"path": path, "text": content or ""})

    # leer archivo: "lee <path>" / "leer archivo <path>"
    m = re.search(r"^(lee|leer)\s+(archivo\s+)?(.+)$", t, flags=re.IGNORECASE)
    if m:
        path = _strip_quotes(m.group(3).strip())
        return ("files.read_text", {"path": path, "max_bytes": 200000})

    # listar: "lista archivos" / "listar <path>" / "lista carpeta <path>"
    if any(k in tl for k in ["lista", "listar", "muestra"]):
        # intenta encontrar un path al final
        parts = t.split()
        # si solo dice "lista" o "lista archivos" -> root
        if len(parts) <= 2:
            return ("files.list_dir", {"path": ""})
        # path al final (puede venir entre comillas)
        path = _strip_quotes(parts[-1])
        # si el último token es "archivos" o "carpeta" o "directorio", usar root
        if path.lower() in ("archivos", "carpeta", "directorio"):
            path = ""
        return ("files.list_dir", {"path": path})

    # ejecutar python: "ejecuta python <codigo>" o "python: <codigo>"
    if tl.startswith("ejecuta python "):
        code = t[len("ejecuta python "):].strip()
        return ("shell.exec", {"cmd": ["python", "-c", code]})
    if tl.startswith("python:"):
        code = t.split(":", 1)[1].strip()
        return ("shell.exec", {"cmd": ["python", "-c", code]})

    return (None, None)

# -----------------------------
# Router hooks
# -----------------------------
def can_handle(command: str) -> bool:
    c = (command or "").strip().lower()
    if c.startswith("task "):
        return True
    # lenguaje natural (keywords)
    return any(k in c for k in [
        "crea", "crear", "escribe", "guardar",
        "lee", "leer",
        "lista", "listar", "muestra",
        "ejecuta python", "python:"
    ])

# -----------------------------
# Main
# -----------------------------
def run(command: str):
    _ensure_runner()
    c = (command or "").strip()
    cl = c.lower().strip()

    # =========================
    # Comandos clásicos (rápidos)
    # =========================
    if cl == "task a":
        tid = _enqueue("files.write_text", {"path": "test/hello.txt", "text": "AETHER v26 OK (real)\n"}, priority=10)
        done = _wait_task_done(tid, 4)
        return {"ok": True, "msg": "Encolada TASK A", "task_id": tid, "done": done}

    if cl == "task b":
        tid = _enqueue("files.list_dir", {"path": ""}, priority=20)
        done = _wait_task_done(tid, 4)
        return {"ok": True, "msg": "Encolada TASK B", "task_id": tid, "done": done}

    if cl == "task c":
        tid = _enqueue("shell.exec", {"cmd": ["python", "-c", "print('runner ok')"]}, priority=5)
        done = _wait_task_done(tid, 4)
        return {"ok": True, "msg": "Encolada TASK C", "task_id": tid, "done": done}

    if cl in ("task last", "task recent"):
        return {"ok": True, "recent": _store.list_recent(10)}

    if cl.startswith("task show "):
        tid = c.split(" ", 2)[2].strip()
        return {"ok": True, "task": _store.get_task(tid)}

    # nuevos comandos útiles
    if cl.startswith("task read "):
        path = _strip_quotes(c.split(" ", 2)[2].strip())
        tid = _enqueue("files.read_text", {"path": path, "max_bytes": 200000}, priority=12)
        done = _wait_task_done(tid, 4)
        return {"ok": True, "msg": f"Leyendo {path}", "task_id": tid, "done": done}

    if cl.startswith("task list"):
        # task list o task list <path>
        parts = c.split(" ", 2)
        path = ""
        if len(parts) == 3:
            path = _strip_quotes(parts[2].strip())
        tid = _enqueue("files.list_dir", {"path": path}, priority=15)
        done = _wait_task_done(tid, 4)
        return {"ok": True, "msg": f"Listando {path or '/'}", "task_id": tid, "done": done}

    # =========================
    # Lenguaje natural
    # =========================
    task_type, payload = _nlp_to_task(c)
    if task_type:
        tid = _enqueue(task_type, payload, priority=15)
        done = _wait_task_done(tid, 4)
        return {
            "ok": True,
            "msg": f"Encolada (NL): {task_type}",
            "task_id": tid,
            "payload": payload,
            "done": done
        }

    return {
        "ok": False,
        "error": "No entendí el comando",
        "help": [
            "task a | task b | task c | task last | task show <id>",
            "task read <path> | task list [path]",
            "crea un archivo <path> con <texto>",
            "lee <path>",
            "lista archivos [path]",
            "ejecuta python <code> | python: <code>",
        ],
    }
