import tkinter as tk
from tkinter import ttk


class DownloadManagerWindow:
    def __init__(self, parent, dl_manager):
        self.parent = parent
        self.dl_manager = dl_manager

        self.window = tk.Toplevel(parent)
        self.window.title("下载管理")
        self.window.transient(parent)

        px = parent.winfo_x() + (parent.winfo_width() - 850) // 2
        py = parent.winfo_y() + (parent.winfo_height() - 520) // 2
        self.window.geometry(f"850x520+{max(px, 0)}+{max(py, 0)}")
        self.window.resizable(True, True)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        self.colors = {
            "bg": "#f5f5f5",
            "card_bg": "#ffffff",
            "primary": "#1976D2",
            "accent": "#FF9800",
            "success": "#4CAF50",
            "error": "#F44336",
            "text": "#333333",
            "text_secondary": "#666666",
            "text_hint": "#999999",
        }

        self._current_tab = "active"
        self._widgets = {}
        self._done_widgets = {}
        self._last_active_ids = None
        self._last_done_ids = None
        self._empty_active_label = None
        self._empty_done_label = None

        self._create_ui()
        self.dl_manager.add_observer(self._refresh)
        self._switch_tab("active")

    def _create_ui(self):
        c = self.colors
        main = tk.Frame(self.window, bg=c["bg"])
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        tk.Label(main, text="下载任务管理", font=("Microsoft YaHei UI", 14, "bold"),
                 bg=c["bg"], fg=c["text"]).pack(anchor=tk.W)

        btn_bar = tk.Frame(main, bg=c["bg"])
        btn_bar.pack(fill=tk.X, pady=(12, 8))

        self.btn_active = tk.Button(btn_bar, text=" 正在下载 ", font=("Microsoft YaHei UI", 10),
                                     bg="#E8F0FE", fg=c["primary"], activebackground="#D2E3FC",
                                     activeforeground=c["primary"],
                                     relief=tk.FLAT, bd=0, cursor="hand2",
                                     command=lambda: self._switch_tab("active"))
        self.btn_active.pack(side=tk.LEFT)

        self.btn_done = tk.Button(btn_bar, text=" 已完成 ", font=("Microsoft YaHei UI", 10),
                                   bg=c["bg"], fg=c["text_secondary"],
                                   activebackground=c["bg"], activeforeground=c["primary"],
                                   relief=tk.FLAT, bd=0, cursor="hand2",
                                   command=lambda: self._switch_tab("done"))
        self.btn_done.pack(side=tk.LEFT, padx=(4, 0))

        self.count_label = tk.Label(btn_bar, text="", font=("Microsoft YaHei UI", 9),
                                     bg=c["bg"], fg=c["text_hint"])
        self.count_label.pack(side=tk.RIGHT)

        sep = ttk.Separator(main)
        sep.pack(fill=tk.X, pady=(0, 8))

        content_frame = tk.Frame(main, bg=c["card_bg"])
        content_frame.pack(fill=tk.BOTH, expand=True)

        self.active_container = tk.Frame(content_frame)
        self.active_canvas = tk.Canvas(self.active_container, bg=c["card_bg"], highlightthickness=0)
        active_sbar = ttk.Scrollbar(self.active_container, orient=tk.VERTICAL,
                                    command=self.active_canvas.yview)
        self.active_canvas.configure(yscrollcommand=active_sbar.set)
        active_sbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.active_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.active_inner = tk.Frame(self.active_canvas, bg=c["card_bg"])
        self.active_canvas.create_window((0, 0), window=self.active_inner, anchor="nw")
        self.active_inner.bind("<Configure>", lambda e: self.active_canvas.configure(
            scrollregion=self.active_canvas.bbox("all")))

        self.done_container = tk.Frame(content_frame)
        self.done_canvas = tk.Canvas(self.done_container, bg=c["card_bg"], highlightthickness=0)
        done_sbar = ttk.Scrollbar(self.done_container, orient=tk.VERTICAL,
                                  command=self.done_canvas.yview)
        self.done_canvas.configure(yscrollcommand=done_sbar.set)
        done_sbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.done_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.done_inner = tk.Frame(self.done_canvas, bg=c["card_bg"])
        self.done_canvas.create_window((0, 0), window=self.done_inner, anchor="nw")
        self.done_inner.bind("<Configure>", lambda e: self.done_canvas.configure(
            scrollregion=self.done_canvas.bbox("all")))

        bottom = tk.Frame(main, bg=c["bg"])
        bottom.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(bottom, text="关闭", command=self._on_close).pack(side=tk.RIGHT)

    def _switch_tab(self, tab):
        self._current_tab = tab
        c = self.colors
        if tab == "active":
            self.btn_active.config(bg="#E8F0FE", fg=c["primary"])
            self.btn_done.config(bg=c["bg"], fg=c["text_secondary"])
            self.active_container.pack(fill=tk.BOTH, expand=True)
            self.done_container.forget()
        else:
            self.btn_done.config(bg="#E8F0FE", fg=c["primary"])
            self.btn_active.config(bg=c["bg"], fg=c["text_secondary"])
            self.done_container.pack(fill=tk.BOTH, expand=True)
            self.active_container.forget()
        self._last_active_ids = None
        self._last_done_ids = None
        self._refresh()

    def _build_active_row(self, task):
        c = self.colors
        row = tk.Frame(self.active_inner, bg=c["card_bg"])
        row.pack(fill=tk.X, pady=1, padx=4, ipady=4)

        sv = task.status.value if hasattr(task.status, 'value') else str(task.status)
        status_map = {
            ("submitting", "downloading"): ("\u25cf 下载中", c["primary"]),
            ("queued",): ("\u25cb 等待下载", c["accent"]),
            ("failed",): ("\u2717 失败", c["error"]),
        }
        status_text = sv
        status_color = c["text_hint"]
        for keys, val in status_map.items():
            if sv in keys:
                status_text, status_color = val
                break

        status_lbl = tk.Label(row, text=status_text, font=("Microsoft YaHei UI", 9),
                              bg=c["card_bg"], fg=status_color, width=10, anchor=tk.W)
        status_lbl.pack(side=tk.LEFT, padx=(8, 4))

        id_text = task.work_id[:11] if len(task.work_id) > 11 else task.work_id
        id_lbl = tk.Label(row, text=id_text, font=("Consolas", 9, "bold"),
                          bg=c["card_bg"], fg=c["primary"], width=12, anchor=tk.W)
        id_lbl.pack(side=tk.LEFT, padx=(0, 4))

        title_text = task.title[:35] if len(task.title) > 35 else task.title
        title_lbl = tk.Label(row, text=title_text, font=("Microsoft YaHei UI", 9),
                             bg=c["card_bg"], fg=c["text"], width=35, anchor=tk.W)
        title_lbl.pack(side=tk.LEFT, padx=(0, 4))

        pbar = ttk.Progressbar(row, mode='determinate', length=120)
        pbar.pack(side=tk.LEFT, padx=(0, 2))

        pct_var = tk.StringVar(value="...")
        pct_lbl = tk.Label(row, textvariable=pct_var, font=("Consolas", 9),
                            bg=c["card_bg"], fg=c["text"], width=5, anchor=tk.E)
        pct_lbl.pack(side=tk.LEFT, padx=(0, 4))

        speed_var = tk.StringVar(value="")
        speed_lbl = tk.Label(row, textvariable=speed_var, font=("Microsoft YaHei UI", 8),
                             bg=c["card_bg"], fg=c["text_hint"], width=10, anchor=tk.W)
        speed_lbl.pack(side=tk.LEFT, padx=(0, 8))

        btn_widget = None
        if sv == "failed":
            def _retry(wid=task.work_id):
                self.dl_manager.retry(wid)
            btn_widget = ttk.Button(row, text="重试", width=5, command=_retry)
            btn_widget.pack(side=tk.RIGHT, padx=(0, 8))
        elif sv in ("submitting", "downloading", "queued"):
            def _cancel(wid=task.work_id):
                self.dl_manager.cancel(wid)
            btn_widget = ttk.Button(row, text="取消", width=5, command=_cancel)
            btn_widget.pack(side=tk.RIGHT, padx=(0, 8))

        return {
            "pbar": pbar, "pct": pct_var, "speed": speed_var,
            "status": status_lbl, "row": row, "btn": btn_widget,
        }

    def _build_done_row(self, task):
        c = self.colors
        row = tk.Frame(self.done_inner, bg=c["card_bg"])
        row.pack(fill=tk.X, pady=1, padx=4, ipady=3)

        id_text = task.work_id[:12] if len(task.work_id) > 12 else task.work_id
        id_lbl = tk.Label(row, text=id_text, font=("Consolas", 9, "bold"),
                          bg=c["card_bg"], fg=c["success"], width=13, anchor=tk.W)
        id_lbl.pack(side=tk.LEFT, padx=(10, 6))

        title_text = task.title[:50] if len(task.title) > 50 else task.title
        title_lbl = tk.Label(row, text=title_text, font=("Microsoft YaHei UI", 9),
                             bg=c["card_bg"], fg=c["text"], anchor=tk.W)
        title_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        check_lbl = tk.Label(row, text="\u2713", font=("Microsoft YaHei UI", 14),
                             bg=c["card_bg"], fg=c["success"])
        check_lbl.pack(side=tk.RIGHT, padx=(0, 10))
        return {"row": row}

    @staticmethod
    def _clear(frame):
        for w in frame.winfo_children():
            w.destroy()

    def _refresh(self):
        try:
            tasks = self.dl_manager.get_all_tasks()
        except Exception:
            return

        active_tasks = []
        done_tasks = []
        for t in tasks:
            sv = t.status.value if hasattr(t.status, 'value') else str(t.status)
            if sv == "completed":
                done_tasks.append(t)
            elif sv != "cancelled":
                active_tasks.append(t)

        self.count_label.config(text=f"正在下载: {len(active_tasks)}  |  已完成: {len(done_tasks)}")

        current_active_ids = {t.work_id for t in active_tasks}
        current_done_ids = {t.work_id for t in done_tasks}
        active_changed = (current_active_ids != self._last_active_ids)
        done_changed = (current_done_ids != self._last_done_ids)

        if active_changed:
            self._rebuild_active(active_tasks)
            self._last_active_ids = current_active_ids

        if done_changed:
            self._rebuild_done(done_tasks)
            self._last_done_ids = current_done_ids

        self._update_progress(tasks)

        if active_changed:
            self.active_canvas.update_idletasks()
        if done_changed:
            self.done_canvas.update_idletasks()

    def _rebuild_active(self, active_tasks):
        for w in self._widgets.values():
            try:
                w["row"].destroy()
            except Exception:
                pass
        self._widgets.clear()

        if self._empty_active_label:
            try:
                self._empty_active_label.destroy()
            except Exception:
                pass
            self._empty_active_label = None

        if not active_tasks:
            self._empty_active_label = tk.Label(
                self.active_inner, text="暂无进行中的下载任务",
                font=("Microsoft YaHei UI", 10), bg=self.colors["card_bg"],
                fg=self.colors["text_hint"])
            self._empty_active_label.pack(pady=40)
        else:
            for t in active_tasks:
                self._widgets[t.work_id] = self._build_active_row(t)

    def _rebuild_done(self, done_tasks):
        for w in self._done_widgets.values():
            try:
                w["row"].destroy()
            except Exception:
                pass
        self._done_widgets.clear()

        if self._empty_done_label:
            try:
                self._empty_done_label.destroy()
            except Exception:
                pass
            self._empty_done_label = None

        if not done_tasks:
            self._empty_done_label = tk.Label(
                self.done_inner, text="暂无已完成记录",
                font=("Microsoft YaHei UI", 10), bg=self.colors["card_bg"],
                fg=self.colors["text_hint"])
            self._empty_done_label.pack(pady=40)
        else:
            sorted_done = sorted(done_tasks, key=lambda x: x.completed_at or 0, reverse=True)
            for t in sorted_done[:100]:
                self._done_widgets[t.work_id] = self._build_done_row(t)

    def _update_progress(self, tasks):
        for t in tasks:
            wid = t.work_id
            if wid not in self._widgets:
                continue
            w = self._widgets[wid]
            sv = t.status.value if hasattr(t.status, 'value') else str(t.status)

            status_map = {
                ("submitting", "downloading"): ("\u25cf 下载中", self.colors["primary"]),
                ("queued",): ("\u25cb 等待下载", self.colors["accent"]),
                ("failed",): ("\u2717 失败", self.colors["error"]),
            }
            new_status_text = sv
            new_status_color = self.colors["text_hint"]
            for keys, val in status_map.items():
                if sv in keys:
                    new_status_text, new_status_color = val
                    break
            w["status"].config(text=new_status_text, fg=new_status_color)

            if sv in ("submitting", "downloading"):
                if t.total_bytes > 0:
                    pct = min(int(t.completed_bytes * 100 / t.total_bytes), 100)
                    w["pbar"]["value"] = pct
                    w["pct"].set(f"{pct}%")
                else:
                    w["pbar"]["value"] = 0
                    if sv == "submitting":
                        w["pct"].set("提交中")
                    else:
                        w["pct"].set("下载中")

                if t.speed > 0:
                    w["speed"].set(self._fmt_speed(t.speed))
                else:
                    w["speed"].set("")
            elif sv == "failed":
                w["pbar"]["value"] = 0
                w["pct"].set("")
                w["speed"].set("")
            elif sv == "queued":
                w["pbar"]["value"] = 0
                w["pct"].set("")
                w["speed"].set("")

    @staticmethod
    def _fmt_speed(bps):
        if bps < 1024:
            return f"{bps} B/s"
        elif bps < 1048576:
            return f"{bps / 1024:.1f} KB/s"
        return f"{bps / 1048576:.1f} MB/s"

    def _on_close(self):
        try:
            self.dl_manager.remove_observer(self._refresh)
        except Exception:
            pass
        try:
            self.window.destroy()
        except Exception:
            pass
