import importlib.util
import json
import os
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


SELFTEST_COMMANDS = {
    "selftest",
    "selftest core",
    "selftest plugins",
    "selftest full",
}


def can_handle(command: str) -> bool:
    c = (command or "").strip().lower()
    return c in SELFTEST_COMMANDS


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_json_load(path: str) -> Tuple[bool, Optional[Any], Optional[str]]:
    try:
        if not os.path.exists(path):
            return False, None, "missing"
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return False, None, "empty"
        return True, json.loads(raw), None
    except Exception as exc:
        return False, None, str(exc)


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


def _core_selftest(ctx: Dict[str, Any]) -> Dict[str, Any]:
    data_dir = ctx.get("data_dir") or "/tmp/aether"
    state = ctx.get("state", {}) if isinstance(ctx.get("state"), dict) else {}
    status = state.get("status") or ctx.get("status") or "unknown"
    queue_size = ctx.get("queue_size")
    freeze = ctx.get("freeze")
    kill_switch = ctx.get("kill_switch")
    watchdog = ctx.get("watchdog")
    recent_errors = ctx.get("recent_errors", [])

    critical_files = [
        "aether_state.json",
        "aether_memory.json",
        "aether_strategic.json",
        "aether_log.json",
        "aether_dashboard.json",
        "projects.json",
        "tasks.json",
    ]

    files_report: List[Dict[str, Any]] = []
    for filename in critical_files:
        path = os.path.join(data_dir, filename)
        ok, _, err = safe_json_load(path)
        files_report.append(
            {
                "file": filename,
                "path": path,
                "exists": os.path.exists(path),
                "ok": ok,
                "error": err,
            }
        )

    status_ok = status in {"IDLE", "RUNNING", "FROZEN", "SAFE_MODE"}

    return {
        "status": status,
        "status_ok": status_ok,
        "queue_size": queue_size,
        "freeze_present": isinstance(freeze, dict),
        "kill_switch_present": isinstance(kill_switch, dict),
        "watchdog_present": isinstance(watchdog, dict),
        "recent_errors_count": len(recent_errors) if isinstance(recent_errors, list) else None,
        "critical_files": files_report,
    }


def _plugins_selftest(ctx: Dict[str, Any]) -> Dict[str, Any]:
    modules_dir = ctx.get("modules_dir") or "plugins"
    loaded_modules = ctx.get("modules", [])
    if not isinstance(loaded_modules, list):
        loaded_modules = []

    plugin_files: List[str] = []
    try:
        plugin_files = [fn for fn in os.listdir(modules_dir) if fn.endswith("_ai.py") and not fn.startswith("_")]
        plugin_files.sort()
    except Exception:
        plugin_files = []

    reports: List[Dict[str, Any]] = []
    for filename in plugin_files:
        name = filename[:-3]
        module_name = f"plugins.{name}"
        info: Dict[str, Any] = {
            "module": name,
            "file": os.path.join(modules_dir, filename),
            "loaded": name in loaded_modules,
            "contract_ok": False,
            "can_handle_ok": None,
            "run_ok": None,
            "error": None,
        }

        try:
            if module_name in sys.modules:
                mod = sys.modules[module_name]
            else:
                spec = importlib.util.spec_from_file_location(module_name, os.path.join(modules_dir, filename))
                if not spec or not spec.loader:
                    info["error"] = "missing spec"
                    reports.append(info)
                    continue
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

            can_handle_fn = getattr(mod, "can_handle", None)
            run_fn = getattr(mod, "run", None)
            info["contract_ok"] = callable(can_handle_fn) and callable(run_fn)
            if not info["contract_ok"]:
                reports.append(info)
                continue

            if name == "selftest_ai":
                info["can_handle_ok"] = True
                info["run_ok"] = "skipped-self"
                reports.append(info)
                continue

            can_ok, can_val, can_err = _threaded_call(can_handle_fn, 0.5, "selftest")
            info["can_handle_ok"] = can_ok and isinstance(can_val, bool)
            if not info["can_handle_ok"]:
                info["error"] = can_err or "can_handle returned non-bool"
                reports.append(info)
                continue

            if can_val is True:
                run_ok, _, run_err = _threaded_call(run_fn, 1.0, "selftest", ctx)
                info["run_ok"] = run_ok
                if not run_ok:
                    info["error"] = run_err
            else:
                info["run_ok"] = "skipped-not-handled"
            reports.append(info)
        except Exception as exc:
            info["error"] = str(exc)
            reports.append(info)

    summary = {
        "total_files": len(plugin_files),
        "loaded_modules": len(loaded_modules),
        "contracts_ok": sum(1 for item in reports if item.get("contract_ok")),
        "run_timeouts": sum(1 for item in reports if item.get("error") == "timeout"),
    }
    return {"summary": summary, "plugins": reports}


def run(command: str, root: Any = None, ctx: Any = None, state: Any = None):
    if not can_handle(command):
        return None

    ctx_payload: Dict[str, Any] = {}
    if isinstance(ctx, dict):
        ctx_payload = ctx
    elif isinstance(state, dict):
        ctx_payload = state
    elif isinstance(root, dict):
        ctx_payload = root

    mode = (command or "").strip().lower()
    report: Dict[str, Any] = {}
    if mode in {"selftest", "selftest full"}:
        report["core"] = _core_selftest(ctx_payload)
        report["plugins"] = _plugins_selftest(ctx_payload)
    elif mode == "selftest core":
        report["core"] = _core_selftest(ctx_payload)
    elif mode == "selftest plugins":
        report["plugins"] = _plugins_selftest(ctx_payload)

    ok = True
    if "core" in report:
        ok = ok and bool(report["core"].get("status_ok"))
        for entry in report["core"].get("critical_files", []):
            ok = ok and bool(entry.get("ok"))
    if "plugins" in report:
        ok = ok and all(item.get("contract_ok") for item in report["plugins"].get("plugins", []))

    return {
        "ok": ok,
        "ts": _now_ts(),
        "mode": mode,
        "report": report,
    }
