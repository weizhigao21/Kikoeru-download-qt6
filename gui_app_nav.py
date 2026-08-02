import tkinter as tk
from tkinter import messagebox
import threading
import logging

from src.config import SHOW_ALL, HIDE_DOWNLOADED, DOWNLOADED_TAB

logger = logging.getLogger('gui_app')


class NavigationMixin:
    def _on_tab_changed(self, event):
        tab_text = self.tab_var.get()
        _tab_map = {"推荐作品": "recommend", "最新收录": "latest", "下载作品": "downloaded"}
        new_tab = _tab_map.get(tab_text, "recommend")

        if self.current_tab == new_tab:
            return

        if self.loading:
            _reverse = {v: k for k, v in _tab_map.items()}
            self.tab_var.set(_reverse.get(self.current_tab, "推荐作品"))
            return

        self.current_tab = new_tab
        self.current_page = 1
        self.page_var.set("1")
        self._load_downloaded_ids()
        self._bump_generation()

        if new_tab == "downloaded":
            self.show_downloaded = DOWNLOADED_TAB
            self.sort_label.pack(side=tk.LEFT, padx=(10, 5))
            self.sort_combo.pack(side=tk.LEFT, padx=5)
            self.hide_dl_btn.pack_forget()
            self.clear_search_history()
            if self.current_tags or self.circle_query or self.keyword_query:
                self.current_page = 1
                self.page_var.set("1")
                self.loading = True
                self._search_in_downloaded_works()
            elif self._all_downloaded_works and self._downloaded_cache_valid:
                self.data_loaded = True
                self._show_downloaded_page()
            else:
                self.status_label.config(text="正在加载已下载作品信息...")
                sort_key = self.sort_map.get(self.sort_var.get(), "download_time_desc")
                threading.Thread(target=self._load_downloaded_works, args=(sort_key,), daemon=True).start()
        else:
            self.sort_label.pack_forget()
            self.sort_combo.pack_forget()
            self.hide_dl_btn.pack(side=tk.LEFT, padx=(10, 5))
            if self._hide_downloaded:
                self.show_downloaded = HIDE_DOWNLOADED
                self.hide_dl_btn.config(text="隐藏下载")
            else:
                self.show_downloaded = SHOW_ALL
                self.hide_dl_btn.config(text="显示全部")

            if self.current_tags:
                self._search_by_tag(1)
            elif self.circle_query:
                self.status_label.config(text=f"正在搜索厂商: {self.circle_query} (第1页)...")
                self.loading = True
                gen = self._nav_generation
                self.show_loading()
                threading.Thread(target=self._search_by_circle_async, args=(1, gen), daemon=True).start()
            elif self.keyword_query:
                self.status_label.config(text=f"正在搜索: {self.keyword_query} (第1页)...")
                self.loading = True
                gen = self._nav_generation
                self.show_loading()
                threading.Thread(target=self._search_by_keyword_async, args=(1, gen), daemon=True).start()
            else:
                self.load_data_async()

    def load_data_async(self):
        self.loading = True
        self._bump_generation()
        gen = self._nav_generation
        logger.debug("load_data_async 开始 gen=%s page=%s", gen, self.current_page)
        self.show_loading()
        self.refresh_btn.config(state=tk.DISABLED)

        if self.current_tab == "downloaded":
            sort_key = self.sort_map.get(self.sort_var.get(), "download_time_desc")
            threading.Thread(target=self._load_downloaded_works, args=(sort_key,), daemon=True).start()
            return

        # 捕获快照避免闭包执行期间实例属性被主线程修改导致状态不一致
        tab_snapshot = self.current_tab
        page_snapshot = self.current_page

        def load():
            logger.debug("load() 后台线程启动 tab=%s page=%s", tab_snapshot, page_snapshot)
            if tab_snapshot == "recommend":
                cached_works = self.db.get_works_by_page(page_snapshot)
                logger.debug("load() DB查询: %s 条", len(cached_works) if cached_works else 0)
                if cached_works:
                    if self._nav_generation != gen:
                        logger.debug("load() gen过期, 取消")
                        self.root.after(0, self._safe_reset_loading)
                        return
                    self.works = cached_works
                    self.all_works = cached_works.copy()
                    self.original_works = cached_works.copy()
                    self.max_page = self.db.get_max_page()
                    self.data_loaded = True
                    logger.debug("load() 提交 _on_data_loaded(True)")
                    self.root.after(0, self._on_data_loaded, True)
                else:
                    logger.debug("load() 走API路径")
                    self._fetch_from_api(gen)
            else:
                logger.debug("load() 最新收录走API")
                self._fetch_latest_from_api(gen)
            logger.debug("load() 后台线程结束")

        threading.Thread(target=load, daemon=True).start()

    def _fetch_from_api(self, gen=0):
        try:
            logger.debug("_fetch_from_api 开始 page=%s gen=%s", self.current_page, gen)
            from src.api_client import get_api_client
            api_client = get_api_client()
            works, max_page = api_client.fetch_works_page(self.current_page)
            logger.debug("_fetch_from_api API返回 works=%s max_page=%s", len(works) if works else 0, max_page)
            if self._nav_generation != gen:
                logger.debug("_fetch_from_api gen过期, 取消")
                self.root.after(0, self._safe_reset_loading)
                return
            self.works = works
            self.all_works = self.works.copy()
            self.original_works = self.works.copy()
            self.max_page = max_page
            self.db.save_works(self.works, self.current_page)
            self.data_loaded = True
            logger.debug("_fetch_from_api 提交 _on_data_loaded(False)")
            self.root.after(0, self._on_data_loaded, False)
        except Exception as e:
            logger.exception("_fetch_from_api 异常: %s", e)
            if self._nav_generation != gen:
                self.root.after(0, self._safe_reset_loading)
                return
            self.root.after(0, self._on_error, f"加载数据失败: {str(e)}")

    def _fetch_latest_from_api(self, gen=0):
        try:
            from src.api_client import get_api_client
            api_client = get_api_client()
            works, max_page = api_client.fetch_latest_works_page(self.current_page)
            if self._nav_generation != gen:
                self.root.after(0, self._safe_reset_loading)
                return
            self.works = works
            self.all_works = self.works.copy()
            self.original_works = self.works.copy()
            self.max_page = max_page
            self.data_loaded = True
            self.root.after(0, self._on_data_loaded, False)
        except Exception as e:
            logger.exception("_fetch_latest_from_api 异常: %s", e)
            if self._nav_generation != gen:
                self.root.after(0, self._safe_reset_loading)
                return
            self.root.after(0, self._on_error, f"加载数据失败: {str(e)}")

    def _on_data_loaded(self, from_cache: bool):
        logger.debug("_on_data_loaded 开始 from_cache=%s page=%s", from_cache, self.current_page)
        self.hide_loading()
        self.refresh_btn.config(state=tk.NORMAL)
        self.status_label.config(text=f"✓ 数据加载完成 (第{self.current_page}页)" if from_cache else f"↓ 从网络获取 (第{self.current_page}页)")

        if self.works:
            logger.debug("_on_data_loaded >> 批量UI更新")
            if self.show_downloaded == HIDE_DOWNLOADED:
                self._apply_filter()
            else:
                self._batch_ui_update()
            logger.debug("_on_data_loaded 完成")
        else:
            self.display_empty_state()
            self.update_buttons()
            self.status_label.config(text="当前页没有数据")

    def _batch_ui_update(self):
        self.hide_loading()
        self.refresh_btn.config(state=tk.NORMAL)

        try:
            self.display_works_list()
            self.show_work_detail(0)
        except Exception as e:
            logger.error("_batch_ui_update 异常: %s", e)

        self.update_buttons()

    def _on_error(self, msg: str):
        self.hide_loading()
        self.refresh_btn.config(state=tk.NORMAL)
        self.update_buttons()
        messagebox.showerror("错误", msg)

    def _safe_reset_loading(self):
        self.loading = False
        self.data_loaded = False
        self.hide_loading()
        self.refresh_btn.config(state=tk.NORMAL)
        self.update_buttons()

    def _toggle_hide_downloaded(self):
        if self.current_tab == "downloaded":
            return
        self._hide_downloaded = not self._hide_downloaded
        if self._hide_downloaded:
            self.show_downloaded = HIDE_DOWNLOADED
            self.hide_dl_btn.config(text="隐藏下载")
        else:
            self.show_downloaded = SHOW_ALL
            self.hide_dl_btn.config(text="显示全部")
        self.current_page = 1
        self.page_var.set("1")
        self._bump_generation()
        self._apply_filter()

    def refresh_data(self):
        self.keyword_query = ""
        self.current_tags = []
        self.circle_query = ""
        self._fetched_ids.clear()
        self.clear_search_history()
        self.load_data_async()

    def _navigate_search(self, page: int):
        """翻页时根据当前搜索条件触发对应加载路径（标签/厂商/关键词/无搜索）。

        消除 go_to_page/prev_page/next_page 中重复的搜索分支代码。
        """
        if self.current_tags:
            self.search_by_tag(page)
        elif self.circle_query:
            self._bump_generation()
            gen = self._nav_generation
            self.loading = True
            self.show_loading()
            threading.Thread(target=self._search_by_circle_async, args=(page, gen), daemon=True).start()
        elif self.keyword_query:
            self._bump_generation()
            gen = self._nav_generation
            self.loading = True
            self.show_loading()
            threading.Thread(target=self._search_by_keyword_async, args=(page, gen), daemon=True).start()
        else:
            self.load_data_async()

    def go_to_page(self):
        if self.loading:
            return
        if self._nav_debounce_id:
            return
        self._nav_debounce_id = self.root.after(300, self._clear_nav_debounce)
        try:
            page = int(self.page_var.get())
            if page < 1:
                page = 1
            if self.show_downloaded == DOWNLOADED_TAB:
                if self.current_tags or self.keyword_query or self.circle_query:
                    self._downloaded_page = page
                    self.page_var.set(str(page))
                    self._show_searched_downloaded_page()
                else:
                    if not self._all_downloaded_works:
                        return
                    total_pages = max(1, (len(self._all_downloaded_works) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
                    page = min(page, total_pages)
                    self._downloaded_page = page
                    self.page_var.set(str(page))
                    self._show_downloaded_page()
                return
            self.current_page = page
            self.page_var.set(str(page))
            self._navigate_search(self.current_page)
        except ValueError:
            messagebox.showerror("错误", "请输入有效的页码")

    def _clear_nav_debounce(self):
        self._nav_debounce_id = None

    def prev_page(self):
        if self.loading:
            return
        if self.show_downloaded == DOWNLOADED_TAB:
            if not self._all_downloaded_works or self._downloaded_page <= 1:
                return
            if self._nav_debounce_id:
                return
            self._nav_debounce_id = self.root.after(300, self._clear_nav_debounce)
            self._downloaded_page -= 1
            self.page_var.set(str(self._downloaded_page))
            if self.current_tags or self.keyword_query or self.circle_query:
                self._show_searched_downloaded_page()
            else:
                self._show_downloaded_page()
            return
        if self.current_page <= 1:
            return
        if self._nav_debounce_id:
            return
        self._nav_debounce_id = self.root.after(300, self._clear_nav_debounce)
        self.current_page -= 1
        self.page_var.set(str(self.current_page))
        self._navigate_search(self.current_page)

    def next_page(self):
        if self.loading:
            return
        if self.show_downloaded == DOWNLOADED_TAB:
            if not self._all_downloaded_works:
                return
            if self.current_tags or self.keyword_query or self.circle_query:
                total_pages = max(1, (len(self.works) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
                if self._downloaded_page >= total_pages:
                    return
            else:
                total_pages = max(1, (len(self._all_downloaded_works) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
                if self._downloaded_page >= total_pages:
                    return
            if self._nav_debounce_id:
                return
            self._nav_debounce_id = self.root.after(300, self._clear_nav_debounce)
            self._downloaded_page += 1
            self.page_var.set(str(self._downloaded_page))
            if self.current_tags or self.keyword_query or self.circle_query:
                self._show_searched_downloaded_page()
            else:
                self._show_downloaded_page()
            return
        if self._nav_debounce_id:
            return
        self._nav_debounce_id = self.root.after(300, self._clear_nav_debounce)
        self.current_page += 1
        self.page_var.set(str(self.current_page))
        self._navigate_search(self.current_page)

    def prev_work(self):
        if self.works and self.current_work_index > 0:
            self.show_work_detail(self.current_work_index - 1)

    def next_work(self):
        if self.works and self.current_work_index < len(self.works) - 1:
            self.show_work_detail(self.current_work_index + 1)

    def update_buttons(self):
        if self.show_downloaded == DOWNLOADED_TAB:
            if not self._all_downloaded_works:
                self.prev_btn.config(state=tk.DISABLED)
                self.next_btn.config(state=tk.DISABLED)
                return
            if self.current_tags or self.keyword_query or self.circle_query:
                total_pages = max(1, (len(self.works) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            else:
                total_pages = max(1, (len(self._all_downloaded_works) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            if self._downloaded_page > 1:
                self.prev_btn.config(state=tk.NORMAL)
            else:
                self.prev_btn.config(state=tk.DISABLED)
            if self._downloaded_page < total_pages:
                self.next_btn.config(state=tk.NORMAL)
            else:
                self.next_btn.config(state=tk.DISABLED)
            return
        if self.current_page > 1 and self.data_loaded:
            self.prev_btn.config(state=tk.NORMAL)
        else:
            self.prev_btn.config(state=tk.DISABLED)
        if self.data_loaded:
            self.next_btn.config(state=tk.NORMAL)
        else:
            self.next_btn.config(state=tk.DISABLED)