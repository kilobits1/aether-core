import json
import os
from typing import Any, Tuple


def _normalize_command(command: str) -> str:
    return (command or "").strip().lower()


def _strip_console_alias(command: str) -> str:
    normalized = _normalize_command(command)
    if normalized.startswith("console "):
        return normalized[len("console ") :].strip()
    if normalized == "console":
        return ""
    return normalized


def _load_json(path: str) -> Tuple[bool, Any, str]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return True, json.load(handle), ""
    except FileNotFoundError:
        return False, None, f"file not found: {path}"
    except json.JSONDecodeError as exc:
        return False, None, f"invalid json in {path}: {exc}"
    except OSError as exc:
        return False, None, f"unable to read {path}: {exc}"


def _data_dir() -> str:
    return os.getenv("AETHER_DATA_DIR", "/tmp/aether")


def _status() -> dict:
    base = _data_dir()
    state_path = os.path.join(base, "aether_state.json")
    dashboard_path = os.path.join(base, "aether_dashboard.json")

    ok, state, error = _load_json(state_path)
    if not ok:
        return {"ok": False, "error": error}

    ok, dashboard, error = _load_json(dashboard_path)
    if not ok:
        return {"ok": False, "error": error}

    return {"ok": True, "state": state, "dashboard": dashboard}


def _logs(command: str) -> dict:
    base = _data_dir()
    log_path = os.path.join(base, "aether_log.json")

    tokens = (command or "").strip().split()
    count = 50
    if len(tokens) >= 2:
        try:
            count = int(tokens[1])
        except ValueError:
            count = 50

    count = max(1, min(500, count))

    ok, data, error = _load_json(log_path)
    if not ok:
        return {"ok": False, "error": error}

    if not isinstance(data, list):
        return {"ok": False, "error": f"log file is not a list: {log_path}"}

    return {"ok": True, "entries": data[-count:]}


def _export_demo1() -> dict:
    base = _data_dir()
    demo_path = os.path.join(base, "demo1.json")

    ok, data, error = _load_json(demo_path)
    if not ok:
        return {"ok": False, "error": error}

    return {"ok": True, "data": data}


def can_handle(command: str) -> bool:
    normalized = _strip_console_alias(command)
    return (
        normalized == "status"
        or normalized == "export demo1"
        or normalized == "logs"
        or normalized.startswith("logs ")
        or normalized == ""
    )


def run(command: str):
    normalized = _strip_console_alias(command)
    if not normalized:
        return {"ok": False, "error": "missing console subcommand"}

    if normalized == "status":
        return _status()

    if normalized == "export demo1":
        return _export_demo1()

    if normalized == "logs" or normalized.startswith("logs "):
        return _logs(normalized)

    return {"ok": False, "error": f"unsupported command: {normalized}"}
