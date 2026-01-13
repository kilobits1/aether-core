def can_handle(command: str) -> bool:
    c = (command or "").lower()
    return "hola" in c or "hello" in c or "saluda" in c

def run(command: str):
    return {"ok": True, "msg": "Hola desde un módulo IA hot-reload.", "input": command}

