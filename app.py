# ======================================================
# AETHER CORE — PRO TOTAL (HF SPACES) — GRADIO ONLY (NO FASTAPI)
# Objetivo: 0 runtime-crash en HF.
# Incluye:
#   - Chat compatible con gradio clásico (tuplas usuario/asistente)
#   - Cola + scheduler
#   - Plugins hot-reload *_ai.py
#   - Logs + dashboard + demo1 export
# ======================================================

import os
import json
import uuid
import threading
import importlib.util
import sys
from queue import PriorityQueue
from datetime import datetime, timezone

import numpy as np
import gradio as gr

# -----------------------------
# TIME (timezone-aware)
# -----------------------------
def safe_now():
    return datetime.now(timezone.utc).isoformat()

# -----------------------------
# ENV HELPERS
# -----------------------------
def env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "y", "on", "t"}:
        return True
    if value in {"0", "false", "no", "n", "off", "f"}:
        return False
    return bool(default)

# -----------------------------
# DIRECTORIO DE DATOS (HF-safe)
# -----------------------------
DATA_DIR = os.environ.get("AETHER_DATA_DIR", "/tmp/aether")
os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------
# VERSIONADO Y ARCHIVOS
# -----------------------------
AETHER_VERSION = "3.5.2-heartbeat-switch"

STATE_FILE = os.path.join(DATA_DIR, "aether_state.json")
MEMORY_FILE = os.path.join(DATA_DIR, "aether_memory.json")
STRATEGIC_FILE = os.path.join(DATA_DIR, "aether_strategic.json")
LOG_FILE = os.path.join(DATA_DIR, "aether_log.json")
DASHBOARD_FILE = os.path.join(DATA_DIR, "aether_dashboard.json")
DEMO1_FILE = os.path.join(DATA_DIR, "demo1.json")

MODULES_DIR = "plugins"
os.makedirs(MODULES_DIR, exist_ok=True)

MAX_MEMORY_ENTRIES = 500
MAX_LOG_ENTRIES = 1000
MAX_STRATEGY_HISTORY = 1000

MAX_DEDUP_KEYS = 5000

# -----------------------------
# HEARTBEAT CONFIG
# -----------------------------
HEARTBEAT_CMD = "revisar estado interno"
HEARTBEAT_INTERVAL_SEC = int(os.environ.get("AETHER_HEARTBEAT_SEC", "120"))
HEARTBEAT_MIN_ENERGY = int(os.environ.get("AETHER_HEARTBEAT_MIN_ENERGY", "40"))
AETHER_HEARTBEAT_ENABLED = env_bool("AETHER_HEARTBEAT_ENABLED", True)

# -----------------------------
# ESTADO GLOBAL
# -----------------------------
DEFAULT_STATE = {
    "id": "AETHER",
    "version": AETHER_VERSION,
    "status": "IDLE",
    "energy": 100,
    "focus": "STANDBY",
    "created_at": safe_now(),
    "last_cycle": None,
    "last_heartbeat_ts": None,
}

ROOT_GOAL = "EXECUTE_USER_COMMANDS_ONLY"
KILL_SWITCH = {"enabled": True, "status": "ARMED"}

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

# -----------------------------
# JSON IO (robusto + atómico)
# -----------------------------
def load_json(path, default):
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

def save_json_atomic(path, data):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

# -----------------------------
# CARGA INICIAL
# -----------------------------
AETHER_STATE = load_json(STATE_FILE, DEFAULT_STATE.copy())
AETHER_MEMORY = load_json(MEMORY_FILE, [])
STRATEGIC_MEMORY = load_json(
    STRATEGIC_FILE,
    {"patterns": {}, "failures": {}, "history": [], "last_update": None},
)
AETHER_LOGS = load_json(LOG_FILE, [])
LOADED_MODULES = {}

if "last_heartbeat_ts" not in AETHER_STATE:
    AETHER_STATE["last_heartbeat_ts"] = None
    save_json_atomic(STATE_FILE, AETHER_STATE)

# -----------------------------
# DEMO SNAPSHOT (auto-creación)
# -----------------------------
def ensure_demo1():
    if os.path.exists(DEMO1_FILE):
        return True
    try:
        save_json_atomic(
            DEMO1_FILE,
            {"name": "demo1", "created_at": safe_now(), "events": [], "notes": "auto-created"},
        )
        return True
    except Exception:
        return False

