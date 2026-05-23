import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import sys
import logging

logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] %(threadName)s: %(message)s')
logger = logging.getLogger('gui_app')

from PIL import Image, ImageTk

from src import (
    _APP_ROOT, VERSION, MEMORY_CACHE_SIZE,
    CACHE_DIR, DB_PATH, DOWNLOAD_HISTORY_DB_PATH, ICON_PATH,
    DOWNLOAD_DIR,
    ImageCacheManager, DatabaseManager, DownloadHistoryManager,
    get_api_client, DownloadWindow, SettingsWindow
)
from src.download.manager import DownloadManager
from src.ui.detail_mixin import DetailMixin
from src.ui.list_mixin import ListMixin
from src.ui.search_mixin import SearchMixin
from src.ui.filter_mixin import FilterMixin
from src.services.translator import get_translator
from src import config as _config


class WorkApp(DetailMixin, ListMixin, SearchMixin, FilterMixin):
    def __init__(self, root):
        self.root = root
        self.root.title(f"音声浏览下载 {VERSION}")
        win_w, win_h = 1250, 800
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pos_x = (screen_w - win_w) // 2
        pos_y = (screen_h - win_h) // 2
        self.root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")

        try:
            img = Image.open(ICON_PATH)
            img = img.resize((32, 32), Image.LANCZOS)
            icon = ImageTk.PhotoImage(img)
            self.root.iconphoto(True, icon)
        except Exception as e:
            print(f"设置图标失败: {e}")

        self._setup_styles()

        self.current_page = 1
        self.works = []
        self.current_work_index = -1

        self.image_cache = ImageCacheManager(CACHE_DIR, MEMORY_CACHE_SIZE)
        self.db = DatabaseManager(DB_PATH)
        self.download_history = DownloadHistoryManager(DOWNLOAD_HISTORY_DB_PATH)

        self.dl_manager = DownloadManager()
        self.dl_manager.set_download_history(self.download_history)
        self.dl_manager.add_observer(self._on_dl_tasks_changed)
        self.dl_manager.set_queue_mode(_config.QUEUE_MODE, _config.MAX_CONCURRENT_DOWNLOADS)

        self._init_translator()

        self.loading = False
        self.data_loaded = False
        self.max_page = 1
        self.show_downloaded = 1
        self.all_works = []
        self.original_works = []
        self.downloaded_works_cache = []
        self._all_downloaded_works = []
        self.downloaded_ids_cache = set()
        self._downloaded_page = 1
        self._downloaded_cache_valid = False
        self._fetched_ids = set()
        self.current_tab = "recommend"
        self.current_tags = []
        self.keyword_query = ""
        self.circle_query = ""
        self.sort_map = {
            "下载时间最新": "download_time_desc",
            "下载时间最旧": "download_time_asc",
            "标题 A-Z": "title_asc",
            "标题 Z-A": "title_desc",
            "ID 从小到大": "id_asc",
            "ID 从大到小": "id_desc"
        }

        self.setup_ui()
        self._load_downloaded_ids()
        self._bind_shortcuts()
        self.show_loading()
        self.root.after(100, self.load_data_async)

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

    def _normalize_rj_id(self, rj_id):
        if not rj_id:
            return ""
        return str(rj_id).replace("RJ", "").replace("rg", "").replace("RG", "").strip().zfill(6)

    def _load_downloaded_ids(self):
        try:
            rj_ids = self.download_history.get_all_downloaded_rj_ids()
            self.downloaded_ids_cache = set()
            for rid in rj_ids:
                normalized = self._normalize_rj_id(rid)
                if normalized:
                    self.downloaded_ids_cache.add(normalized)
            self._update_downloaded_count()
        except Exception as e:
            print(f"[DEBUG] 加载已下载ID失败: {e}")
            self.downloaded_ids_cache = set()

    def _update_downloaded_count(self):
        count = len(self.downloaded_ids_cache)
        if count > 0:
            self.downloaded_count_label.config(text=f"已下载 {count} 个作品")
        else:
            self.downloaded_count_label.config(text="")

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

        ttk.Label(control_frame, text="排序:", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=(10, 5))
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

        self.root.bind("<MouseWheel>", self._on_mouse_wheel)
        self.root.bind("<Button-4>", lambda e: self._on_linux_scroll(e, -1))
        self.root.bind("<Button-5>", lambda e: self._on_linux_scroll(e, 1))

        self.root.bind("<Configure>", self._on_root_resize)

        right_frame = tk.Frame(content_frame, width=400, bg=colors["card_bg"], relief=tk.SOLID, bd=1)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        right_frame.pack_propagate(False)

        bottom_frame = tk.Frame(main_frame, bg=colors["bg"])
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        bottom_frame.columnconfigure(0, weight=1)
        bottom_frame.columnconfigure(1, weight=0)
        bottom_frame.columnconfigure(2, weight=1)

        self.dl_task_frame = tk.Frame(bottom_frame, bg=colors["card_bg"], relief=tk.SOLID, bd=1)
        self.dl_task_frame.grid(row=0, column=0, sticky="w")
        self._dl_task_slots = []
        for i in range(3):
            slot = self._create_task_slot()
            slot["frame"].grid(row=i, column=0, sticky="ew")
            slot["frame"].grid_remove()
            self._dl_task_slots.append(slot)

        btn_container = tk.Frame(bottom_frame, bg=colors["bg"])
        btn_container.grid(row=0, column=1, padx=10)

        self.prev_btn = ttk.Button(btn_container, text="← 上一页", command=self.prev_page, state=tk.DISABLED)
        self.prev_btn.grid(row=0, column=0, padx=5)

        self.page_var = tk.StringVar(value="1")
        ttk.Label(btn_container, text="页码:").grid(row=0, column=1, padx=(5, 2))
        self.page_entry = ttk.Entry(btn_container, textvariable=self.page_var, width=8, font=("Microsoft YaHei UI", 10))
        self.page_entry.grid(row=0, column=2, padx=2)
        self.page_entry.bind("<Return>", lambda e: self.go_to_page())
        ttk.Button(btn_container, text="跳转", command=self.go_to_page).grid(row=0, column=3, padx=2)

        self.next_btn = ttk.Button(btn_container, text="下一页 →", command=self.next_page, state=tk.DISABLED)
        self.next_btn.grid(row=0, column=4, padx=5)

        self.settings_btn = ttk.Button(bottom_frame, text="设置", command=self.open_settings)
        self.settings_btn.grid(row=0, column=2, sticky="e", padx=5)

        tk.Label(right_frame, text="当前作品", font=("Microsoft YaHei UI", 14, "bold"),
                 bg=colors["card_bg"], fg=colors["text"]).pack(pady=(10, 10))

        self.detail_frame = tk.Frame(right_frame, bg=colors["card_bg"])
        self.detail_frame.pack(fill=tk.BOTH, expand=True)

        self.info_labels = {}
        self.setup_detail_panel()

    def _bump_generation(self):
        self._nav_generation += 1

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
        self.keyword_query = ""
        self.current_tags = []
        self.circle_query = ""
        self._bump_generation()

        if new_tab == "downloaded":
            self.show_downloaded = 3
            if self._all_downloaded_works and self._downloaded_cache_valid:
                self.data_loaded = True
                self._show_downloaded_page()
            else:
                self.status_label.config(text="正在加载已下载作品信息...")
                sort_key = self.sort_map.get(self.sort_var.get(), "download_time_desc")
                threading.Thread(target=self._load_downloaded_works, args=(sort_key,), daemon=True).start()
        else:
            self.show_downloaded = 1
            self.load_data_async()

    def switch_tab(self, tab_name):
        pass

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

        def load():
            logger.debug("load() 后台线程启动 tab=%s page=%s", self.current_tab, self.current_page)
            if self.current_tab == "recommend":
                cached_works = self.db.get_works_by_page(self.current_page)
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
            logger.debug("_fetch_from_api 异常: %s", e)
            if self._nav_generation != gen:
                self.root.after(0, self._safe_reset_loading)
                return
            self.root.after(0, self._on_error, f"加载数据失败: {str(e)}")

    def _fetch_latest_from_api(self, gen=0):
        try:
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
            logger.debug("_on_data_loaded >> display_works_list")
            self.display_works_list()
            logger.debug("_on_data_loaded >> show_work_detail(0)")
            self.show_work_detail(0)
            logger.debug("_on_data_loaded >> update_buttons")
            self.update_buttons()
            logger.debug("_on_data_loaded 完成")
        else:
            self.display_empty_state()
            self.update_buttons()
            messagebox.showinfo("提示", "当前页没有数据")

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

    def _init_translator(self):
        if _config.AI_TRANSLATE_ENABLED and _config.AI_API_KEY:
            translator = get_translator()
            translator.update_config(
                _config.AI_API_KEY,
                _config.AI_API_BASE_URL,
                _config.AI_MODEL
            )

    def refresh_data(self):
        self.keyword_query = ""
        self.current_tags = []
        self._fetched_ids.clear()
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
            if self.show_downloaded == 3:
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
            if self.current_tags:
                self.search_by_tag(self.current_page)
            elif self.circle_query:
                self._bump_generation()
                gen = self._nav_generation
                self.loading = True
                self.show_loading()
                threading.Thread(target=self._search_by_circle_async, args=(self.current_page, gen), daemon=True).start()
            elif self.keyword_query:
                self._bump_generation()
                gen = self._nav_generation
                self.loading = True
                self.show_loading()
                threading.Thread(target=self._search_by_keyword_async, args=(self.current_page, gen), daemon=True).start()
            else:
                self.load_data_async()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的页码")

    def _clear_nav_debounce(self):
        self._nav_debounce_id = None

    def prev_page(self):
        if self.loading:
            return
        if self.show_downloaded == 3:
            if not self._all_downloaded_works or self._downloaded_page <= 1:
                return
            if self._nav_debounce_id:
                return
            self._nav_debounce_id = self.root.after(300, self._clear_nav_debounce)
            self._downloaded_page -= 1
            self.page_var.set(str(self._downloaded_page))
            self._show_downloaded_page()
            return
        if self.current_page <= 1:
            return
        if self._nav_debounce_id:
            return
        self._nav_debounce_id = self.root.after(300, self._clear_nav_debounce)
        self.current_page -= 1
        self.page_var.set(str(self.current_page))
        if self.current_tags:
            self.search_by_tag(self.current_page)
        elif self.circle_query:
            self._bump_generation()
            gen = self._nav_generation
            self.loading = True
            self.show_loading()
            threading.Thread(target=self._search_by_circle_async, args=(self.current_page, gen), daemon=True).start()
        elif self.keyword_query:
            self._bump_generation()
            gen = self._nav_generation
            self.loading = True
            self.show_loading()
            threading.Thread(target=self._search_by_keyword_async, args=(self.current_page, gen), daemon=True).start()
        else:
            self.load_data_async()

    def next_page(self):
        if self.loading:
            return
        if self.show_downloaded == 3:
            if not self._all_downloaded_works:
                return
            total_pages = max(1, (len(self._all_downloaded_works) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            if self._downloaded_page >= total_pages:
                return
            if self._nav_debounce_id:
                return
            self._nav_debounce_id = self.root.after(300, self._clear_nav_debounce)
            self._downloaded_page += 1
            self.page_var.set(str(self._downloaded_page))
            self._show_downloaded_page()
            return
        if self._nav_debounce_id:
            return
        self._nav_debounce_id = self.root.after(300, self._clear_nav_debounce)
        self.current_page += 1
        self.page_var.set(str(self.current_page))
        if self.current_tags:
            self.search_by_tag(self.current_page)
        elif self.circle_query:
            self._bump_generation()
            gen = self._nav_generation
            self.loading = True
            self.show_loading()
            threading.Thread(target=self._search_by_circle_async, args=(self.current_page, gen), daemon=True).start()
        elif self.keyword_query:
            self._bump_generation()
            gen = self._nav_generation
            self.loading = True
            self.show_loading()
            threading.Thread(target=self._search_by_keyword_async, args=(self.current_page, gen), daemon=True).start()
        else:
            self.load_data_async()

    def prev_work(self):
        if self.works and self.current_work_index > 0:
            self.show_work_detail(self.current_work_index - 1)

    def next_work(self):
        if self.works and self.current_work_index < len(self.works) - 1:
            self.show_work_detail(self.current_work_index + 1)

    def update_buttons(self):
        if self.show_downloaded == 3:
            if not self._all_downloaded_works:
                self.prev_btn.grid_remove()
                self.next_btn.grid_remove()
                return
            total_pages = max(1, (len(self._all_downloaded_works) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            if self._downloaded_page > 1:
                self.prev_btn.config(state=tk.NORMAL)
                self.prev_btn.grid()
            else:
                self.prev_btn.grid_remove()
            if self._downloaded_page < total_pages:
                self.next_btn.config(state=tk.NORMAL)
                self.next_btn.grid()
            else:
                self.next_btn.grid_remove()
            return
        if self.current_page > 1 and self.data_loaded:
            self.prev_btn.config(state=tk.NORMAL)
            self.prev_btn.grid()
        else:
            self.prev_btn.grid_remove()
        if self.data_loaded:
            self.next_btn.config(state=tk.NORMAL)
            self.next_btn.grid()
        else:
            self.next_btn.grid_remove()

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

    def _create_task_slot(self):
        colors = self.COLORS
        row = tk.Frame(self.dl_task_frame, bg=colors["card_bg"])

        id_label = tk.Label(row, font=("Microsoft YaHei UI", 9),
                            bg=colors["card_bg"], fg=colors["text_secondary"], width=10, anchor=tk.W)
        id_label.pack(side=tk.LEFT, padx=(5, 3))

        title_label = tk.Label(row, font=("Microsoft YaHei UI", 9),
                               bg=colors["card_bg"], fg=colors["text"], anchor=tk.W)
        title_label.pack(side=tk.LEFT, padx=(0, 5))

        pbar = ttk.Progressbar(row, mode='determinate', length=100)

        pct_label = tk.Label(row, font=("Microsoft YaHei UI", 9),
                             bg=colors["card_bg"], fg=colors["text"], width=4)

        speed_label = tk.Label(row, font=("Microsoft YaHei UI", 9),
                               bg=colors["card_bg"], fg=colors["text_hint"])

        done_label = tk.Label(row, text="下载完成 ✓", font=("Microsoft YaHei UI", 9),
                              bg=colors["card_bg"], fg=colors["success"])

        fail_label = tk.Label(row, text="下载失败", font=("Microsoft YaHei UI", 9),
                              bg=colors["card_bg"], fg=colors["error"])

        retry_btn = ttk.Button(row, text="重试", width=6)

        queued_label = tk.Label(row, text="排队中...", font=("Microsoft YaHei UI", 9),
                                bg=colors["card_bg"], fg=colors["accent"])

        return {
            "frame": row,
            "id_label": id_label,
            "title_label": title_label,
            "pbar": pbar,
            "pct_label": pct_label,
            "speed_label": speed_label,
            "done_label": done_label,
            "fail_label": fail_label,
            "retry_btn": retry_btn,
            "queued_label": queued_label,
        }

    def _on_dl_tasks_changed(self):
        self.root.after(0, self._refresh_task_display)
        self.root.after(0, self._update_downloaded_count)
        # 只在下载任务完成或失败时才使缓存失效（新增/删除作品）
        # 进度更新不应使缓存失效
        tasks = self.dl_manager.get_all_tasks()
        completed_or_failed = [t for t in tasks 
                              if t.status.value in ("completed", "failed")]
        if completed_or_failed:
            self._downloaded_cache_valid = False

    def _refresh_task_display(self):
        tasks = self.dl_manager.get_all_tasks()
        active_tasks = [t for t in tasks if t.status.value in ("submitting", "downloading")]
        queued_tasks = [t for t in tasks if t.status.value == "queued"]
        failed_tasks = [t for t in tasks if t.status.value == "failed"]
        completed_tasks = [t for t in tasks if t.status.value == "completed"]
        recent_completed = [t for t in completed_tasks
                           if t.completed_at and time.time() - t.completed_at < 10]

        display_tasks = (active_tasks + queued_tasks[:1] + failed_tasks + recent_completed)[:3]

        for idx, slot in enumerate(self._dl_task_slots):
            if idx < len(display_tasks):
                task = display_tasks[idx]
                slot["id_label"].config(text=task.work_id)
                slot["title_label"].config(text=task.title[:20])

                slot["pbar"].pack_forget()
                slot["pct_label"].pack_forget()
                slot["speed_label"].pack_forget()
                slot["done_label"].pack_forget()
                slot["fail_label"].pack_forget()
                slot["retry_btn"].pack_forget()
                slot["queued_label"].pack_forget()

                if task.status.value in ("submitting", "downloading"):
                    slot["pbar"].pack(side=tk.LEFT, padx=(0, 5))
                    slot["pct_label"].pack(side=tk.LEFT)

                    if task.total_bytes > 0:
                        pct = min(int(task.completed_bytes * 100 / task.total_bytes), 100)
                        slot["pbar"]["value"] = pct
                        slot["pct_label"].config(text=f"{pct}%")
                    else:
                        slot["pbar"]["value"] = 0
                        slot["pct_label"].config(text="...")

                    if task.speed > 0:
                        slot["speed_label"].config(text=self._format_speed(task.speed))
                        slot["speed_label"].pack(side=tk.LEFT, padx=(5, 0))
                elif task.status.value == "queued":
                    slot["queued_label"].pack(side=tk.LEFT)
                    queue_pos = queued_tasks.index(task) + 1 if task in queued_tasks else 0
                    slot["queued_label"].config(text=f"排队中 ({queue_pos})")
                elif task.status.value == "failed":
                    slot["fail_label"].pack(side=tk.LEFT, padx=(0, 5))
                    slot["retry_btn"].config(command=lambda wid=task.work_id: self._retry_download(wid))
                    slot["retry_btn"].pack(side=tk.LEFT)
                elif task.status.value == "completed":
                    slot["pbar"].pack(side=tk.LEFT, padx=(0, 5))
                    slot["pbar"]["value"] = 100
                    slot["pct_label"].pack(side=tk.LEFT)
                    slot["pct_label"].config(text="100%")
                    slot["done_label"].pack(side=tk.LEFT, padx=(5, 0))

                slot["frame"].grid(pady=1)
            else:
                slot["frame"].grid_remove()

    def _retry_download(self, work_id):
        success = self.dl_manager.retry(work_id)
        if success:
            self.status_label.config(text=f"正在重试下载: {work_id}")
        else:
            self.status_label.config(text=f"重试失败: {work_id}")

    def open_download_window(self, work, display_title=None):
        self._dl_win = DownloadWindow(self.root, work, self.downloaded_ids_cache, display_title)

    def _format_size(self, size):
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"

    def _format_speed(self, speed_bytes):
        if speed_bytes < 1024:
            return f"{speed_bytes} B/s"
        elif speed_bytes < 1024 * 1024:
            return f"{speed_bytes / 1024:.1f} KB/s"
        else:
            return f"{speed_bytes / (1024 * 1024):.1f} MB/s"

    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_label.config(text=f"✓ 已复制: {text}")

    def _bind_shortcuts(self):
        self.root.bind("<Control-f>", lambda e: self._focus_search())
        self.root.bind("<Control-F>", lambda e: self._focus_search())
        self.root.bind("<Escape>", lambda e: self._on_escape())
        self.root.bind("<Left>", lambda e: self._shortcut_prev())
        self.root.bind("<Right>", lambda e: self._shortcut_next())

    def _focus_search(self):
        self.search_entry.focus_set()
        self.search_entry.select_range(0, tk.END)
        return "break"

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

    def open_settings(self):
        self._settings_win = SettingsWindow(self.root, image_cache=self.image_cache)


if __name__ == "__main__":
    root = tk.Tk()
    app = WorkApp(root)
    root.mainloop()
