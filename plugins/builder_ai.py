def can_handle(command: str) -> bool:
    return (command or "").strip().lower().startswith("builder:")


def run(command: str, ctx=None, state=None):
    text = (command or "").split(":", 1)[1].strip() if ":" in (command or "") else ""
    if not text:
        text = "Solicitud de builder vacía."
    return {
        "message": "Builder listo. Recibí tu solicitud.",
        "input": text,
        "next_steps": [
            "Clarificar objetivo y alcance",
            "Definir stack y componentes",
            "Proponer plan inicial",
        ],
    }
