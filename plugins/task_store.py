# task_store.py
import os
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class TaskStore:
    """
    Cola persistente SQLite (HF-safe).
    Estados: queued, running, success, failed, retry_scheduled, canceled
    """
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        return con

    def _init_db(self) -> None:
        con = self._connect()
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    created_at TEXT,
                    updated_at TEXT,
                    status TEXT,
                    priority INTEGER,
                    task_type TEXT,
                    payload_json TEXT,
                    result_json TEXT,
                    error_json TEXT,
                    attempt INTEGER,
                    max_attempts INTEGER,
                    run_after TEXT,
                    locked_by TEXT,
                    locked_at TEXT,
                    timeout_s INTEGER
                )
                """
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_runafter_pri ON tasks(status, run_after, priority);")
            con.commit()
        finally:
            con.close()

    def enqueue(
        self,
        task_id: str,
        task_type: str,
        payload: Dict[str, Any],
        priority: int = 50,
        max_attempts: int = 3,
        timeout_s: int = 60,
        run_after: Optional[str] = None,
    ) -> str:
        now = utc_now_iso()
        run_after = run_after or now
        con = self._connect()
        try:
            con.execute(
                """
                INSERT INTO tasks (
                    id, created_at, updated_at, status, priority, task_type,
                    payload_json, result_json, error_json, attempt, max_attempts,
                    run_after, locked_by, locked_at, timeout_s
                )
                VALUES (?, ?, ?, 'queued', ?, ?, ?, NULL, NULL, 0, ?, ?, NULL, NULL, ?)
                """,
                (task_id, now, now, priority, task_type, json.dumps(payload), max_attempts, run_after, timeout_s),
            )
            con.commit()
            return task_id
        finally:
            con.close()

    def fetch_next_runnable(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """
        Reclama una tarea de forma atómica (best-effort con transacción).
        Considera status queued o retry_scheduled y run_after <= now.
        """
        now = utc_now_iso()
        con = self._connect()
        con.isolation_level = None  # manual transactions
        try:
            con.execute("BEGIN IMMEDIATE;")
            row = con.execute(
                """
                SELECT id, task_type, payload_json, priority, attempt, max_attempts, timeout_s
                FROM tasks
                WHERE status IN ('queued', 'retry_scheduled')
                  AND run_after <= ?
                  AND locked_by IS NULL
                ORDER BY priority ASC, created_at ASC
                LIMIT 1
                """,
                (now,),
            ).fetchone()

            if not row:
                con.execute("COMMIT;")
                return None

            task_id = row[0]
            con.execute(
                """
                UPDATE tasks
                SET status='running', locked_by=?, locked_at=?, updated_at=?
                WHERE id=? AND locked_by IS NULL
                """,
                (worker_id, now, now, task_id),
            )
            changed = con.total_changes
            con.execute("COMMIT;")
            if changed == 0:
                return None

            return {
                "id": task_id,
                "task_type": row[1],
                "payload": json.loads(row[2]),
                "priority": row[3],
                "attempt": row[4],
                "max_attempts": row[5],
                "timeout_s": row[6],
            }
        except Exception:
            try:
                con.execute("ROLLBACK;")
            except Exception:
                pass
            raise
        finally:
            con.close()

    def heartbeat_running(self, task_id: str, worker_id: str) -> None:
        now = utc_now_iso()
        con = self._connect()
        try:
            con.execute(
                """
                UPDATE tasks
                SET updated_at=?
                WHERE id=? AND locked_by=? AND status='running'
                """,
                (now, task_id, worker_id),
            )
            con.commit()
        finally:
            con.close()

    def mark_success(self, task_id: str, worker_id: str, result: Dict[str, Any]) -> None:
        now = utc_now_iso()
        con = self._connect()
        try:
            con.execute(
                """
                UPDATE tasks
                SET status='success', result_json=?, error_json=NULL,
                    updated_at=?, locked_by=NULL, locked_at=NULL
                WHERE id=? AND locked_by=? AND status='running'
                """,
                (json.dumps(result), now, task_id, worker_id),
            )
            con.commit()
        finally:
            con.close()

    def mark_failed(self, task_id: str, worker_id: str, error: Dict[str, Any]) -> None:
        now = utc_now_iso()
        con = self._connect()
        try:
            con.execute(
                """
                UPDATE tasks
                SET status='failed', error_json=?, updated_at=?,
                    locked_by=NULL, locked_at=NULL
                WHERE id=? AND locked_by=? AND status='running'
                """,
                (json.dumps(error), now, task_id, worker_id),
            )
            con.commit()
        finally:
            con.close()

    def schedule_retry(self, task_id: str, worker_id: str, next_run_after: str, error: Dict[str, Any]) -> None:
        now = utc_now_iso()
        con = self._connect()
        try:
            con.execute(
                """
                UPDATE tasks
                SET status='retry_scheduled', run_after=?, error_json=?,
                    updated_at=?, locked_by=NULL, locked_at=NULL
                WHERE id=? AND locked_by=? AND status='running'
                """,
                (next_run_after, json.dumps(error), now, task_id, worker_id),
            )
            con.commit()
        finally:
            con.close()

    def increment_attempt(self, task_id: str, worker_id: str) -> int:
        """
        Incrementa attempt mientras está running. Devuelve attempt nuevo.
        """
        con = self._connect()
        try:
            con.execute(
                """
                UPDATE tasks
                SET attempt = attempt + 1, updated_at=?
                WHERE id=? AND locked_by=? AND status='running'
                """,
                (utc_now_iso(), task_id, worker_id),
            )
            con.commit()
            row = con.execute("SELECT attempt FROM tasks WHERE id=?", (task_id,)).fetchone()
            return int(row[0]) if row else 0
        finally:
            con.close()

    def list_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        con = self._connect()
        try:
            rows = con.execute(
                """
                SELECT id, status, task_type, priority, attempt, max_attempts,
                       created_at, updated_at, run_after, timeout_s
                FROM tasks
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [
                {
                    "id": r[0],
                    "status": r[1],
                    "task_type": r[2],
                    "priority": r[3],
                    "attempt": r[4],
                    "max_attempts": r[5],
                    "created_at": r[6],
                    "updated_at": r[7],
                    "run_after": r[8],
                    "timeout_s": r[9],
                }
                for r in rows
            ]
        finally:
            con.close()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        con = self._connect()
        try:
            r = con.execute(
                """
                SELECT id, status, task_type, payload_json, result_json, error_json,
                       attempt, max_attempts, created_at, updated_at, run_after, timeout_s
                FROM tasks WHERE id=?
                """,
                (task_id,),
            ).fetchone()
            if not r:
                return None
            return {
                "id": r[0],
                "status": r[1],
                "task_type": r[2],
                "payload": json.loads(r[3]) if r[3] else None,
                "result": json.loads(r[4]) if r[4] else None,
                "error": json.loads(r[5]) if r[5] else None,
                "attempt": r[6],
                "max_attempts": r[7],
                "created_at": r[8],
                "updated_at": r[9],
                "run_after": r[10],
                "timeout_s": r[11],
            }
        finally:
            con.close()
