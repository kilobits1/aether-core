# plugins/tasks_ai.py
from datetime import datetime

def can_handle(command: str) -> bool:
    c = (command or "").lower().strip()
    return c.startswith("task ")

def run(command: str):
    c = (command or "").lower().strip()
    if c == "task a":
        return {"ok": True, "msg": "TASK A ejecutada", "ts": datetime.utcnow().isoformat()}
    if c == "task last":
        return {"ok": True, "msg": "TASK LAST (demo)", "ts": datetime.utcnow().isoformat()}
    return {"ok": False, "error": "Comando task no reconocido"}
