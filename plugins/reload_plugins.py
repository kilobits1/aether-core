# plugins/reload_plugins.py
from plugins import router_help

def can_handle(command: str) -> bool:
    c = (command or "").lower()
    return "reload" in c and ("plugin" in c or "plugins" in c or "modulos" in c or "módulos" in c)

def run(command: str, state: dict = None):
    loaded = router_help.load_plugins()
    return [{"text": f"Plugins recargados: {loaded}", "type": "text"}]
