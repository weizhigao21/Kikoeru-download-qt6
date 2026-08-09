import sqlite3
import json
import logging

from .base import BaseDatabaseManager
from ..utils import normalize_rj_id

logger = logging.getLogger(__name__)


class DownloadHistoryManager(BaseDatabaseManager):

    def _init_db(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS download_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rj_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    tags TEXT,
                    cv_names TEXT,
                    circle_name TEXT,
                    thumbnail_url TEXT,
                    main_cover_url TEXT,
                    vas TEXT,
                    circle_data TEXT,
                    other_editions TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

            cursor.execute("PRAGMA table_info(download_history)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            new_columns = [
                ("thumbnail_url", "TEXT"),
                ("main_cover_url", "TEXT"),
                ("vas", "TEXT"),
                ("circle_data", "TEXT"),
                ("other_editions", "TEXT"),
                ("translated_title", "TEXT")
            ]
            for col_name, col_type in new_columns:
                if col_name not in existing_columns:
                    cursor.execute(f"ALTER TABLE download_history ADD COLUMN {col_name} {col_type}")

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_dl_rj_id ON download_history(rj_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_dl_created_at ON download_history(created_at)
            """)
            conn.commit()

    @staticmethod
    def _parse_tags(tags_str):
        """解析 tags 字段，兼容 JSON 数组和旧版逗号分隔格式。

        旧格式：tag1,tag2,tag3（逗号分隔）
        新格式：["tag1","tag2","tag3"]（JSON 数组）
        """
        if not tags_str:
            return []
        # 优先尝试 JSON 解析
        if tags_str.strip().startswith("["):
            parsed = DownloadHistoryManager._safe_json_load(tags_str, [])
            if isinstance(parsed, list):
                return parsed
        # 回退到旧版逗号分隔格式
        return [t for t in tags_str.split(",") if t]

    def add_download(self, rj_id: str, title: str, tags: list, cv_names: list, circle_name: str,
                     thumbnail_url: str = "", main_cover_url: str = "", vas: list = None,
                     circle_data: dict = None, other_editions: list = None):
        normalized_rj_id = f"RJ{self._normalize_rj_id(rj_id)}"
        with self._connect() as conn:
            cursor = conn.cursor()
            # tags 改用 JSON 序列化，避免标签名含逗号时被错误分割
            tags_str = json.dumps(tags, ensure_ascii=False) if tags else ""
            cv_names_str = ",".join(cv_names) if cv_names else ""
            vas_str = json.dumps(vas, ensure_ascii=False) if vas else ""
            circle_str = json.dumps(circle_data, ensure_ascii=False) if circle_data else ""
            other_editions_str = json.dumps(other_editions, ensure_ascii=False) if other_editions else ""
            # 让异常传播：_connect 的 contextmanager 会自动 rollback
            cursor.execute("""
                INSERT OR REPLACE INTO download_history
                (rj_id, title, tags, cv_names, circle_name, thumbnail_url, main_cover_url, vas, circle_data, other_editions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (normalized_rj_id, title, tags_str, cv_names_str, circle_name, thumbnail_url, main_cover_url, vas_str, circle_str, other_editions_str))

    def get_download_history(self) -> list:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM download_history ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_all_downloaded_works_full(self, sort: str = "download_time_desc") -> list:
        order_map = {
            "download_time_desc": "created_at DESC",
            "download_time_asc": "created_at ASC",
            "title_asc": "title ASC",
            "title_desc": "title DESC",
            "id_asc": "rj_id ASC",
            "id_desc": "rj_id DESC"
        }
        if sort not in order_map:
            sort = "download_time_desc"
        order_by = order_map[sort]

        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT rj_id, title, tags, thumbnail_url, main_cover_url,
                       vas, circle_data, other_editions
                FROM download_history ORDER BY {order_by}
            """)
            rows = cursor.fetchall()

            works = []
            for row in rows:
                # _parse_tags 兼容 JSON 数组和旧版逗号分隔格式
                tags_list = self._parse_tags(row[2])
                work = {
                    "id": row[0] or "",
                    "title": row[1] or "",
                    "source_id": row[0] or "",
                    "thumbnailCoverUrl": row[3] or "",
                    "mainCoverUrl": row[4] or "",
                    "tags": [{"i18n": {"zh-cn": {"name": tag}}} for tag in tags_list],
                    "vas": self._safe_json_load(row[5], []),
                    "circle": self._safe_json_load(row[6], {}),
                    "other_language_editions_in_db": self._safe_json_load(row[7], [])
                }
                works.append(work)
            return works

    def delete_download(self, rj_id: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM download_history WHERE rj_id = ?", (rj_id,))
            conn.commit()

    def update_thumbnail(self, rj_id: str, thumbnail_url: str, main_cover_url: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE download_history SET thumbnail_url = ?, main_cover_url = ? WHERE rj_id = ?",
                (thumbnail_url, main_cover_url, rj_id)
            )
            conn.commit()

    def update_work_detail(self, rj_id: str, thumbnail_url: str = None, main_cover_url: str = None,
                           tags: list = None, vas: list = None, circle_data: dict = None,
                           other_editions: list = None):
        with self._connect() as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            if thumbnail_url is not None:
                updates.append("thumbnail_url = ?")
                params.append(thumbnail_url)
            if main_cover_url is not None:
                updates.append("main_cover_url = ?")
                params.append(main_cover_url)
            if tags is not None:
                updates.append("tags = ?")
                # tags 改用 JSON 序列化保持一致
                params.append(json.dumps(tags, ensure_ascii=False) if tags else "")
            if vas is not None:
                updates.append("vas = ?")
                params.append(json.dumps(vas, ensure_ascii=False) if vas else "")
            if circle_data is not None:
                updates.append("circle_data = ?")
                params.append(json.dumps(circle_data, ensure_ascii=False) if circle_data else "")
            if other_editions is not None:
                updates.append("other_editions = ?")
                params.append(json.dumps(other_editions, ensure_ascii=False) if other_editions else "")
            if updates:
                normalized_id = f"RJ{self._normalize_rj_id(rj_id)}"
                params.append(normalized_id)
                cursor.execute(f"UPDATE download_history SET {', '.join(updates)} WHERE rj_id = ?", params)
                conn.commit()

    def _normalize_rj_id(self, rj_id):
        return normalize_rj_id(rj_id)

    def is_downloaded(self, rj_id: str) -> bool:
        normalized = self._normalize_rj_id(rj_id)
        if not normalized:
            return False
        target = f"RJ{normalized}"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM download_history WHERE rj_id = ? LIMIT 1", (target,))
            return cursor.fetchone() is not None

    def get_all_downloaded_rj_ids(self) -> list:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT rj_id FROM download_history")
            rows = cursor.fetchall()
            result = []
            for row in rows:
                normalized = self._normalize_rj_id(row[0])
                if normalized:
                    result.append(f"RJ{normalized}")
            return result

    def get_translated_title(self, rj_id: str) -> str:
        normalized = f"RJ{self._normalize_rj_id(rj_id)}"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT translated_title FROM download_history WHERE rj_id = ? LIMIT 1", (normalized,))
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
            return ""

    def save_translated_title(self, rj_id: str, translated_title: str):
        normalized = f"RJ{self._normalize_rj_id(rj_id)}"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE download_history SET translated_title = ? WHERE rj_id = ?",
                           (translated_title, normalized))
            conn.commit()