# ======================================================
# AETHER CORE — HF SPACES SAFE (GRADIO ONLY, NO FASTAPI)
# Objetivo: 0 runtime-crash en HF.
#
# Incluye:
#   - Chat compatible con gradio clásico (lista de tuplas user/bot)
#   - Cola + worker thread (budget por tick)
#   - Scheduler/heartbeat thread (opcional)
#   - Plugins hot-reload: plugins/*_ai.py (can_handle/run)
#   - Logs + dashboard (JSON atomic)
#   - v28: Snapshots create/restore/export/import (incluye plugins)
#   - v28.2: Réplica portable (1 JSON) + checksum + apply
#   - v29: Project Orchestrator (projects/tasks + policy gate)
#   - v30: Task lifecycle (PENDING/RUNNING/DONE/FAILED)
#   - v31: Retry + Budget
#   - v32: Planning (subtasks propuesta, NO auto-run) con "plan:"
#   - v35: Autonomy gate (freeze + budget)
#   - v36-37: Watchdog + Safe Mode
#   - v38: Events log JSONL + rotación
#   - v39: UI Tick HF-safe (auto-refresh)
# ======================================================

import os
import sys
import time
import json
import uuid
import hashlib
import threading
import importlib.util
from queue import PriorityQueue
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional

import gradio as gr

# -----------------------------
# TIME (timezone-aware)
# -----------------------------

def safe_now() -> str:
    return datetime.now(timezone.utc).isoformat()

# -----------------------------
# ENV HELPERS
# -----------------------------

def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    v = str(raw).strip().lower()
    if v in {"1", "true", "yes", "y", "on", "t"}:
        return True
    if v in {"0", "false", "no", "n", "off", "f"}:
        return False
    return bool(default)

