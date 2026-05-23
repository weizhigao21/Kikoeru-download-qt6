import sqlite3
import json
import threading
from contextlib import contextmanager


class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            self._local.conn = conn
        try:
            yield conn
        except Exception:
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
                CREATE TABLE IF NOT EXISTS works (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_id TEXT UNIQUE,
                    title TEXT,
                    source_id TEXT,
                    thumbnail_url TEXT,
                    tags TEXT,
                    other_editions TEXT,
                    page INTEGER,
                    hidden INTEGER DEFAULT 0,
                    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_work_id ON works(work_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_page ON works(page)
            """)
            cursor.execute("PRAGMA table_info(works)")
            columns = [row[1] for row in cursor.fetchall()]
            for col_name, col_type in [("hidden", "INTEGER DEFAULT 0"),
                                        ("main_cover_url", "TEXT"),
                                        ("vas", "TEXT"),
                                        ("circle_data", "TEXT")]:
                if col_name not in columns:
                    cursor.execute(f"ALTER TABLE works ADD COLUMN {col_name} {col_type}")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS translations (
                    work_id TEXT PRIMARY KEY,
                    translated_title TEXT
                )
            """)
            conn.commit()

    def save_works(self, works: list, page: int):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM works WHERE page = ?", (page,))

            works_data = []
            for work in works:
                work_id = str(work.get("id", ""))
                title = work.get("title", "")
                source_id = work.get("source_id", "")
                thumbnail_url = work.get("thumbnailCoverUrl", "")
                main_cover_url = work.get("mainCoverUrl", "")
                tags = json.dumps(work.get("tags", []), ensure_ascii=False)
                vas = json.dumps(work.get("vas", []), ensure_ascii=False)
                circle_data = json.dumps(work.get("circle", {}), ensure_ascii=False)
                other_editions = json.dumps(work.get("other_language_editions_in_db", []), ensure_ascii=False)
                works_data.append((work_id, title, source_id, thumbnail_url, main_cover_url,
                                   tags, vas, circle_data, other_editions, page))

            cursor.executemany("""
                INSERT INTO works (work_id, title, source_id, thumbnail_url, main_cover_url,
                                   tags, vas, circle_data, other_editions, page)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, works_data)

            conn.commit()

    def get_works_by_page(self, page: int) -> list:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM works WHERE page = ? AND hidden = 0 ORDER BY id", (page,))
            rows = cursor.fetchall()

            works = []
            for row in rows:
                thumbnail_url = row["thumbnail_url"] if "thumbnail_url" in row.keys() else ""
                main_cover_url = row["main_cover_url"] if "main_cover_url" in row.keys() else ""
                vas_str = row["vas"] if "vas" in row.keys() else ""
                circle_str = row["circle_data"] if "circle_data" in row.keys() else ""
                work = {
                    "id": row["work_id"],
                    "title": row["title"],
                    "source_id": row["source_id"],
                    "thumbnailCoverUrl": thumbnail_url,
                    "mainCoverUrl": main_cover_url,
                    "tags": json.loads(row["tags"]) if row["tags"] else [],
                    "vas": json.loads(vas_str) if vas_str else [],
                    "circle": json.loads(circle_str) if circle_str else {},
                    "other_language_editions_in_db": json.loads(row["other_editions"]) if row["other_editions"] else []
                }
                works.append(work)
            return works

    def get_max_page(self) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(page) FROM works WHERE hidden = 0")
            result = cursor.fetchone()[0]
            return result or 1

    def hide_work(self, work_id: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE works SET hidden = 1 WHERE work_id = ?", (work_id,))
            conn.commit()

    def get_work_detail_cached(self, work_id: str) -> dict:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM works WHERE work_id = ? LIMIT 1", (work_id,))
            row = cursor.fetchone()
            if not row:
                return None
            vas_str = row["vas"] if "vas" in row.keys() else ""
            circle_str = row["circle_data"] if "circle_data" in row.keys() else ""
            vas = json.loads(vas_str) if vas_str else []
            circle = json.loads(circle_str) if circle_str else {}
            if vas or (circle and isinstance(circle, dict) and circle.get("name")):
                return {"vas": vas, "circle": circle}
            return None

    def update_works_cache(self, work: dict, page: int):
        work_id = str(work.get("id", ""))
        if not work_id:
            return
        title = work.get("title", "")
        source_id = work.get("source_id", "")
        thumbnail_url = work.get("thumbnailCoverUrl", "")
        main_cover_url = work.get("mainCoverUrl", "")
        tags = json.dumps(work.get("tags", []), ensure_ascii=False)
        vas = json.dumps(work.get("vas", []), ensure_ascii=False)
        circle_data = json.dumps(work.get("circle", {}), ensure_ascii=False)
        other_editions = json.dumps(work.get("other_language_editions_in_db", []), ensure_ascii=False)
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE works SET title=?, source_id=?, thumbnail_url=?, main_cover_url=?,
                                 tags=?, vas=?, circle_data=?, other_editions=?
                WHERE work_id=? AND page=?
            """, (title, source_id, thumbnail_url, main_cover_url,
                  tags, vas, circle_data, other_editions, work_id, page))
            conn.commit()

    def get_translated_title(self, work_id: str) -> str:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT translated_title FROM translations WHERE work_id = ? LIMIT 1", (work_id,))
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
            return ""

    def save_translated_title(self, work_id: str, translated_title: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO translations (work_id, translated_title) VALUES (?, ?)",
                           (work_id, translated_title))
            conn.commit()

    def delete_translated_title(self, work_id: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM translations WHERE work_id = ?", (work_id,))
            conn.commit()


class DownloadHistoryManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            self._local.conn = conn
        try:
            yield conn
        except Exception:
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

    def add_download(self, rj_id: str, title: str, tags: list, cv_names: list, circle_name: str,
                     thumbnail_url: str = "", main_cover_url: str = "", vas: list = None,
                     circle_data: dict = None, other_editions: list = None):
        normalized_rj_id = f"RJ{self._normalize_rj_id(rj_id)}"
        with self._connect() as conn:
            cursor = conn.cursor()
            tags_str = ",".join(tags) if tags else ""
            cv_names_str = ",".join(cv_names) if cv_names else ""
            vas_str = json.dumps(vas, ensure_ascii=False) if vas else ""
            circle_str = json.dumps(circle_data, ensure_ascii=False) if circle_data else ""
            other_editions_str = json.dumps(other_editions, ensure_ascii=False) if other_editions else ""
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO download_history
                    (rj_id, title, tags, cv_names, circle_name, thumbnail_url, main_cover_url, vas, circle_data, other_editions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (normalized_rj_id, title, tags_str, cv_names_str, circle_name, thumbnail_url, main_cover_url, vas_str, circle_str, other_editions_str))
                conn.commit()
            except Exception as e:
                print(f"添加下载历史失败: {e}")

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
        order_by = order_map.get(sort, "created_at DESC")

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM download_history ORDER BY {order_by}")
            rows = cursor.fetchall()

            works = []
            for row in rows:
                thumbnail_url = row["thumbnail_url"] if "thumbnail_url" in row.keys() else ""
                main_cover_url = row["main_cover_url"] if "main_cover_url" in row.keys() else ""
                vas_str = row["vas"] if "vas" in row.keys() else ""
                circle_str = row["circle_data"] if "circle_data" in row.keys() else ""
                other_editions_str = row["other_editions"] if "other_editions" in row.keys() else ""

                work = {
                    "id": row["rj_id"],
                    "title": row["title"],
                    "source_id": row["rj_id"],
                    "thumbnailCoverUrl": thumbnail_url or "",
                    "mainCoverUrl": main_cover_url or "",
                    "tags": [{"i18n": {"zh-cn": {"name": tag}}} for tag in (row["tags"] or "").split(",") if tag],
                    "vas": json.loads(vas_str) if vas_str else [],
                    "circle": json.loads(circle_str) if circle_str else {},
                    "other_language_editions_in_db": json.loads(other_editions_str) if other_editions_str else []
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
                params.append(",".join(tags) if tags else "")
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
        if not rj_id:
            return ""
        return str(rj_id).replace("RJ", "").replace("rg", "").replace("RG", "").strip().zfill(6)

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
