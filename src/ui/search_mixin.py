import tkinter as tk
from tkinter import messagebox
import threading

from ..api_client import get_api_client


class SearchMixin:
    def _show_search_entry(self):
        self.search_tags_frame.pack_forget()
        for widget in self.search_tags_frame.winfo_children():
            widget.pack_forget()
        self.search_entry.pack(side=tk.LEFT, padx=5, pady=3)

    def _search_by_tag(self, tag_or_page, page=None):
        self.keyword_query = ""
        self.circle_query = ""
        if isinstance(tag_or_page, str):
            tag = tag_or_page
            if page is None:
                page = 1
            if tag not in self.current_tags:
                self.current_tags.append(tag)
                is_new_search = True
            else:
                is_new_search = False
        else:
            page = tag_or_page
            is_new_search = False
            if not self.current_tags:
                return
        if not self.current_tags:
            return
        
        self._update_tag_search_display()
        self.current_page = page
        self.page_var.set(str(page))
        
        if hasattr(self, 'current_tab') and self.current_tab == "downloaded":
            if is_new_search:
                self._push_search_history({"type": "tag", "tags": self.current_tags.copy(), "page": page})
            self._search_in_downloaded_works()
            return
        
        self.status_label.config(text=f"正在搜索标签: {' + '.join(self.current_tags)} (第{page}页)...")
        self.loading = True
        self._bump_generation()
        gen = self._nav_generation
        if is_new_search:
            self._push_search_history({"type": "tag", "tags": self.current_tags.copy(), "page": page})
        self.show_loading()
        threading.Thread(target=self._search_by_tag_async, args=(page, gen), daemon=True).start()

    search_by_tag = _search_by_tag

    def _search_by_tag_async(self, page: int = 1, gen: int = 0):
        try:
            api_client = get_api_client()
            works, max_page = api_client.search_by_tag(self.current_tags, page)
            if getattr(self, '_nav_generation', 0) != gen:
                self.root.after(0, self._safe_reset_loading)
                return
            self.works = works
            self.all_works = works.copy()
            self.original_works = works.copy()
            self.max_page = max_page
            self.data_loaded = True
            self.root.after(0, self._on_tag_search_success)
        except Exception as e:
            if getattr(self, '_nav_generation', 0) != gen:
                self.root.after(0, self._safe_reset_loading)
                return
            self.root.after(0, self._on_error, f"标签搜索失败: {str(e)}")

    def _display_works_with_filter(self):
        if self.show_downloaded == 2:
            self.works = [w for w in self.works
                          if self._normalize_rj_id(w.get('source_id', '')) not in self.downloaded_ids_cache]
            self.original_works = self.works.copy()
        self.display_works_list()
        self.show_work_detail(0)
        self.update_buttons()

    def _on_tag_search_success(self):
        self.hide_loading()
        self.refresh_btn.config(state=tk.NORMAL)
        self._update_tag_search_display()
        tags_str = " + ".join(self.current_tags)
        total = len(self.works)
        if self.show_downloaded == 2:
            visible = sum(1 for w in self.works
                          if self._normalize_rj_id(w.get('source_id', '')) not in self.downloaded_ids_cache)
            self.status_label.config(text=f"标签「{tags_str}」搜索结果 (共 {total} 个，隐藏已下载后 {visible} 个)")
        else:
            self.status_label.config(text=f"标签「{tags_str}」搜索结果 (共 {total} 个作品)")
        if self.works:
            self._display_works_with_filter()
        else:
            self.display_empty_state()
            self.update_buttons()
            messagebox.showinfo("提示", f"没有找到标签「{tags_str}」的作品")

    def _update_tag_search_display(self):
        if not self.current_tags:
            self._show_search_entry()
            return
        self.search_entry.pack_forget()
        self.search_tags_frame.pack(side=tk.LEFT, padx=(0, 5))
        existing = self.search_tags_frame.winfo_children()
        for i, tag in enumerate(self.current_tags):
            if i < len(existing):
                frame = existing[i]
                frame.pack(side=tk.LEFT, padx=1)
                label = frame.winfo_children()[0]
                label.config(text=tag)
                close_btn = frame.winfo_children()[1]
                close_btn.bind("<Button-1>", lambda e, t=tag: self._remove_tag(t))
            else:
                tag_frame = tk.Frame(self.search_tags_frame, bg="#FF9800", padx=4, pady=1)
                tag_frame.pack(side=tk.LEFT, padx=1)
                tag_label = tk.Label(tag_frame, text=tag, bg="#FF9800", fg="white",
                                     font=("Microsoft YaHei UI", 9))
                tag_label.pack(side=tk.LEFT)
                close_btn = tk.Label(tag_frame, text="✕", bg="#FF9800", fg="white",
                                     font=("Microsoft YaHei UI", 9), cursor="hand2")
                close_btn.pack(side=tk.LEFT, padx=(3, 0))
                close_btn.bind("<Button-1>", lambda e, t=tag: self._remove_tag(t))
        for widget in existing[len(self.current_tags):]:
            widget.pack_forget()

    def _remove_tag(self, tag):
        if tag in self.current_tags:
            self.current_tags.remove(tag)
        if self.current_tags:
            self._update_tag_search_display()
            self.current_page = 1
            self.page_var.set("1")
            self.status_label.config(text=f"正在搜索标签: {' + '.join(self.current_tags)} (第1页)...")
            self.loading = True
            self._bump_generation()
            gen = self._nav_generation
            self.show_loading()
            threading.Thread(target=self._search_by_tag_async, args=(1, gen), daemon=True).start()
        else:
            self._show_search_entry()
            self.clear_tag_search()

    def clear_tag_search(self):
        self.current_tags = []
        self.current_page = 1
        self.page_var.set("1")
        self._show_search_entry()
        self.load_data_async()

    def do_search(self):
        text = self.search_var.get().strip()
        if not text:
            messagebox.showwarning("提示", "请输入搜索内容（RJ ID 或关键词）")
            return

        self._bump_generation()
        gen = self._nav_generation
        numeric_id = text.replace("RJ", "").replace("rg", "").replace("RG", "")
        if numeric_id.isdigit():
            self.keyword_query = ""
            self.current_tags = []
            self._show_search_entry()
            self.status_label.config(text="正在搜索...")
            threading.Thread(target=self._search_by_id_async, args=(numeric_id, gen), daemon=True).start()
        else:
            self.keyword_query = text
            self.current_page = 1
            self.page_var.set("1")
            self.current_tags = []
            self.circle_query = ""
            
            if hasattr(self, 'current_tab') and self.current_tab == "downloaded":
                self._push_search_history({"type": "keyword", "keyword": text, "page": 1})
                self._update_keyword_search_display()
                self._search_in_downloaded_works()
                return
            
            self._push_search_history({"type": "keyword", "keyword": text, "page": 1})
            self._update_keyword_search_display()
            self.status_label.config(text=f"正在搜索: {text} (第1页)...")
            self.loading = True
            self.show_loading()
            threading.Thread(target=self._search_by_keyword_async, args=(1, gen), daemon=True).start()

    def _search_by_keyword_async(self, page: int = 1, gen: int = 0):
        try:
            api_client = get_api_client()
            works, max_page = api_client.search_by_keyword(self.keyword_query, page)
            if getattr(self, '_nav_generation', 0) != gen:
                self.root.after(0, self._safe_reset_loading)
                return
            self.works = works
            self.all_works = works.copy()
            self.original_works = works.copy()
            self.max_page = max_page
            self.data_loaded = True
            self.root.after(0, self._on_keyword_search_success)
        except Exception as e:
            if getattr(self, '_nav_generation', 0) != gen:
                self.root.after(0, self._safe_reset_loading)
                return
            self.root.after(0, self._on_error, f"关键词搜索失败: {str(e)}")

    def _on_keyword_search_success(self):
        self.hide_loading()
        self.refresh_btn.config(state=tk.NORMAL)
        self._update_keyword_search_display()
        total = len(self.works)
        if self.show_downloaded == 2:
            visible = sum(1 for w in self.works
                          if self._normalize_rj_id(w.get('source_id', '')) not in self.downloaded_ids_cache)
            self.status_label.config(text=f"关键词「{self.keyword_query}」搜索结果 (共 {total} 个，隐藏已下载后 {visible} 个)")
        else:
            self.status_label.config(text=f"关键词「{self.keyword_query}」搜索结果 (共 {total} 个作品)")
        if self.works:
            self._display_works_with_filter()
        else:
            self.display_empty_state()
            self.update_buttons()
            messagebox.showinfo("提示", f"没有找到关键词「{self.keyword_query}」的作品")

    def _update_keyword_search_display(self):
        if not self.keyword_query:
            self._show_search_entry()
            return
        self.search_entry.pack_forget()
        self.search_tags_frame.pack(side=tk.LEFT, padx=(0, 5))
        existing = self.search_tags_frame.winfo_children()
        if existing:
            frame = existing[0]
            frame.pack(side=tk.LEFT)
            label = frame.winfo_children()[0]
            label.config(text=self.keyword_query)
            close_btn = frame.winfo_children()[1]
            close_btn.bind("<Button-1>", lambda e: self.clear_keyword_search())
        else:
            frame = tk.Frame(self.search_tags_frame, bg="#2196F3", padx=4, pady=1)
            frame.pack(side=tk.LEFT)
            label = tk.Label(frame, text=self.keyword_query, bg="#2196F3", fg="white",
                             font=("Microsoft YaHei UI", 9))
            label.pack(side=tk.LEFT)
            close_btn = tk.Label(frame, text="✕", bg="#2196F3", fg="white",
                                 font=("Microsoft YaHei UI", 9), cursor="hand2")
            close_btn.pack(side=tk.LEFT, padx=(3, 0))
            close_btn.bind("<Button-1>", lambda e: self.clear_keyword_search())
        for widget in existing[1:]:
            widget.pack_forget()

    def clear_keyword_search(self):
        self.keyword_query = ""
        self.search_var.set("")
        self.current_page = 1
        self.page_var.set("1")
        self._show_search_entry()
        self.load_data_async()

    def search_by_circle(self, circle_name):
        if not circle_name:
            return
        self.keyword_query = ""
        self.current_tags = []
        self.circle_query = circle_name
        self.current_page = 1
        self.page_var.set("1")
        
        if hasattr(self, 'current_tab') and self.current_tab == "downloaded":
            self._push_search_history({"type": "circle", "circle": circle_name, "page": 1})
            self._update_circle_search_display()
            self._search_in_downloaded_works()
            return
        
        self._push_search_history({"type": "circle", "circle": circle_name, "page": 1})
        self._update_circle_search_display()
        self.status_label.config(text=f"正在搜索厂商: {circle_name} (第1页)...")
        self.loading = True
        self._bump_generation()
        gen = self._nav_generation
        self.show_loading()
        threading.Thread(target=self._search_by_circle_async, args=(1, gen), daemon=True).start()

    def _search_by_circle_async(self, page: int = 1, gen: int = 0):
        try:
            api_client = get_api_client()
            works, max_page = api_client.search_by_circle(self.circle_query, page)
            if getattr(self, '_nav_generation', 0) != gen:
                self.root.after(0, self._safe_reset_loading)
                return
            self.works = works
            self.all_works = works.copy()
            self.original_works = works.copy()
            self.max_page = max_page
            self.data_loaded = True
            self.root.after(0, self._on_circle_search_success)
        except Exception as e:
            if getattr(self, '_nav_generation', 0) != gen:
                self.root.after(0, self._safe_reset_loading)
                return
            self.root.after(0, self._on_error, f"厂商搜索失败: {str(e)}")

    def _on_circle_search_success(self):
        self.hide_loading()
        self.refresh_btn.config(state=tk.NORMAL)
        self._update_circle_search_display()
        total = len(self.works)
        if self.show_downloaded == 2:
            visible = sum(1 for w in self.works
                          if self._normalize_rj_id(w.get('source_id', '')) not in self.downloaded_ids_cache)
            self.status_label.config(text=f"厂商「{self.circle_query}」搜索结果 (共 {total} 个，隐藏已下载后 {visible} 个)")
        else:
            self.status_label.config(text=f"厂商「{self.circle_query}」搜索结果 (共 {total} 个作品)")
        if self.works:
            self._display_works_with_filter()
        else:
            self.display_empty_state()
            self.update_buttons()
            messagebox.showinfo("提示", f"没有找到厂商「{self.circle_query}」的作品")

    def _update_circle_search_display(self):
        if not self.circle_query:
            self._show_search_entry()
            return
        self.search_entry.pack_forget()
        self.search_tags_frame.pack(side=tk.LEFT, padx=(0, 5))
        existing = self.search_tags_frame.winfo_children()
        if existing:
            frame = existing[0]
            frame.pack(side=tk.LEFT)
            label = frame.winfo_children()[0]
            label.config(text=f"厂商: {self.circle_query}")
            close_btn = frame.winfo_children()[1]
            close_btn.bind("<Button-1>", lambda e: self.clear_circle_search())
        else:
            frame = tk.Frame(self.search_tags_frame, bg="#E91E63", padx=4, pady=1)
            frame.pack(side=tk.LEFT)
            label = tk.Label(frame, text=f"厂商: {self.circle_query}", bg="#E91E63", fg="white",
                             font=("Microsoft YaHei UI", 9))
            label.pack(side=tk.LEFT)
            close_btn = tk.Label(frame, text="✕", bg="#E91E63", fg="white",
                                 font=("Microsoft YaHei UI", 9), cursor="hand2")
            close_btn.pack(side=tk.LEFT, padx=(3, 0))
            close_btn.bind("<Button-1>", lambda e: self.clear_circle_search())
        for widget in existing[1:]:
            widget.pack_forget()

    def clear_circle_search(self):
        self.circle_query = ""
        self.current_page = 1
        self.page_var.set("1")
        self._show_search_entry()
        self.load_data_async()

    def _search_by_edition_id(self, rj_id):
        numeric_id = rj_id.replace("RJ", "").replace("rg", "").replace("RG", "")
        self.keyword_query = ""
        self.current_tags = []
        self._show_search_entry()
        self.status_label.config(text=f"正在搜索其他版本: {rj_id}...")
        self.loading = True
        self._bump_generation()
        gen = self._nav_generation
        self.show_loading()
        threading.Thread(target=self._search_by_id_async, args=(numeric_id, gen), daemon=True).start()

    def _search_by_id_async(self, numeric_id, gen=0):
        try:
            api_client = get_api_client()
            work_data = api_client.fetch_work_detail(numeric_id)
            if getattr(self, '_nav_generation', 0) != gen:
                self.root.after(0, self._safe_reset_loading)
                return
            self.root.after(0, self._on_search_success, work_data)
        except Exception as e:
            if getattr(self, '_nav_generation', 0) != gen:
                self.root.after(0, self._safe_reset_loading)
                return
            self.root.after(0, self._on_search_error, f"搜索失败: {str(e)}")

    def _on_search_success(self, work_data):
        self.hide_loading()
        self.refresh_btn.config(state=tk.NORMAL)
        self.status_label.config(text="搜索成功")
        self.search_var.set("")

        source_id = work_data.get("source_id", "")
        work = {
            "id": work_data.get("id"),
            "title": work_data.get("title", ""),
            "source_id": source_id,
            "thumbnailCoverUrl": work_data.get("thumbnailCoverUrl", ""),
            "mainCoverUrl": work_data.get("mainCoverUrl", ""),
            "tags": work_data.get("tags", []),
            "vas": work_data.get("vas", []),
            "circle": work_data.get("circle", {}),
            "other_language_editions_in_db": work_data.get("other_language_editions_in_db", [])
        }

        self.all_works = [work]
        self.works = [work]
        self.current_work_index = 0
        self.data_loaded = True
        self.display_works_list()
        self.show_work_detail(0)
        self.update_buttons()

    def _on_search_error(self, msg):
        self.hide_loading()
        self.refresh_btn.config(state=tk.NORMAL)
        self.status_label.config(text="")
        messagebox.showerror("错误", msg)