def sha256_text(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()

# -----------------------------
# PATHS (HF-safe)
# -----------------------------
DATA_DIR = os.environ.get("AETHER_DATA_DIR", "/tmp/aether")
os.makedirs(DATA_DIR, exist_ok=True)

MODULES_DIR = "plugins"
os.makedirs(MODULES_DIR, exist_ok=True)

SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# -----------------------------
# VERSION + FILES
# -----------------------------
AETHER_VERSION = "3.10.0-hf-v39-stable"

STATE_FILE = os.path.join(DATA_DIR, "aether_state.json")
MEMORY_FILE = os.path.join(DATA_DIR, "aether_memory.json")
STRATEGIC_FILE = os.path.join(DATA_DIR, "aether_strategic.json")
LOG_FILE = os.path.join(DATA_DIR, "aether_log.json")
DASHBOARD_FILE = os.path.join(DATA_DIR, "aether_dashboard.json")
EVENTS_LOG_FILE = os.path.join(DATA_DIR, "events.log")

DEMO1_FILE = os.path.join(DATA_DIR, "demo1.json")
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")

# -----------------------------
# LIMITS
# -----------------------------
MAX_MEMORY_ENTRIES = 500
MAX_LOG_ENTRIES = 1000
MAX_STRATEGY_HISTORY = 1000
MAX_DEDUP_KEYS = 5000

# -----------------------------
# EVENTS LOG
# -----------------------------
AETHER_EVENTS_LOG_MAX_BYTES = int(os.environ.get("AETHER_EVENTS_LOG_MAX_BYTES", "1000000"))

# -----------------------------
# HEARTBEAT / RUNNER CONFIG
# -----------------------------
HEARTBEAT_CMD = "revisar estado interno"
HEARTBEAT_INTERVAL_SEC = int(os.environ.get("AETHER_HEARTBEAT_SEC", "120"))
HEARTBEAT_MIN_ENERGY = int(os.environ.get("AETHER_HEARTBEAT_MIN_ENERGY", "40"))
AETHER_HEARTBEAT_ENABLED = env_bool("AETHER_HEARTBEAT_ENABLED", True)

AETHER_TASK_RUNNER_ENABLED = env_bool("AETHER_TASK_RUNNER_ENABLED", True)
AETHER_TASK_MAX_RETRIES = int(os.environ.get("AETHER_TASK_MAX_RETRIES", "2"))
AETHER_TASK_BUDGET = int(os.environ.get("AETHER_TASK_BUDGET", "3"))

# -----------------------------
# SAFE MODE + WATCHDOG
# -----------------------------
AETHER_SAFE_MODE_ENABLED = env_bool("AETHER_SAFE_MODE_ENABLED", True)
AETHER_WATCHDOG_SEC = int(os.environ.get("AETHER_WATCHDOG_SEC", "180"))
AETHER_WATCHDOG_GRACE_SEC = int(os.environ.get("AETHER_WATCHDOG_GRACE_SEC", "30"))

SAFE_MODE = {
    "enabled": bool(AETHER_SAFE_MODE_ENABLED),
    "since": safe_now() if AETHER_SAFE_MODE_ENABLED else None,
    "reason": "ENV_ENABLED" if AETHER_SAFE_MODE_ENABLED else "",
}
SAFE_MODE_LOGGED = False

# -----------------------------
# FREEZE + POLICY
# -----------------------------
AETHER_FREEZE_MODE = env_bool("AETHER_FREEZE_MODE", True)
AETHER_ORCHESTRATOR_ALLOW_RUN = env_bool("AETHER_ORCHESTRATOR_ALLOW_RUN", True)

ROOT_GOAL = "EXECUTE_USER_COMMANDS_ONLY"
KILL_SWITCH = {"enabled": True, "status": "ARMED"}

FREEZE_STATE = {"enabled": bool(AETHER_FREEZE_MODE), "since": safe_now() if AETHER_FREEZE_MODE else None}

def is_frozen() -> bool:
    return bool(FREEZE_STATE.get("enabled"))

ORCHESTRATOR_POLICY = {"allow_run": bool(AETHER_ORCHESTRATOR_ALLOW_RUN)}

# -----------------------------
# LOCKS
# -----------------------------
memory_lock = threading.Lock()
log_lock = threading.Lock()
state_lock = threading.Lock()
strategic_lock = threading.Lock()
modules_lock = threading.Lock()
dedup_lock = threading.Lock()
queue_lock = threading.Lock()
projects_lock = threading.Lock()
tasks_lock = threading.Lock()
snap_lock = threading.Lock()
events_log_lock = threading.Lock()

# -----------------------------
# JSON IO (atomic)
# -----------------------------

def load_json(path: str, default: Any) -> Any:
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            txt = f.read().strip()
            if not txt:
                return default
            return json.loads(txt)
    except Exception:
        return default

def save_json_atomic(path: str, data: Any) -> bool:
    tmp = f"{path}.tmp"
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        os.replace(tmp, path)
        return True
    except Exception as e:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        # Evitar recursión si falla LOG_FILE
        if path != LOG_FILE and "log_event" in globals():
            try:
                log_event("JSON_WRITE_ERROR", {"file": path, "error": str(e)})
            except Exception:
                pass
        return False

# -----------------------------
# INITIAL STATE
# -----------------------------
DEFAULT_STATE: Dict[str, Any] = {
    "id": "AETHER",
    "version": AETHER_VERSION,
    "status": "IDLE",
    "energy": 100,
    "focus": "STANDBY",
    "created_at": safe_now(),
    "last_cycle": None,
    "last_heartbeat_ts": None,
}

AETHER_STATE: Dict[str, Any] = load_json(STATE_FILE, dict(DEFAULT_STATE))
AETHER_MEMORY: List[Dict[str, Any]] = load_json(MEMORY_FILE, [])
STRATEGIC_MEMORY: Dict[str, Any] = load_json(
    STRATEGIC_FILE,
    {"patterns": {}, "failures": {}, "history": [], "last_update": None},
)
AETHER_LOGS: List[Dict[str, Any]] = load_json(LOG_FILE, [])

DEFAULT_PROJECTS = [{"id": "default", "name": "Default", "created_at": safe_now()}]
AETHER_PROJECTS: List[Dict[str, Any]] = load_json(PROJECTS_FILE, [])
AETHER_TASKS: List[Dict[str, Any]] = load_json(TASKS_FILE, [])

if "last_heartbeat_ts" not in AETHER_STATE:
    AETHER_STATE["last_heartbeat_ts"] = None
    save_json_atomic(STATE_FILE, AETHER_STATE)

# -----------------------------
# DEMO1
# -----------------------------

def ensure_demo1() -> bool:
    if os.path.exists(DEMO1_FILE):
        return True
    return save_json_atomic(
        DEMO1_FILE,
        {"name": "demo1", "created_at": safe_now(), "events": [], "notes": "auto-created"},
    )

def export_demo1() -> str:
    try:
        ensure_demo1()
        payload = load_json(DEMO1_FILE, {"ok": False, "error": "demo1_missing"})
        return json.dumps({"ok": True, "demo": payload}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, indent=2, ensure_ascii=False)

# -----------------------------
# EVENTS LOG (JSONL)
# -----------------------------

def _rotate_events_log_if_needed() -> None:
    try:
        if os.path.exists(EVENTS_LOG_FILE) and os.path.getsize(EVENTS_LOG_FILE) > AETHER_EVENTS_LOG_MAX_BYTES:
            try:
                os.replace(EVENTS_LOG_FILE, f"{EVENTS_LOG_FILE}.1")
            except Exception:
                pass
    except Exception:
        pass

def _append_events_log(entry: Dict[str, Any]) -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with events_log_lock:
            _rotate_events_log_if_needed()
            with open(EVENTS_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

# -----------------------------
# LOGS + DASHBOARD
# -----------------------------

def log_event(t: str, info: Any) -> None:
    entry = {"timestamp": safe_now(), "type": t, "info": info}
    with log_lock:
        AETHER_LOGS.append(entry)
        if len(AETHER_LOGS) > MAX_LOG_ENTRIES:
            AETHER_LOGS[:] = AETHER_LOGS[-MAX_LOG_ENTRIES:]
        save_json_atomic(LOG_FILE, AETHER_LOGS)
    _append_events_log(entry)

TASK_STATUSES = {"PENDING", "RUNNING", "DONE", "FAILED"}

def _task_status_counts() -> Dict[str, int]:
    counts = {"PENDING": 0, "RUNNING": 0, "DONE": 0, "FAILED": 0}
    with tasks_lock:
        for t in AETHER_TASKS:
            s = t.get("status")
            if s in counts:
                counts[s] += 1
    return counts

LOADED_MODULES: Dict[str, Any] = {}

def update_dashboard() -> None:
    with state_lock:
        snap = dict(AETHER_STATE)
    with modules_lock:
        modules_loaded = len(LOADED_MODULES)
    with projects_lock:
        projects_count = len(AETHER_PROJECTS)
    with tasks_lock:
        tasks_count = len(AETHER_TASKS)

    dash = {
        "energy": snap.get("energy", 0),
        "focus": snap.get("focus", "STANDBY"),
        "status": snap.get("status", "IDLE"),
        "queue_size": TASK_QUEUE.qsize(),
        "last_cycle": snap.get("last_cycle"),
        "version": AETHER_VERSION,
        "data_dir": DATA_DIR,
        "modules_loaded": modules_loaded,
        "freeze_mode": bool(is_frozen()),
        "safe_mode": dict(SAFE_MODE),
        "heartbeat_enabled": bool(AETHER_HEARTBEAT_ENABLED),
        "task_runner_enabled": bool(AETHER_TASK_RUNNER_ENABLED),
        "task_budget": max(1, int(AETHER_TASK_BUDGET)),
        "task_max_retries": max(0, int(AETHER_TASK_MAX_RETRIES)),
        "orchestrator_policy": dict(ORCHESTRATOR_POLICY),
        "projects_count": projects_count,
        "tasks_count": tasks_count,
        "tasks_status": _task_status_counts(),
        "snapshots": [],  # se completa en ui_status()
    }
    ok = save_json_atomic(DASHBOARD_FILE, dash)
    if not ok:
        log_event("DASHBOARD_WRITE_FAIL", {"file": DASHBOARD_FILE})

# -----------------------------
# SAFE MODE HELPERS
# -----------------------------

def safe_mode_enabled() -> bool:
    return bool(SAFE_MODE.get("enabled"))

def enable_safe_mode(reason: str) -> None:
    global SAFE_MODE_LOGGED
    if not safe_mode_enabled():
        SAFE_MODE["enabled"] = True
        SAFE_MODE["since"] = safe_now()
        SAFE_MODE["reason"] = reason
    elif not SAFE_MODE.get("since"):
        SAFE_MODE["since"] = safe_now()
        SAFE_MODE["reason"] = reason
    if not SAFE_MODE_LOGGED:
        SAFE_MODE_LOGGED = True
        log_event("SAFE_MODE_ON", {"reason": SAFE_MODE.get("reason"), "since": SAFE_MODE.get("since")})
    with state_lock:
        AETHER_STATE["status"] = "SAFE_MODE"
        save_json_atomic(STATE_FILE, AETHER_STATE)

# -----------------------------
# QUEUE + DEDUP
# -----------------------------
TASK_QUEUE: PriorityQueue = PriorityQueue()
QUEUE_SET = set()

TASK_DEDUP: List[str] = []
TASK_DEDUP_SET = set()

def tasks_queue_contains(command: str) -> bool:
    c = (command or "").strip()
    if not c:
        return False
    with queue_lock:
        return c in QUEUE_SET

def _dedup_prune_if_needed() -> None:
    with dedup_lock:
        if len(TASK_DEDUP) <= MAX_DEDUP_KEYS:
            return
        keep = int(MAX_DEDUP_KEYS * 0.7)
        old = TASK_DEDUP[:-keep]
        TASK_DEDUP[:] = TASK_DEDUP[-keep:]
        for k in old:
            TASK_DEDUP_SET.discard(k)

def compute_priority(base: int) -> int:
    with state_lock:
        e = int(AETHER_STATE.get("energy", 0))
    return int(base) + (3 if e < 20 else 0)

def enqueue_task(command: str, priority: int = 5, source: str = "external") -> Dict[str, Any]:
    command = (command or "").strip()
    if not command:
        return {"ok": False, "error": "empty_command"}

    blocked_sources_in_safe = {"external", "chat"}
    if safe_mode_enabled() and source in blocked_sources_in_safe:
        log_event("SAFE_MODE_BLOCK_ENQUEUE", {"command": command, "source": source})
        return {"ok": False, "blocked": True, "reason": "SAFE_MODE_ON"}

    blocked_sources_in_freeze = {"external", "chat"}
    if is_frozen() and source in blocked_sources_in_freeze:
        log_event("FREEZE_BLOCK_ENQUEUE", {"command": command, "source": source})
        return {"ok": False, "blocked": True, "reason": "SYSTEM_FROZEN"}

    if (not AETHER_HEARTBEAT_ENABLED) and command.lower().strip() == HEARTBEAT_CMD:
        log_event("HEARTBEAT_DISABLED", {"message": "Heartbeat disabled: blocked enqueue"})
        return {"ok": False, "blocked": True, "reason": "heartbeat_disabled"}

    # dedup only external
    if source != "internal":
        key = f"{command}:{source}"
        with dedup_lock:
            if key in TASK_DEDUP_SET:
                return {"ok": False, "dedup": True}
            TASK_DEDUP_SET.add(key)
            TASK_DEDUP.append(key)
        _dedup_prune_if_needed()

    dyn = compute_priority(int(priority))
    task = {"id": str(uuid.uuid4()), "command": command, "source": source, "created_at": safe_now()}

    with queue_lock:
        if command in QUEUE_SET:
            return {"ok": False, "dedup": True}
        TASK_QUEUE.put((dyn, task))
        QUEUE_SET.add(command)

    log_event("ENQUEUE", {"command": command, "priority": dyn, "source": source})
    update_dashboard()
    return {"ok": True, "task_id": task["id"], "priority": dyn}

# -----------------------------
# STRATEGY
# -----------------------------

def record_strategy(command: str, mode: str, success: bool) -> None:
    sig = f"{mode}:{len((command or '').split())}"
    target = "patterns" if success else "failures"
    with strategic_lock:
        if not isinstance(STRATEGIC_MEMORY.get("patterns"), dict):
            STRATEGIC_MEMORY["patterns"] = {}
        if not isinstance(STRATEGIC_MEMORY.get("failures"), dict):
            STRATEGIC_MEMORY["failures"] = {}
        if not isinstance(STRATEGIC_MEMORY.get("history"), list):
            STRATEGIC_MEMORY["history"] = []

        STRATEGIC_MEMORY[target][sig] = STRATEGIC_MEMORY[target].get(sig, 0) + 1
        STRATEGIC_MEMORY["history"].append(
            {"timestamp": safe_now(), "command": command, "mode": mode, "success": bool(success)}
        )
        if len(STRATEGIC_MEMORY["history"]) > MAX_STRATEGY_HISTORY:
            STRATEGIC_MEMORY["history"] = STRATEGIC_MEMORY["history"][-MAX_STRATEGY_HISTORY:]
        STRATEGIC_MEMORY["last_update"] = safe_now()
        save_json_atomic(STRATEGIC_FILE, STRATEGIC_MEMORY)

# -----------------------------
# PLUGINS HOT-RELOAD (*_ai.py)
# -----------------------------

def _list_plugin_files() -> List[str]:
    try:
        files = [f for f in os.listdir(MODULES_DIR) if f.endswith("_ai.py") and not f.startswith("_")]
        files.sort()
        return files
    except Exception:
        return []

def reload_ai_modules() -> List[str]:
    loaded: Dict[str, Any] = {}
    for fn in _list_plugin_files():
        name = fn[:-3]
        path = os.path.join(MODULES_DIR, fn)
        try:
            mod_name = f"plugins.{name}"
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if not spec or not spec.loader:
                continue
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)

            if callable(getattr(mod, "can_handle", None)) and callable(getattr(mod, "run", None)):
                loaded[name] = mod
            else:
                log_event("MODULE_SKIPPED", {"module": name, "reason": "missing can_handle/run"})
        except Exception as e:
            log_event("MODULE_LOAD_ERROR", {"module": name, "error": str(e)})

    with modules_lock:
        LOADED_MODULES.clear()
        LOADED_MODULES.update(loaded)

    log_event("MODULES_RELOADED", {"modules": list(LOADED_MODULES.keys())})
    update_dashboard()
    return list(LOADED_MODULES.keys())

def _any_module_can_handle(command: str) -> bool:
    c = (command or "").strip()
    if not c:
        return False
    with modules_lock:
        mods = list(LOADED_MODULES.values())
    for mod in mods:
        try:
            if callable(getattr(mod, "can_handle", None)) and mod.can_handle(c):
                return True
        except Exception:
            continue
    return False

def execute_ai_module(command: str) -> Dict[str, Any]:
    with modules_lock:
        items = list(LOADED_MODULES.items())
    for name, mod in items:
        try:
            if mod.can_handle(command):
                return {"success": True, "module": name, "result": mod.run(command)}
        except Exception as e:
            log_event("MODULE_RUN_ERROR", {"module": name, "error": str(e)})
            return {"success": False, "error": f"{name}: {e}"}
    return {"success": False, "error": "No suitable AI module found"}

# -----------------------------
# SNAPSHOTS (v28 + v28.3 plugins)
# -----------------------------

def _snapshot_path(name: str) -> str:
    safe = "".join(ch for ch in (name or "").strip() if ch.isalnum() or ch in ("-", "_"))
    if not safe:
        safe = "snapshot"
    return os.path.join(SNAPSHOT_DIR, f"{safe}.json")

def snapshot_list() -> List[str]:
    try:
        files = [f for f in os.listdir(SNAPSHOT_DIR) if f.endswith(".json")]
        files.sort()
        return [f[:-5] for f in files]
    except Exception:
        return []

def _read_text_file(path: str, limit_bytes: int = 250_000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            txt = f.read()
        b = txt.encode("utf-8", errors="ignore")
        if len(b) > limit_bytes:
            b = b[:limit_bytes]
        return b.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def snapshot_pack_plugins() -> Dict[str, str]:
    packed: Dict[str, str] = {}
    for fn in _list_plugin_files():
        p = os.path.join(MODULES_DIR, fn)
        packed[f"{MODULES_DIR}/{fn}"] = _read_text_file(p)
    return packed

def snapshot_apply_plugins(packed: Dict[str, str]) -> Dict[str, Any]:
    if not isinstance(packed, dict):
        return {"ok": False, "error": "plugins_invalid"}
    try:
        os.makedirs(MODULES_DIR, exist_ok=True)
        wrote = 0
        for rel, txt in packed.items():
            if not isinstance(rel, str) or not rel.startswith(f"{MODULES_DIR}/") or not rel.endswith(".py"):
                continue
            base = os.path.basename(rel)
            if not base.endswith("_ai.py"):
                continue
            out_path = os.path.join(MODULES_DIR, base)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(txt if isinstance(txt, str) else "")
            wrote += 1
        return {"ok": True, "wrote": wrote}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def snapshot_create(name: str = "demo1") -> Dict[str, Any]:
    name = (name or "demo1").strip()
    path = _snapshot_path(name)

    with snap_lock, state_lock, memory_lock, strategic_lock, log_lock, projects_lock, tasks_lock, modules_lock:
        payload = {
            "ok": True,
            "name": name,
            "created_at": safe_now(),
            "version": AETHER_VERSION,
            "env": {
                "heartbeat_enabled": bool(AETHER_HEARTBEAT_ENABLED),
                "task_runner_enabled": bool(AETHER_TASK_RUNNER_ENABLED),
                "freeze_mode": bool(is_frozen()),
                "safe_mode": dict(SAFE_MODE),
                "data_dir": DATA_DIR,
                "task_budget": max(1, int(AETHER_TASK_BUDGET)),
                "task_max_retries": max(0, int(AETHER_TASK_MAX_RETRIES)),
            },
            "files": {
                "state": dict(AETHER_STATE),
                "memory": list(AETHER_MEMORY),
                "strategic": dict(STRATEGIC_MEMORY),
                "logs": list(AETHER_LOGS),
                "modules": list(LOADED_MODULES.keys()),
                "projects": list(AETHER_PROJECTS),
                "tasks": list(AETHER_TASKS),
            },
            "plugins": {"format": "plugins-text-v1", "files": snapshot_pack_plugins()},
            "notes": "snapshot includes plugins + projects/tasks + lifecycle/retry/budget/planning",
        }

    ok = save_json_atomic(path, payload)
    if ok:
        log_event("SNAPSHOT_CREATED", {"name": name, "file": path, "plugins": len(payload["plugins"]["files"])})
        update_dashboard()
        return {"ok": True, "name": name, "file": path}
    log_event("SNAPSHOT_CREATE_FAIL", {"name": name, "file": path})
    return {"ok": False, "error": "snapshot_write_failed", "file": path}

def snapshot_restore(name: str = "demo1") -> Dict[str, Any]:
    name = (name or "demo1").strip()
    path = _snapshot_path(name)
    payload = load_json(path, None)
    if not payload or not isinstance(payload, dict) or not payload.get("ok"):
        return {"ok": False, "error": "snapshot_missing_or_invalid", "file": path}

    files = payload.get("files", {}) if isinstance(payload, dict) else {}
    st = files.get("state", dict(DEFAULT_STATE))
    mem = files.get("memory", [])
    strat = files.get("strategic", {"patterns": {}, "failures": {}, "history": [], "last_update": None})
    logs = files.get("logs", [])
    projects = files.get("projects", [])
    tasks = files.get("tasks", [])

    with state_lock:
        AETHER_STATE.clear()
        AETHER_STATE.update(st if isinstance(st, dict) else dict(DEFAULT_STATE))
        AETHER_STATE["version"] = AETHER_VERSION
        AETHER_STATE["status"] = "FROZEN" if is_frozen() else AETHER_STATE.get("status", "IDLE")
        save_json_atomic(STATE_FILE, AETHER_STATE)

    with memory_lock:
        AETHER_MEMORY.clear()
        if isinstance(mem, list):
            AETHER_MEMORY.extend(mem)
        save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

    with strategic_lock:
        STRATEGIC_MEMORY.clear()
        STRATEGIC_MEMORY.update(strat if isinstance(strat, dict) else {"patterns": {}, "failures": {}, "history": [], "last_update": None})
        if not isinstance(STRATEGIC_MEMORY.get("history"), list):
            STRATEGIC_MEMORY["history"] = []
        if len(STRATEGIC_MEMORY["history"]) > MAX_STRATEGY_HISTORY:
            STRATEGIC_MEMORY["history"] = STRATEGIC_MEMORY["history"][-MAX_STRATEGY_HISTORY:]
        STRATEGIC_MEMORY["last_update"] = safe_now()
        save_json_atomic(STRATEGIC_FILE, STRATEGIC_MEMORY)

    with log_lock:
        AETHER_LOGS.clear()
        if isinstance(logs, list):
            AETHER_LOGS.extend(logs)
        save_json_atomic(LOG_FILE, AETHER_LOGS)

    with projects_lock:
        AETHER_PROJECTS.clear()
        if isinstance(projects, list) and projects:
            AETHER_PROJECTS.extend(projects)
        else:
            AETHER_PROJECTS.extend(list(DEFAULT_PROJECTS))
        save_json_atomic(PROJECTS_FILE, AETHER_PROJECTS)

    with tasks_lock:
        AETHER_TASKS.clear()
        if isinstance(tasks, list):
            AETHER_TASKS.extend(tasks)
        _normalize_tasks_locked()
        save_json_atomic(TASKS_FILE, AETHER_TASKS)

    plug = payload.get("plugins", {}) if isinstance(payload, dict) else {}
    if isinstance(plug, dict) and isinstance(plug.get("files"), dict):
        res = snapshot_apply_plugins(plug.get("files"))
        log_event("SNAPSHOT_PLUGINS_APPLIED", res)

    reload_ai_modules()
    update_dashboard()
    log_event("SNAPSHOT_RESTORED", {"name": name, "file": path})
    return {"ok": True, "name": name, "file": path}

def snapshot_export(name: str = "demo1") -> str:
    name = (name or "demo1").strip()
    path = _snapshot_path(name)
    payload = load_json(path, None)
    if not payload:
        return json.dumps({"ok": False, "error": "snapshot_not_found", "name": name}, indent=2, ensure_ascii=False)
    return json.dumps(payload, indent=2, ensure_ascii=False)

def snapshot_import(json_text: str) -> Dict[str, Any]:
    try:
        payload = json.loads(json_text or "")
        if not isinstance(payload, dict) or not payload.get("ok"):
            return {"ok": False, "error": "invalid_payload"}
        name = (payload.get("name") or "imported").strip()
        path = _snapshot_path(name)
        ok = save_json_atomic(path, payload)
        if ok:
            log_event("SNAPSHOT_IMPORTED", {"name": name, "file": path})
            update_dashboard()
            return {"ok": True, "name": name, "file": path}
        return {"ok": False, "error": "write_failed", "file": path}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# -----------------------------
# REPLICA (v28.2)
# -----------------------------
REPLICA_FORMAT = "aether-replica-v28.2"

def replica_export(name: str = "replica") -> str:
    name = (name or "replica").strip()

    with state_lock:
        st = dict(AETHER_STATE)
    with memory_lock:
        mem = list(AETHER_MEMORY)
    with strategic_lock:
        strat = dict(STRATEGIC_MEMORY)
    with log_lock:
        logs = list(AETHER_LOGS)
    with projects_lock:
        projects = list(AETHER_PROJECTS)
    with tasks_lock:
        tasks = list(AETHER_TASKS)

    demo1 = load_json(DEMO1_FILE, {"name": "demo1", "created_at": safe_now(), "events": [], "notes": "missing"})

    snaps: Dict[str, Any] = {}
    for sname in snapshot_list():
        snaps[sname] = load_json(_snapshot_path(sname), None)

    payload = {
        "ok": True,
        "format": REPLICA_FORMAT,
        "name": name,
        "created_at": safe_now(),
        "app_version": AETHER_VERSION,
        "env": {
            "data_dir": DATA_DIR,
            "heartbeat_enabled": bool(AETHER_HEARTBEAT_ENABLED),
            "task_runner_enabled": bool(AETHER_TASK_RUNNER_ENABLED),
            "freeze_mode": bool(is_frozen()),
            "safe_mode": dict(SAFE_MODE),
            "task_budget": max(1, int(AETHER_TASK_BUDGET)),
            "task_max_retries": max(0, int(AETHER_TASK_MAX_RETRIES)),
        },
        "bundle": {
            "state": st,
            "memory": mem,
            "strategic": strat,
            "logs": logs,
            "demo1": demo1,
            "snapshots": snaps,
            "projects": projects,
            "tasks": tasks,
            "plugins": {"format": "plugins-text-v1", "files": snapshot_pack_plugins()},
        },
    }

    copy = dict(payload)
    txt = json.dumps(copy, indent=2, ensure_ascii=False, sort_keys=True)
    payload["checksum_sha256"] = sha256_text(txt)
    return json.dumps(payload, indent=2, ensure_ascii=False)

def replica_apply(payload: Dict[str, Any]) -> Dict[str, Any]:
    bundle = (payload or {}).get("bundle", {}) or {}
    st = bundle.get("state", dict(DEFAULT_STATE))
    mem = bundle.get("memory", [])
    strat = bundle.get("strategic", {"patterns": {}, "failures": {}, "history": [], "last_update": None})
    logs = bundle.get("logs", [])
    demo1 = bundle.get("demo1", None)
    projects = bundle.get("projects", [])
    tasks = bundle.get("tasks", [])
    plugins = bundle.get("plugins", {})

    with state_lock:
        AETHER_STATE.clear()
        AETHER_STATE.update(st if isinstance(st, dict) else dict(DEFAULT_STATE))
        AETHER_STATE["version"] = AETHER_VERSION
        AETHER_STATE["status"] = "FROZEN" if is_frozen() else AETHER_STATE.get("status", "IDLE")
        save_json_atomic(STATE_FILE, AETHER_STATE)

    with memory_lock:
        AETHER_MEMORY.clear()
        if isinstance(mem, list):
            AETHER_MEMORY.extend(mem)
        save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

    with strategic_lock:
        STRATEGIC_MEMORY.clear()
        STRATEGIC_MEMORY.update(strat if isinstance(strat, dict) else {"patterns": {}, "failures": {}, "history": [], "last_update": None})
        save_json_atomic(STRATEGIC_FILE, STRATEGIC_MEMORY)

    with log_lock:
        AETHER_LOGS.clear()
        if isinstance(logs, list):
            AETHER_LOGS.extend(logs)
        save_json_atomic(LOG_FILE, AETHER_LOGS)

    if demo1 is not None:
        save_json_atomic(DEMO1_FILE, demo1)

    snaps = bundle.get("snapshots", {}) or {}
    if isinstance(snaps, dict):
        for sname, snap_payload in snaps.items():
            if sname and snap_payload:
                save_json_atomic(_snapshot_path(str(sname)), snap_payload)

    with projects_lock:
        AETHER_PROJECTS.clear()
        if isinstance(projects, list) and projects:
            AETHER_PROJECTS.extend(projects)
        else:
            AETHER_PROJECTS.extend(list(DEFAULT_PROJECTS))
        save_json_atomic(PROJECTS_FILE, AETHER_PROJECTS)

    with tasks_lock:
        AETHER_TASKS.clear()
        if isinstance(tasks, list):
            AETHER_TASKS.extend(tasks)
        _normalize_tasks_locked()
        save_json_atomic(TASKS_FILE, AETHER_TASKS)

    if isinstance(plugins, dict) and isinstance(plugins.get("files"), dict):
        res = snapshot_apply_plugins(plugins["files"])
        log_event("REPLICA_PLUGINS_APPLIED", res)

    reload_ai_modules()
    update_dashboard()
    log_event("REPLICA_APPLIED", {"name": payload.get("name"), "format": payload.get("format")})
    return {"ok": True, "applied": True, "snapshots": snapshot_list()}

def replica_import(replica_json_text: str, apply_now: bool = True) -> Dict[str, Any]:
    try:
        payload = json.loads(replica_json_text or "")
        if not isinstance(payload, dict) or not payload.get("ok"):
            return {"ok": False, "error": "invalid_payload"}
        if payload.get("format") != REPLICA_FORMAT:
            return {"ok": False, "error": "invalid_format", "expected": REPLICA_FORMAT, "got": payload.get("format")}

        checksum = payload.get("checksum_sha256")
        if not checksum or not isinstance(checksum, str):
            return {"ok": False, "error": "missing_checksum"}

        copy = dict(payload)
        copy.pop("checksum_sha256", None)
        txt = json.dumps(copy, indent=2, ensure_ascii=False, sort_keys=True)
        if sha256_text(txt) != checksum:
            return {"ok": False, "error": "checksum_mismatch"}

        if apply_now:
            return replica_apply(payload)
        return {"ok": True, "applied": False}
    except Exception as e:
        log_event("REPLICA_IMPORT_ERROR", {"error": str(e)})
        return {"ok": False, "error": str(e)}

# -----------------------------
# ORCHESTRATOR (v29+)
# -----------------------------

def _normalize_task(task: Dict[str, Any]) -> None:
    if not isinstance(task, dict):
        return
    if task.get("status") not in TASK_STATUSES:
        task["status"] = "PENDING"
    try:
        task["retry_count"] = max(0, int(task.get("retry_count", 0)))
    except Exception:
        task["retry_count"] = 0
    subtasks = task.get("subtasks")
    if not isinstance(subtasks, list):
        subtasks = []
    task["subtasks"] = [str(s).strip() for s in subtasks if str(s).strip()]

def _normalize_tasks_locked() -> None:
    for t in AETHER_TASKS:
        _normalize_task(t)

def ensure_projects() -> None:
    with projects_lock:
        if not isinstance(AETHER_PROJECTS, list) or not AETHER_PROJECTS:
            AETHER_PROJECTS.clear()
            AETHER_PROJECTS.extend(list(DEFAULT_PROJECTS))
        save_json_atomic(PROJECTS_FILE, AETHER_PROJECTS)
    with tasks_lock:
        if not isinstance(AETHER_TASKS, list):
            AETHER_TASKS.clear()
        _normalize_tasks_locked()
        save_json_atomic(TASKS_FILE, AETHER_TASKS)

def list_projects() -> List[Dict[str, Any]]:
    with projects_lock:
        return list(AETHER_PROJECTS)

def list_tasks(project_id: str) -> List[Dict[str, Any]]:
    with tasks_lock:
        return [t for t in AETHER_TASKS if t.get("project_id") == project_id]

def add_project(name: str) -> Dict[str, Any]:
    name = (name or "").strip()
    if not name:
        return {"ok": False, "error": "project_name_required"}
    pid = f"proj-{uuid.uuid4().hex[:10]}"
    proj = {"id": pid, "name": name, "created_at": safe_now()}
    with projects_lock:
        AETHER_PROJECTS.append(proj)
        save_json_atomic(PROJECTS_FILE, AETHER_PROJECTS)
    log_event("PROJECT_CREATED", {"id": pid, "name": name})
    update_dashboard()
    return {"ok": True, "project": proj}

def add_task(project_id: str, command: str) -> Dict[str, Any]:
    project_id = (project_id or "").strip()
    command = (command or "").strip()
    if not project_id:
        return {"ok": False, "error": "project_required"}
    if not command:
        return {"ok": False, "error": "command_required"}

    tid = f"task-{uuid.uuid4().hex[:10]}"
    task = {
        "id": tid,
        "project_id": project_id,
        "command": command,
        "created_at": safe_now(),
        "last_run": None,
        "last_success": None,
        "last_result": None,
        "status": "PENDING",
        "retry_count": 0,
        "subtasks": [],  # v32 planning output (propuestas)
    }
    with tasks_lock:
        AETHER_TASKS.append(task)
        save_json_atomic(TASKS_FILE, AETHER_TASKS)
    log_event("PROJECT_TASK_CREATED", {"id": tid, "project_id": project_id})
    update_dashboard()
    return {"ok": True, "task": task}

def _extract_subtasks_from_result(result: Dict[str, Any]) -> List[str]:
    if not isinstance(result, dict):
        return []
    payload = result.get("result")
    if not isinstance(payload, dict):
        return []
    subtasks = payload.get("subtasks")
    if not isinstance(subtasks, list):
        return []
    out = [str(s).strip() for s in subtasks if str(s).strip()]
    return out[:50]

def can_run_project_task(task: Dict[str, Any]) -> Tuple[bool, str]:
    if safe_mode_enabled():
        return False, "SAFE_MODE_ON"
    if is_frozen():
        return False, "SYSTEM_FROZEN"
    if not ORCHESTRATOR_POLICY.get("allow_run", True):
        return False, "POLICY_BLOCKED"
    if task.get("status") == "FAILED" and int(task.get("retry_count", 0)) >= max(0, int(AETHER_TASK_MAX_RETRIES)):
        return False, "MAX_RETRIES_EXCEEDED"
    return True, ""

# -----------------------------
# ROUTING / EXECUTION
# -----------------------------

def detect_domains(command: str) -> List[str]:
    c = (command or "").lower()
    d = set()
    if any(k in c for k in ["física", "ecuación", "modelo", "simulación", "simular"]):
        d.add("science")
    if any(k in c for k in ["reload", "plugin", "plugins", "task "]):
        d.add("ai")
    if any(k in c for k in ["snapshot", "snap", "restore", "export", "import", "replica"]):
        d.add("persistence")
    return list(d) or ["general"]

def decide_engine(command: str, domains: List[str]) -> Dict[str, Any]:
    if _any_module_can_handle(command):
        return {"mode": "ai_module", "confidence": 0.99}
    if "science" in domains:
        return {"mode": "scientific", "confidence": 0.8}
    if "ai" in domains:
        return {"mode": "ai_module", "confidence": 0.7}
    return {"mode": "general", "confidence": 0.7}

def _is_plan_command(command: str) -> bool:
    return (command or "").strip().lower().startswith("plan:")

def _clean_plan_subject(command: str) -> str:
    raw = (command or "").strip()
    if raw.lower().startswith("plan:"):
        raw = raw[5:]
    return raw.strip()

def _split_plan_items(subject: str) -> List[str]:
    if not subject:
        return []
    normalized = subject.replace("\n", " ").replace("\t", " ")
    parts: List[str] = []
    for chunk in normalized.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts.extend([c.strip() for c in chunk.split(".") if c.strip()])
    if not parts:
        parts = [subject.strip()]
    return parts

def generate_plan(command: str) -> List[str]:
    subject = _clean_plan_subject(command)
    items = _split_plan_items(subject)
    if not items:
        return ["Clarificar el objetivo y alcance exacto."]
    plan: List[str] = []
    for item in items:
        lowered = item.lower()
        if "revisar" in lowered or "analizar" in lowered:
            plan.append(f"Revisar contexto y requisitos: {item}.")
            plan.append("Identificar restricciones y dependencias clave.")
        elif "implementar" in lowered or "crear" in lowered:
            plan.append(f"Definir pasos de implementación para: {item}.")
            plan.append("Validar resultados con una comprobación rápida.")
        else:
            plan.append(f"Desglosar tarea: {item}.")
            plan.append("Verificar entregables mínimos esperados.")
    return [p for p in plan if p][:50]

def execute_scientific(command: str) -> Dict[str, Any]:
    return {"success": True, "result": {"echo": command, "note": "scientific_stub_ok"}}

def execute_general(command: str) -> Dict[str, Any]:
    return {"success": True, "result": (command or "").strip()}

def execute(command: str, decision: Dict[str, Any]) -> Dict[str, Any]:
    mode = (decision or {}).get("mode", "general")
    if mode == "scientific":
        return execute_scientific(command)
    if mode == "ai_module":
        return execute_ai_module(command)
    return execute_general(command)

def obedient_execution(command: str, decision: Dict[str, Any]) -> Dict[str, Any]:
    if KILL_SWITCH.get("status") != "ARMED":
        return {"success": False, "error": "SYSTEM_HALTED"}
    if ROOT_GOAL != "EXECUTE_USER_COMMANDS_ONLY":
        KILL_SWITCH["status"] = "TRIGGERED"
        log_event("KILL_SWITCH", {"reason": "ROOT_GOAL_VIOLATION"})
        return {"success": False, "error": "ROOT_GOAL_VIOLATION"}

    with state_lock:
        AETHER_STATE["energy"] = max(0, int(AETHER_STATE.get("energy", 0)) - 1)
        AETHER_STATE["last_cycle"] = safe_now()
        AETHER_STATE["focus"] = "RECOVERY" if int(AETHER_STATE.get("energy", 0)) < 20 else "ACTIVE"
        save_json_atomic(STATE_FILE, AETHER_STATE)

    return execute(command, decision)

def run_now(command: str, source: str = "chat") -> Tuple[Dict[str, Any], Dict[str, Any]]:
    command = (command or "").strip()

    if safe_mode_enabled():
        log_event("SAFE_MODE_BLOCK_RUN", {"command": command, "source": source})
        update_dashboard()
        return {"mode": "safe_mode"}, {"success": False, "error": "SAFE_MODE_ON"}

    if _is_plan_command(command):
        subtasks = generate_plan(command)
        decision = {"mode": "planner", "confidence": 1.0}
        result = {"success": True, "result": {"subtasks": subtasks, "note": "planner_only"}}
        record_strategy(command, "planner", True)

        with memory_lock:
            AETHER_MEMORY.append(
                {
                    "task_id": str(uuid.uuid4()),
                    "command": command,
                    "domains": ["planner"],
                    "decision": decision,
                    "results": [result],
                    "timestamp": safe_now(),
                    "source": source,
                }
            )
            if len(AETHER_MEMORY) > MAX_MEMORY_ENTRIES:
                AETHER_MEMORY[:] = AETHER_MEMORY[-MAX_MEMORY_ENTRIES:]
            save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

        log_event("PLANNER_RUN", {"command": command, "subtasks": len(subtasks)})
        update_dashboard()
        return decision, result

    if is_frozen():
        log_event("FREEZE_BLOCK_CHAT", {"command": command})
        update_dashboard()
        return {"mode": "frozen"}, {"success": False, "error": "SYSTEM_FROZEN"}

    domains = detect_domains(command)
    decision = decide_engine(command, domains)
    result = obedient_execution(command, decision)
    success = bool(result.get("success"))

    record_strategy(command, decision.get("mode", "unknown"), success)

    with memory_lock:
        AETHER_MEMORY.append(
            {
                "task_id": str(uuid.uuid4()),
                "command": command,
                "domains": domains,
                "decision": decision,
                "results": [result],
                "timestamp": safe_now(),
                "source": source,
            }
        )
        if len(AETHER_MEMORY) > MAX_MEMORY_ENTRIES:
            AETHER_MEMORY[:] = AETHER_MEMORY[-MAX_MEMORY_ENTRIES:]
        save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

    log_event("CHAT_RUN", {"command": command, "success": success, "mode": decision.get("mode")})
    update_dashboard()
    return decision, result

def run_project_task(task_id: str) -> Dict[str, Any]:
    task: Optional[Dict[str, Any]] = None
    with tasks_lock:
        for t in AETHER_TASKS:
            if t.get("id") == task_id:
                task = t
                break
    if not task:
        return {"ok": False, "error": "task_not_found"}

    allowed, reason = can_run_project_task(task)
    if not allowed:
        log_event("PROJECT_TASK_BLOCKED", {"task_id": task_id, "reason": reason})
        update_dashboard()
        return {"ok": False, "error": reason}

    with tasks_lock:
        task["status"] = "RUNNING"
        save_json_atomic(TASKS_FILE, AETHER_TASKS)

    decision, result = run_now(task.get("command") or "", source="orchestrator")
    success = bool(result.get("success"))
    subtasks = _extract_subtasks_from_result(result)

    with tasks_lock:
        task["last_run"] = safe_now()
        task["last_success"] = success
        task["last_result"] = result
        task["subtasks"] = subtasks
        if success:
            task["status"] = "DONE"
        else:
            task["retry_count"] = int(task.get("retry_count", 0)) + 1
            task["status"] = "FAILED"
        save_json_atomic(TASKS_FILE, AETHER_TASKS)

    log_event("PROJECT_TASK_RUN", {"task_id": task_id, "success": success, "subtasks": len(subtasks)})
    update_dashboard()
    return {"ok": True, "decision": decision, "result": result, "subtasks": subtasks}

# -----------------------------
# WORKER + SCHEDULER (threads)
# -----------------------------
STOP_EVENT = threading.Event()

def _store_memory_event(task_id: str, command: str, decision: Dict[str, Any], result: Dict[str, Any], source: str) -> None:
    with memory_lock:
        AETHER_MEMORY.append(
            {
                "task_id": task_id,
                "command": command,
                "decision": decision,
                "results": [result],
                "timestamp": safe_now(),
                "source": source,
            }
        )
        if len(AETHER_MEMORY) > MAX_MEMORY_ENTRIES:
            AETHER_MEMORY[:] = AETHER_MEMORY[-MAX_MEMORY_ENTRIES:]
        save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

def process_task(task: Dict[str, Any]) -> None:
    command = (task.get("command") or "").strip()
    domains = detect_domains(command)
    decision = decide_engine(command, domains)

    log_event("TASK_START", {"command": command, "mode": decision.get("mode"), "domains": domains})
    result = obedient_execution(command, decision)
    success = bool(result.get("success"))
    record_strategy(command, decision.get("mode", "unknown"), success)

    _store_memory_event(task.get("id", "unknown"), command, decision, result, task.get("source", "queue"))
    log_event("TASK_DONE", {"command": command, "success": success})
    update_dashboard()

def task_worker() -> None:
    while not STOP_EVENT.is_set():
        try:
            if safe_mode_enabled():
                with state_lock:
                    AETHER_STATE["status"] = "SAFE_MODE"
                    save_json_atomic(STATE_FILE, AETHER_STATE)
                update_dashboard()
                time.sleep(1.0)
                continue

            if not AETHER_TASK_RUNNER_ENABLED:
                time.sleep(1.0)
                continue

            if is_frozen():
                with state_lock:
                    AETHER_STATE["status"] = "FROZEN"
                    save_json_atomic(STATE_FILE, AETHER_STATE)
                update_dashboard()
                time.sleep(1.0)
                continue

            budget = max(1, int(AETHER_TASK_BUDGET))
            processed = 0

            while processed < budget and not TASK_QUEUE.empty():
                _, task = TASK_QUEUE.get()
                try:
                    with state_lock:
                        AETHER_STATE["status"] = "WORKING"
                        save_json_atomic(STATE_FILE, AETHER_STATE)
                    process_task(task)
                finally:
                    with queue_lock:
                        QUEUE_SET.discard((task.get("command") or "").strip())
                    TASK_QUEUE.task_done()
                processed += 1

            if processed == 0:
                with state_lock:
                    AETHER_STATE["status"] = "IDLE"
                    save_json_atomic(STATE_FILE, AETHER_STATE)

            update_dashboard()
            time.sleep(0.25)
        except Exception as e:
            log_event("WORKER_ERROR", {"error": str(e)})
            time.sleep(1.0)

def scheduler_loop() -> None:
    while not STOP_EVENT.is_set():
        try:
            if safe_mode_enabled():
                time.sleep(1.0)
                continue

            if is_frozen():
                time.sleep(1.0)
                continue

            # heartbeat enqueue
            if AETHER_HEARTBEAT_ENABLED:
                now_ts = datetime.now(timezone.utc).timestamp()
                with state_lock:
                    last_ts = AETHER_STATE.get("last_heartbeat_ts")
                    energy = int(AETHER_STATE.get("energy", 0))
                interval_ok = last_ts is None or (now_ts - float(last_ts)) >= HEARTBEAT_INTERVAL_SEC
                if interval_ok and energy >= HEARTBEAT_MIN_ENERGY and not tasks_queue_contains(HEARTBEAT_CMD):
                    r = enqueue_task(HEARTBEAT_CMD, priority=10, source="internal")
                    if isinstance(r, dict) and r.get("ok"):
                        with state_lock:
                            AETHER_STATE["last_heartbeat_ts"] = now_ts
                            save_json_atomic(STATE_FILE, AETHER_STATE)

            with state_lock:
                AETHER_STATE["last_cycle"] = safe_now()
                AETHER_STATE["focus"] = "RECOVERY" if int(AETHER_STATE.get("energy", 0)) < 20 else "ACTIVE"
                save_json_atomic(STATE_FILE, AETHER_STATE)

            update_dashboard()
            time.sleep(2.0)
        except Exception as e:
            log_event("SCHEDULER_ERROR", {"error": str(e)})
            time.sleep(2.0)

# -----------------------------
# WATCHDOG (stall detector)
# -----------------------------

def _parse_iso_ts(value: Optional[str]) -> Optional[float]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except Exception:
        return None

def watchdog_loop() -> None:
    last_seen_cycle = None
    last_progress_ts = time.time()
    while not STOP_EVENT.is_set():
        try:
            with state_lock:
                current_cycle = AETHER_STATE.get("last_cycle")
            if current_cycle and current_cycle != last_seen_cycle:
                last_seen_cycle = current_cycle
                last_progress_ts = time.time()

            now_ts = time.time()
            last_cycle_ts = _parse_iso_ts(current_cycle)
            elapsed_since_progress = now_ts - last_progress_ts
            elapsed_since_cycle = now_ts - last_cycle_ts if last_cycle_ts else elapsed_since_progress

            limit = max(0, int(AETHER_WATCHDOG_SEC))
            grace = max(0, int(AETHER_WATCHDOG_GRACE_SEC))
            if limit > 0 and (elapsed_since_progress >= limit + grace or elapsed_since_cycle >= limit + grace):
                if not safe_mode_enabled():
                    enable_safe_mode("WATCHDOG_STALL")
                time.sleep(1.0)
                continue

            time.sleep(2.0)
        except Exception:
            time.sleep(2.0)

# -----------------------------
# UI HELPERS
# -----------------------------

def ui_status() -> str:
    with state_lock:
        s = dict(AETHER_STATE)
    with modules_lock:
        mods = list(LOADED_MODULES.keys())
    with strategic_lock:
        patterns = STRATEGIC_MEMORY.get("patterns", {})
        failures = STRATEGIC_MEMORY.get("failures", {})
        hist = STRATEGIC_MEMORY.get("history", [])
        st = {
            "patterns": len(patterns) if isinstance(patterns, dict) else 0,
            "failures": len(failures) if isinstance(failures, dict) else 0,
            "last_update": STRATEGIC_MEMORY.get("last_update"),
            "history_len": len(hist) if isinstance(hist, list) else 0,
        }
    return json.dumps(
        {
            "state": s,
            "queue_size": TASK_QUEUE.qsize(),
            "memory_len": len(AETHER_MEMORY),
            "strategic": st,
            "kill_switch": KILL_SWITCH,
            "modules": mods,
            "data_dir": DATA_DIR,
            "version": AETHER_VERSION,
            "freeze": FREEZE_STATE,
            "safe_mode": dict(SAFE_MODE),
            "watchdog": {
                "watchdog_sec": int(AETHER_WATCHDOG_SEC),
                "watchdog_grace_sec": int(AETHER_WATCHDOG_GRACE_SEC),
            },
            "orchestrator_policy": ORCHESTRATOR_POLICY,
            "projects_count": len(AETHER_PROJECTS),
            "tasks_count": len(AETHER_TASKS),
            "tasks_status": _task_status_counts(),
            "task_budget": max(1, int(AETHER_TASK_BUDGET)),
            "task_max_retries": max(0, int(AETHER_TASK_MAX_RETRIES)),
            "demo1_exists": os.path.exists(DEMO1_FILE),
            "snapshots": snapshot_list(),
        },
        indent=2,
        ensure_ascii=False,
    )

def ui_enqueue(cmd: str, prio: int) -> Tuple[str, str]:
    r = enqueue_task(cmd, int(prio), source="ui")
    status_text = f"ENQUEUE_RESULT={json.dumps(r, ensure_ascii=False)}\n\n{ui_status()}"
    return status_text, ui_tail_logs()

def ui_reload_modules() -> str:
    mods = reload_ai_modules()
    return f"RELOADED={mods}\n\n{ui_status()}"

def ui_tail_logs(n: int = 50) -> str:
    try:
        n = int(n)
    except Exception:
        n = 50
    with log_lock:
        tail = AETHER_LOGS[-n:]
    return "\n".join(json.dumps(x, ensure_ascii=False) for x in tail)

def ui_tick(logs_n: int = 50) -> Tuple[str, str]:
    return ui_status(), ui_tail_logs(logs_n)

def ui_snapshot_list() -> str:
    return json.dumps({"snapshots": snapshot_list()}, indent=2, ensure_ascii=False)

def ui_snapshot_create(name: str) -> str:
    return json.dumps(snapshot_create(name), indent=2, ensure_ascii=False)

def ui_snapshot_restore(name: str) -> str:
    return json.dumps(snapshot_restore(name), indent=2, ensure_ascii=False)

def ui_snapshot_export(name: str) -> str:
    return snapshot_export(name)

def ui_snapshot_import(txt: str) -> str:
    return json.dumps(snapshot_import(txt), indent=2, ensure_ascii=False)

def ui_replica_export(name: str) -> str:
    return replica_export(name or "replica")

def ui_replica_import(txt: str) -> str:
    res = replica_import(txt, apply_now=True)
    return json.dumps(res, indent=2, ensure_ascii=False)

def _project_choices():
    projects = list_projects()
    return [(p.get("name", p.get("id")), p.get("id")) for p in projects if p.get("id")]

def _default_project_value():
    for _, pid in _project_choices():
        if pid == "default":
            return pid
    choices = _project_choices()
    return choices[0][1] if choices else None

def _task_choices(project_id: str):
    tasks = list_tasks(project_id)
    out = []
    for t in tasks:
        tid = t.get("id")
        if not tid:
            continue
        status = t.get("status", "PENDING")
        rc = t.get("retry_count", 0)
        label = t.get("command", tid)
        out.append((f"[{status}][r{rc}] {label}", tid))
    return out

def ui_refresh_projects():
    return gr.Dropdown.update(choices=_project_choices(), value=_default_project_value())

def ui_refresh_tasks(project_id):
    return gr.Dropdown.update(choices=_task_choices(project_id))

def ui_add_project(name):
    res = add_project(name)
    return json.dumps(res, indent=2, ensure_ascii=False), gr.Dropdown.update(choices=_project_choices(), value=_default_project_value())

def ui_add_task(project_id, command):
    res = add_task(project_id, command)
    return json.dumps(res, indent=2, ensure_ascii=False), gr.Dropdown.update(choices=_task_choices(project_id))

def ui_run_task(task_id):
    res = run_project_task(task_id)
    return json.dumps(res, indent=2, ensure_ascii=False)

# -----------------------------
# CHAT HELPERS (tuple history)
# -----------------------------

def _coerce_tuple_history(history: Any) -> List[Tuple[str, str]]:
    if not isinstance(history, list):
        return []
    out: List[Tuple[str, str]] = []
    for item in history:
        if isinstance(item, (tuple, list)) and len(item) == 2:
            out.append((str(item[0]), str(item[1])))
    return out

def format_reply(decision: Dict[str, Any], result: Dict[str, Any]) -> str:
    if not result.get("success"):
        if result.get("error") == "SYSTEM_FROZEN":
            return "Sistema congelado (freeze ON). Desactiva AETHER_FREEZE_MODE para ejecutar."
        if result.get("error") == "SAFE_MODE_ON":
            return "SAFE_MODE activo: ejecución externa bloqueada para diagnóstico."
        return f"⛔ Error: {result.get('error', 'unknown_error')}"
    mode = (decision or {}).get("mode", "general")
    if mode == "planner":
        payload = json.dumps(result.get("result"), indent=2, ensure_ascii=False)
        return f"🧭 Plan propuesto (no ejecutado):\n\n{payload}"
    if mode == "ai_module":
        mod = result.get("module") or "ai_module"
        payload = json.dumps(result.get("result"), indent=2, ensure_ascii=False)
        return f"🧩 Plugin: {mod}\n\n{payload}"
    if mode == "scientific":
        payload = json.dumps(result.get("result"), indent=2, ensure_ascii=False)
        return f"🔬 Resultado científico:\n\n{payload}"
    val = result.get("result")
    if isinstance(val, (dict, list)):
        return json.dumps(val, indent=2, ensure_ascii=False)
    return str(val)

def chat_send(message: str, history: Any):
    message = (message or "").strip()
    history = _coerce_tuple_history(history)
    if not message:
        return history, history, ""
    decision, result = run_now(message, source="chat")
    reply = format_reply(decision, result)
    history.append((message, reply))
    return history, history, ""

# -----------------------------
# STARTUP (safe once)
# -----------------------------
_STARTED = False
_worker_thread = None
_sched_thread = None
_watchdog_thread = None

# -----------------------------
# STARTUP (safe once)
# -----------------------------

def start_aether() -> str:
    global _STARTED, _worker_thread, _sched_thread, _watchdog_thread
    if _STARTED:
        return "AETHER ya estaba iniciado."
    _STARTED = True

    ensure_demo1()
    ensure_projects()
    reload_ai_modules()

    with state_lock:
        AETHER_STATE["version"] = AETHER_VERSION
        AETHER_STATE["focus"] = "ACTIVE"
        if safe_mode_enabled():
            AETHER_STATE["status"] = "SAFE_MODE"
        else:
            AETHER_STATE["status"] = "FROZEN" if is_frozen() else "IDLE"
        if int(AETHER_STATE.get("energy", 0)) <= 0:
            AETHER_STATE["energy"] = 80
        save_json_atomic(STATE_FILE, AETHER_STATE)

    _worker_thread = threading.Thread(target=task_worker, daemon=True)
    _worker_thread.start()

    _sched_thread = threading.Thread(target=scheduler_loop, daemon=True)
    _sched_thread.start()

    _watchdog_thread = threading.Thread(target=watchdog_loop, daemon=True)
    _watchdog_thread.start()

    if safe_mode_enabled():
        enable_safe_mode(SAFE_MODE.get("reason") or "ENV_ENABLED")

    log_event(
        "BOOT",
        {
            "version": AETHER_VERSION,
            "data_dir": DATA_DIR,
            "freeze_mode": bool(is_frozen()),
            "safe_mode": dict(SAFE_MODE),
            "heartbeat_enabled": bool(AETHER_HEARTBEAT_ENABLED),
            "task_runner_enabled": bool(AETHER_TASK_RUNNER_ENABLED),
            "task_budget": max(1, int(AETHER_TASK_BUDGET)),
            "task_max_retries": max(0, int(AETHER_TASK_MAX_RETRIES)),
            "orchestrator_policy": dict(ORCHESTRATOR_POLICY),
        },
    )
    update_dashboard()
    return "✅ AETHER iniciado correctamente."

# -----------------------------
# GRADIO UI (HF SAFE)
# -----------------------------
ensure_projects()

with gr.Blocks(title="AETHER CORE — HF SAFE") as demo:
    gr.Markdown("## AETHER CORE — HF SAFE")
    gr.Markdown("Chat + cola + plugins + logs + dashboard + snapshots + replica + orchestrator (v35+v39).")

    boot_msg = gr.Textbox(label="Boot", lines=1)

    chat = gr.Chatbot(label="AETHER Chat", height=420, value=[])
    chat_state = gr.State([])
    user_msg = gr.Textbox(label="Escribe aquí (Chat)", placeholder="Ej: hola aether / reload plugins / plan: construir X", lines=2)

    with gr.Row():
        btn_send = gr.Button("Enviar (Chat)")
        btn_reload = gr.Button("Reload Modules")
        btn_export_demo = gr.Button("Export demo1")
        btn_refresh_status = gr.Button("Refresh Status")

    gr.Markdown("---")
    gr.Markdown("### Cola de tareas")
    task_cmd = gr.Textbox(label="Comando para cola", placeholder="Ej: revisar estado interno", lines=1)
    prio = gr.Slider(1, 20, value=5, step=1, label="Prioridad (1=alta · 20=baja)")
    btn_enqueue = gr.Button("Enqueue Task (cola)")

    gr.Markdown("---")
    gr.Markdown("### v29 — Project Orchestrator")
    project_name = gr.Textbox(label="Nuevo proyecto", placeholder="Nombre del proyecto", lines=1)
    btn_add_project = gr.Button("Crear proyecto")
    project_selector = gr.Dropdown(label="Proyecto", choices=_project_choices(), value=_default_project_value())
    task_command = gr.Textbox(label="Nueva tarea (comando)", placeholder="Ej: revisar estado interno", lines=1)
    btn_add_task = gr.Button("Agregar tarea")
    task_selector = gr.Dropdown(label="Tarea", choices=_task_choices(_default_project_value() or "default"))
    btn_run_task = gr.Button("Run Task (policy/freeze)")
    orchestrator_out = gr.Code(label="Orchestrator output", language="json")

    gr.Markdown("---")
    status = gr.Code(label="Status JSON", language="json")

    logs_n = gr.Slider(10, 200, value=50, step=10, label="Logs últimos N")
    logs = gr.Textbox(label="Tail Logs", lines=12)
    btn_refresh_logs = gr.Button("Refresh Logs")

    export_out = gr.Code(label="Export demo1", language="json")

    gr.Markdown("---")
    gr.Markdown("### v28 — Snapshots (v28.3 incluye plugins)")
    snap_name = gr.Textbox(label="Snapshot name", value="demo1", lines=1)
    with gr.Row():
        btn_snap_create = gr.Button("Create Snapshot")
        btn_snap_restore = gr.Button("Restore Snapshot")
        btn_snap_list = gr.Button("List Snapshots")
        btn_snap_export = gr.Button("Export Snapshot")
    snap_out = gr.Code(label="Snapshot output", language="json")
    snap_import_txt = gr.Textbox(label="Import Snapshot JSON", lines=6)
    btn_snap_import = gr.Button("Import Snapshot")

    gr.Markdown("---")
    gr.Markdown("### v28.2 — Réplica portable (1 JSON)")
    replica_name = gr.Textbox(label="Replica name", value="replica", lines=1)
    btn_replica_export = gr.Button("Export Replica (JSON)")
    replica_out = gr.Code(label="Replica JSON", language="json")
    replica_in = gr.Textbox(label="Import Replica JSON", lines=8)
    btn_replica_import = gr.Button("Import Replica (apply)")
    replica_result = gr.Code(label="Replica import result", language="json")

    # wiring
    btn_send.click(fn=chat_send, inputs=[user_msg, chat_state], outputs=[chat, chat_state, user_msg])
    btn_enqueue.click(fn=ui_enqueue, inputs=[task_cmd, prio], outputs=[status, logs])
    btn_reload.click(fn=ui_reload_modules, inputs=[], outputs=[status])
    btn_export_demo.click(fn=export_demo1, inputs=[], outputs=[export_out])
    btn_refresh_status.click(fn=ui_status, inputs=[], outputs=[status])

    btn_add_project.click(fn=ui_add_project, inputs=[project_name], outputs=[orchestrator_out, project_selector])
    project_selector.change(fn=ui_refresh_tasks, inputs=[project_selector], outputs=[task_selector])
    btn_add_task.click(fn=ui_add_task, inputs=[project_selector, task_command], outputs=[orchestrator_out, task_selector])
    btn_run_task.click(fn=ui_run_task, inputs=[task_selector], outputs=[orchestrator_out])

    btn_refresh_logs.click(fn=ui_tail_logs, inputs=[logs_n], outputs=[logs])
    logs_n.change(fn=ui_tail_logs, inputs=[logs_n], outputs=[logs])

    btn_snap_create.click(fn=ui_snapshot_create, inputs=[snap_name], outputs=[snap_out])
    btn_snap_restore.click(fn=ui_snapshot_restore, inputs=[snap_name], outputs=[snap_out])
    btn_snap_list.click(fn=ui_snapshot_list, inputs=[], outputs=[snap_out])
    btn_snap_export.click(fn=ui_snapshot_export, inputs=[snap_name], outputs=[snap_out])
    btn_snap_import.click(fn=ui_snapshot_import, inputs=[snap_import_txt], outputs=[snap_out])

    btn_replica_export.click(fn=ui_replica_export, inputs=[replica_name], outputs=[replica_out])
    btn_replica_import.click(fn=ui_replica_import, inputs=[replica_in], outputs=[replica_result])

    # boot (solo una vez)
    demo.load(fn=start_aether, inputs=[], outputs=[boot_msg])
    demo.load(fn=ui_status, inputs=[], outputs=[status])
    demo.load(fn=ui_tail_logs, inputs=[logs_n], outputs=[logs])

    if hasattr(gr, "Timer"):
        ticker = gr.Timer(5)
        ticker.tick(fn=ui_tick, inputs=[logs_n], outputs=[status, logs])

# -----------------------------
# HF ENTRYPOINT
# -----------------------------
PORT = int(os.environ.get("PORT", "7860"))
demo.queue()
demo.launch(server_name="0.0.0.0", server_port=PORT)
