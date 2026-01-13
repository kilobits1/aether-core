def can_handle(command: str) -> bool:
    c = (command or "").lower()
    return "help" in c or "ayuda" in c or "comandos" in c

def run(command: str):
    return {
        "title": "AETHER Help",
        "how_to_use": [
            "Escribe un mensaje y presiona Enviar (Chat).",
            "Si un plugin lo reconoce, lo ejecuta.",
            "Si no, responde modo general / científico."
        ],
        "commands": [
            "ayuda / help / comandos",
            "estado",
            "reload plugins",
            "simular fisica"
        ]
    }
