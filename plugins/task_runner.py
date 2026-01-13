# plugins/task_runner.py
import uuid
import time
import traceback
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from plugins.task_store import TaskStore
from plugins.adapters import Adapters, PolicyError

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def backoff_seconds(attempt: int) -> int:
    # 1->5s, 2->15s, 3->45s, 4->120s...
    return min(300, int(5 * (3 ** max(0, attempt - 1))))

class TaskRunner:
    def __init__(self, store: TaskStore, adapters: Adapters, worker_id: Optional[str] = None, poll_interval_s: float = 0.5):
        self.store = store
        self.adapters = adapters
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.poll_interval_s = poll_interval_s
        self._running = False

        self.handlers = {
            "files.write_text": self._handle_write_text,
            "files.read_text": self._handle_read_text,
            "files.list_dir": self._handle_list_dir,
            "shell.exec": self._handle_shell_exec,
            "http.json": self._handle_http_json,
        }

    def start_loop(self):
        self._running = True
        while self._running:
            task = self.store.fetch_next_runnable(self.worker_id)
            if not task:
                time.sleep(self.poll_interval_s)
                continue

            task_id = task["id"]
            ttype = task["task_type"]
            payload = task["payload"] or {}
            timeout_s = int(task.get("timeout_s") or 60)

            attempt = self.store.increment_attempt(task_id, self.worker_id)

            try:
                handler = self.handlers.get(ttype)
                if not handler:
                    raise ValueError(f"Unknown task_type: {ttype}")

                result = handler(payload, timeout_s=timeout_s)
                self.store.mark_success(task_id, self.worker_id, result)

            except PolicyError as e:
                self.store.mark_failed(task_id, self.worker_id, {"type": "policy_error", "message": str(e)})

            except Exception as e:
                err = {
                    "type": "exception",
                    "message": str(e),
                    "trace": traceback.format_exc()[-15000:],
                }
                max_attempts = int(task.get("max_attempts") or 3)
                if attempt < max_attempts:
                    delay = backoff_seconds(attempt)
                    next_run = (utc_now() + timedelta(seconds=delay)).isoformat()
                    self.store.schedule_retry(task_id, self.worker_id, next_run, err)
                else:
                    self.store.mark_failed(task_id, self.worker_id, err)

    def stop(self):
        self._running = False

    # -------- Handlers --------
    def _handle_write_text(self, payload: Dict[str, Any], timeout_s: int) -> Dict[str, Any]:
        return self.adapters.write_text(payload["path"], payload.get("text", ""))

    def _handle_read_text(self, payload: Dict[str, Any], timeout_s: int) -> Dict[str, Any]:
        return self.adapters.read_text(payload["path"], max_bytes=int(payload.get("max_bytes", 200_000)))

    def _handle_list_dir(self, payload: Dict[str, Any], timeout_s: int) -> Dict[str, Any]:
        return self.adapters.list_dir(payload.get("path", ""))

    def _handle_shell_exec(self, payload: Dict[str, Any], timeout_s: int) -> Dict[str, Any]:
        return self.adapters.shell(payload["cmd"], timeout_s=timeout_s, cwd_rel=payload.get("cwd_rel", ""))

    def _handle_http_json(self, payload: Dict[str, Any], timeout_s: int) -> Dict[str, Any]:
        return self.adapters.http_json(
            payload["url"],
            method=payload.get("method", "GET"),
            headers=payload.get("headers"),
            body=payload.get("body"),
            timeout_s=min(timeout_s, 60),
        )