def export_demo1():
    try:
        if not os.path.exists(DEMO1_FILE):
            ensure_demo1()
        payload = load_json(DEMO1_FILE, {"ok": False, "error": "demo1_missing"})
        return json.dumps({"ok": True, "demo": payload}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, indent=2, ensure_ascii=False)

# -----------------------------
# LOGS + DASHBOARD
# -----------------------------
def log_event(t, info):
    entry = {"timestamp": safe_now(), "type": t, "info": info}
    with log_lock:
        AETHER_LOGS.append(entry)
        if len(AETHER_LOGS) > MAX_LOG_ENTRIES:
            AETHER_LOGS[:] = AETHER_LOGS[-MAX_LOG_ENTRIES:]
        save_json_atomic(LOG_FILE, AETHER_LOGS)

def update_dashboard():
    with state_lock:
        snap = dict(AETHER_STATE)
    dash = {
        "energy": snap.get("energy", 0),
        "focus": snap.get("focus", "STANDBY"),
        "status": snap.get("status", "IDLE"),
        "queue_size": TASK_QUEUE.qsize(),
        "last_cycle": snap.get("last_cycle"),
        "version": AETHER_VERSION,
        "data_dir": DATA_DIR,
        "modules_loaded": len(LOADED_MODULES),
    }
    save_json_atomic(DASHBOARD_FILE, dash)

# -----------------------------
# COLA DE TAREAS
# -----------------------------
TASK_QUEUE = PriorityQueue()

TASK_DEDUP = []
TASK_DEDUP_SET = set()
QUEUE_SET = set()

def tasks_queue_contains(command: str) -> bool:
    command = (command or "").strip()
    if not command:
        return False
    with queue_lock:
        return command in QUEUE_SET

def _dedup_prune_if_needed():
    with dedup_lock:
        if len(TASK_DEDUP) <= MAX_DEDUP_KEYS:
            return
        keep = int(MAX_DEDUP_KEYS * 0.7)
        old = TASK_DEDUP[:-keep]
        TASK_DEDUP[:] = TASK_DEDUP[-keep:]
        for k in old:
            TASK_DEDUP_SET.discard(k)

def compute_priority(base):
    with state_lock:
        e = int(AETHER_STATE.get("energy", 0))
    return int(base) + (3 if e < 20 else 0)

def enqueue_task(command, priority=5, source="external"):
    command = (command or "").strip()
    if not command:
        return {"ok": False, "error": "empty_command"}

    if (
        not AETHER_HEARTBEAT_ENABLED
        and command.lower().strip() == HEARTBEAT_CMD
    ):
        log_event(
            "HEARTBEAT_DISABLED",
            {"message": "Heartbeat DISABLED: blocked enqueue of 'revisar estado interno'"},
        )
        return {"ok": False, "blocked": True, "reason": "heartbeat_disabled"}

    # DEDUP solo para external
    if source != "internal":
        key = f"{command}:{source}"
        with dedup_lock:
            if key in TASK_DEDUP_SET:
                return {"ok": False, "dedup": True}
            TASK_DEDUP_SET.add(key)
            TASK_DEDUP.append(key)
        _dedup_prune_if_needed()

    dyn = compute_priority(priority)
    with queue_lock:
        QUEUE_SET.add(command)
    TASK_QUEUE.put(
        (
            dyn,
            {"id": str(uuid.uuid4()), "command": command, "source": source, "created_at": safe_now()},
        )
    )
    log_event("ENQUEUE", {"command": command, "priority": dyn, "source": source})
    update_dashboard()
    return {"ok": True}

# -----------------------------
# DOMINIOS + DECISIÓN
# -----------------------------
def detect_domains(command):
    c = (command or "").lower()
    d = set()
    if any(k in c for k in ["física", "ecuación", "modelo", "simulación", "simular"]):
        d.add("science")
    if c.startswith("task ") or "reload" in c or "plugin" in c or "plugins" in c:
        d.add("ai")
    if any(k in c for k in ["ia", "algoritmo", "llm", "embedding", "hola", "hello"]):
        d.add("ai")
    return list(d) or ["general"]

def _any_module_can_handle(command: str) -> bool:
    c = (command or "").strip()
    if not c:
        return False
    with modules_lock:
        mods = list(LOADED_MODULES.values())
    for mod in mods:
        try:
            if hasattr(mod, "can_handle") and mod.can_handle(c):
                return True
        except Exception:
            continue
    return False

