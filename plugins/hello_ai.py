def can_handle(command: str) -> bool:
    c = (command or "").lower()
    return "hola" in c or "hello" in c

def run(command: str):
    return {"msg": "Hola, soy hello_ai", "input": command}
