def can_handle(command: str) -> bool:
    c = (command or "").lower()
    return "reload" in c and ("plugin" in c or "plugins" in c or "modulos" in c or "módulos" in c)

def run(command: str):
    return {
        "msg": "Usa el botón 'Reload Modules' para recargar. Si quieres, puedo habilitar recarga desde chat conectándolo al core."
    }
