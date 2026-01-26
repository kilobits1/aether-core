import difflib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

SANDBOX_ROOT = "/tmp/aether_sandbox"
SANDBOX_VERSION = "43.0-sandbox-self-fix"

SANDBOX_COMMANDS = {
    "sandbox",
    "sandbox status",
    "sandbox report",
    "sandbox selffix",
    "sandbox self-fix",
    "sandbox self fix",
    "sandbox fix",
    "sandbox reparar",
    "sandbox reparar",
}

PRIORITY = 43


def can_handle(command: str) -> bool:
    c = (command or "").strip().lower()
    return c in SANDBOX_COMMANDS


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


def _safe_path(base: str, filename: str) -> Optional[str]:
    candidate = os.path.join(base, filename)
    if not _is_within(base, candidate):
        return None
    return candidate


def _safe_json_load(path: str) -> Tuple[bool, Optional[Any], Optional[str], str]:
    raw = ""
    try:
        if not os.path.exists(path):
            return False, None, "missing", raw
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        content = raw.strip()
        if not content:
            return False, None, "empty", raw
        return True, json.loads(content), None, raw
    except Exception as exc:
        return False, None, str(exc), raw


def _safe_json_write(path: str, payload: Any) -> Tuple[bool, Optional[str]]:
    try:
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        return True, None
    except Exception as exc:
        return False, str(exc)


def _default_state() -> Dict[str, Any]:
    return {
        "id": "AETHER_SANDBOX",
        "version": SANDBOX_VERSION,
        "status": "IDLE",
        "energy": 100,
        "focus": "STANDBY",
        "created_at": _now_ts(),
        "last_cycle": None,
        "level": 43,
    }


def _default_strategic() -> Dict[str, Any]:
    return {
        "patterns": 0,
        "failures": 0,
        "last_update": None,
        "history_len": 0,
        "history": [],
    }


def _default_dashboard() -> Dict[str, Any]:
    return {
        "status": "SANDBOX",
        "updated_at": _now_ts(),
        "notes": "Sandbox-only dashboard.",
    }


def _critical_files() -> Dict[str, Any]:
    return {
        "aether_state.json": _default_state(),
        "aether_memory.json": [],
        "aether_strategic.json": _default_strategic(),
        "aether_log.json": [],
        "aether_dashboard.json": _default_dashboard(),
        "projects.json": [],
        "tasks.json": [],
    }


def _diff_text(before: str, after: str, filename: str) -> str:
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    diff = difflib.unified_diff(before_lines, after_lines, fromfile=f"before/{filename}", tofile=f"after/{filename}")
    return "".join(diff).strip()


def _status_report(base_dir: str) -> Dict[str, Any]:
    files_report: List[Dict[str, Any]] = []
    for filename in _critical_files().keys():
        path = _safe_path(base_dir, filename)
        if path is None:
            files_report.append(
                {
                    "file": filename,
                    "path": None,
                    "exists": False,
                    "ok": False,
                    "error": "path_outside_sandbox",
                }
            )
            continue
        ok, _, err, _ = _safe_json_load(path)
        files_report.append(
            {
                "file": filename,
                "path": path,
                "exists": os.path.exists(path),
                "ok": ok,
                "error": err,
            }
        )
    return {
        "sandbox_root": base_dir,
        "sandbox_root_ok": _is_within(SANDBOX_ROOT, base_dir),
        "files": files_report,
    }


def _self_fix(base_dir: str) -> Dict[str, Any]:
    changes: List[Dict[str, Any]] = []
    diffs: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for filename, default_payload in _critical_files().items():
        path = _safe_path(base_dir, filename)
        if path is None:
            errors.append({"file": filename, "error": "path_outside_sandbox"})
            continue

        ok, _, err, before_raw = _safe_json_load(path)
        if ok:
            continue

        write_ok, write_err = _safe_json_write(path, default_payload)
        changes.append(
            {
                "file": filename,
                "path": path,
                "action": "created" if err == "missing" else "repaired",
                "previous_error": err,
                "write_ok": write_ok,
                "write_error": write_err,
            }
        )

        if write_ok:
            after_text = json.dumps(default_payload, ensure_ascii=False, indent=2)
            diff_text = _diff_text(before_raw, after_text, filename)
            diffs.append({"file": filename, "diff": diff_text})
        else:
            errors.append({"file": filename, "error": write_err or "write_failed"})

    return {
        "changes": changes,
        "diffs": diffs,
        "errors": errors,
    }


def run(command: str, root: Any = None, ctx: Any = None, state: Any = None):
    if not can_handle(command):
        return None

    base_dir = _safe_root()
    mode = (command or "").strip().lower()
    is_fix = "fix" in mode or "repar" in mode

    report = {
        "policy": {
            "writes_only": SANDBOX_ROOT,
            "no_shell": True,
            "no_http": True,
            "no_subprocess": True,
        },
        "status": _status_report(base_dir),
    }

    if is_fix:
        report["self_fix"] = _self_fix(base_dir)
        report["post_fix_status"] = _status_report(base_dir)

    ok = True
    status_files = report.get("status", {}).get("files", [])
    ok = ok and all(item.get("ok") for item in status_files)
    if is_fix:
        ok = ok and not report.get("self_fix", {}).get("errors")

    return {
        "ok": ok,
        "ts": _now_ts(),
        "mode": "self_fix" if is_fix else "status",
        "report": report,
    }
