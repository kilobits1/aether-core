# ======================================================
# AETHER CORE — VERSIÓN PRO TOTAL (HF Spaces OK)
# - Thread-safe SIN deadlocks
# - Logs + dashboard JSON
# - Prioridad dinámica por energía
# - Módulos IA hot-reload (modules/*.py)
# - Gradio UI (necesario para HF)
# ======================================================

import os
import time
import json
import uuid
import threading
import importlib.util
from queue import PriorityQueue
from datetime import datetime

import numpy as np
import gradio as gr

# ======================================================
# VERSIONADO Y ARCHIVOS
# ======================================================
AETHER_VERSION = "3.4.1-pro-total-hf"

STATE_FILE = "aether_state.json"
MEMORY_FILE = "aether_memory.json"
STRATEGIC_FILE = "aether_strategic.json"
LOG_FILE = "aether_log.json"
DASHBOARD_FILE = "aether_dashboard.json"

MODULES_DIR = "modules"

MAX_MEMORY_ENTRIES = 500
MAX_LOG_ENTRIES = 1000
MAX_STRATEGY_HISTORY = 1000

# ======================================================
# ESTADO GLOBAL
# ======================================================
DEFAULT_STATE = {
    "id": "AETHER",
    "version": AETHER_VERSION,
    "status": "IDLE",
    "energy": 100,
    "focus": "STANDBY",
    "created_at": datetime.utcnow().isoformat(),
    "last_cycle": None,
}

ROOT_GOAL = "EXECUTE_USER_COMMANDS_ONLY"
KILL_SWITCH = {"enabled": True, "status": "ARMED"}

# ======================================================
# LOCKS (NO reentrantes; evitar lock dentro de lock)
# ======================================================
memory_lock = threading.Lock()
log_lock = threading.Lock()
state_lock = threading.Lock()
strategic_lock = threading.Lock()
modules_lock = threading.Lock()

# ======================================================
# IO JSON ATÓMICO (sin locks adentro)
# ======================================================
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json_atomic(path, data):
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)

# ======================================================
# CARGA INICIAL
# ======================================================
AETHER_STATE = load_json(STATE_FILE, DEFAULT_STATE.copy())
AETHER_MEMORY = load_json(MEMORY_FILE, [])
STRATEGIC_MEMORY = load_json(STRATEGIC_FILE, {"patterns": {}, "failures": {}, "history": [], "last_update": None})
AETHER_LOGS = load_json(LOG_FILE, [])
LOADED_MODULES = {}

# ======================================================
# HELPERS DE GUARDADO (lock afuera, write adentro)
# ======================================================
def save_state_locked():
    save_json_atomic(STATE_FILE, AETHER_STATE)

def save_memory_locked():
    save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

def save_logs_locked():
    save_json_atomic(LOG_FILE, AETHER_LOGS)

def save_strategic_locked():
    save_json_atomic(STRATEGIC_FILE, STRATEGIC_MEMORY)

# ======================================================
# LOGS + DASHBOARD
# ======================================================
def log_event(event_type, info):
    entry = {"timestamp": datetime.utcnow().isoformat(), "type": event_type, "info": info}
    with log_lock:
        AETHER_LOGS.append(entry)
        if len(AETHER_LOGS) > MAX_LOG_ENTRIES:
            AETHER_LOGS[:] = AETHER_LOGS[-MAX_LOG_ENTRIES:]
        save_logs_locked()

def update_dashboard():
    with state_lock:
        snapshot = {
            "energy": AETHER_STATE["energy"],
            "focus": AETHER_STATE["focus"],
            "status": AETHER_STATE["status"],
            "last_cycle": AETHER_STATE["last_cycle"],
        }
    snapshot["queue_size"] = TASK_QUEUE.qsize()
    save_json_atomic(DASHBOARD_FILE, snapshot)

# ======================================================
# COLA DE TAREAS (prioridad dinámica)
# ======================================================
TASK_QUEUE = PriorityQueue()
TASK_DEDUP = set()

def compute_priority(base_priority):
    with state_lock:
        energy = AETHER_STATE["energy"]
    return base_priority + 5 if energy < 20 else base_priority

def enqueue_task(command, priority=5, source="external"):
    key = f"{command}:{source}"
    if key in TASK_DEDUP:
        return False
    TASK_DEDUP.add(key)
    dyn_priority = compute_priority(priority)
    TASK_QUEUE.put((dyn_priority, {
        "id": str(uuid.uuid4()),
        "command": command,
        "source": source,
        "created_at": datetime.utcnow().isoformat()
    }))
    log_event("ENQUEUE", {"command": command, "priority": dyn_priority, "source": source})
    update_dashboard()
    return True

# ======================================================
# DOMINIOS + DECISIÓN
# ======================================================
def detect_domains(command):
    c = (command or "").lower()
    domains = set()
    if any(k in c for k in ["física", "ecuación", "modelo", "simulación", "simular"]):
        domains.add("science")
    if any(k in c for k in ["ia", "algoritmo", "modelo ia", "llm", "embedding"]):
        domains.add("ai")
    if any(k in c for k in ["imagen", "video", "audio"]):
        domains.add("multimedia")
    return list(domains) or ["general"]

