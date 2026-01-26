import importlib
import importlib.util
import inspect
import json
import os
import shutil
import socket
import sys
import threading
import time
import types
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


SANDBOX_TEST_COMMANDS = {"sandbox_test"}
SANDBOX_ROOT = os.environ.get("AETHER_SANDBOX_DIR", "/tmp/aether_sandbox")
SUITE_TIMEOUT_SEC = 30
PLUGIN_TIMEOUT_SEC = 5

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


def can_handle(command: str) -> bool:
    c = (command or "").strip().lower()
    if c in SANDBOX_TEST_COMMANDS:
        return True
    return c.startswith("sandbox_test report ")


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_root() -> str:
    root = os.path.abspath(SANDBOX_ROOT)
    os.makedirs(root, exist_ok=True)
    return root


def _is_within(base: str, path: str) -> bool:
    base_abs = os.path.abspath(base)
    path_abs = os.path.abspath(path)
    return path_abs == base_abs or path_abs.startswith(base_abs + os.sep)


def _safe_join(base: str, *parts: str) -> str:
    candidate = os.path.join(base, *parts)
    if not _is_within(base, candidate):
        raise ValueError("path_outside_sandbox")
    return candidate


def _threaded_call(fn, timeout_sec: float, *args, **kwargs) -> Tuple[bool, Optional[Any], Optional[str]]:
    result: Dict[str, Any] = {"done": False, "value": None, "error": None}

    def _runner():
        try:
            result["value"] = fn(*args, **kwargs)
        except Exception as exc:
            result["error"] = str(exc)
        finally:
            result["done"] = True

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join(timeout=max(0.0, float(timeout_sec)))
    if not result["done"]:
        return False, None, "timeout"
    if result["error"]:
        return False, None, result["error"]
    return True, result["value"], None


class _NetworkGuard:
    def __init__(self):
        self._orig_socket = socket.socket
        self._orig_urlopen = None

    def __enter__(self):
        def _blocked(*_args, **_kwargs):
            raise RuntimeError("network_blocked")

        socket.socket = _blocked  # type: ignore[assignment]
        try:
            import urllib.request

            self._orig_urlopen = urllib.request.urlopen
            urllib.request.urlopen = _blocked  # type: ignore[assignment]
        except Exception:
            self._orig_urlopen = None
        return self

    def __exit__(self, exc_type, exc, tb):
        socket.socket = self._orig_socket  # type: ignore[assignment]
        if self._orig_urlopen is not None:
            import urllib.request

            urllib.request.urlopen = self._orig_urlopen  # type: ignore[assignment]


class _CwdGuard:
    def __init__(self, path: str):
        self._path = path
        self._prev = os.getcwd()

    def __enter__(self):
        os.chdir(self._path)
        return self

    def __exit__(self, exc_type, exc, tb):
        os.chdir(self._prev)


def _suite_dirs(root: str, suite_id: str) -> Dict[str, str]:
    workspace = _safe_join(root, "workspace")
    suite_dir = _safe_join(workspace, suite_id)
    repo_copy = _safe_join(suite_dir, "repo_copy")
    artifacts = _safe_join(suite_dir, "artifacts")
    data_dir = _safe_join(suite_dir, "data")
    return {
        "workspace": workspace,
        "suite": suite_dir,
        "repo_copy": repo_copy,
        "artifacts": artifacts,
        "data_dir": data_dir,
    }


def _copy_repo(src_root: str, dest_root: str) -> None:
    if os.path.exists(dest_root):
        shutil.rmtree(dest_root)

    def _ignore(_root: str, names: List[str]) -> List[str]:
        ignore = {"__pycache__", ".pytest_cache", ".git", ".venv", ".mypy_cache"}
        return [n for n in names if n in ignore]

    shutil.copytree(src_root, dest_root, ignore=_ignore)


