import json

from .base import BaseDatabaseManager


class DatabaseManager(BaseDatabaseManager):

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
            cursor = conn.cursor()

            cursor.execute("""
                SELECT work_id, title, source_id, thumbnail_url, main_cover_url,
                       tags, vas, circle_data, other_editions
                FROM works WHERE page = ? AND hidden = 0 ORDER BY id
            """, (page,))
            rows = cursor.fetchall()

            works = []
            for row in rows:
                work = {
                    "id": row[0],
                    "title": row[1] or "",
                    "source_id": row[2] or "",
                    "thumbnailCoverUrl": row[3] or "",
                    "mainCoverUrl": row[4] or "",
                    "tags": self._safe_json_load(row[5], []),
                    "vas": self._safe_json_load(row[6], []),
                    "circle": self._safe_json_load(row[7], {}),
                    "other_language_editions_in_db": self._safe_json_load(row[8], [])
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
            cursor = conn.cursor()
            # 明确指定列名，避免 SELECT * 冗余读取（仅需 vas / circle_data 两列；
            # 旧库缺失列已由 _init_db 的 ALTER TABLE 迁移补齐）
            cursor.execute("SELECT vas, circle_data FROM works WHERE work_id = ? LIMIT 1", (work_id,))
            row = cursor.fetchone()
            if not row:
                return None
            # 使用 _safe_json_load 容错处理损坏的 JSON，与同类其他方法一致
            vas = self._safe_json_load(row[0], [])
            circle = self._safe_json_load(row[1], {})
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

    def get_translated_titles(self, work_ids) -> dict:
        """批量查询翻译标题，一次 SQL 返回 {work_id: translated_title}。

        避免翻页时每张卡片单独执行一次 get_translated_title 的 UI 线程阻塞。
        """
        ids = [str(w) for w in work_ids if str(w)]
        if not ids:
            return {}
        placeholders = ",".join("?" * len(ids))
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT work_id, translated_title FROM translations "
                f"WHERE work_id IN ({placeholders})",
                ids,
            )
            rows = cursor.fetchall()
        return {r[0]: r[1] for r in rows if r[0] and r[1]}

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