# plugins/reload_plugins.py
import importlib
from plugins import router_help

def can_handle(command: str) -> bool:
    c = (command or "").lower()
    return "reload" in c and (
        "plugin" in c
        or "plugins" in c
        or "modulos" in c
        or "módulos" in c
    )

def run(command: str, state: dict = None):
    try:
        # Fuerza reload del router
        importlib.reload(router_help)

        # Vuelve a cargar plugins *_ai.py
        loaded = router_help.load_plugins()

        return [{
            "text": f"🔄 Plugins recargados correctamente: {loaded}",
            "type": "text"
        }]
    except Exception as e:
        return [{
            "text": f"❌ Error al recargar plugins: {e}",
            "type": "text"
        }]
