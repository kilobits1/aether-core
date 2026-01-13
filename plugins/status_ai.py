def can_handle(command: str) -> bool:
    c = (command or "").lower()
    return c.strip() in ["estado", "status", "estado aether", "aether status"]

def run(command: str):
    return {
        "ok": True,
        "msg": "Para ver el estado completo mira el panel Status JSON. (Este plugin está listo para extenderse: firebase, métricas, etc.)"
    }
