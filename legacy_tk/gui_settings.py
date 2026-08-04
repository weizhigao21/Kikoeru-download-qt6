import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json
import shutil
import logging

from .. import config as _config
from ..config import _USER_ROOT, CACHE_DIR
from ..services.translator import get_translator
from .fonts import DEFAULT, DEFAULT_BOLD, SMALL, TINY, BODY, TITLE_BOLD

logger = logging.getLogger(__name__)


class SettingsWindow:
    def __init__(self, parent, image_cache=None):
        self.window = tk.Toplevel(parent)
        self.window.title("设置")
        self.image_cache = image_cache

        config_path = _config.CONFIG_PATH
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except FileNotFoundError:
            cfg = {}

        self.current_values = {
            "download_dir": cfg.get("download_dir", "downloads"),
            "aria2_url": cfg.get("aria2_rpc_url", "http://localhost:6800/rpc"),
            "db_dir": cfg.get("db_dir", ""),
            "download_method": cfg.get("download_method", "aria2"),
            "direct_threads": cfg.get("direct_download_threads", 3),
            "queue_mode": cfg.get("queue_mode", False),
            "max_concurrent": cfg.get("max_concurrent_downloads", 1),
            "ai_enabled": cfg.get("ai_translate_enabled", False),
            "ai_key": cfg.get("ai_api_key", ""),
            "ai_base": cfg.get("ai_api_base_url", "https://api.openai.com/v1"),
            "ai_model": cfg.get("ai_model", "gpt-3.5-turbo"),
            "ai_thinking_enabled": cfg.get("ai_thinking_enabled", True),
            "ai_translate_editable": cfg.get("ai_translate_editable", True),
            "filename_filter_chars": cfg.get("filename_filter_chars", ""),
            "subtitle_convert_enabled": cfg.get("subtitle_convert_enabled", True),
            "auto_flatten_enabled": cfg.get("auto_flatten_enabled", True),
            "traditional_to_simplified_enabled": cfg.get("traditional_to_simplified_enabled", True),
        }

        win_w = 700
        win_h = 500
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        pos_x = parent_x + (parent_w - win_w) // 2
        pos_y = parent_y + (parent_h - win_h) // 2
        self.window.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        self._create_layout()
        self._show_page("download")

    def _create_layout(self):
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True)

        left_frame = tk.Frame(main_frame, width=150, bg="#f0f0f0")
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        left_frame.pack_propagate(False)

        right_frame = ttk.Frame(main_frame, padding=20)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.nav_items = [
            ("download", "📥 下载设置"),
            ("queue", "📋 队列设置"),
            ("storage", "💾 存储管理"),
            ("subtitle", "📝 字幕管理"),
            ("ai", "🤖 AI 翻译"),
        ]

        self.nav_buttons = {}
        for key, text in self.nav_items:
            btn = tk.Label(left_frame, text=text, font=BODY,
                          bg="#f0f0f0", fg="#333333", anchor=tk.W, padx=20, pady=12,
                          cursor="hand2")
            btn.pack(fill=tk.X)
            btn.bind("<Button-1>", lambda e, k=key: self._show_page(k))
            self.nav_buttons[key] = btn

        self.pages = {}
        self._create_download_page(right_frame)
        self._create_queue_page(right_frame)
        self._create_storage_page(right_frame)
        self._create_subtitle_page(right_frame)
        self._create_ai_page(right_frame)

        btn_frame = ttk.Frame(right_frame)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(20, 0))
        ttk.Button(btn_frame, text="保存", command=self.save_settings).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(btn_frame, text="取消", command=self.cancel).pack(side=tk.RIGHT)

    def _show_page(self, page_key):
        for key, btn in self.nav_buttons.items():
            if key == page_key:
                btn.config(bg="#2196F3", fg="white")
            else:
                btn.config(bg="#f0f0f0", fg="#333333")

        for page in self.pages.values():
            page.pack_forget()

        if page_key in self.pages:
            self.pages[page_key].pack(fill=tk.BOTH, expand=True)

    def _bind_mousewheel(self, widget):
        """递归绑定滚轮事件，使可滚动区域内的所有子控件都能响应"""
        widget.bind("<MouseWheel>", self._on_ai_scroll)
        for child in widget.winfo_children():
            self._bind_mousewheel(child)

    def _on_ai_scroll(self, event):
        canvas = getattr(self, "_ai_canvas", None)
        if canvas is not None:
            canvas.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    def _create_download_page(self, parent):
        page = ttk.Frame(parent)
        self.pages["download"] = page

        ttk.Label(page, text="下载设置", font=TITLE_BOLD).pack(anchor=tk.W, pady=(0, 20))

        form_frame = ttk.Frame(page)
        form_frame.pack(fill=tk.X)
        form_frame.columnconfigure(1, weight=1)

        ttk.Label(form_frame, text="下载方式:", font=DEFAULT).grid(row=0, column=0, sticky=tk.W, pady=10)
        self.download_method_var = tk.StringVar(value=self.current_values["download_method"])
        method_frame = ttk.Frame(form_frame)
        method_frame.grid(row=0, column=1, sticky=tk.W, padx=(20, 0))
        ttk.Radiobutton(method_frame, text="Aria2", variable=self.download_method_var, value="aria2").pack(side=tk.LEFT)
        ttk.Radiobutton(method_frame, text="直接下载", variable=self.download_method_var, value="direct").pack(side=tk.LEFT, padx=(20, 0))

        ttk.Label(form_frame, text="Aria2 地址:", font=DEFAULT).grid(row=1, column=0, sticky=tk.W, pady=10)
        self.aria2_var = tk.StringVar(value=self.current_values["aria2_url"])
        ttk.Entry(form_frame, textvariable=self.aria2_var, width=40).grid(row=1, column=1, sticky=tk.W, padx=(20, 0))

        ttk.Label(form_frame, text="下载线程数:", font=DEFAULT).grid(row=2, column=0, sticky=tk.W, pady=10)
        self.direct_threads_var = tk.StringVar(value=str(self.current_values["direct_threads"]))
        threads_frame = ttk.Frame(form_frame)
        threads_frame.grid(row=2, column=1, sticky=tk.W, padx=(20, 0))
        ttk.Spinbox(threads_frame, from_=1, to=10, textvariable=self.direct_threads_var, width=8).pack(side=tk.LEFT)
        ttk.Label(threads_frame, text="(直接下载并发数)", font=SMALL, foreground="gray").pack(side=tk.LEFT, padx=(10, 0))

        ttk.Label(form_frame, text="下载目录:", font=DEFAULT).grid(row=3, column=0, sticky=tk.W, pady=10)
        dir_frame = ttk.Frame(form_frame)
        dir_frame.grid(row=3, column=1, sticky=tk.W, padx=(20, 0))
        self.download_dir_var = tk.StringVar(value=self.current_values["download_dir"])
        ttk.Entry(dir_frame, textvariable=self.download_dir_var, width=35).pack(side=tk.LEFT)
        ttk.Button(dir_frame, text="浏览", command=self.browse_dir).pack(side=tk.LEFT, padx=(10, 0))

        ttk.Label(form_frame, text="文件名过滤字符:", font=DEFAULT).grid(row=4, column=0, sticky=tk.W, pady=10)
        filter_frame = ttk.Frame(form_frame)
        filter_frame.grid(row=4, column=1, sticky=tk.W, padx=(20, 0))
        self.filename_filter_var = tk.StringVar(value=self.current_values["filename_filter_chars"])
        ttk.Entry(filter_frame, textvariable=self.filename_filter_var, width=25).pack(side=tk.LEFT)
        ttk.Label(filter_frame, text="(额外过滤的字符，如 【】「」《》…)", font=SMALL, foreground="gray").pack(side=tk.LEFT, padx=(8, 0))

        self.auto_flatten_var = tk.BooleanVar(value=self.current_values["auto_flatten_enabled"])
        ttk.Checkbutton(form_frame, text="默认启用自动整理文件夹（下载完成后扁平化嵌套目录）", variable=self.auto_flatten_var).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=10)

        self.traditional_to_simplified_var = tk.BooleanVar(value=self.current_values["traditional_to_simplified_enabled"])
        ttk.Checkbutton(form_frame, text="启用繁简转换（下载完成后自动将繁体字幕和文件名转为简体）", variable=self.traditional_to_simplified_var).grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=10)

    def _create_queue_page(self, parent):
        page = ttk.Frame(parent)
        self.pages["queue"] = page

        ttk.Label(page, text="队列设置", font=TITLE_BOLD).pack(anchor=tk.W, pady=(0, 20))

        desc = ttk.Label(page, text="启用队列模式后，作品将按顺序下载，一个完成后再开始下一个。\n适合网络受限或需要避免触发限流的场景。",
                        font=SMALL, foreground="gray", wraplength=400)
        desc.pack(anchor=tk.W, pady=(0, 20))

        form_frame = ttk.Frame(page)
        form_frame.pack(fill=tk.X)
        form_frame.columnconfigure(1, weight=1)

        self.queue_mode_var = tk.BooleanVar(value=self.current_values["queue_mode"])
        ttk.Checkbutton(form_frame, text="启用队列模式", variable=self.queue_mode_var).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=10)

        ttk.Label(form_frame, text="最大同时下载:", font=DEFAULT).grid(row=1, column=0, sticky=tk.W, pady=10)
        concurrent_frame = ttk.Frame(form_frame)
        concurrent_frame.grid(row=1, column=1, sticky=tk.W, padx=(20, 0))
        self.max_concurrent_var = tk.StringVar(value=str(self.current_values["max_concurrent"]))
        ttk.Spinbox(concurrent_frame, from_=1, to=5, textvariable=self.max_concurrent_var, width=8).pack(side=tk.LEFT)
        ttk.Label(concurrent_frame, text="(队列模式下同时下载的作品数)", font=SMALL, foreground="gray").pack(side=tk.LEFT, padx=(10, 0))

    def _create_storage_page(self, parent):
        page = ttk.Frame(parent)
        self.pages["storage"] = page

        ttk.Label(page, text="存储管理", font=TITLE_BOLD).pack(anchor=tk.W, pady=(0, 20))

        form_frame = ttk.Frame(page)
        form_frame.pack(fill=tk.X)
        form_frame.columnconfigure(1, weight=1)

        ttk.Label(form_frame, text="数据库目录:", font=DEFAULT).grid(row=0, column=0, sticky=tk.W, pady=10)
        db_frame = ttk.Frame(form_frame)
        db_frame.grid(row=0, column=1, sticky=tk.W, padx=(20, 0))
        self.db_dir_var = tk.StringVar(value=self.current_values["db_dir"])
        ttk.Entry(db_frame, textvariable=self.db_dir_var, width=35).pack(side=tk.LEFT)
        ttk.Button(db_frame, text="浏览", command=self.browse_db_dir).pack(side=tk.LEFT, padx=(10, 0))

        ttk.Label(form_frame, text="", font=TINY).grid(row=1, column=1, sticky=tk.W, padx=(20, 0))
        ttk.Label(form_frame, text="留空使用默认位置 (settings/)", font=SMALL,
                 foreground="gray").grid(row=1, column=1, sticky=tk.W, padx=(20, 0))

        ttk.Separator(page, orient="horizontal").pack(fill=tk.X, pady=20)

        cache_frame = ttk.Frame(page)
        cache_frame.pack(fill=tk.X)

        cache_size = self._get_cache_size()
        self.cache_label = ttk.Label(cache_frame, text=f"图片缓存大小: {cache_size}", font=DEFAULT)
        self.cache_label.pack(side=tk.LEFT)
        ttk.Button(cache_frame, text="清除缓存", command=self.clear_cache).pack(side=tk.RIGHT)

        ttk.Label(page, text="清除缓存将删除所有已下载的图片，程序会重新从网络加载。",
                 font=SMALL, foreground="gray").pack(anchor=tk.W, pady=(10, 0))

    def _create_subtitle_page(self, parent):
        page = ttk.Frame(parent)
        self.pages["subtitle"] = page

        ttk.Label(page, text="字幕管理", font=TITLE_BOLD).pack(anchor=tk.W, pady=(0, 20))

        desc = ttk.Label(page, text="启用字幕转换后，下载的 VTT 字幕文件将自动转换为 LRC 格式。\n转换后的字幕文件名会移除音频格式后缀（如 .mp3.vtt → .lrc）。",
                        font=SMALL, foreground="gray", wraplength=400)
        desc.pack(anchor=tk.W, pady=(0, 20))

        form_frame = ttk.Frame(page)
        form_frame.pack(fill=tk.X)
        form_frame.columnconfigure(1, weight=1)

        self.subtitle_convert_var = tk.BooleanVar(value=self.current_values["subtitle_convert_enabled"])
        ttk.Checkbutton(form_frame, text="启用 VTT 字幕自动转换为 LRC", variable=self.subtitle_convert_var).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=10)

        ttk.Label(form_frame, text="转换说明:", font=DEFAULT_BOLD).grid(row=1, column=0, sticky=tk.W, pady=(20, 5))
        info_text = "• VTT (Web Video Text Tracks) 是一种网页字幕格式\n• LRC (Lyric) 是一种歌词文件格式，支持时间戳\n• 转换后字幕文件名会简化，便于管理\n• 原始 VTT 文件会在转换后自动删除"
        ttk.Label(form_frame, text=info_text, font=SMALL, foreground="gray", justify=tk.LEFT).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=(20, 0))

    def _create_ai_page(self, parent):
        # AI 设置内容较多，使用可滚动容器避免超出窗口高度
        container = ttk.Frame(parent)
        self.pages["ai"] = container

        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        page = ttk.Frame(canvas)
        win_id = canvas.create_window((0, 0), window=page, anchor="nw")
        page.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))

        self._ai_canvas = canvas
        self._bind_mousewheel(canvas)
        self._bind_mousewheel(page)

        ttk.Label(page, text="AI 翻译设置", font=TITLE_BOLD).pack(anchor=tk.W, pady=(0, 20))

        desc = ttk.Label(page, text="启用 AI 翻译后，可以使用 OpenAI 兼容的 API 翻译作品标题。\n支持 DeepSeek、GPT 等模型。",
                        font=SMALL, foreground="gray", wraplength=400)
        desc.pack(anchor=tk.W, pady=(0, 20))

        form_frame = ttk.Frame(page)
        form_frame.pack(fill=tk.X)
        form_frame.columnconfigure(1, weight=1)

        self.ai_enabled_var = tk.BooleanVar(value=self.current_values["ai_enabled"])
        ttk.Checkbutton(form_frame, text="启用 AI 翻译", variable=self.ai_enabled_var).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=10)

        ttk.Label(form_frame, text="API Key:", font=DEFAULT).grid(row=1, column=0, sticky=tk.W, pady=8)
        self.ai_key_var = tk.StringVar(value=self.current_values["ai_key"])
        ttk.Entry(form_frame, textvariable=self.ai_key_var, width=40, show="*").grid(row=1, column=1, sticky=tk.W, padx=(20, 0))

        ttk.Label(form_frame, text="API 地址:", font=DEFAULT).grid(row=2, column=0, sticky=tk.W, pady=8)
        self.ai_base_var = tk.StringVar(value=self.current_values["ai_base"])
        ttk.Entry(form_frame, textvariable=self.ai_base_var, width=40).grid(row=2, column=1, sticky=tk.W, padx=(20, 0))

        ttk.Label(form_frame, text="模型名称:", font=DEFAULT).grid(row=3, column=0, sticky=tk.W, pady=8)
        self.ai_model_var = tk.StringVar(value=self.current_values["ai_model"])
        model_frame = ttk.Frame(form_frame)
        model_frame.grid(row=3, column=1, sticky=tk.W, padx=(20, 0))
        ttk.Entry(model_frame, textvariable=self.ai_model_var, width=25).pack(side=tk.LEFT)
        ttk.Label(model_frame, text="(如 deepseek-chat, gpt-3.5-turbo)", font=SMALL,
                 foreground="gray").pack(side=tk.LEFT, padx=(10, 0))

        self.ai_thinking_var = tk.BooleanVar(value=self.current_values["ai_thinking_enabled"])
        ttk.Checkbutton(form_frame, text="启用思考模式（DeepSeek 推理模式，翻译更准确但响应更慢）",
                        variable=self.ai_thinking_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=10)

        ttk.Separator(form_frame, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", pady=15)

        self.ai_editable_var = tk.BooleanVar(value=self.current_values.get("ai_translate_editable", True))
        ttk.Checkbutton(form_frame, text="启用翻译编辑（允许手动修改翻译结果）", variable=self.ai_editable_var).grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=10)

    def browse_dir(self):
        initial_dir = self.download_dir_var.get().strip()
        if not os.path.isabs(initial_dir):
            initial_dir = os.path.join(_USER_ROOT, initial_dir)
        if not os.path.isdir(initial_dir):
            initial_dir = os.path.dirname(initial_dir)
            if not os.path.isdir(initial_dir):
                initial_dir = os.path.expanduser("~")
        self.window.grab_release()
        dir_path = filedialog.askdirectory(parent=self.window, initialdir=initial_dir)
        self.window.grab_set()
        if dir_path:
            self.download_dir_var.set(dir_path)

    def browse_db_dir(self):
        current = self.db_dir_var.get().strip()
        initial_dir = current if os.path.isabs(current) and os.path.isdir(current) else os.path.expanduser("~")
        self.window.grab_release()
        dir_path = filedialog.askdirectory(parent=self.window, initialdir=initial_dir)
        self.window.grab_set()
        if dir_path:
            self.db_dir_var.set(dir_path)

    def cancel(self):
        self.window.grab_release()
        self.window.destroy()

    def save_settings(self):
        new_rpc_url = self.aria2_var.get().strip()
        new_download_dir = self.download_dir_var.get().strip()
        new_db_dir = self.db_dir_var.get().strip()
        new_download_method = self.download_method_var.get()
        new_direct_threads = int(self.direct_threads_var.get())
        new_queue_mode = self.queue_mode_var.get()
        new_max_concurrent = int(self.max_concurrent_var.get())
        new_ai_enabled = self.ai_enabled_var.get()
        new_ai_key = self.ai_key_var.get().strip()
        new_ai_base = self.ai_base_var.get().strip()
        new_ai_model = self.ai_model_var.get().strip()
        new_ai_thinking = self.ai_thinking_var.get()
        new_ai_editable = self.ai_editable_var.get()
        new_filename_filter = self.filename_filter_var.get().strip()
        new_subtitle_convert = self.subtitle_convert_var.get()
        new_auto_flatten = self.auto_flatten_var.get()
        new_traditional_to_simplified = self.traditional_to_simplified_var.get()

        if not new_download_dir:
            messagebox.showerror("错误", "下载目录不能为空", parent=self.window)
            return

        config_path = _config.CONFIG_PATH
        settings_dir = os.path.dirname(config_path)

        try:
            os.makedirs(settings_dir, exist_ok=True)
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

            old_db_dir = cfg.get("db_dir", "")

            cfg["aria2_rpc_url"] = new_rpc_url
            cfg["download_dir"] = new_download_dir
            cfg["db_dir"] = new_db_dir
            cfg["download_method"] = new_download_method
            cfg["direct_download_threads"] = new_direct_threads
            cfg["queue_mode"] = new_queue_mode
            cfg["max_concurrent_downloads"] = new_max_concurrent
            cfg["ai_translate_enabled"] = new_ai_enabled
            cfg["ai_api_key"] = new_ai_key
            cfg["ai_api_base_url"] = new_ai_base
            cfg["ai_model"] = new_ai_model
            cfg["ai_thinking_enabled"] = new_ai_thinking
            cfg["ai_translate_editable"] = new_ai_editable
            cfg["filename_filter_chars"] = new_filename_filter
            cfg["subtitle_convert_enabled"] = new_subtitle_convert
            cfg["auto_flatten_enabled"] = new_auto_flatten
            cfg["traditional_to_simplified_enabled"] = new_traditional_to_simplified

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
                f.flush()
        except PermissionError:
            messagebox.showerror("错误", "没有权限写入配置文件", parent=self.window)
            return
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}", parent=self.window)
            return

        _config.ARIA2_RPC_URL = new_rpc_url
        _config.DOWNLOAD_DIR = new_download_dir if os.path.isabs(new_download_dir) else os.path.join(_USER_ROOT, new_download_dir)
        _config.DOWNLOAD_METHOD = new_download_method
        _config.DIRECT_DOWNLOAD_THREADS = new_direct_threads
        _config.QUEUE_MODE = new_queue_mode
        _config.MAX_CONCURRENT_DOWNLOADS = new_max_concurrent
        _config.AI_TRANSLATE_ENABLED = new_ai_enabled
        _config.AI_API_KEY = new_ai_key
        _config.AI_API_BASE_URL = new_ai_base
        _config.AI_MODEL = new_ai_model
        _config.AI_THINKING_ENABLED = new_ai_thinking
        _config.AI_TRANSLATE_EDITABLE = new_ai_editable
        _config.FILENAME_FILTER_CHARS = new_filename_filter
        _config.SUBTITLE_CONVERT_ENABLED = new_subtitle_convert
        _config.AUTO_FLATTEN_ENABLED = new_auto_flatten
        _config.TRADITIONAL_TO_SIMPLIFIED_ENABLED = new_traditional_to_simplified

        from ..download.manager import DownloadManager
        manager = DownloadManager()
        manager.set_queue_mode(new_queue_mode, new_max_concurrent)

        translator = get_translator()
        if new_ai_enabled and new_ai_key:
            translator.update_config(new_ai_key, new_ai_base, new_ai_model, new_ai_thinking)

        if new_db_dir != old_db_dir:
            resolved_new = new_db_dir if os.path.isabs(new_db_dir) else os.path.join(_USER_ROOT, new_db_dir) if new_db_dir else os.path.join(_USER_ROOT, "settings")
            resolved_old = old_db_dir if os.path.isabs(old_db_dir) else os.path.join(_USER_ROOT, old_db_dir) if old_db_dir else os.path.join(_USER_ROOT, "settings")

            if os.path.normpath(resolved_new) != os.path.normpath(resolved_old):
                os.makedirs(resolved_new, exist_ok=True)
                for db_name in ("works.db", "download_history.db"):
                    src = os.path.join(resolved_old, db_name)
                    dst = os.path.join(resolved_new, db_name)
                    if os.path.isfile(src) and not os.path.isfile(dst):
                        try:
                            shutil.copy2(src, dst)
                        except Exception as e:
                            logger.exception("复制 %s 失败", db_name)

        _config.DB_DIR = new_db_dir if os.path.isabs(new_db_dir) and new_db_dir else os.path.join(_USER_ROOT, new_db_dir) if new_db_dir else os.path.join(_USER_ROOT, "settings")
        _config.DB_PATH = os.path.join(_config.DB_DIR, "works.db")
        _config.DOWNLOAD_HISTORY_DB_PATH = os.path.join(_config.DB_DIR, "download_history.db")

        self.window.grab_release()
        self.window.destroy()

        if new_db_dir != old_db_dir:
            messagebox.showinfo("提示", "数据库目录已更改，请重启应用后生效")
        else:
            messagebox.showinfo("提示", "设置已保存")

    def _get_cache_size(self):
        try:
            if not os.path.isdir(CACHE_DIR):
                return "0 B"
            total = 0
            for fname in os.listdir(CACHE_DIR):
                fpath = os.path.join(CACHE_DIR, fname)
                if os.path.isfile(fpath):
                    total += os.path.getsize(fpath)
            if total < 1024:
                return f"{total} B"
            elif total < 1024 * 1024:
                return f"{total / 1024:.1f} KB"
            elif total < 1024 * 1024 * 1024:
                return f"{total / (1024 * 1024):.1f} MB"
            else:
                return f"{total / (1024 * 1024 * 1024):.2f} GB"
        except Exception:
            return "未知"

    def clear_cache(self):
        if not messagebox.askyesno("确认", "确定要清除所有图片缓存吗？\n清除后需要重新下载图片。", parent=self.window):
            return
        try:
            if self.image_cache:
                self.image_cache.clear_memory_cache()
            if os.path.isdir(CACHE_DIR):
                for fname in os.listdir(CACHE_DIR):
                    fpath = os.path.join(CACHE_DIR, fname)
                    try:
                        if os.path.isfile(fpath):
                            os.remove(fpath)
                    except Exception:
                        pass
            self.cache_label.config(text="图片缓存大小: 0 B")
            messagebox.showinfo("提示", "缓存已清除", parent=self.window)
        except Exception as e:
            messagebox.showerror("错误", f"清除缓存失败: {e}", parent=self.window)
