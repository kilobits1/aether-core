import json
from typing import Any, Dict


def can_handle(command: str) -> bool:
    c = (command or "").strip().lower()
    return c in ("audit", "audit ai", "auditoria", "auditar")


def _state_view(root: Any) -> Dict[str, Any]:
    if isinstance(root, dict):
        return root.get("state", root)
    return {}


def run(command: str, root: Any = None):
    if not can_handle(command):
        return None

    root = root if isinstance(root, dict) else {}
    st = _state_view(root)

    version = st.get("version", root.get("version", "unknown"))
    status = st.get("status", "unknown")
    aether_id = st.get("id", "unknown")

    payload = {
        "ok": True,
        "id": aether_id,
        "version": version,
        "status": status,
        "data_dir": root.get("data_dir", "unknown"),
        "modules": root.get("modules", []),
        "kill_switch": root.get("kill_switch", {}),
    }

    return json.dumps(payload, ensure_ascii=False, indent=2)