def decide_engine(command, domains):
    if "science" in domains:
        return {"mode": "scientific", "confidence": 0.9}
    if "ai" in domains:
        return {"mode": "ai_module", "confidence": 0.95}
    return {"mode": "general", "confidence": 0.7}

# ======================================================
# EJECUTORES
# ======================================================
def execute_scientific(_command):
    try:
        t = np.linspace(0, 10, 200)
        a, v0, x0 = 2.0, 1.0, 0.0
        x = x0 + v0 * t + 0.5 * a * t**2
        return {
            "success": True,
            "result": {"final_position": float(x[-1]), "stability": float(np.std(x))},
            "metrics": {"samples": len(t), "acceleration": a},
        }
    except Exception as e:
        return {"success": False, "error": f"scientific_error: {e}"}

def execute_general(command):
    try:
        return {"success": True, "result": (command or "").upper(), "metrics": {}}
    except Exception as e:
        return {"success": False, "error": f"general_error: {e}"}

# ======================================================
# MÓDULOS IA HOT-LOAD
# Cada módulo en modules/*.py debe tener:
#   def can_handle(command:str)->bool
#   def run(command:str)->Any
# ======================================================
def reload_ai_modules():
    os.makedirs(MODULES_DIR, exist_ok=True)
    loaded = {}

    for filename in os.listdir(MODULES_DIR):
        if not filename.endswith(".py"):
            continue
        mod_name = filename[:-3]
        path = os.path.join(MODULES_DIR, filename)

        try:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if not spec or not spec.loader:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            # Validación mínima
            if not hasattr(mod, "can_handle") or not hasattr(mod, "run"):
                continue

            loaded[mod_name] = mod
        except Exception as e:
            log_event("MODULE_LOAD_ERROR", {"module": mod_name, "error": str(e)})

    with modules_lock:
        LOADED_MODULES.clear()
        LOADED_MODULES.update(loaded)

    log_event("MODULES_RELOADED", {"modules": list(LOADED_MODULES.keys())})
    return list(LOADED_MODULES.keys())

def execute_ai_module(command):
    with modules_lock:
        items = list(LOADED_MODULES.items())

    for mod_name, mod in items:
        try:
            if mod.can_handle(command):
                return {"success": True, "result": mod.run(command), "module": mod_name}
        except Exception as e:
            log_event("MODULE_RUN_ERROR", {"module": mod_name, "error": str(e)})
            return {"success": False, "error": f"module_run_error:{mod_name}:{e}"}

    return {"success": False, "error": "No suitable AI module found"}

def execute(command, decision):
    if decision["mode"] == "scientific":
        return execute_scientific(command)
    if decision["mode"] == "ai_module":
        return execute_ai_module(command)
    return execute_general(command)

# ======================================================
# KILL SWITCH + OBEDIENCIA
# ======================================================
def system_active():
    return KILL_SWITCH["status"] == "ARMED"

def obedient_execution(command, decision):
    if not system_active():
        return {"success": False, "error": "SYSTEM_HALTED"}

    if ROOT_GOAL != "EXECUTE_USER_COMMANDS_ONLY":
        KILL_SWITCH["status"] = "TRIGGERED"
        log_event("KILL_SWITCH", {"reason": "ROOT_GOAL_VIOLATION"})
        return {"success": False, "error": "ROOT_GOAL_VIOLATION"}

    with state_lock:
        AETHER_STATE["energy"] = max(0, AETHER_STATE["energy"] - 1)
        save_state_locked()

    return execute(command, decision)

# ======================================================
# MEMORIA ESTRATÉGICA
# ======================================================
def strategy_signature(command, mode):
    return f"{mode}:{len((command or '').split())}"

def record_strategy(command, mode, success):
    sig = strategy_signature(command, mode)
    target = "patterns" if success else "failures"
    with strategic_lock:
        STRATEGIC_MEMORY[target][sig] = STRATEGIC_MEMORY[target].get(sig, 0) + 1
        STRATEGIC_MEMORY["history"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "command": command,
            "mode": mode,
            "success": bool(success),
        })
        if len(STRATEGIC_MEMORY["history"]) > MAX_STRATEGY_HISTORY:
            STRATEGIC_MEMORY["history"] = STRATEGIC_MEMORY["history"][-MAX_STRATEGY_HISTORY:]
        STRATEGIC_MEMORY["last_update"] = datetime.utcnow().isoformat()
        save_strategic_locked()

# ======================================================
# CICLO VITAL
# ======================================================
def life_cycle():
    with state_lock:
        AETHER_STATE["last_cycle"] = datetime.utcnow().isoformat()
        AETHER_STATE["focus"] = "RECOVERY" if AETHER_STATE["energy"] < 20 else "ACTIVE"
        save_state_locked()

    update_dashboard()
    log_event("CYCLE", {"energy": AETHER_STATE["energy"], "focus": AETHER_STATE["focus"]})

