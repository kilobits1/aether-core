# ======================================================
# AETHER CORE — VERSIÓN PRO TOTAL + MÓDULOS IA EN CALIENTE
# ======================================================

import time
import json
import uuid
import threading
from queue import PriorityQueue
from datetime import datetime
import numpy as np
import os
import importlib
import importlib.util

# ======================================================
# VERSIONADO Y ARCHIVOS
# ======================================================
AETHER_VERSION = "3.4.0-pro-total"

STATE_FILE = "aether_state.json"
MEMORY_FILE = "aether_memory.json"
STRATEGIC_FILE = "aether_strategic.json"
LOG_FILE = "aether_log.json"
DASHBOARD_FILE = "aether_dashboard.json"

MODULES_DIR = "modules"  # carpeta de módulos IA externos

MAX_MEMORY_ENTRIES = 500
MAX_LOG_ENTRIES = 1000

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
    "last_cycle": None
}

ROOT_GOAL = "EXECUTE_USER_COMMANDS_ONLY"
KILL_SWITCH = {"enabled": True, "status": "ARMED"}

# ======================================================
# BLOQUEOS PARA THREAD-SAFE
# ======================================================
memory_lock = threading.Lock()
log_lock = threading.Lock()
state_lock = threading.Lock()
strategic_lock = threading.Lock()
modules_lock = threading.Lock()

# ======================================================
# FUNCIONES DE CARGA / GUARDADO
# ======================================================
def load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def save_json_atomic(path, data):
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except Exception as e:
        print(f"[ERROR] Guardando {path}: {e}")

def save_state():
    with state_lock:
        save_json_atomic(STATE_FILE, AETHER_STATE)

def save_memory():
    with memory_lock:
        save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

def save_logs():
    with log_lock:
        save_json_atomic(LOG_FILE, AETHER_LOGS)

def save_strategic():
    with strategic_lock:
        save_json_atomic(STRATEGIC_FILE, STRATEGIC_MEMORY)

# ======================================================
# CARGA INICIAL
# ======================================================
AETHER_STATE = load_json(STATE_FILE, DEFAULT_STATE.copy())
AETHER_MEMORY = load_json(MEMORY_FILE, [])
STRATEGIC_MEMORY = load_json(STRATEGIC_FILE, {"patterns": {}, "failures": {}, "history": [], "last_update": None})
AETHER_LOGS = load_json(LOG_FILE, [])
LOADED_MODULES = {}

# ======================================================
# LOGS Y DASHBOARD
# ======================================================
def log_event(event_type, info):
    entry = {"timestamp": datetime.utcnow().isoformat(), "type": event_type, "info": info}
    with log_lock:
        AETHER_LOGS.append(entry)
        if len(AETHER_LOGS) > MAX_LOG_ENTRIES:
            AETHER_LOGS[:] = AETHER_LOGS[-MAX_LOG_ENTRIES:]
        save_logs()

def update_dashboard():
    dashboard = {
        "energy": AETHER_STATE["energy"],
        "focus": AETHER_STATE["focus"],
        "status": AETHER_STATE["status"],
        "queue_size": TASK_QUEUE.qsize(),
        "last_cycle": AETHER_STATE["last_cycle"]
    }
    save_json_atomic(DASHBOARD_FILE, dashboard)

# ======================================================
# COLA DE TAREAS
# ======================================================
TASK_QUEUE = PriorityQueue()
TASK_DEDUP = set()

def compute_priority(base_priority):
    energy = AETHER_STATE["energy"]
    if energy < 20:
        return base_priority + 5
    return base_priority

def enqueue_task(command, priority=5, source="external"):
    key = f"{command}:{source}"
    if key in TASK_DEDUP:
        return
    TASK_DEDUP.add(key)
    dyn_priority = compute_priority(priority)
    TASK_QUEUE.put((dyn_priority, {"id": str(uuid.uuid4()), "command": command, "source": source, "created_at": datetime.utcnow().isoformat()}))
    log_event("ENQUEUE", {"command": command, "priority": dyn_priority, "source": source})

# ======================================================
# DOMINIOS Y DECISIÓN
# ======================================================
def detect_domains(command):
    c = command.lower()
    domains = set()
    if any(k in c for k in ["física", "ecuación", "modelo"]):
        domains.add("science")
    if any(k in c for k in ["ia", "algoritmo"]):
        domains.add("ai")
    if any(k in c for k in ["imagen", "video", "audio"]):
        domains.add("multimedia")
    return list(domains) or ["general"]

def decide_engine(command, domains):
    if "science" in domains:
        return {"mode": "scientific", "confidence": 0.9}
    elif "ai" in domains:
        return {"mode": "ai_module", "confidence": 0.95}
    return {"mode": "general", "confidence": 0.7}

