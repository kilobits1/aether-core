import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional


class Orchestrator:
    def __init__(
        self,
        dashboard_path: str = "/tmp/aether/aether_dashboard.json",
        tick_sec: float = 0.3,
        safe_mode_ref: Optional[Dict[str, Any]] = None,
        freeze_state_ref: Optional[Dict[str, Any]] = None,
        kill_switch_ref: Optional[Dict[str, Any]] = None,
        on_state: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self._dashboard_path = dashboard_path
        self._tick_sec = min(max(tick_sec, 0.25), 0.5)
        self._safe_mode_ref = safe_mode_ref
        self._freeze_state_ref = freeze_state_ref
        self._kill_switch_ref = kill_switch_ref
        self._on_state = on_state
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._state: Optional[Dict[str, Any]] = None

    def start(self, state_dict: Dict[str, Any]) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._state = state_dict
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True, name="aether-orchestrator")
            self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                status = "PAUSED" if self._should_pause() else "RUNNING"
                payload = {
                    "orchestrator": {
                        "status": status,
                        "queue_length": 0,
                        "ts": self._iso_now(),
                    }
                }
                self._write_dashboard(payload)
                if self._on_state:
                    self._on_state(dict(payload["orchestrator"]))
            except Exception:
                pass
            time.sleep(self._tick_sec)

    def _should_pause(self) -> bool:
        if self._safe_mode_ref and self._safe_mode_ref.get("enabled"):
            return True
        if self._freeze_state_ref and self._freeze_state_ref.get("enabled"):
            return True
        if self._kill_switch_ref and self._kill_switch_ref.get("status") != "ARMED":
            return True
        state = self._state or {}
        if state.get("status") in {"SAFE_MODE", "FROZEN"}:
            return True
        if state.get("paused") is True:
            return True
        if state.get("safe_mode", {}).get("enabled"):
            return True
        if state.get("freeze", {}).get("enabled"):
            return True
        if state.get("kill_switch", {}).get("status") not in {None, "ARMED"}:
            return True
        return False

    def _write_dashboard(self, payload: Dict[str, Any]) -> None:
        dashboard_dir = os.path.dirname(self._dashboard_path) or "/tmp/aether"
        os.makedirs(dashboard_dir, exist_ok=True)
        abs_path = os.path.abspath(self._dashboard_path)
        if not abs_path.startswith("/tmp/aether"):
            return
        data: Dict[str, Any] = {}
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except Exception:
                data = {}
        if not isinstance(data, dict):
            data = {}
        data.update(payload)
        tmp_path = os.path.join(dashboard_dir, f".aether_dashboard.{uuid.uuid4().hex}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_path, abs_path)

    @staticmethod
    def _iso_now() -> str:
        return datetime.now(timezone.utc).isoformat()
