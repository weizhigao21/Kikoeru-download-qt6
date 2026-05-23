import sqlite3
import json
import threading
import time
from contextlib import contextmanager

_CONNECTION_TIMEOUT = 300


class PendingTaskManager:
    _PERSISTED_STATUSES = ("submitting", "downloading", "queued", "failed")

    def __init__(self, db_path):
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = getattr(self._local, 'conn', None)
        last_used = getattr(self._local, 'last_used', 0)

        if conn is None or (time.time() - last_used > _CONNECTION_TIMEOUT):
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn

        self._local.last_used = time.time()

        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None
            raise

    def _init_db(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_tasks (
                    work_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    work_data TEXT NOT NULL,
                    files_data TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'submitting',
                    save_dir TEXT DEFAULT '',
                    download_method TEXT DEFAULT 'aria2',
                    created_at REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_tasks(status)
            """)
            conn.commit()

    def save_task(self, task):
        status_value = task.status.value if hasattr(task.status, 'value') else str(task.status)
        if status_value not in self._PERSISTED_STATUSES:
            self.remove_task(task.work_id)
            return
        work_data = json.dumps(task.work, ensure_ascii=False) if task.work else "{}"
        files_data = json.dumps(task.files, ensure_ascii=False) if task.files else "[]"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO pending_tasks (work_id, title, work_data, files_data, status, save_dir, download_method, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (task.work_id, task.title, work_data, files_data,
                  status_value, task.save_dir, task.download_method, task.created_at))
            conn.commit()

    def update_status(self, work_id: str, status):
        status_value = status.value if hasattr(status, 'value') else str(status)
        if status_value not in self._PERSISTED_STATUSES:
            self.remove_task(work_id)
            return
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE pending_tasks SET status = ? WHERE work_id = ?", (status_value, work_id))
            conn.commit()

    def remove_task(self, work_id: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pending_tasks WHERE work_id = ?", (work_id,))
            conn.commit()

    def get_all_pending(self) -> list:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT work_id, title, work_data, files_data, status, save_dir, download_method, created_at
                FROM pending_tasks ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            result = []
            for row in rows:
                try:
                    work_data = json.loads(row[2]) if row[2] else {}
                    files_data = json.loads(row[3]) if row[3] else []
                except (json.JSONDecodeError, TypeError):
                    work_data = {}
                    files_data = []
                result.append({
                    "work_id": row[0],
                    "title": row[1],
                    "work": work_data,
                    "files": files_data,
                    "status": row[4],
                    "save_dir": row[5],
                    "download_method": row[6],
                    "created_at": row[7],
                })
            return result

    def clear_all(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pending_tasks")
            conn.commit()