# --- v26 TASKS INTEGRATION ---
import uuid
import threading

from task_store import TaskStore
from adapters import Adapters
from task_runner import TaskRunner

TASK_DB = os.path.join(DATA_DIR, "tasks.db")
WORK_DIR = os.path.join(DATA_DIR, "workspace")
AUDIT_FILE = os.path.join(DATA_DIR, "audit.log")

store = TaskStore(TASK_DB)

adapters = Adapters(
    base_dir=WORK_DIR,
    allowed_shell_cmds=["python", "pip"],          # ajusta si quieres "node", "npm"
    allowed_http_domains=[],                      # vacío => http bloqueado (seguro por defecto)
)

runner = TaskRunner(store, adapters, poll_interval_s=0.5)

_runner_thread = None
def start_task_runner():
    global _runner_thread
    if _runner_thread and _runner_thread.is_alive():
        return
    _runner_thread = threading.Thread(target=runner.start_loop, daemon=True)
    _runner_thread.start()

start_task_runner()

def enqueue_task(task_type: str, payload: dict, priority: int = 50, max_attempts: int = 3, timeout_s: int = 60):
    task_id = f"task-{uuid.uuid4().hex}"
    store.enqueue(task_id, task_type, payload, priority=priority, max_attempts=max_attempts, timeout_s=timeout_s)
    return task_id
# =========================
# v26 TASKS (Runner + Queue)
# =========================
import os
import uuid
import threading

from plugins.task_store import TaskStore
from plugins.adapters import Adapters
from plugins.task_runner import TaskRunner

# Asegura DATA_DIR (HF-safe)
DATA_DIR = os.environ.get("AETHER_DATA_DIR", "/tmp/aether")
os.makedirs(DATA_DIR, exist_ok=True)

TASK_DB = os.path.join(DATA_DIR, "tasks.db")
WORK_DIR = os.path.join(DATA_DIR, "workspace")

store = TaskStore(TASK_DB)

adapters = Adapters(
    base_dir=WORK_DIR,
    allowed_shell_cmds=["python", "pip"],  # si quieres node/npm lo agregas luego
    allowed_http_domains=[],              # vacío = http bloqueado por seguridad
)

runner = TaskRunner(store, adapters, poll_interval_s=0.5)

_runner_thread = None

def start_task_runner():
    global _runner_thread
    if _runner_thread and _runner_thread.is_alive():
        return
    _runner_thread = threading.Thread(target=runner.start_loop, daemon=True)
    _runner_thread.start()

start_task_runner()

def enqueue_task(task_type: str, payload: dict, priority: int = 50, max_attempts: int = 3, timeout_s: int = 60):
    task_id = f"task-{uuid.uuid4().hex}"
    store.enqueue(task_id, task_type, payload, priority=priority, max_attempts=max_attempts, timeout_s=timeout_s)
    return task_id
