def can_handle(command: str) -> bool:
    c = (command or "").lower()
    return "hola" in c or "hello" in c or "saluda" in c

def run(command: str):
    return {
        "message": "Hola, soy un módulo IA de ejemplo.",
        "input": command
    }