def decide_engine(command, domains):
    if _any_module_can_handle(command):
        return {"mode": "ai_module", "confidence": 0.99}
    if "science" in domains:
        return {"mode": "scientific", "confidence": 0.9}
    if "ai" in domains:
        return {"mode": "ai_module", "confidence": 0.95}
    return {"mode": "general", "confidence": 0.7}

# -----------------------------
# EJECUTORES
# -----------------------------
def execute_scientific(_command):
    try:
        t = np.linspace(0, 10, 200)
        a, v0, x0 = 2.0, 1.0, 0.0
        x = x0 + v0 * t + 0.5 * a * t**2
        return {"success": True, "result": {"final_position": float(x[-1]), "stability": float(np.std(x))}}
    except Exception as e:
        return {"success": False, "error": str(e)}

def execute_general(command):
    return {"success": True, "result": (command or "").upper()}

# -----------------------------
# PLUGINS HOT-RELOAD
# -----------------------------
def reload_ai_modules():
    loaded = {}
    try:
        files = os.listdir(MODULES_DIR)
    except Exception:
        files = []

    for fn in files:
        if not fn.endswith("_ai.py") or fn.startswith("_"):
            continue

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

            if hasattr(mod, "can_handle") and hasattr(mod, "run"):
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

def execute_ai_module(command):
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

def execute(command, decision):
    mode = decision.get("mode", "general")
    if mode == "scientific":
        return execute_scientific(command)
    if mode == "ai_module":
        return execute_ai_module(command)
    return execute_general(command)

# -----------------------------
# OBEDIENCIA + KILL SWITCH
# -----------------------------
def obedient_execution(command, decision):
    if KILL_SWITCH["status"] != "ARMED":
        return {"success": False, "error": "SYSTEM_HALTED"}

    if ROOT_GOAL != "EXECUTE_USER_COMMANDS_ONLY":
        KILL_SWITCH["status"] = "TRIGGERED"
        log_event("KILL_SWITCH", {"reason": "ROOT_GOAL_VIOLATION"})
        return {"success": False, "error": "ROOT_GOAL_VIOLATION"}

    with state_lock:
        AETHER_STATE["energy"] = max(0, int(AETHER_STATE.get("energy", 0)) - 1)
        save_json_atomic(STATE_FILE, AETHER_STATE)

    return execute(command, decision)

# -----------------------------
# ESTRATEGIA
# -----------------------------
def record_strategy(command, mode, success):
    sig = f"{mode}:{len((command or '').split())}"
    target = "patterns" if success else "failures"
    with strategic_lock:
        STRATEGIC_MEMORY[target][sig] = STRATEGIC_MEMORY[target].get(sig, 0) + 1
        STRATEGIC_MEMORY["history"].append(
            {"timestamp": safe_now(), "command": command, "mode": mode, "success": bool(success)}
        )
        if len(STRATEGIC_MEMORY["history"]) > MAX_STRATEGY_HISTORY:
            STRATEGIC_MEMORY["history"] = STRATEGIC_MEMORY["history"][-MAX_STRATEGY_HISTORY:]
        STRATEGIC_MEMORY["last_update"] = safe_now()
        save_json_atomic(STRATEGIC_FILE, STRATEGIC_MEMORY)

# -----------------------------
# CICLO VITAL
# -----------------------------
def life_cycle():
    with state_lock:
        AETHER_STATE["last_cycle"] = safe_now()
        AETHER_STATE["focus"] = "RECOVERY" if int(AETHER_STATE.get("energy", 0)) < 20 else "ACTIVE"
        save_json_atomic(STATE_FILE, AETHER_STATE)
    update_dashboard()
    log_event("CYCLE", {"energy": AETHER_STATE.get("energy", 0), "focus": AETHER_STATE.get("focus")})

# -----------------------------
# WORKER + SCHEDULER (tick-driven)
# -----------------------------
SCHEDULER_INTERVAL = 15

def process_task(task):
    command = task["command"]
    domains = detect_domains(command)
    decision = decide_engine(command, domains)

    log_event("TASK_START", {"command": command, "mode": decision.get("mode"), "domains": domains})

    result = obedient_execution(command, decision)
    success = bool(result.get("success"))

    record_strategy(command, decision.get("mode", "unknown"), success)

    with memory_lock:
        AETHER_MEMORY.append(
            {
                "task_id": task["id"],
                "command": command,
                "domains": domains,
                "decision": decision,
                "results": [result],
                "timestamp": safe_now(),
                "source": task.get("source"),
            }
        )
        if len(AETHER_MEMORY) > MAX_MEMORY_ENTRIES:
            AETHER_MEMORY[:] = AETHER_MEMORY[-MAX_MEMORY_ENTRIES:]
        save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

    log_event("TASK_DONE", {"command": command, "success": success})
    update_dashboard()

