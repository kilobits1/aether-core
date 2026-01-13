# plugins/router_help.py
import os
import importlib

PLUGINS_DIR = os.path.dirname(__file__)

_loaded_plugins = []

def load_plugins():
    global _loaded_plugins
    _loaded_plugins = []

    for fname in os.listdir(PLUGINS_DIR):
        # SOLO plugins tipo *_ai.py
        if not fname.endswith("_ai.py"):
            continue
        if fname.startswith("_"):
            continue

        module_name = fname.replace(".py", "")
        try:
            module = importlib.import_module(f"plugins.{module_name}")
            _loaded_plugins.append(module_name)
        except Exception as e:
            print(f"[ROUTER] Error cargando {module_name}: {e}")

    return _loaded_plugins


def route(command: str, state: dict):
    """
    Envía el comando a cada plugin *_ai hasta que alguno responda.
    """
    for name in _loaded_plugins:
        try:
            plugin = importlib.import_module(f"plugins.{name}")

            # Compatibilidad: run() o handle()
            if hasattr(plugin, "run"):
                result = plugin.run(command, state)
            elif hasattr(plugin, "handle"):
                result = plugin.handle(command, state)
            else:
                continue

            if result:
                return result

        except Exception as e:
            return [{"text": f"[ERROR en {name}] {e}", "type": "text"}]

    return None


# Carga automática al iniciar
load_plugins()
