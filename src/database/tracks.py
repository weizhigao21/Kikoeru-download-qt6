import json
import time

from .base import BaseDatabaseManager


class WorkTracksManager(BaseDatabaseManager):
    """作品文件树(tracks)持久化缓存。

    完整缓存 tracks JSON（含 mediaDownloadUrl），用于：
    1. DownloadWindow 双击时三层查询的第一层（命中即展示，避免打 API）
    2. 下载失败重试时 _refresh_task_urls 拿到新 tracks 后同步更新 DB
    """

    def _init_db(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS work_tracks (
                    source_id   TEXT PRIMARY KEY,
                    tracks_data TEXT NOT NULL,
                    title       TEXT DEFAULT '',
                    updated_at  REAL NOT NULL
                )
            """)
            conn.commit()

    def get_tracks(self, source_id: str):
        """返回 tracks（list/dict）；未命中或数据损坏返回 None（让调用方回退到 API）。"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tracks_data FROM work_tracks WHERE source_id = ?", (source_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = self._safe_json_load(row[0], default=None)
            # 空 dict 表示损坏/无效，视为未命中走 API
            return data if isinstance(data, (list, dict)) and data else None

    def save_tracks(self, source_id: str, tracks, title: str = ""):
        """INSERT OR REPLACE 完整 tracks JSON。"""
        tracks_data = json.dumps(tracks, ensure_ascii=False)
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO work_tracks (source_id, tracks_data, title, updated_at)
                VALUES (?, ?, ?, ?)
            """, (source_id, tracks_data, title, time.time()))
            conn.commit()

    def remove_tracks(self, source_id: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM work_tracks WHERE source_id = ?", (source_id,))
            conn.commit()