def process_queue_once():
    try:
        if not TASK_QUEUE.empty():
            _, task = TASK_QUEUE.get()
            with state_lock:
                AETHER_STATE["status"] = "WORKING"
                save_json_atomic(STATE_FILE, AETHER_STATE)
            try:
                process_task(task)
            finally:
                with queue_lock:
                    QUEUE_SET.discard(task.get("command"))
                TASK_QUEUE.task_done()
        else:
            with state_lock:
                AETHER_STATE["status"] = "IDLE"
                save_json_atomic(STATE_FILE, AETHER_STATE)
        update_dashboard()
    except Exception as e:
        log_event("WORKER_ERROR", {"error": str(e)})
    return ui_status()

def scheduler_tick():
    try:
        if not AETHER_HEARTBEAT_ENABLED:
            return ui_status()
        life_cycle()
        now_ts = datetime.now(timezone.utc).timestamp()
        with state_lock:
            last_ts = AETHER_STATE.get("last_heartbeat_ts")
            energy = int(AETHER_STATE.get("energy", 0))
        interval_ok = last_ts is None or (now_ts - float(last_ts)) >= HEARTBEAT_INTERVAL_SEC
        if (
            interval_ok
            and energy >= HEARTBEAT_MIN_ENERGY
            and not tasks_queue_contains(HEARTBEAT_CMD)
        ):
            enqueue_result = enqueue_task(HEARTBEAT_CMD, priority=10, source="internal")
            if enqueue_result.get("ok"):
                with state_lock:
                    AETHER_STATE["last_heartbeat_ts"] = now_ts
                    save_json_atomic(STATE_FILE, AETHER_STATE)
    except Exception as e:
        log_event("SCHEDULER_ERROR", {"error": str(e)})
    return ui_status()

# -----------------------------
# ARRANQUE SEGURO (solo una vez)
# -----------------------------
_STARTED = False

def start_aether():
    global _STARTED
    if _STARTED:
        return "AETHER ya estaba iniciado."
    _STARTED = True

    ensure_demo1()
    reload_ai_modules()
    if not AETHER_HEARTBEAT_ENABLED:
        log_event(
            "HEARTBEAT_DISABLED",
            {"message": "Heartbeat DISABLED via env: skipping boot enqueue"},
        )
    with state_lock:
        if int(AETHER_STATE.get("energy", 0)) <= 0:
            AETHER_STATE["energy"] = 80
            AETHER_STATE["focus"] = "ACTIVE"
            AETHER_STATE["status"] = "IDLE"
            save_json_atomic(STATE_FILE, AETHER_STATE)

    log_event("BOOT", {"version": AETHER_VERSION, "data_dir": DATA_DIR})
    update_dashboard()
    return "✅ AETHER iniciado correctamente."

# -----------------------------
# CHAT (sync)
# -----------------------------
def run_now(command: str):
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
                "source": "chat",
            }
        )
        if len(AETHER_MEMORY) > MAX_MEMORY_ENTRIES:
            AETHER_MEMORY[:] = AETHER_MEMORY[-MAX_MEMORY_ENTRIES:]
        save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

    log_event("CHAT_RUN", {"command": command, "success": success, "mode": decision.get("mode")})
    update_dashboard()
    return decision, result

def format_reply(decision, result):
    if not result.get("success"):
        return f"⛔ Error: {result.get('error', 'unknown_error')}"
    mode = decision.get("mode", "general")
    if mode == "ai_module":
        mod = result.get("module") or "ai_module"
        payload = json.dumps(result.get("result"), indent=2, ensure_ascii=False)
        return f"🧩 Plugin: {mod}\n\n{payload}"
    if mode == "scientific":
        payload = json.dumps(result.get("result"), indent=2, ensure_ascii=False)
        return f"🔬 Resultado científico:\n\n{payload}"
    return str(result.get("result"))

def _coerce_tuple_history(history):
    if not isinstance(history, list):
        return []
    normalized = []
    for item in history:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            normalized.append((str(item[0]), str(item[1])))
    return normalized

