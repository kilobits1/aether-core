def can_handle(command: str) -> bool:
    return (command or "").strip().lower().startswith("scientific:")


def run(command: str, ctx=None, state=None):
    text = (command or "").split(":", 1)[1].strip() if ":" in (command or "") else ""
    if not text:
        text = "Consulta científica vacía."
    return {
        "message": "Scientific listo. Procesando tu consulta.",
        "input": text,
        "notes": [
            "Revisar hipótesis inicial",
            "Definir variables y supuestos",
            "Proponer metodología",
        ],
    }
