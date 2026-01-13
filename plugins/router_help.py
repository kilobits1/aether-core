# plugins/router_help.py
import os
import sys
import importlib.util
import traceback

PLUGINS_DIR = os.path.dirname(__file__)

_loaded = {}  # name -> module object
_loaded_names = []

def _load_module_from_path(mod_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No spec/loader for {mod_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module

def load_plugins():
    """
    Carga todos los plugins *_ai.py desde /plugins usando carga por archivo.
    Devuelve lista de nombres cargados.
    """
    global _loaded, _loaded_names
    _loaded = {}
    _loaded_names = []

    for fname in sorted(os.listdir(PLUGINS_DIR)):
        if not fname.endswith("_ai.py"):
            continue
        if fname.startswith("_"):
            continue

        name = fname[:-3]  # sin .py
        path = os.path.join(PLUGINS_DIR, fname)

        try:
            mod = _load_module_from_path(f"plugins.{name}", path)
            _loaded[name] = mod
            _loaded_names.append(name)
        except Exception as e:
            print(f"[ROUTER] Error cargando {name}: {e}")
            print(traceback.format_exc())

    return list(_loaded_names)

def route(command: str, state: dict):
    """
    Envía el texto a plugins (run o handle). Si alguno responde (no None), se devuelve.
    """
    for name, mod in _loaded.items():
        try:
            if hasattr(mod, "run"):
                out = mod.run(command, state)
            elif hasattr(mod, "handle"):
                out = mod.handle(command, state)
            else:
                continue

            if out is not None:
                return out
        except Exception as e:
            return [{"text": f"[ERROR {name}] {e}", "type": "text"}]

    return None

# auto-load al importar
load_plugins()