def _load_module(path: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"missing spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call_run(module, command: str, ctx: dict):
    run_fn = getattr(module, "run")
    sig = inspect.signature(run_fn)
    if len(sig.parameters) <= 1:
        return run_fn(command)
    return run_fn(command, ctx)


def _swap_plugins_package(plugins_dir: str):
    saved: Dict[str, Any] = {}
    for name in list(sys.modules.keys()):
        if name == "plugins" or name.startswith("plugins."):
            saved[name] = sys.modules[name]
            del sys.modules[name]
    pkg = types.ModuleType("plugins")
    pkg.__path__ = [plugins_dir]
    pkg.__file__ = os.path.join(plugins_dir, "__init__.py")
    sys.modules["plugins"] = pkg
    return saved


def _restore_plugins_package(saved: Dict[str, Any]):
    for name in list(sys.modules.keys()):
        if name == "plugins" or name.startswith("plugins."):
            del sys.modules[name]
    sys.modules.update(saved)


def _list_plugin_files(repo_root: str) -> List[str]:
    plugins_dir = os.path.join(repo_root, "plugins")
    try:
        files = [fn for fn in os.listdir(plugins_dir) if fn.endswith("_ai.py") and not fn.startswith("_")]
    except FileNotFoundError:
        return []
    return sorted(files)


def _safe_ctx(state: Dict[str, Any], data_dir: str) -> Dict[str, Any]:
    ctx = dict(state) if isinstance(state, dict) else {}
    ctx.setdefault("data_dir", data_dir)
    ctx.setdefault("modules", [])
    ctx.setdefault("freeze", {"enabled": False})
    ctx.setdefault("kill_switch", {"enabled": True, "status": "ARMED"})
    return ctx


def _kill_switch_blocked(kill_switch: Dict[str, Any]) -> bool:
    if not isinstance(kill_switch, dict):
        return False
    if not kill_switch.get("enabled", True):
        return False
    status = str(kill_switch.get("status", "ARMED")).upper()
    return status != "ARMED"


def _freeze_enabled(freeze_state: Dict[str, Any]) -> bool:
    if not isinstance(freeze_state, dict):
        return False
    return bool(freeze_state.get("enabled"))


def _core_import_test() -> Dict[str, Any]:
    def _import():
        return importlib.import_module("plugins.aether_core")

    ok, _, err = _threaded_call(_import, 3.0)
    return {"ok": ok, "evidence": err or "import_ok"}


def _evaluate_plugin(plugin_path: str, plugin_id: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    evidence: List[str] = []
    safe_command = SAFE_COMMANDS.get(plugin_id)
    if not safe_command:
        return {
            "plugin_id": plugin_id,
            "contract": "skipped",
            "dry_run": "skipped",
            "evidence": ["no_safe_command"],
        }

    try:
        module = _load_module(plugin_path, f"sandbox_suite.{plugin_id}.{uuid.uuid4().hex}")
    except Exception as exc:
        return {
            "plugin_id": plugin_id,
            "contract": "fail",
            "dry_run": "skipped",
            "evidence": [f"import_error: {exc}"],
        }

    can_handle_fn = getattr(module, "can_handle", None)
    run_fn = getattr(module, "run", None)
    if not callable(can_handle_fn) or not callable(run_fn):
        return {
            "plugin_id": plugin_id,
            "contract": "fail",
            "dry_run": "skipped",
            "evidence": ["missing_can_handle_or_run"],
        }

    can_ok, can_val, can_err = _threaded_call(can_handle_fn, 1.0, safe_command)
    if not can_ok:
        return {
            "plugin_id": plugin_id,
            "contract": "fail",
            "dry_run": "skipped",
            "evidence": [f"can_handle_error: {can_err}"],
        }
    if not isinstance(can_val, bool):
        return {
            "plugin_id": plugin_id,
            "contract": "fail",
            "dry_run": "skipped",
            "evidence": ["can_handle_non_bool"],
        }
    if can_val is False:
        return {
            "plugin_id": plugin_id,
            "contract": "skipped",
            "dry_run": "skipped",
            "evidence": ["safe_command_not_handled"],
        }

    def _run():
        return _call_run(module, safe_command, ctx)

    run_ok, run_val, run_err = _threaded_call(_run, PLUGIN_TIMEOUT_SEC)
    if not run_ok:
        evidence.append(f"run_error: {run_err}")
        return {
            "plugin_id": plugin_id,
            "contract": "pass",
            "dry_run": "fail",
            "evidence": evidence,
        }

    if not isinstance(run_val, (dict, str)):
        evidence.append("run_return_invalid_type")
        return {
            "plugin_id": plugin_id,
            "contract": "pass",
            "dry_run": "fail",
            "evidence": evidence,
        }

    return {
        "plugin_id": plugin_id,
        "contract": "pass",
        "dry_run": "pass",
        "evidence": ["ok"],
    }


def _suite_report(base: Dict[str, Any], path: str) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(base, handle, ensure_ascii=False, indent=2)
    return base


def _run_suite(command_ctx: Dict[str, Any]) -> Dict[str, Any]:
    start_ts = _now_ts()
    start_time = time.time()
    suite_id = uuid.uuid4().hex
    sandbox_root = _safe_root()
    dirs = _suite_dirs(sandbox_root, suite_id)
    os.makedirs(dirs["workspace"], exist_ok=True)
    os.makedirs(dirs["artifacts"], exist_ok=True)
    os.makedirs(dirs["data_dir"], exist_ok=True)

    gates_applied = {
        "no_network": True,
        "shell_policy": {"mode": "deny", "allowed_cmds": []},
        "timeout_sec": SUITE_TIMEOUT_SEC,
        "freeze_status": command_ctx.get("freeze", {}),
        "kill_switch_status": command_ctx.get("kill_switch", {}),
    }

    report: Dict[str, Any] = {
        "suite_id": suite_id,
        "started_at": start_ts,
        "core_import": {"ok": False, "evidence": "not_run"},
        "plugins": [],
        "totals": {"passed": 0, "failed": 0, "skipped": 0},
        "gates_applied": gates_applied,
    }

    if _freeze_enabled(command_ctx.get("freeze", {})):
        report["status"] = "FROZEN"
        report["ended_at"] = _now_ts()
        report["duration_ms"] = int((time.time() - start_time) * 1000)
        return _suite_report(report, os.path.join(dirs["artifacts"], "test_report.json"))

    if _kill_switch_blocked(command_ctx.get("kill_switch", {})):
        report["status"] = "KILL_SWITCH"
        report["ended_at"] = _now_ts()
        report["duration_ms"] = int((time.time() - start_time) * 1000)
        report["core_import"] = {"ok": False, "evidence": "kill_switch_blocked"}
        return _suite_report(report, os.path.join(dirs["artifacts"], "test_report.json"))

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _copy_repo(repo_root, dirs["repo_copy"])

    data_dir = dirs["data_dir"]
    os.environ["AETHER_DATA_DIR"] = data_dir
    os.environ["AETHER_SANDBOX_DIR"] = sandbox_root

    saved_plugins = _swap_plugins_package(os.path.join(dirs["repo_copy"], "plugins"))
    sys.path.insert(0, dirs["repo_copy"])
    try:
        with _CwdGuard(sandbox_root), _NetworkGuard():
            report["core_import"] = _core_import_test()

            plugin_files = _list_plugin_files(dirs["repo_copy"])
            for filename in plugin_files:
                if time.time() - start_time > SUITE_TIMEOUT_SEC:
                    report["plugins"].append(
                        {
                            "plugin_id": filename[:-3],
                            "contract": "skipped",
                            "dry_run": "skipped",
                            "evidence": ["suite_timeout"],
                        }
                    )
                    report["totals"]["skipped"] += 1
                    continue

                plugin_id = filename[:-3]
                plugin_path = os.path.join(dirs["repo_copy"], "plugins", filename)
                ctx = _safe_ctx(command_ctx, data_dir)
                ok, result, err = _threaded_call(
                    _evaluate_plugin,
                    PLUGIN_TIMEOUT_SEC,
                    plugin_path,
                    plugin_id,
                    ctx,
                )
                if not ok:
                    report["plugins"].append(
                        {
                            "plugin_id": plugin_id,
                            "contract": "fail",
                            "dry_run": "fail",
                            "evidence": [f"timeout: {err}"],
                        }
                    )
                    report["totals"]["failed"] += 1
                    continue

                report["plugins"].append(result)
                if result["contract"] == "pass" and result["dry_run"] == "pass":
                    report["totals"]["passed"] += 1
                elif result["contract"] == "skipped" and result["dry_run"] == "skipped":
                    report["totals"]["skipped"] += 1
                else:
                    report["totals"]["failed"] += 1
    finally:
        if dirs["repo_copy"] in sys.path:
            sys.path.remove(dirs["repo_copy"])
        _restore_plugins_package(saved_plugins)

    report["ended_at"] = _now_ts()
    report["duration_ms"] = int((time.time() - start_time) * 1000)
    if report["core_import"].get("ok"):
        report["totals"]["passed"] += 1
    else:
        report["totals"]["failed"] += 1

    return _suite_report(report, os.path.join(dirs["artifacts"], "test_report.json"))


def _load_report(suite_id: str) -> Dict[str, Any]:
    sandbox_root = _safe_root()
    dirs = _suite_dirs(sandbox_root, suite_id)
    report_path = os.path.join(dirs["artifacts"], "test_report.json")
    if not os.path.exists(report_path):
        return {"ok": False, "error": "report_missing", "suite_id": suite_id}
    try:
        with open(report_path, "r", encoding="utf-8") as handle:
            return {"ok": True, "suite_id": suite_id, "report": json.load(handle)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "suite_id": suite_id}


def run(command: str, root: Any = None, ctx: Any = None, state: Any = None):
    if not can_handle(command):
        return None

    payload: Dict[str, Any] = {}
    if isinstance(ctx, dict):
        payload = ctx
    elif isinstance(state, dict):
        payload = state
    elif isinstance(root, dict):
        payload = root

    c = (command or "").strip().lower()
    if c.startswith("sandbox_test report "):
        suite_id = c.split("sandbox_test report ", 1)[1].strip()
        return _load_report(suite_id)

    report = _run_suite(payload)
    return {"ok": True, "suite_id": report.get("suite_id"), "report": report}
