# ======================================================
# AETHER CORE — HF SPACES FIXED (PRO TOTAL) + CHAT (GRADIO "messages" DEFAULT)
#   CORREGIDO: loader *_ai.py + plugins can_handle/run + decide_engine por plugins
#   CORREGIDO: FastAPI + Gradio:
#       - /api/* = API (incluye /api/health)
#       - /ui    = Gradio UI
#       - /      = redirect a /ui (HF no muestra Not Found)
# ======================================================

import os
import time
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
# DIRECTORIO DE DATOS (HF-safe)
# -----------------------------
DATA_DIR = os.environ.get("AETHER_DATA_DIR", "/tmp/aether")
os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------
# VERSIONADO Y ARCHIVOS
# -----------------------------
AETHER_VERSION = "3.4.5-pro-total-hf-chat-messages"

STATE_FILE = os.path.join(DATA_DIR, "aether_state.json")
MEMORY_FILE = os.path.join(DATA_DIR, "aether_memory.json")
STRATEGIC_FILE = os.path.join(DATA_DIR, "aether_strategic.json")
LOG_FILE = os.path.join(DATA_DIR, "aether_log.json")
DASHBOARD_FILE = os.path.join(DATA_DIR, "aether_dashboard.json")

MODULES_DIR = "plugins"  # dentro del repo
os.makedirs(MODULES_DIR, exist_ok=True)

MAX_MEMORY_ENTRIES = 500
MAX_LOG_ENTRIES = 1000
MAX_STRATEGY_HISTORY = 1000

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

# -----------------------------
# JSON IO (atómico)
# -----------------------------
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
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
    }
    save_json_atomic(DASHBOARD_FILE, dash)

# -----------------------------
# COLA DE TAREAS
# -----------------------------
TASK_QUEUE = PriorityQueue()
TASK_DEDUP = set()

def compute_priority(base):
    with state_lock:
        e = int(AETHER_STATE.get("energy", 0))
    return base + 5 if e < 20 else base

def enqueue_task(command, priority=5, source="external"):
    command = (command or "").strip()
    if not command:
        return False

    key = f"{command}:{source}"
    if key in TASK_DEDUP:
        return False

    TASK_DEDUP.add(key)
    dyn = compute_priority(int(priority))
    TASK_QUEUE.put(
        (
            dyn,
            {
                "id": str(uuid.uuid4()),
                "command": command,
                "source": source,
                "created_at": safe_now(),
            },
        )
    )
    log_event("ENQUEUE", {"command": command, "priority": dyn, "source": source})
    update_dashboard()
    return True

# -----------------------------
# DOMINIOS + DECISIÓN
# -----------------------------
def detect_domains(command):
    c = (command or "").lower()
    d = set()

    # ciencia
    if any(k in c for k in ["física", "ecuación", "modelo", "simulación", "simular"]):
        d.add("science")

    # comandos / plugins (clave para "task a" y "reload plugins")
    if c.startswith("task ") or "reload" in c or "plugin" in c or "plugins" in c or "modulos" in c or "módulos" in c:
        d.add("ai")

    # texto común
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
    # Si cualquier plugin lo puede manejar, SIEMPRE usa ai_module
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
        return {
            "success": True,
            "result": {"final_position": float(x[-1]), "stability": float(np.std(x))},
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def execute_general(command):
    return {"success": True, "result": (command or "").upper()}

# -----------------------------
# MÓDULOS IA HOT-RELOAD (CORREGIDO)
# -----------------------------
def reload_ai_modules():
    loaded = {}
    for fn in os.listdir(MODULES_DIR):
        if not fn.endswith("_ai.py"):
            continue
        if fn.startswith("_"):
            continue

        name = fn[:-3]  # sin .py
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
        AETHER_STATE["focus"] = "RECOVERY" if AETHER_STATE["energy"] < 20 else "ACTIVE"
        save_json_atomic(STATE_FILE, AETHER_STATE)
    update_dashboard()
    log_event("CYCLE", {"energy": AETHER_STATE["energy"], "focus": AETHER_STATE["focus"]})

# -----------------------------
# WORKER + SCHEDULER
# -----------------------------
STOP_EVENT = threading.Event()
SCHEDULER_INTERVAL = 15

def process_task(task):
    command = task["command"]
    domains = detect_domains(command)
    decision = decide_engine(command, domains)

    steps = ["analizar solicitud", "ejecutar", "validar"]
    results = [obedient_execution(f"{command} :: {step}", decision) for step in steps]

    success = all(r.get("success") for r in results)
    record_strategy(command, decision["mode"], success)

    with memory_lock:
        AETHER_MEMORY.append(
            {
                "task_id": task["id"],
                "command": command,
                "domains": domains,
                "decision": decision,
                "results": results,
                "timestamp": safe_now(),
            }
        )
        if len(AETHER_MEMORY) > MAX_MEMORY_ENTRIES:
            AETHER_MEMORY[:] = AETHER_MEMORY[-MAX_MEMORY_ENTRIES:]
        save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

    log_event("TASK_DONE", {"command": command, "success": success})
    update_dashboard()

def task_worker():
    while not STOP_EVENT.is_set():
        try:
            if not TASK_QUEUE.empty():
                _, task = TASK_QUEUE.get()
                with state_lock:
                    AETHER_STATE["status"] = "WORKING"
                    save_json_atomic(STATE_FILE, AETHER_STATE)
                process_task(task)
                TASK_QUEUE.task_done()
            else:
                with state_lock:
                    AETHER_STATE["status"] = "IDLE"
                    save_json_atomic(STATE_FILE, AETHER_STATE)
            update_dashboard()
            time.sleep(1)
        except Exception as e:
            log_event("WORKER_ERROR", {"error": str(e)})
            time.sleep(1)

def scheduler_loop():
    while not STOP_EVENT.is_set():
        try:
            life_cycle()
            enqueue_task("revisar estado interno", priority=10, source="internal")
            time.sleep(SCHEDULER_INTERVAL)
        except Exception as e:
            log_event("SCHEDULER_ERROR", {"error": str(e)})
            time.sleep(2)

# -----------------------------
# ARRANQUE SEGURO (solo una vez)
# -----------------------------
_STARTED = False

def start_aether():
    global _STARTED
    if _STARTED:
        return "AETHER ya estaba iniciado."
    _STARTED = True

    reload_ai_modules()
    threading.Thread(target=task_worker, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()

    log_event("BOOT", {"version": AETHER_VERSION, "data_dir": DATA_DIR})
    update_dashboard()
    return "✅ AETHER iniciado correctamente."

# -----------------------------
# CHAT SÍNCRONO (visible)
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
        },
        indent=2,
        ensure_ascii=False,
    )

