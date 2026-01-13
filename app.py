# ======================================================
# AETHER CORE — VERSIÓN REAL CORREGIDA
# ======================================================

import time
import json
import uuid
import threading
from queue import PriorityQueue
from datetime import datetime

# ======================================================
# VERSIONADO Y ARCHIVOS
# ======================================================
AETHER_VERSION = "3.1.0"

STATE_FILE = "aether_state.json"
MEMORY_FILE = "aether_memory.json"
STRATEGIC_FILE = "aether_strategic.json"

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

KILL_SWITCH = {
    "enabled": True,
    "status": "ARMED"
}

# ======================================================
# CARGA / GUARDADO
# ======================================================
def load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

AETHER_STATE = load_json(STATE_FILE, DEFAULT_STATE.copy())
AETHER_MEMORY = load_json(MEMORY_FILE, [])
STRATEGIC_MEMORY = load_json(STRATEGIC_FILE, {
    "patterns": {},
    "failures": {},
    "last_update": None
})

# ======================================================
# COLA DE TAREAS REAL (CON PRIORIDAD)
# ======================================================
TASK_QUEUE = PriorityQueue()
TASK_DEDUP = set()

def enqueue_task(command, priority=5, source="external"):
    key = f"{command}:{source}"
    if key in TASK_DEDUP:
        return
    TASK_DEDUP.add(key)

    TASK_QUEUE.put((
        priority,
        {
            "id": str(uuid.uuid4()),
            "command": command,
            "source": source,
            "created_at": datetime.utcnow().isoformat()
        }
    ))

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
    return list(domains) or ["general"]

def decide_engine(command, domains):
    if "science" in domains:
        return {"mode": "scientific", "confidence": 0.9}
    return {"mode": "general", "confidence": 0.7}

# ======================================================
# EJECUTORES REALES
# ======================================================
def execute_scientific(command):
    # simulación mínima real
    value = len(command.split()) ** 2
    return {
        "success": True,
        "result": value,
        "metrics": {"complexity": value}
    }

def execute_general(command):
    return {
        "success": True,
        "result": command.upper(),
        "metrics": {}
    }

def execute(command, decision):
    if decision["mode"] == "scientific":
        return execute_scientific(command)
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

    AETHER_STATE["energy"] = max(0, AETHER_STATE["energy"] - 1)
    return execute(command, decision)

# ======================================================
# MEMORIA ESTRATÉGICA REAL
# ======================================================
def strategy_signature(command, mode):
    return f"{mode}:{len(command.split())}"

def record_strategy(command, mode, quality):
    sig = strategy_signature(command, mode)
    target = "patterns" if quality else "failures"
    STRATEGIC_MEMORY[target][sig] = STRATEGIC_MEMORY[target].get(sig, 0) + 1
    STRATEGIC_MEMORY["last_update"] = datetime.utcnow().isoformat()
    save_json(STRATEGIC_FILE, STRATEGIC_MEMORY)

# ======================================================
# CICLO VITAL
# ======================================================
def life_cycle():
    AETHER_STATE["last_cycle"] = datetime.utcnow().isoformat()
    AETHER_STATE["focus"] = "RECOVERY" if AETHER_STATE["energy"] < 20 else "ACTIVE"
    save_json(STATE_FILE, AETHER_STATE)

# ======================================================
# PROCESAMIENTO DE TAREA
# ======================================================
def process_task(task):
    command = task["command"]
    domains = detect_domains(command)
    decision = decide_engine(command, domains)

    result = obedient_execution(command, decision)
    quality = result.get("success", False)

    record_strategy(command, decision["mode"], quality)

    AETHER_MEMORY.append({
        "task_id": task["id"],
        "command": command,
        "decision": decision,
        "result": result,
        "timestamp": datetime.utcnow().isoformat()
    })
    save_json(MEMORY_FILE, AETHER_MEMORY)

# ======================================================
# WORKER Y SCHEDULER
# ======================================================
def task_worker():
    while True:
        if not TASK_QUEUE.empty():
            _, task = TASK_QUEUE.get()
            AETHER_STATE["status"] = "WORKING"
            process_task(task)
            TASK_QUEUE.task_done()
        else:
            AETHER_STATE["status"] = "IDLE"

        save_json(STATE_FILE, AETHER_STATE)
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
    threading.Thread(target=task_worker, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    print("✅ AETHER REAL INICIADO — CONTROLADO Y PERSISTENTE")

# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    start_aether()
    enqueue_task("analizar sistema físico", priority=3)
    enqueue_task("optimizar algoritmo IA", priority=2)

    while True:
        time.sleep(60)