# ======================================================
# EJECUTORES REALES
# ======================================================
def execute_scientific(command):
    try:
        t = np.linspace(0, 10, 200)
        a = 2.0
        v0 = 1.0
        x0 = 0.0
        x = x0 + v0*t + 0.5*a*t**2
        stability = float(np.std(x))
        final_position = float(x[-1])
        return {"success": True, "result": {"final_position": final_position, "stability": stability}, "metrics": {"samples": len(t), "acceleration": a}}
    except Exception as e:
        return {"success": False, "error": str(e)}

def execute_general(command):
    try:
        return {"success": True, "result": command.upper(), "metrics": {}}
    except Exception as e:
        return {"success": False, "error": str(e)}

def reload_ai_modules():
    with modules_lock:
        global LOADED_MODULES
        LOADED_MODULES = {}
        if not os.path.exists(MODULES_DIR):
            os.mkdir(MODULES_DIR)
        for filename in os.listdir(MODULES_DIR):
            if filename.endswith(".py"):
                mod_name = filename[:-3]
                path = os.path.join(MODULES_DIR, filename)
                spec = importlib.util.spec_from_file_location(mod_name, path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                LOADED_MODULES[mod_name] = mod
        log_event("MODULES_RELOADED", {"modules": list(LOADED_MODULES.keys())})

def execute_ai_module(command):
    with modules_lock:
        for mod_name, mod in LOADED_MODULES.items():
            if hasattr(mod, "can_handle") and mod.can_handle(command):
                result = mod.run(command)
                return {"success": True, "result": result, "module": mod_name}
    return {"success": False, "error": "No suitable AI module found"}

def execute(command, decision):
    if decision["mode"] == "scientific":
        return execute_scientific(command)
    elif decision["mode"] == "ai_module":
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
        return {"success": False, "error": "ROOT_GOAL_VIOLATION"}
    with state_lock:
        AETHER_STATE["energy"] = max(0, AETHER_STATE["energy"] - 1)
    return execute(command, decision)

# ======================================================
# MEMORIA ESTRATÉGICA CON HISTORIAL
# ======================================================
def strategy_signature(command, mode):
    return f"{mode}:{len(command.split())}"

def record_strategy(command, mode, quality):
    sig = strategy_signature(command, mode)
    target = "patterns" if quality else "failures"
    with strategic_lock:
        STRATEGIC_MEMORY[target][sig] = STRATEGIC_MEMORY[target].get(sig, 0) + 1
        STRATEGIC_MEMORY["history"].append({"timestamp": datetime.utcnow().isoformat(), "command": command, "mode": mode, "success": quality})
        STRATEGIC_MEMORY["last_update"] = datetime.utcnow().isoformat()
        save_strategic()

# ======================================================
# CICLO VITAL
# ======================================================
def life_cycle():
    with state_lock:
        AETHER_STATE["last_cycle"] = datetime.utcnow().isoformat()
        AETHER_STATE["focus"] = "RECOVERY" if AETHER_STATE["energy"] < 20 else "ACTIVE"
        save_state()
    update_dashboard()
    log_event("CYCLE", {"energy": AETHER_STATE["energy"], "focus": AETHER_STATE["focus"]})

# ======================================================
# PLANIFICADOR MULTI-PASO
# ======================================================
def decompose_command(command, decision):
    if decision["mode"] == "scientific":
        return ["preparar simulación", "ejecutar simulación", "analizar resultados"]
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

    quality = all(r.get("success") for r in step_results)
    record_strategy(command, decision["mode"], quality)

    with memory_lock:
        AETHER_MEMORY.append({"task_id": task["id"], "command": command, "decision": decision, "steps": steps, "results": step_results, "timestamp": datetime.utcnow().isoformat()})
        if len(AETHER_MEMORY) > MAX_MEMORY_ENTRIES:
            AETHER_MEMORY[:] = AETHER_MEMORY[-MAX_MEMORY_ENTRIES:]
        save_memory()

    log_event("TASK_DONE", {"command": command, "success": quality})

# ======================================================
# WORKER Y SCHEDULER
# ======================================================
def task_worker():
    while True:
        if not TASK_QUEUE.empty():
            _, task = TASK_QUEUE.get()
            with state_lock:
                AETHER_STATE["status"] = "WORKING"
            process_task(task)
            TASK_QUEUE.task_done()
        else:
            with state_lock:
                AETHER_STATE["status"] = "IDLE"
        save_state()
        update_dashboard()
        time.sleep(1)

def scheduler_loop():
    while True:
        life_cycle()
        enqueue_task("revisar estado interno", priority=10, source="internal")
        time.sleep(15)

# ======================================================
# ARRANQUE
# ======================================================
def start_aether():
    if not os.path.exists(MODULES_DIR):
        os.mkdir(MODULES_DIR)
    reload_ai_modules()  # cargar módulos IA al inicio
    threading.Thread(target=task_worker, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    print("✅ AETHER PRO TOTAL INICIADO — MÓDULOS IA HOT-LOADED, CONTROLADO Y MONITOREADO")

# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    start_aether()
    enqueue_task("analizar sistema físico", priority=3)
    enqueue_task("optimizar algoritmo IA", priority=2)
    while True:
        time.sleep(60)
