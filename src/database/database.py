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
                                        ("circle_data", "TEXT"),
                                        ("release", "TEXT")]:
                if col_name not in columns:
                    cursor.execute(f"ALTER TABLE works ADD COLUMN {col_name} {col_type}")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS translations (
                    work_id TEXT PRIMARY KEY,
                    translated_title TEXT
                )
            """)
            # 旧库缺列迁移：词义拆解（v2.2.0）
            cursor.execute("PRAGMA table_info(translations)")
            t_columns = [row[1] for row in cursor.fetchall()]
            if "title_explanation" not in t_columns:
                cursor.execute("ALTER TABLE translations ADD COLUMN title_explanation TEXT")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS collector_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
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
                release = work.get("release", "") or ""
                works_data.append((work_id, title, source_id, thumbnail_url, main_cover_url,
                                   tags, vas, circle_data, other_editions, release, page))

            cursor.executemany("""
                INSERT INTO works (work_id, title, source_id, thumbnail_url, main_cover_url,
                                   tags, vas, circle_data, other_editions, release, page)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, works_data)

            conn.commit()

    def upsert_works(self, works: list, page: int):
        """按 work_id 去重写入（ON CONFLICT DO UPDATE）。

        供自动采集使用：持续翻页时同一作品会随「最新收录」列表滚动而跨页重复出现，
        save_works 的「按页删除再插入」会撞 work_id UNIQUE 约束，这里改为 upsert。
        注意：不更新 hidden（保留用户隐藏操作）与 create_time（保留首次收录时间）。
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            works_data = []
            for work in works:
                work_id = str(work.get("id", ""))
                if not work_id:
                    continue
                title = work.get("title", "")
                source_id = work.get("source_id", "")
                thumbnail_url = work.get("thumbnailCoverUrl", "")
                main_cover_url = work.get("mainCoverUrl", "")
                tags = json.dumps(work.get("tags", []), ensure_ascii=False)
                vas = json.dumps(work.get("vas", []), ensure_ascii=False)
                circle_data = json.dumps(work.get("circle", {}), ensure_ascii=False)
                other_editions = json.dumps(work.get("other_language_editions_in_db", []), ensure_ascii=False)
                release = work.get("release", "") or ""
                works_data.append((work_id, title, source_id, thumbnail_url, main_cover_url,
                                   tags, vas, circle_data, other_editions, release, page))

            cursor.executemany("""
                INSERT INTO works (work_id, title, source_id, thumbnail_url, main_cover_url,
                                   tags, vas, circle_data, other_editions, release, page)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(work_id) DO UPDATE SET
                    title=excluded.title,
                    source_id=excluded.source_id,
                    thumbnail_url=excluded.thumbnail_url,
                    main_cover_url=excluded.main_cover_url,
                    tags=excluded.tags,
                    vas=excluded.vas,
                    circle_data=excluded.circle_data,
                    other_editions=excluded.other_editions,
                    release=excluded.release,
                    page=excluded.page
            """, works_data)

            conn.commit()

    def existing_work_ids(self, work_ids: list) -> set:
        """返回 work_ids 中已存在于 works 表的 work_id 集合（批量查重）。"""
        ids = [str(w) for w in work_ids if str(w)]
        if not ids:
            return set()
        placeholders = ",".join("?" * len(ids))
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT work_id FROM works WHERE work_id IN ({placeholders})",
                ids,
            )
            return {row[0] for row in cursor.fetchall()}

    def get_works_by_page(self, page: int) -> list:
        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT work_id, title, source_id, thumbnail_url, main_cover_url,
                       tags, vas, circle_data, other_editions, release
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
                    "other_language_editions_in_db": self._safe_json_load(row[8], []),
                    "release": row[9] or ""
                }
                works.append(work)
            return works

    def get_max_page(self) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(page) FROM works WHERE hidden = 0")
            result = cursor.fetchone()[0]
            return result or 1

    def get_all_works(self, order: str = "release_desc") -> list:
        """返回全部未隐藏作品（下载页数据源）。字段与 get_works_by_page 一致。

        默认按发售顺序倒序（最新发售在前）：有 release 的按发售日期倒序；
        无 release 的（BJ/VJ 旧数据，workInfo 查不到）排最后，按编号数值倒序兜底。
        """
        order_map = {
            "release_desc": "CASE WHEN release IS NULL OR release = '' THEN 1 ELSE 0 END, "
                            "release DESC, CAST(SUBSTR(COALESCE(source_id, ''), 3) AS INTEGER) DESC",
            "release_asc": "CASE WHEN release IS NULL OR release = '' THEN 1 ELSE 0 END, "
                           "release ASC, CAST(SUBSTR(COALESCE(source_id, ''), 3) AS INTEGER) ASC",
            "id_desc": "id DESC",
            "id_asc": "id ASC",
            "title_asc": "title ASC",
            "title_desc": "title DESC",
        }
        order_by = order_map.get(order, order_map["release_desc"])
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT work_id, title, source_id, thumbnail_url, main_cover_url,
                       tags, vas, circle_data, other_editions, release
                FROM works WHERE hidden = 0 ORDER BY {order_by}
            """)
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
                    "other_language_editions_in_db": self._safe_json_load(row[8], []),
                    "release": row[9] or ""
                }
                works.append(work)
            return works

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
        """保存翻译标题。

        UPSERT（ON CONFLICT DO UPDATE）而非 INSERT OR REPLACE：
        REPLACE 会删旧行插新行，未指定的 title_explanation 列会被重置为 NULL，
        导致先拆解、后编辑译文时拆解结果静默丢失（v2.2.0 两列共存后必须）。
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO translations (work_id, translated_title) VALUES (?, ?) "
                "ON CONFLICT(work_id) DO UPDATE SET translated_title = excluded.translated_title",
                (work_id, translated_title))
            conn.commit()

    def get_title_explanation(self, work_id: str) -> str:
        """查询词义拆解（v2.2.0，translations 表 title_explanation 列）。"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title_explanation FROM translations WHERE work_id = ? LIMIT 1", (work_id,))
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
            return ""

    def save_title_explanation(self, work_id: str, explanation: str):
        """保存词义拆解（UPSERT，只更新 explanation 列，保留 translated_title）。"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO translations (work_id, title_explanation) VALUES (?, ?) "
                "ON CONFLICT(work_id) DO UPDATE SET title_explanation = excluded.title_explanation",
                (work_id, explanation))
            conn.commit()

    def delete_translated_title(self, work_id: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM translations WHERE work_id = ?", (work_id,))
            conn.commit()

    def update_release(self, work_id: str, release: str):
        """仅更新作品的发售日期（release 回填用，不动其他字段）。"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE works SET release = ? WHERE work_id = ?", (release, work_id))
            conn.commit()

    def save_collector_state(self, state: dict):
        """持久化采集游标状态（单行 JSON，key='main'）。"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO collector_state (key, value) VALUES ('main', ?)",
                (json.dumps(state, ensure_ascii=False),),
            )
            conn.commit()

    def load_collector_state(self) -> dict:
        """读取采集游标状态；无记录或损坏返回空 dict。"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM collector_state WHERE key = 'main'")
            row = cursor.fetchone()
        if not row:
            return {}
        state = self._safe_json_load(row[0], {})
        return state if isinstance(state, dict) else {}