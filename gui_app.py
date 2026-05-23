import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] %(threadName)s: %(message)s')
logger = logging.getLogger('gui_app')

from PIL import Image, ImageTk

from src import (
    _APP_ROOT, VERSION, MEMORY_CACHE_SIZE,
    CACHE_DIR, DB_PATH, DOWNLOAD_HISTORY_DB_PATH, ICON_PATH,
    DOWNLOAD_DIR,
    ImageCacheManager, DatabaseManager, DownloadHistoryManager, PendingTaskManager,
    get_api_client, DownloadWindow, SettingsWindow, DownloadManagerWindow
)
from src.download.manager import DownloadManager
from src.ui.detail_mixin import DetailMixin
from src.ui.list_mixin import ListMixin
from src.ui.search_mixin import SearchMixin
from src.ui.filter_mixin import FilterMixin
from src.services.translator import get_translator
from src import config as _config

from gui_app_ui import UISetupMixin
from gui_app_nav import NavigationMixin
from gui_app_events import EventMixin


class WorkApp(DetailMixin, ListMixin, SearchMixin, FilterMixin,
              UISetupMixin, NavigationMixin, EventMixin):
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
        self._thumb_pool = ThreadPoolExecutor(max_workers=8)
        self._data_pool = ThreadPoolExecutor(max_workers=4)
        self.db = DatabaseManager(DB_PATH)
        self.download_history = DownloadHistoryManager(DOWNLOAD_HISTORY_DB_PATH)
        self.pending_task_db = PendingTaskManager(DOWNLOAD_HISTORY_DB_PATH)

        self.dl_manager = DownloadManager()
        self.dl_manager.set_download_history(self.download_history)
        self.dl_manager.set_pending_db(self.pending_task_db)
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
        self.search_history = [{"type": "recommend", "page": 1}]
        self.current_search_index = 0
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
        self.root.after(100, self._on_startup_restore)
        self.root.after(150, self.load_data_async)

    def _on_startup_restore(self):
        try:
            count = self.dl_manager.restore_pending_tasks()
            if count > 0:
                self.status_label.config(text=f"已恢复 {count} 个未完成下载任务")
        except Exception as e:
            print(f"[启动] 恢复待处理任务异常: {e}")

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

    def _init_translator(self):
        if _config.AI_TRANSLATE_ENABLED and _config.AI_API_KEY:
            translator = get_translator()
            translator.update_config(
                _config.AI_API_KEY,
                _config.AI_API_BASE_URL,
                _config.AI_MODEL
            )

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

    def _focus_search(self):
        self.search_entry.focus_set()
        self.search_entry.select_range(0, tk.END)
        return "break"


if __name__ == "__main__":
    root = tk.Tk()
    app = WorkApp(root)
    root.mainloop()