# ======================================================
# PLANIFICADOR MULTI-PASO
# ======================================================
def decompose_command(_command, decision):
    if decision["mode"] == "scientific":
        return ["preparar simulación", "ejecutar simulación", "analizar resultados"]
    if decision["mode"] == "ai_module":
        return ["analizar solicitud", "ejecutar módulo IA", "validar salida"]
    return ["analizar solicitud", "generar respuesta"]

# ======================================================
# PROCESAMIENTO DE TAREA
# ======================================================
def process_task(task):
    command = task["command"]
    domains = detect_domains(command)
    decision = decide_engine(command, domains)
    steps = decompose_command(command, decision)

    step_results = []
    for step in steps:
        r = obedient_execution(f"{command} :: {step}", decision)
        step_results.append(r)

    success = all(r.get("success") for r in step_results)

    record_strategy(command, decision["mode"], success)

    with memory_lock:
        AETHER_MEMORY.append({
            "task_id": task["id"],
            "command": command,
            "domains": domains,
            "decision": decision,
            "steps": steps,
            "results": step_results,
            "timestamp": datetime.utcnow().isoformat(),
        })
        if len(AETHER_MEMORY) > MAX_MEMORY_ENTRIES:
            AETHER_MEMORY[:] = AETHER_MEMORY[-MAX_MEMORY_ENTRIES:]
        save_memory_locked()

    log_event("TASK_DONE", {"command": command, "success": success})
    update_dashboard()
    return success

# ======================================================
# WORKER + SCHEDULER
# ======================================================
SCHEDULER_INTERVAL = 15
STOP_EVENT = threading.Event()

def task_worker():
    while not STOP_EVENT.is_set():
        try:
            if not TASK_QUEUE.empty():
                _, task = TASK_QUEUE.get()
                with state_lock:
                    AETHER_STATE["status"] = "WORKING"
                    save_state_locked()

                process_task(task)

                TASK_QUEUE.task_done()
            else:
                with state_lock:
                    AETHER_STATE["status"] = "IDLE"
                    save_state_locked()

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

def start_aether_once():
    # Evitar doble arranque si Gradio reinicia componentes
    if getattr(start_aether_once, "_started", False):
        return
    start_aether_once._started = True

    os.makedirs(MODULES_DIR, exist_ok=True)
    reload_ai_modules()

    threading.Thread(target=task_worker, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()

    log_event("BOOT", {"version": AETHER_VERSION})
    update_dashboard()

# ======================================================
# GRADIO UI (HF necesita server)
# ======================================================
def ui_status():
    with state_lock:
        state = dict(AETHER_STATE)
    with strategic_lock:
        strategic = {
            "patterns": len(STRATEGIC_MEMORY.get("patterns", {})),
            "failures": len(STRATEGIC_MEMORY.get("failures", {})),
            "last_update": STRATEGIC_MEMORY.get("last_update"),
            "history_len": len(STRATEGIC_MEMORY.get("history", [])),
        }
    return json.dumps({
        "state": state,
        "queue_size": TASK_QUEUE.qsize(),
        "memory_len": len(AETHER_MEMORY),
        "strategic": strategic,
        "kill_switch": KILL_SWITCH,
        "modules": list(LOADED_MODULES.keys()),
    }, indent=2, ensure_ascii=False)

def ui_enqueue(cmd, prio):
    ok = enqueue_task(cmd, int(prio), source="external")
    return f"ENQUEUED={ok}\n\n" + ui_status()

def ui_reload_modules():
    mods = reload_ai_modules()
    return f"RELOADED: {mods}\n\n" + ui_status()

def ui_tail_logs(n=50):
    with log_lock:
        tail = AETHER_LOGS[-int(n):]
    return "\n".join(json.dumps(x, ensure_ascii=False) for x in tail)

with gr.Blocks(title="AETHER CORE — PRO") as demo:
    gr.Markdown("## AETHER CORE — PRO TOTAL (HF Spaces OK)")
    gr.Markdown("Estado, cola, módulos IA hot-reload, logs y dashboard.")

    with gr.Row():
        cmd = gr.Textbox(label="Comando", placeholder="Ej: optimizar algoritmo IA", lines=2)
        prio = gr.Slider(1, 20, value=5, step=1, label="Prioridad (1=alta, 20=baja)")

    with gr.Row():
        btn_enqueue = gr.Button("Enqueue Task")
        btn_reload = gr.Button("Reload AI Modules")

    status = gr.Code(label="Status JSON", language="json")
    logs_n = gr.Slider(10, 200, value=50, step=10, label="Logs (últimos N)")
    logs = gr.Textbox(label="Tail Logs", lines=12)

    btn_enqueue.click(fn=ui_enqueue, inputs=[cmd, prio], outputs=[status])
    btn_reload.click(fn=ui_reload_modules, inputs=[], outputs=[status])

    # refresco manual (sin polling)
    demo.load(fn=ui_status, inputs=[], outputs=[status])
    demo.load(fn=lambda n: ui_tail_logs(n), inputs=[logs_n], outputs=[logs])

# Arranque Aether (threads) una sola vez
start_aether_once()

# HF Spaces: lanzar gradio
if __name__ == "__main__":
    demo.launch()
