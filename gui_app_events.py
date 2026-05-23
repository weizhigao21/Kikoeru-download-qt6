import tkinter as tk
import threading


class EventMixin:
    def _push_search_history(self, state):
        self.search_history = self.search_history[:self.current_search_index + 1]
        self.search_history.append(state)
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
            self._update_keyword_search_display()
            self.status_label.config(text=f"正在搜索: {self.keyword_query} (第{self.current_page}页)...")
            self.loading = True
            gen = self._nav_generation
            self.show_loading()
            threading.Thread(target=self._search_by_keyword_async, args=(self.current_page, gen), daemon=True).start()
        elif search_type == "circle":
            self.circle_query = state.get("circle", "")
            self.current_tags = []
            self.keyword_query = ""
            self.current_page = state.get("page", 1)
            self.page_var.set(str(self.current_page))
            self._update_circle_search_display()
            self.status_label.config(text=f"正在搜索厂商: {self.circle_query} (第{self.current_page}页)...")
            self.loading = True
            gen = self._nav_generation
            self.show_loading()
            threading.Thread(target=self._search_by_circle_async, args=(self.current_page, gen), daemon=True).start()

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

    def _on_root_resize(self, event=None):
        self._schedule_canvas_configure()

    def _on_escape(self):
        if self.keyword_query or self.current_tags or self.circle_query:
            self.search_var.set("")
            self.keyword_query = ""
            self.current_tags = []
            self.circle_query = ""
            self.search_chips.clear_chips()
            self.search_chips.hide()
            self.search_button.grid()
            self.title_label.grid()
            self.btn_row.grid_remove()
            self.page_var.set("1")
            self.current_page = 1
            self.data_loaded = False
            self.clear_all_items()
            self.refresh_works()
            return "break"

    def _shortcut_prev(self):
        widget = self.root.focus_get()
        if isinstance(widget, tk.Entry):
            return
        self.prev_page()

    def _shortcut_next(self):
        widget = self.root.focus_get()
        if isinstance(widget, tk.Entry):
            return
        self.next_page()

    def _shortcut_download(self):
        widget = self.root.focus_get()
        if isinstance(widget, tk.Entry):
            return
        if self.current_work_index >= 0 and self.current_work_index < len(self.works):
            display_title = self._get_display_title(self.current_work_index)
            self.open_download_window(self.works[self.current_work_index], display_title)
        return "break"

    def _shortcut_select_prev(self):
        widget = self.root.focus_get()
        if isinstance(widget, tk.Entry):
            return
        if self.works and self.current_work_index > 0:
            self.show_work_detail(self.current_work_index - 1)
        return "break"

    def _shortcut_select_next(self):
        widget = self.root.focus_get()
        if isinstance(widget, tk.Entry):
            return
        if self.works and self.current_work_index < len(self.works) - 1:
            self.show_work_detail(self.current_work_index + 1)
        return "break"