import tkinter as tk
import threading


class EventMixin:
    _MAX_SEARCH_HISTORY = 50

    def _push_search_history(self, state):
        self.search_history = self.search_history[:self.current_search_index + 1]
        self.search_history.append(state)
        # 限制历史长度，避免长期使用内存增长
        if len(self.search_history) > self._MAX_SEARCH_HISTORY:
            overflow = len(self.search_history) - self._MAX_SEARCH_HISTORY
            self.search_history = self.search_history[overflow:]
            self.current_search_index = max(0, self.current_search_index - overflow)
        else:
            self.current_search_index = len(self.search_history) - 1
        self._update_back_button()

    def _update_back_button(self):
        if self.current_search_index > 0:
            self.back_btn.config(state=tk.NORMAL)
        else:
            self.back_btn.config(state=tk.DISABLED)

    def go_back_search(self):
        if self.current_search_index <= 0:
            return
        self.current_search_index -= 1
        state = self.search_history[self.current_search_index]
        self._restore_search_state(state)

    def _restore_search_state(self, state):
        search_type = state.get("type", "recommend")

        if search_type == "recommend":
            self.current_tags = []
            self.keyword_query = ""
            self.circle_query = ""
            self.current_page = state.get("page", 1)
            self.page_var.set(str(self.current_page))
            self._show_search_entry()
            self.load_data_async()
        elif search_type == "tag":
            self.current_tags = state.get("tags", [])
            self.keyword_query = ""
            self.circle_query = ""
            self.current_page = state.get("page", 1)
            self.page_var.set(str(self.current_page))
            self._search_by_tag(self.current_page)
        elif search_type == "keyword":
            self.keyword_query = state.get("keyword", "")
            self.current_tags = []
            self.circle_query = ""
            self.current_page = state.get("page", 1)
            self.page_var.set(str(self.current_page))
            self._restore_async_search(
                "keyword",
                f"正在搜索: {self.keyword_query} (第{self.current_page}页)...",
                self._update_keyword_search_display,
                self._search_by_keyword_async,
            )
        elif search_type == "circle":
            self.circle_query = state.get("circle", "")
            self.current_tags = []
            self.keyword_query = ""
            self.current_page = state.get("page", 1)
            self.page_var.set(str(self.current_page))
            self._restore_async_search(
                "circle",
                f"正在搜索厂商: {self.circle_query} (第{self.current_page}页)...",
                self._update_circle_search_display,
                self._search_by_circle_async,
            )

    def _restore_async_search(self, search_type, status_text, update_display, async_method):
        """恢复 keyword/circle 类型的异步搜索状态（两者结构完全相同）。

        Args:
            search_type: 仅用于语义标记（"keyword"/"circle"）
            status_text: 状态栏显示文本
            update_display: 更新搜索 UI 的回调
            async_method: 实际执行搜索的异步方法
        """
        self.status_label.config(text=status_text)
        self.loading = True
        gen = self._nav_generation
        update_display()
        self.show_loading()
        threading.Thread(target=async_method, args=(self.current_page, gen), daemon=True).start()

    def clear_search_history(self):
        self.search_history = [{"type": "recommend", "page": 1}]
        self.current_search_index = 0
        self._update_back_button()

    def _on_mouse_wheel(self, event):
        scroll_units = int(-1 * (event.delta / 120))
        if scroll_units == 0:
            return
        target = self._get_scrollable_canvas()
        if target:
            target.yview_scroll(scroll_units * 3, "units")

    def _on_linux_scroll(self, event, direction):
        target = self._get_scrollable_canvas()
        if target:
            target.yview_scroll(direction * 3, "units")

    def _get_scrollable_canvas(self):
        mouse_x = self.root.winfo_pointerx()
        mouse_y = self.root.winfo_pointery()
        widget = self.root.winfo_containing(mouse_x, mouse_y)
        while widget:
            if widget == self.canvas:
                return self.canvas
            if widget == self.detail_canvas:
                return self.detail_canvas
            widget = widget.master
        return None

    def _bind_shortcuts(self):
        self.root.bind("<MouseWheel>", self._on_mouse_wheel)
        self.root.bind("<Button-4>", lambda e: self._on_linux_scroll(e, -1))
        self.root.bind("<Button-5>", lambda e: self._on_linux_scroll(e, 1))
        self.root.bind("<Configure>", self._on_root_resize)