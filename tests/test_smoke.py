import importlib
import importlib.util
import inspect
import os
from pathlib import Path
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_DIR = REPO_ROOT / "plugins"

SAFE_COMMANDS = {
    "audit_ai": "audit",
    "console_ai": "console status",
    "hello_ai": "hello",
    "restore_ai": "exports",
    "sandbox_ai": "sandbox status",
    "sandbox_test_ai": "sandbox_test report demo",
    "selftest_ai": "selftest",
    "status_ai": "status",
    "tasks_ai": "task list",
}


def _list_plugin_files():
    return sorted(
        path
        for path in PLUGINS_DIR.iterdir()
        if path.name.endswith("_ai.py") and not path.name.startswith("_")
    )


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Missing spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call_run(module, command: str, ctx: dict):
    run_fn = getattr(module, "run")
    sig = inspect.signature(run_fn)
    if len(sig.parameters) <= 1:
        return run_fn(command)
    return run_fn(command, ctx)


def test_core_import():
    module = importlib.import_module("plugins.aether_core")
    assert module is not None


def test_plugins_discovery():
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ["AETHER_DATA_DIR"] = temp_dir
        os.environ["AETHER_SANDBOX_DIR"] = os.path.join(temp_dir, "sandbox")
        router_help = importlib.import_module("plugins.router_help")
        loaded = router_help.load_plugins()

    plugin_files = _list_plugin_files()
    expected = {path.stem for path in plugin_files}
    assert set(loaded) == expected


def test_plugin_contract():
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ["AETHER_DATA_DIR"] = temp_dir
        os.environ["AETHER_SANDBOX_DIR"] = os.path.join(temp_dir, "sandbox")
        for plugin_path in _list_plugin_files():
            module = _load_module(plugin_path, f"tests.contract.{plugin_path.stem}")
            assert callable(getattr(module, "can_handle", None)), f"{plugin_path.stem} missing can_handle"
            assert callable(getattr(module, "run", None)), f"{plugin_path.stem} missing run"
            command = SAFE_COMMANDS.get(plugin_path.stem)
            assert command is not None, f"{plugin_path.stem} missing safe command"
            can_val = module.can_handle(command)
            assert isinstance(can_val, bool), f"{plugin_path.stem} can_handle non-bool"
            assert can_val is True, f"{plugin_path.stem} cannot handle safe command"
            result = _call_run(module, command, {"data_dir": temp_dir})
            assert isinstance(result, (dict, str)), f"{plugin_path.stem} run result type invalid"


def test_plugin_dry_run():
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ["AETHER_DATA_DIR"] = temp_dir
        os.environ["AETHER_SANDBOX_DIR"] = os.path.join(temp_dir, "sandbox")
        ctx = {
            "data_dir": temp_dir,
            "modules": [],
            "freeze": {"enabled": False},
            "kill_switch": {"enabled": True, "status": "ARMED"},
        }
        for plugin_path in _list_plugin_files():
            module = _load_module(plugin_path, f"tests.dry_run.{plugin_path.stem}")
            command = SAFE_COMMANDS.get(plugin_path.stem)
            assert command is not None, f"{plugin_path.stem} missing safe command"
            result = _call_run(module, command, ctx)
            assert isinstance(result, (dict, str)), f"{plugin_path.stem} dry run result type invalid"
