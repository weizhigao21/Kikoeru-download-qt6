import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..api_client import get_api_client


class FilterMixin:
    PAGE_SIZE = 20

    def _apply_filter(self):
        if self.show_downloaded == 1:
            self.works = self.original_works.copy()
            self.current_work_index = -1
            if self.works:
                self.display_works_list()
                self.show_work_detail(0)
            else:
                self.display_empty_state()
                self.show_work_detail(-1)
        elif self.show_downloaded == 2:
            self.works = []
            for work in self.original_works:
                source_id = work.get('source_id', '')
                normalized_id = self._normalize_rj_id(source_id)
                if normalized_id not in self.downloaded_ids_cache:
                    self.works.append(work)
            self.current_work_index = -1
            if self.works:
                self.display_works_list()
                self.show_work_detail(0)
            else:
                self.display_empty_state()
                self.show_work_detail(-1)
        elif self.show_downloaded == 3:
            self._show_downloaded_page()

    def _show_downloaded_page(self):
        self.hide_loading()
        if not self._all_downloaded_works:
            self.display_empty_state()
            self.show_work_detail(-1)
            self.update_buttons()
            return
        start = (self._downloaded_page - 1) * self.PAGE_SIZE
        end = start + self.PAGE_SIZE
        page_works = self._all_downloaded_works[start:end]
        self.works = page_works
        self.downloaded_works_cache = page_works
        self.current_work_index = -1
        total = len(self._all_downloaded_works)
        total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self.max_page = total_pages
        self.data_loaded = True
        msg = f"已下载 {total} 个作品，第 {self._downloaded_page}/{total_pages} 页"
        self.status_label.config(text=msg)
        if self.works:
            self.display_works_list()
            self.show_work_detail(0)
        else:
            self.display_empty_state()
            self.show_work_detail(-1)
        self.update_buttons()

    def _load_downloaded_works(self, sort_key="download_time_desc"):
        self._all_downloaded_works = self.download_history.get_all_downloaded_works_full("download_time_desc")

        if not self._all_downloaded_works:
            self.root.after(0, self._on_no_downloaded_works)
            return

        self._all_downloaded_works = self._sort_works(self._all_downloaded_works, sort_key)
        
        self._fetched_ids.clear()
        for work in self._all_downloaded_works:
            rj_id = work.get("source_id")
            has_thumb = bool(work.get("thumbnailCoverUrl"))
            vas = work.get("vas")
            has_vas = vas is not None  # vas 为空列表 [] 也算"已获取"
            circle = work.get("circle")
            has_circle_name = circle is not None and isinstance(circle, dict)  # circle 为空字典 {} 也算"已获取"
            
            if rj_id and has_thumb and has_vas and has_circle_name:
                self._fetched_ids.add(rj_id)
        
        self._downloaded_cache_valid = True
        self.root.after(0, self._show_downloaded_page)

        self._check_and_fetch_missing_data()

    def _check_and_fetch_missing_data(self):
        if not self._all_downloaded_works:
            return
        missing = [(i, work.get("source_id"))
                   for i, work in enumerate(self._all_downloaded_works)
                   if work.get("source_id") not in self._fetched_ids
                   and (not work.get("thumbnailCoverUrl")
                        or work.get("vas") is None
                        or work.get("circle") is None)]
        
        if missing:
            self.status_label.config(text=f"正在补全 {len(missing)} 个作品的信息...")
            threading.Thread(target=self._fetch_missing_thumbnails, args=(missing,), daemon=True).start()

    def _sort_works(self, works, sort_key):
        if sort_key == "download_time_desc":
            return works[:]
        elif sort_key == "download_time_asc":
            return list(reversed(works))
        elif sort_key == "title_asc":
            return sorted(works, key=lambda w: w.get("title", "").lower())
        elif sort_key == "title_desc":
            return sorted(works, key=lambda w: w.get("title", "").lower(), reverse=True)
        elif sort_key == "id_asc":
            return sorted(works, key=lambda w: w.get("source_id", ""))
        elif sort_key == "id_desc":
            return sorted(works, key=lambda w: w.get("source_id", ""), reverse=True)
        return works[:]

    def _on_sort_changed(self):
        if self.show_downloaded == 3 and self._all_downloaded_works:
            sort_key = self.sort_map.get(self.sort_var.get(), "download_time_desc")
            self._all_downloaded_works = self._sort_works(self._all_downloaded_works, sort_key)
            self._downloaded_page = 1
            self.page_var.set("1")
            self.root.after(0, self._show_downloaded_page)

    def _fetch_missing_thumbnails(self, missing_items):
        def extract_tags(tags_data):
            raw = [tag["i18n"]["zh-cn"]["name"]
                   for tag in tags_data
                   if tag.get("i18n", {}).get("zh-cn")]
            return [t for t in raw if t]

        def fetch_one(args):
            index, rj_id = args
            try:
                api_client = get_api_client()
                data = api_client.fetch_work_detail(rj_id)
                thumbnail_url = data.get("thumbnailCoverUrl", "")
                main_cover_url = data.get("mainCoverUrl", "")
                tags = data.get("tags", [])
                vas = data.get("vas", [])
                circle = data.get("circle", {})
                other_editions = data.get("other_language_editions_in_db", [])
                return rj_id, thumbnail_url, main_cover_url, tags, vas, circle, other_editions
            except Exception:
                return rj_id, None, None, None, None, None, None

        saved = 0
        total = len(missing_items)
        batch_size = 20
        _progress = {'done': 0}

        def _throttled_progress():
            done = _progress.get('done', 0)
            if done < total:
                self.status_label.config(text=f"正在补全信息... ({done}/{total})")

        for batch_start in range(0, total, batch_size):
            batch = missing_items[batch_start:batch_start + batch_size]
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(fetch_one, item): item for item in batch}
                for future in as_completed(futures):
                    rj_id, thumb_url, main_url, tags, vas, circle, other_editions = future.result()
                    self._fetched_ids.add(rj_id)
                    
                    if thumb_url is None:
                        continue
                    
                    tag_names = extract_tags(tags) if tags else []
                    
                    self.download_history.update_work_detail(
                        rj_id,
                        thumbnail_url=thumb_url or None,
                        main_cover_url=main_url or None,
                        tags=tag_names or None,
                        vas=vas or None,
                        circle_data=circle or None,
                        other_editions=other_editions or None
                    )
                    saved += 1
                    for work in self._all_downloaded_works:
                        if work.get("source_id") == rj_id:
                            if thumb_url:
                                work["thumbnailCoverUrl"] = thumb_url
                                work["mainCoverUrl"] = main_url
                            if tags:
                                work["tags"] = tags
                            if vas:
                                work["vas"] = vas
                            if circle:
                                work["circle"] = circle
                            if other_editions:
                                work["other_language_editions_in_db"] = other_editions
                            break
            _progress['done'] = min(batch_start + batch_size, total)
            if batch_start + batch_size < total:
                self.root.after(0, _throttled_progress)

        self.root.after(0, self._on_thumbnails_fetched, saved)

    def _on_thumbnails_fetched(self, count):
        if self.show_downloaded != 3:
            return
        total_pages = max(1, (len(self._all_downloaded_works) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self._downloaded_page > total_pages:
            self._downloaded_page = total_pages
        self.page_var.set(str(self._downloaded_page))
        self._show_downloaded_page()
        self.status_label.config(text=f"已补全 {count} 个作品信息" if count else "所有作品信息已是最新")

    def _on_no_downloaded_works(self):
        self.hide_loading()
        self.works = []
        self.downloaded_works_cache = []
        self._all_downloaded_works = []
        self.current_work_index = -1
        self.max_page = 1
        self.status_label.config(text="暂无已下载作品")
        self.display_empty_state()
        self.show_work_detail(-1)
        self.update_buttons()