def chat_send(message, history):
    message = (message or "").strip()
    history = _coerce_tuple_history(history)
    if not message:
        return history, history, ""
    decision, result = run_now(message)
    reply = format_reply(decision, result)
    history.append((message, reply))
    return history, history, ""

# -----------------------------
# UI HELPERS
# -----------------------------
def ui_status():
    with state_lock:
        s = dict(AETHER_STATE)
    with strategic_lock:
        st = {
            "patterns": len(STRATEGIC_MEMORY.get("patterns", {})),
            "failures": len(STRATEGIC_MEMORY.get("failures", {})),
            "last_update": STRATEGIC_MEMORY.get("last_update"),
            "history_len": len(STRATEGIC_MEMORY.get("history", [])),
        }
    with modules_lock:
        mods = list(LOADED_MODULES.keys())
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
            "demo1_exists": os.path.exists(DEMO1_FILE),
        },
        indent=2,
        ensure_ascii=False,
    )

def ui_enqueue(cmd, prio):
    result = enqueue_task(cmd, prio, source="external")
    return f"ENQUEUED={result.get('ok')}\n\n" + ui_status()

def ui_reload_modules():
    mods = reload_ai_modules()
    return f"RELOADED={mods}\n\n" + ui_status()

def ui_tail_logs(n=50):
    try:
        n = int(n)
    except Exception:
        n = 50
    with log_lock:
        tail = AETHER_LOGS[-n:]
    return "\n".join(json.dumps(x, ensure_ascii=False) for x in tail)

# -----------------------------
# GRADIO UI (HF SAFE)
# -----------------------------
with gr.Blocks(title="AETHER CORE — PRO TOTAL") as demo:
    gr.Markdown("## AETHER CORE — PRO TOTAL")
    gr.Markdown("Chat + cola + plugins hot-reload + logs + dashboard.")

    boot_msg = gr.Textbox(label="Boot", lines=1)

    chat = gr.Chatbot(label="AETHER Chat", height=420, value=[], type="tuple")
    chat_state = gr.State([])
    user_msg = gr.Textbox(label="Escribe aquí (Chat)", placeholder="Ej: hola aether / reload plugins", lines=2)

    with gr.Row():
        btn_send = gr.Button("Enviar (Chat)")
        btn_reload = gr.Button("Reload Modules")
        btn_export_demo = gr.Button("Export demo1")

    gr.Markdown("---")
    gr.Markdown("### Cola de tareas (separado del chat)")
    task_cmd = gr.Textbox(label="Comando para cola", placeholder="Ej: revisar estado interno", lines=1)
    prio = gr.Slider(1, 20, value=5, step=1, label="Prioridad (1=alta · 20=baja)")
    btn_enqueue = gr.Button("Enqueue Task (cola)")

    status = gr.Code(label="Status JSON", language="json")

    logs_n = gr.Slider(10, 200, value=50, step=10, label="Logs últimos N")
    logs = gr.Textbox(label="Tail Logs", lines=12)
    btn_refresh_logs = gr.Button("Refresh Logs")

    export_out = gr.Code(label="Export demo1", language="json")

    btn_send.click(fn=chat_send, inputs=[user_msg, chat_state], outputs=[chat, chat_state, user_msg])
    btn_enqueue.click(fn=ui_enqueue, inputs=[task_cmd, prio], outputs=[status])
    btn_reload.click(fn=ui_reload_modules, inputs=[], outputs=[status])
    btn_export_demo.click(fn=export_demo1, inputs=[], outputs=[export_out])

    btn_refresh_logs.click(fn=ui_tail_logs, inputs=[logs_n], outputs=[logs])
    logs_n.change(fn=ui_tail_logs, inputs=[logs_n], outputs=[logs])

    demo.load(fn=start_aether, inputs=[], outputs=[boot_msg])
    demo.load(fn=ui_status, inputs=[], outputs=[status])
    demo.load(fn=ui_tail_logs, inputs=[logs_n], outputs=[logs])
    demo.load(fn=process_queue_once, inputs=[], outputs=[status], every=2)
    demo.load(fn=scheduler_tick, inputs=[], outputs=[status], every=SCHEDULER_INTERVAL)

# -----------------------------
# HF ENTRYPOINT
# -----------------------------
# En Spaces, esto es lo más estable:
# - NO uvicorn.run
# - NO mounts
PORT = int(os.environ.get("PORT", "7860"))
demo.queue()
demo.launch(server_name="0.0.0.0", server_port=PORT)
