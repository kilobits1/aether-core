from datetime import datetime, timezone
from typing import Any, Dict


def can_handle(command: str) -> bool:
    c = (command or "").strip().lower()
    return c in ("audit", "audit ai", "auditoria", "auditar", "review", "design review")


def _state_view(root: Any) -> Dict[str, Any]:
    if isinstance(root, dict):
        st = root.get("state", root)
        return st if isinstance(st, dict) else {}
    return {}


def run(command: str, root: Any = None, ctx: Any = None, state: Any = None):
    if not can_handle(command):
        return None

    root = root if isinstance(root, dict) else {}
    if isinstance(ctx, dict):
        root = ctx
    elif isinstance(state, dict):
        root = state
    st = _state_view(root)

    version = st.get("version", root.get("version", "unknown"))
    status = st.get("status", "unknown")
    aether_id = st.get("id", "unknown")
    mode = "review" if (command or "").strip().lower() in ("review", "design review") else "audit"

    payload = {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "report": {
            "id": aether_id,
            "version": version,
            "status": status,
            "data_dir": root.get("data_dir", "unknown"),
            "modules": root.get("modules", []),
            "kill_switch": root.get("kill_switch", {}),
            "freeze": root.get("freeze", {}),
            "watchdog": root.get("watchdog", {}),
            "planner_only": True,
            "autorun": False,
            "writes": False,
            "design_review": {
                "constraints": [
                    "hf_safe",
                    "no_shell",
                    "no_http",
                    "no_writes_outside_tmp",
                    "planner_only",
                ],
                "notes": "Review-only: no execution or writes are performed.",
            },
        },
    }

    return payload
