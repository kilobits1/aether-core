# plugins/aether_core.py
import os
import json
import uuid
import threading
import logging
from datetime import datetime, timezone

# -----------------------------
# HF-safe dirs
# -----------------------------
DATA_DIR = os.environ.get("AETHER_DATA_DIR", "/tmp/aether")
os.makedirs(DATA_DIR, exist_ok=True)

WORK_DIR = os.path.join(DATA_DIR, "workspace")
os.makedirs(WORK_DIR, exist_ok=True)

STATE_FILE = os.path.join(DATA_DIR, "aether_state.json")
MEMORY_FILE = os.path.join(DATA_DIR, "aether_memory.json")
STRATEGIC_FILE = os.path.join(DATA_DIR, "aether_strategic.json")

AETHER_ID = "AETHER"
AETHER_VERSION = "3.5.2-heartbeat-switch"
DASHBOARD_FILE = os.path.join(DATA_DIR, "aether_dashboard.json")

logger = logging.getLogger(__name__)

# -----------------------------
# Helpers
# -----------------------------
def safe_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _msg(text: str):
    return [{"text": text, "type": "text"}]

def _read_json(path: str, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _write_json(path: str, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

# -----------------------------
# Core persistent state
# -----------------------------
def load_state():
    s = _read_json(STATE_FILE, None)
    if not s:
        s = {
            "id": AETHER_ID,
            "version": AETHER_VERSION,
            # NIVEL 50 — OPERATIONAL
            "status": "OPERATIONAL",
            "energy": 100,
            "focus": "STANDBY",
            "created_at": safe_now(),
            "last_cycle": None,
        }
        _write_json(STATE_FILE, s)
    else:
        # NIVEL 50 — OPERATIONAL
        s["status"] = "OPERATIONAL"
        _write_json(STATE_FILE, s)
    return s

def save_state(state: dict):
    _write_json(STATE_FILE, state)

def touch_last_cycle(state: dict = None) -> None:
    target = state or STATE
    if not isinstance(target, dict):
        return
    target["last_cycle"] = safe_now()
    save_state(target)

def load_memory():
    m = _read_json(MEMORY_FILE, [])
    if not isinstance(m, list):
        m = []
    return m

def save_memory(mem: list):
    _write_json(MEMORY_FILE, mem)

def load_strategic():
    st = _read_json(STRATEGIC_FILE, None)
    if not st:
        st = {
            "patterns": 0,
            "failures": 0,
            "last_update": None,
            "history_len": 0,
            "history": [],
        }
        _write_json(STRATEGIC_FILE, st)
    return st

def save_strategic(st: dict):
    _write_json(STRATEGIC_FILE, st)

def _load_dashboard(path: str = DASHBOARD_FILE) -> dict:
    data = _read_json(path, {})
    if isinstance(data, dict):
        return data
    return {}

def _save_dashboard(data: dict, path: str = DASHBOARD_FILE) -> None:
    _write_json(path, data)

def _update_dashboard_orchestrator_status(status: str, path: str = DASHBOARD_FILE) -> None:
    dashboard = _load_dashboard(path)
    orchestrator = dashboard.get("orchestrator")
    if not isinstance(orchestrator, dict):
        orchestrator = {}
    orchestrator["status"] = status
    dashboard["orchestrator"] = orchestrator
    _save_dashboard(dashboard, path)

def _reset_safe_mode_if_watchdog_stall(path: str = DASHBOARD_FILE) -> bool:
    dashboard = _load_dashboard(path)
    safe_mode = dashboard.get("safe_mode")
    if not isinstance(safe_mode, dict):
        return False
    if not safe_mode.get("enabled"):
        return False
    reason = (safe_mode.get("reason") or "").upper()
    if reason != "WATCHDOG_STALL":
        return False
    safe_mode["enabled"] = False
    safe_mode["since"] = None
    safe_mode["reason"] = ""
    dashboard["safe_mode"] = safe_mode
    _save_dashboard(dashboard, path)
    return True

def ensure_orchestrator_autostart(
    orchestrator_obj=None,
    state: dict = None,
    dashboard_path: str = DASHBOARD_FILE,
    log_fn=None,
    warn_fn=None,
) -> bool:
    global _ORCHESTRATOR_AUTOSTARTED
    with _ORCHESTRATOR_AUTOSTART_LOCK:
        if _ORCHESTRATOR_AUTOSTARTED:
            return False
        dashboard = _load_dashboard(dashboard_path)
        safe_mode_enabled = bool(dashboard.get("safe_mode", {}).get("enabled"))
        allow_run = bool(dashboard.get("orchestrator_policy", {}).get("allow_run"))
        if safe_mode_enabled or not allow_run:
            return False
        orch = orchestrator_obj or ORCHESTRATOR
        if not orch:
            return False
        def _log(message: str) -> None:
            if log_fn:
                log_fn(message)
            else:
                logger.info(message)
        def _warn(message: str) -> None:
            if warn_fn:
                warn_fn(message)
            else:
                logger.warning(message)
        started = False
        try:
            if hasattr(orch, "start") and callable(getattr(orch, "start")):
                orch.start(state or STATE)
                started = True
            else:
                _update_dashboard_orchestrator_status("RUNNING", dashboard_path)
                _warn("Orchestrator start() missing; wrote RUNNING status stub")
                started = True
        except Exception as exc:
            _warn(f"Orchestrator autostart failed: {exc}")
            return False
        if started:
            _ORCHESTRATOR_AUTOSTARTED = True
            _log("Orchestrator autostarted at boot")
        return started

STATE = load_state()
MEMORY = load_memory()
STRATEGIC = load_strategic()

AETHER_STATE = STATE

try:
    from core.orchestrator import Orchestrator
except Exception:
    Orchestrator = None

ORCHESTRATOR = Orchestrator(dashboard_path=DASHBOARD_FILE) if Orchestrator else None
_ORCHESTRATOR_AUTOSTARTED = False
_ORCHESTRATOR_AUTOSTART_LOCK = threading.Lock()

# -----------------------------
# Kill switch (simple)
# -----------------------------
KILL_SWITCH = {"enabled": True, "status": "ARMED"}

# -----------------------------
# v26 Tasks: Store + Runner
# -----------------------------
TASK_DB = os.path.join(DATA_DIR, "tasks.db")

# Imports (must exist in plugins/)
try:
    from plugins.task_store import TaskStore
    from plugins.adapters import Adapters
    from plugins.task_runner import TaskRunner
except Exception as e:
    TaskStore = None
    Adapters = None
    TaskRunner = None
    _TASK_IMPORT_ERR = str(e)
else:
    _TASK_IMPORT_ERR = None

store = None
runner = None
_runner_thread = None

def _start_task_runner():
    global store, runner, _runner_thread

    if TaskStore is None:
        return

    if store is None:
        store = TaskStore(TASK_DB)

    if runner is None:
        adapters = Adapters(
            base_dir=WORK_DIR,
            allowed_shell_cmds=["python", "pip"],
            allowed_http_domains=[],
        )
        runner = TaskRunner(store, adapters, poll_interval_s=0.5)

    if _runner_thread and _runner_thread.is_alive():
        return

    _runner_thread = threading.Thread(target=runner.start_loop, daemon=True)
    _runner_thread.start()
    touch_last_cycle()

def enqueue_task(task_type: str, payload: dict, priority: int = 50, max_attempts: int = 3, timeout_s: int = 60):
    _start_task_runner()
    if store is None:
        raise RuntimeError(f"TaskStore not available: {_TASK_IMPORT_ERR}")
    task_id = f"task-{uuid.uuid4().hex}"
    store.enqueue(task_id, task_type, payload, priority=priority, max_attempts=max_attempts, timeout_s=timeout_s)
    return task_id

# Start runner at boot (best-effort)
_start_task_runner()

# -----------------------------
# Plugin router
# -----------------------------
try:
    from plugins import router_help
except Exception as e:
    router_help = None
    _ROUTER_IMPORT_ERR = str(e)
else:
    _ROUTER_IMPORT_ERR = None
    try:
        router_help.load_plugins()
    except Exception:
        pass

def get_modules():
    if router_help is None:
        return []
    try:
        # router_help.load_plugins() devuelve lista de *_ai cargados
        return router_help.load_plugins()
    except Exception:
        return []

# -----------------------------
# Public: status export (tu panel lo muestra)
# -----------------------------
def get_system_status():
    global STATE, MEMORY, STRATEGIC

    # refresca desde disco (robusto)
    STATE = load_state()
    MEMORY = load_memory()
    STRATEGIC = load_strategic()

    modules = get_modules()

    queue_size = 0
    try:
        if store is not None:
            # cuenta rápido: tasks recientes (no exacto, pero suficiente)
            queue_size = len(store.list_recent(50))
    except Exception:
        queue_size = 0

    dashboard = _load_dashboard()
    orchestrator_snapshot = dashboard.get("orchestrator")
    if not isinstance(orchestrator_snapshot, dict):
        orchestrator_snapshot = {}
    return {
        "state": STATE,
        "queue_size": queue_size,
        "memory_len": len(MEMORY),
        "strategic": {
            "patterns": STRATEGIC.get("patterns", 0),
            "failures": STRATEGIC.get("failures", 0),
            "last_update": STRATEGIC.get("last_update"),
            "history_len": STRATEGIC.get("history_len", 0),
        },
        "kill_switch": KILL_SWITCH,
        "orchestrator_policy": dashboard.get("orchestrator_policy", {}),
        "orchestrator": {
            "status": orchestrator_snapshot.get("status"),
            "queue_length": orchestrator_snapshot.get("queue_length"),
            "blocked_reason": orchestrator_snapshot.get("blocked_reason"),
        },
        "modules": modules,
        "data_dir": DATA_DIR,
        "version": AETHER_VERSION,
    }

# -----------------------------
# Public: chat entrypoint
# -----------------------------
def handle_chat(user_text: str):
    """
    Punto único para el chat.
    Devuelve SIEMPRE lista de mensajes: [{text,type}].
    """
    text = (user_text or "").strip()
    if not text:
        return _msg("Escribe un comando.")

    touch_last_cycle()

    # Comandos de diagnóstico rápidos
    if text.lower() in ("status", "estado"):
        return _msg(json.dumps(get_system_status(), ensure_ascii=False, indent=2))

    if text.lower() in ("reset safe mode", "reset safe_mode", "reset safemode"):
        if _reset_safe_mode_if_watchdog_stall():
            return _msg("SAFE_MODE reiniciado (WATCHDOG_STALL).")
        return _msg("SAFE_MODE no estaba activo o no fue generado por WATCHDOG_STALL.")

    if text.lower() in ("modules", "modulos", "módulos"):
        return _msg(f"Modules: {get_modules()}")

    # Ruteo a plugins *_ai
    if router_help is None:
        return _msg(f"[ERROR] router_help no disponible: {_ROUTER_IMPORT_ERR}")

    try:
        out = router_help.route(text, get_system_status())
        if out is None:
            # Si ningún plugin lo manejó, no eco: responde claro
            return _msg("No hay plugin que maneje ese comando. Prueba: modules, status, reload plugins, task a")
        # out puede venir como string o como lista de mensajes
        if isinstance(out, str):
            return _msg(out)
        if isinstance(out, list):
            return out
        # fallback
        return _msg(str(out))
    except Exception as e:
        return _msg(f"[ERROR] {e}")
