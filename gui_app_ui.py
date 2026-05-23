import tkinter as tk
from tkinter import ttk


class UISetupMixin:
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        self.COLORS = {
            "bg": "#f5f5f5",
            "card_bg": "#ffffff",
            "primary": "#1976D2",
            "primary_light": "#E3F2FD",
            "accent": "#FF9800",
            "success": "#4CAF50",
            "error": "#F44336",
            "text": "#333333",
            "text_secondary": "#666666",
            "text_hint": "#999999",
            "border": "#e0e0e0",
            "hover": "#e8e8e8",
        }

        default_font = ("Microsoft YaHei UI", 10)
        bold_font = ("Microsoft YaHei UI", 10, "bold")
        small_font = ("Microsoft YaHei UI", 9)

        style.configure(".", font=default_font, background=self.COLORS["bg"])
        style.configure("TLabel", font=default_font, padding=2, background=self.COLORS["bg"])
        style.configure("TButton", font=default_font, padding=6, background=self.COLORS["primary"], foreground="white")
        style.configure("TEntry", font=default_font, padding=4)
        style.configure("TCombobox", font=default_font, padding=4)
        style.configure("TCheckbutton", font=default_font, padding=4, background=self.COLORS["bg"])
        style.configure("TRadiobutton", font=default_font, padding=4, background=self.COLORS["bg"])
        style.configure("TSpinbox", font=default_font, padding=4)
        style.configure("TLabelframe", font=default_font, background=self.COLORS["bg"])
        style.configure("TLabelframe.Label", font=bold_font, background=self.COLORS["bg"])
        style.configure("TNotebook.Tab", font=default_font, padding=[12, 6])

        style.configure("Treeview", font=small_font, rowheight=28, background=self.COLORS["card_bg"],
                        fieldbackground=self.COLORS["card_bg"])
        style.configure("Treeview.Heading", font=bold_font, background=self.COLORS["border"])

        style.configure("TProgressbar", thickness=18, background=self.COLORS["primary"])

        style.map("TButton",
                  background=[("active", self.COLORS["primary"]), ("disabled", self.COLORS["border"])],
                  foreground=[("disabled", self.COLORS["text_hint"])])

        self.root.configure(bg=self.COLORS["bg"])
        self.root.option_add("*Font", default_font)
        self.root.option_add("*TCombobox*Listbox.font", default_font)
        self.root.option_add("*Background", self.COLORS["bg"])
        self.root.option_add("*Foreground", self.COLORS["text"])

    def setup_ui(self):
        colors = self.COLORS

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        self.tab_var = tk.StringVar(value="推荐作品")
        self.tab_combo = ttk.Combobox(control_frame, textvariable=self.tab_var, width=12,
                                       font=("Microsoft YaHei UI", 10), state="readonly")
        self.tab_combo['values'] = ("推荐作品", "最新收录", "下载作品")
        self.tab_combo.pack(side=tk.LEFT)
        self.tab_combo.bind("<<ComboboxSelected>>", self._on_tab_changed)

        self.back_btn = ttk.Button(control_frame, text="← 返回", command=self.go_back_search, state=tk.DISABLED)
        self.back_btn.pack(side=tk.LEFT, padx=(10, 5))

        self.refresh_btn = ttk.Button(control_frame, text="刷新", command=self.refresh_data)
        self.refresh_btn.pack(side=tk.LEFT, padx=(20, 5))

        ttk.Label(control_frame, text="搜索:", font=("Microsoft YaHei UI", 11)).pack(side=tk.LEFT, padx=(20, 5))
        self.search_container = tk.Frame(control_frame, bg=colors["card_bg"], relief=tk.SOLID, bd=1)
        self.search_container.pack(side=tk.LEFT, padx=5)

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(self.search_container, textvariable=self.search_var, width=20, font=("Microsoft YaHei UI", 11))
        self.search_entry.pack(side=tk.LEFT, padx=5, pady=3)
        self.search_entry.bind("<Return>", lambda e: self.do_search())

        self.search_tags_frame = tk.Frame(self.search_container, bg=colors["card_bg"])
        ttk.Button(control_frame, text="搜索", command=self.do_search).pack(side=tk.LEFT, padx=5)

        self.downloaded_count_label = ttk.Label(control_frame, text="", font=("Microsoft YaHei UI", 9), foreground=colors["text_secondary"])
        self.downloaded_count_label.pack(side=tk.LEFT, padx=(0, 10))

        self.hide_dl_btn = ttk.Button(control_frame, text="显示全部", command=self._toggle_hide_downloaded)
        self.hide_dl_btn.pack(side=tk.LEFT, padx=(10, 5))
        self._hide_downloaded = False

        self.sort_label = ttk.Label(control_frame, text="排序:", font=("Microsoft YaHei UI", 10))
        self.sort_label.pack(side=tk.LEFT, padx=(10, 5))
        self.sort_var = tk.StringVar(value="下载时间最新")
        self.sort_combo = ttk.Combobox(control_frame, textvariable=self.sort_var, width=15,
                                        font=("Microsoft YaHei UI", 10), state="readonly")
        self.sort_combo['values'] = ("下载时间最新", "下载时间最旧", "标题 A-Z", "标题 Z-A", "ID 从小到大", "ID 从大到小")
        self.sort_combo.pack(side=tk.LEFT, padx=5)
        self.sort_combo.bind("<<ComboboxSelected>>", lambda e: self._on_sort_changed())

        self.status_label = ttk.Label(control_frame, text="", font=("Microsoft YaHei UI", 10), foreground=colors["text_hint"])
        self.status_label.pack(side=tk.RIGHT)

        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        left_frame = tk.Frame(content_frame, bg=colors["card_bg"], relief=tk.SOLID, bd=1)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.canvas = tk.Canvas(left_frame, bg=colors["card_bg"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=colors["card_bg"])

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._configure_pending = False
        self._nav_generation = 0
        self._nav_debounce_id = None
        self.scrollable_frame.bind(
            "<Configure>",
            self._on_frame_configure
        )

        right_frame = tk.Frame(content_frame, width=400, bg=colors["card_bg"], relief=tk.SOLID, bd=1)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        right_frame.pack_propagate(False)

        bottom_frame = tk.Frame(main_frame, bg=colors["bg"])
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        bottom_frame.columnconfigure(0, weight=0)
        bottom_frame.columnconfigure(1, weight=0)
        bottom_frame.columnconfigure(2, weight=1)
        bottom_frame.columnconfigure(3, weight=0)

        self.dl_task_frame = tk.Frame(bottom_frame, bg=colors["card_bg"], relief=tk.SOLID, bd=1)
        self.dl_task_frame.grid(row=0, column=1, sticky="w")
        self._dl_mgr_win = None
        self._dl_task_slots = []
        for i in range(1):
            slot = self._create_task_slot()
            slot["frame"].grid(row=i, column=0, sticky="ew")
            slot["frame"].grid_remove()
            self._dl_task_slots.append(slot)

        self.dl_mgr_btn = ttk.Button(bottom_frame, text="下载管理", command=self.open_download_manager)
        self.dl_mgr_btn.grid(row=0, column=0, padx=(5, 10), pady=2)

        btn_container = tk.Frame(bottom_frame, bg=colors["bg"])
        btn_container.grid(row=0, column=2)

        self.prev_btn = ttk.Button(btn_container, text="← 上一页", command=self.prev_page, state=tk.DISABLED)
        self.prev_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.page_var = tk.StringVar(value="1")
        ttk.Label(btn_container, text="页码:").pack(side=tk.LEFT, padx=(5, 2))
        self.page_entry = ttk.Entry(btn_container, textvariable=self.page_var, width=8, font=("Microsoft YaHei UI", 10))
        self.page_entry.pack(side=tk.LEFT, padx=2)
        self.page_entry.bind("<Return>", lambda e: self.go_to_page())
        ttk.Button(btn_container, text="跳转", command=self.go_to_page).pack(side=tk.LEFT, padx=2)

        self.next_btn = ttk.Button(btn_container, text="下一页 →", command=self.next_page, state=tk.DISABLED)
        self.next_btn.pack(side=tk.LEFT, padx=(5, 0))

        self.settings_btn = ttk.Button(bottom_frame, text="设置", command=self.open_settings)
        self.settings_btn.grid(row=0, column=3, sticky="e", padx=(10, 5))

        tk.Label(right_frame, text="当前作品", font=("Microsoft YaHei UI", 14, "bold"),
                 bg=colors["card_bg"], fg=colors["text"]).pack(pady=(10, 10))

        self.detail_frame = tk.Frame(right_frame, bg=colors["card_bg"])
        self.detail_frame.pack(fill=tk.BOTH, expand=True)

        self.info_labels = {}
        self.setup_detail_panel()

    def _bump_generation(self):
        self._nav_generation += 1

    def _create_task_slot(self):
        colors = self.COLORS
        row = tk.Frame(self.dl_task_frame, bg=colors["card_bg"])

        id_label = tk.Label(row, font=("Consolas", 9, "bold"),
                            bg=colors["card_bg"], fg=colors["primary"], width=12, anchor=tk.W)
        id_label.pack(side=tk.LEFT, padx=(5, 5))

        pct_label = tk.Label(row, font=("Consolas", 10),
                             bg=colors["card_bg"], fg=colors["text"], width=5)
        pct_label.pack(side=tk.LEFT)

        speed_label = tk.Label(row, font=("Microsoft YaHei UI", 8),
                               bg=colors["card_bg"], fg=colors["text_hint"], width=10)
        speed_label.pack(side=tk.LEFT, padx=(5, 0))

        return {
            "frame": row,
            "id_label": id_label,
            "pct_label": pct_label,
            "speed_label": speed_label,
            "_visible": False,
        }

    def _on_dl_tasks_changed(self):
        self.root.after(0, self._refresh_task_display)
        self.root.after(0, self._update_downloaded_count)
        tasks = self.dl_manager.get_all_tasks()
        completed_or_failed = [t for t in tasks
                              if t.status.value in ("completed", "failed")]
        if completed_or_failed:
            self._downloaded_cache_valid = False

    def _refresh_task_display(self):
        tasks = self.dl_manager.get_all_tasks()
        active_tasks = [t for t in tasks if t.status.value in ("submitting", "downloading")]

        while len(self._dl_task_slots) < len(active_tasks):
            new_slot = self._create_task_slot()
            new_slot["frame"].grid(row=len(self._dl_task_slots), column=0, sticky="ew", pady=1)
            new_slot["frame"].grid_remove()
            self._dl_task_slots.append(new_slot)

        for idx, slot in enumerate(self._dl_task_slots):
            if idx < len(active_tasks):
                task = active_tasks[idx]
                slot["id_label"].config(text=task.work_id[:12])

                if task.total_bytes > 0:
                    pct = min(int(task.completed_bytes * 100 / task.total_bytes), 100)
                    slot["pct_label"].config(text=f"{pct}%")
                elif task.status.value == "submitting":
                    slot["pct_label"].config(text="提交中")
                elif task.total_files > 0:
                    slot["pct_label"].config(text="下载中")
                else:
                    slot["pct_label"].config(text="...")

                if task.speed > 0:
                    slot["speed_label"].config(text=self._format_speed(task.speed))
                else:
                    slot["speed_label"].config(text="")

                if not slot["_visible"]:
                    slot["frame"].grid(pady=1)
                    slot["_visible"] = True
            else:
                if slot["_visible"]:
                    slot["frame"].grid_remove()
                    slot["_visible"] = False

    def open_settings(self):
        from src.ui.gui_settings import SettingsWindow
        self._settings_win = SettingsWindow(self.root, image_cache=self.image_cache)

    def open_download_manager(self):
        from src.ui.gui_download_manager import DownloadManagerWindow

        if self._dl_mgr_win is not None:
            try:
                if self._dl_mgr_win.winfo_exists():
                    self._dl_mgr_win.lift()
                    self._dl_mgr_win.focus_force()
                    return
            except Exception:
                pass
            self._dl_mgr_win = None

        win = DownloadManagerWindow(self.root, self.dl_manager)
        self._dl_mgr_win = win.window
        original_close = win._on_close

        def _on_close_wrapper():
            original_close()
            self._dl_mgr_win = None

        win._on_close = _on_close_wrapper