def ui_enqueue(cmd, prio):
    ok = enqueue_task(cmd, prio, source="external")
    return f"ENQUEUED={ok}\n\n" + ui_status()

def ui_reload_modules():
    mods = reload_ai_modules()
    return f"RELOADED={mods}\n\n" + ui_status()

def ui_tail_logs(n=50):
    with log_lock:
        tail = AETHER_LOGS[-int(n):]
    return "\n".join(json.dumps(x, ensure_ascii=False) for x in tail)

# ======================================================
# CHATBOT: FORMATO "messages"
# ======================================================
def _normalize_history_to_messages(history):
    if not history:
        return []
    out = []
    for item in history:
        if isinstance(item, dict) and "role" in item and "content" in item:
            out.append({"role": str(item["role"]), "content": str(item["content"])})
            continue
        if isinstance(item, (tuple, list)) and len(item) == 2:
            u, a = item
            out.append({"role": "user", "content": "" if u is None else str(u)})
            out.append({"role": "assistant", "content": "" if a is None else str(a)})
            continue
        out.append({"role": "system", "content": str(item)})
    return out

def chat_send(message, history):
    message = (message or "").strip()
    if not message:
        return history, ""

    history = _normalize_history_to_messages(history)

    decision, result = run_now(message)
    reply = format_reply(decision, result)

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})

    return history, ""

# -----------------------------
# GRADIO UI
# -----------------------------
with gr.Blocks(title="AETHER CORE — PRO TOTAL") as demo:
    gr.Markdown("## AETHER CORE — PRO TOTAL")
    gr.Markdown("Chat + cola + plugins hot-reload + logs + dashboard.")

    boot_msg = gr.Textbox(label="Boot", lines=1)

    chat = gr.Chatbot(label="AETHER Chat", height=420)
    user_msg = gr.Textbox(
        label="Escribe aquí",
        placeholder="Ej: hola aether / task a / task last / reload plugins",
        lines=2,
    )

    with gr.Row():
        btn_send = gr.Button("Enviar (Chat)")
        prio = gr.Slider(1, 20, value=5, step=1, label="Prioridad (cola) 1=alta")
        btn_enqueue = gr.Button("Enqueue Task (cola)")
        btn_reload = gr.Button("Reload Modules")

    status = gr.Code(label="Status JSON", language="json")

    logs_n = gr.Slider(10, 200, value=50, step=10, label="Logs últimos N")
    logs = gr.Textbox(label="Tail Logs", lines=12)
    btn_refresh_logs = gr.Button("Refresh Logs")

    btn_send.click(fn=chat_send, inputs=[user_msg, chat], outputs=[chat, user_msg])
    btn_enqueue.click(fn=ui_enqueue, inputs=[user_msg, prio], outputs=[status])
    btn_reload.click(fn=ui_reload_modules, inputs=[], outputs=[status])

    btn_refresh_logs.click(fn=ui_tail_logs, inputs=[logs_n], outputs=[logs])
    logs_n.change(fn=ui_tail_logs, inputs=[logs_n], outputs=[logs])

    demo.load(fn=start_aether, inputs=[], outputs=[boot_msg])
    demo.load(fn=ui_status, inputs=[], outputs=[status])
    demo.load(fn=ui_tail_logs, inputs=[logs_n], outputs=[logs])

# -----------------------------
# SERVIDOR: FastAPI (root) + API + Gradio (/ui) + redirect (/ -> /ui)
# -----------------------------
PORT = int(os.environ.get("PORT", "7860"))

try:
    from fastapi import FastAPI
    from fastapi.responses import RedirectResponse
    import uvicorn
    from api import app as api_app
    from gradio.routes import mount_gradio_app

    root = FastAPI()

    # 1) incluir rutas del api_app (mantiene /api/health y demás)
    root.include_router(api_app.router)

    # 2) montar Gradio en /ui
    root = mount_gradio_app(root, demo, path="/ui")

    # 3) redirect del root para que HF no muestre Not Found
    @root.get("/")
    def _home():
        return RedirectResponse(url="/ui")

    uvicorn.run(root, host="0.0.0.0", port=PORT)

except Exception:
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=PORT)
