# -*- coding: utf-8 -*-
"""设置对话框（阶段 3，替代 tkinter 版 gui_settings.py）。

左侧导航 + QStackedWidget 五页（下载/队列/存储/字幕/AI）；
保存时写回 config.json、同步 src.config 模块常量、
更新 DownloadManager 队列模式与翻译服务配置（对齐 tkinter 版 save_settings）。
"""
import json
import logging
import os
import shutil

from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QFileDialog,
                             QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                             QMessageBox, QPushButton, QRadioButton, QScrollArea,
                             QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from src import config as _config
from src.services.translator import get_translator
from src.ui.qt.qt_fonts import DEFAULT, SMALL, TITLE_BOLD
from src.utils import format_size as _fmt_size

logger = logging.getLogger(__name__)

_HINT = "#999999"


class SettingsDialog(QDialog):
    def __init__(self, parent, image_cache=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(720, 520)
        self.setModal(False)
        self.image_cache = image_cache

        # 读配置（与 tkinter 版一致：直接读 JSON，避免依赖模块级缓存）
        try:
            with open(_config.CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            cfg = {}

        def get(key, default):
            v = cfg.get(key)
            return default if v is None else v

        self.cfg = cfg
        self.current_values = {
            "download_dir": get("download_dir", "downloads"),
            "aria2_url": get("aria2_rpc_url", "http://localhost:6800/rpc"),
            "db_dir": get("db_dir", ""),
            "download_method": get("download_method", "aria2"),
            "direct_threads": get("direct_download_threads", 3),
            "queue_mode": get("queue_mode", False),
            "max_concurrent": get("max_concurrent_downloads", 1),
            "ai_enabled": get("ai_translate_enabled", False),
            "ai_key": get("ai_api_key", ""),
            "ai_base": get("ai_api_base_url", "https://api.openai.com/v1"),
            "ai_model": get("ai_model", "gpt-3.5-turbo"),
            "ai_thinking_enabled": get("ai_thinking_enabled", True),
            "ai_translate_editable": get("ai_translate_editable", True),
            "filename_filter_chars": get("filename_filter_chars", ""),
            "folder_title_max_len": get("folder_title_max_len", 120),
            "subtitle_convert_enabled": get("subtitle_convert_enabled", True),
            "auto_flatten_enabled": get("auto_flatten_enabled", True),
            "traditional_to_simplified_enabled": get("traditional_to_simplified_enabled", True),
            "auto_collect_enabled": get("auto_collect_enabled", True),
            "daily_new_works_limit": get("daily_new_works_limit", 500),
            "head_poll_interval": get("head_poll_interval", 60),
        }

        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 左侧导航
        nav = QVBoxLayout()
        nav.setContentsMargins(10, 16, 10, 16)
        nav.setSpacing(2)
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons = []
        nav_items = [
            ("download", "\U0001F4E5 下载设置"),
            ("queue", "\U0001F4CB 队列设置"),
            ("storage", "\U0001F4BE 存储管理"),
            ("subtitle", "\U0001F4DD 字幕管理"),
            ("ai", "\U0001F916 AI 翻译"),
        ]
        for key, text in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setFont(DEFAULT)
            btn.clicked.connect(lambda _=False, k=key: self._show_page(k))
            nav.addWidget(btn)
            self._nav_group.addButton(btn)
            self._nav_buttons.append(btn)
        nav.addStretch(1)
        nav_wrap = QWidget()
        nav_wrap.setLayout(nav)
        nav_wrap.setFixedWidth(150)
        root.addWidget(nav_wrap)

        # 右侧页面
        right = QVBoxLayout()
        right.setContentsMargins(16, 12, 16, 12)
        right.setSpacing(10)
        self.pages = QStackedWidget()
        self._create_download_page()
        self._create_queue_page()
        self._create_storage_page()
        self._create_subtitle_page()
        self._create_ai_page()
        right.addWidget(self.pages, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("取消")
        cancel_btn.setFlat(True)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_settings)
        btn_row.addWidget(save_btn)
        right.addLayout(btn_row)
        root.addLayout(right, 1)

        self._nav_buttons[0].setChecked(True)

    _PAGE_INDEX = {"download": 0, "queue": 1, "storage": 2, "subtitle": 3, "ai": 4}

    def _show_page(self, key):
        self.pages.setCurrentIndex(self._PAGE_INDEX[key])

    def _hint(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {_HINT};")
        lbl.setFont(SMALL)
        return lbl

    def _form_grid(self, page_lay):
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)
        page_lay.addLayout(grid)
        return grid

    def _create_download_page(self):
        page = QWidget()
        page_lay = QVBoxLayout(page)
        page_lay.setContentsMargins(4, 4, 4, 4)
        page_lay.setSpacing(8)

        title = QLabel("下载设置")
        title.setFont(TITLE_BOLD)
        page_lay.addWidget(title)

        grid = self._form_grid(page_lay)
        v = self.current_values

        # 下载方式
        grid.addWidget(QLabel("下载方式:"), 0, 0)
        method_row = QHBoxLayout()
        method_row.setSpacing(16)
        self._method_group = QButtonGroup(self)
        self.aria2_radio = QRadioButton("Aria2")
        self.direct_radio = QRadioButton("直接下载")
        self._method_group.addButton(self.aria2_radio)
        self._method_group.addButton(self.direct_radio)
        method_row.addWidget(self.aria2_radio)
        method_row.addWidget(self.direct_radio)
        method_row.addStretch(1)
        if v["download_method"] == "direct":
            self.direct_radio.setChecked(True)
        else:
            self.aria2_radio.setChecked(True)
        grid.addLayout(method_row, 0, 1)

        # Aria2 地址
        grid.addWidget(QLabel("Aria2 地址:"), 1, 0)
        self.aria2_edit = QLineEdit(v["aria2_url"])
        grid.addWidget(self.aria2_edit, 1, 1)

        # 下载线程数
        grid.addWidget(QLabel("下载线程数:"), 2, 0)
        threads_row = QHBoxLayout()
        threads_row.setSpacing(8)
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 10)
        self.threads_spin.setValue(int(v["direct_threads"]))
        threads_row.addWidget(self.threads_spin)
        threads_row.addWidget(self._hint("(直接下载并发数)"))
        threads_row.addStretch(1)
        grid.addLayout(threads_row, 2, 1)

        # 下载目录
        grid.addWidget(QLabel("下载目录:"), 3, 0)
        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)
        self.download_dir_edit = QLineEdit(v["download_dir"])
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self._browse_download_dir)
        dir_row.addWidget(self.download_dir_edit)
        dir_row.addWidget(browse_btn)
        grid.addLayout(dir_row, 3, 1)

        # 文件名过滤字符
        grid.addWidget(QLabel("文件名过滤字符:"), 4, 0)
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self.filter_edit = QLineEdit(v["filename_filter_chars"])
        filter_row.addWidget(self.filter_edit)
        filter_row.addWidget(self._hint("(额外过滤的字符，如 【】「」《》…)"))
        filter_row.addStretch(1)
        grid.addLayout(filter_row, 4, 1)

        # 目录名标题最大长度
        grid.addWidget(QLabel("目录名标题最大长度:"), 5, 0)
        title_len_row = QHBoxLayout()
        title_len_row.setSpacing(8)
        self.title_len_spin = QSpinBox()
        self.title_len_spin.setRange(0, 500)
        self.title_len_spin.setValue(int(v["folder_title_max_len"]))
        self.title_len_spin.setSuffix(" 字符")
        title_len_row.addWidget(self.title_len_spin)
        title_len_row.addWidget(self._hint("(下载文件夹名中标题的最大长度，0 = 不限制)"))
        title_len_row.addStretch(1)
        grid.addLayout(title_len_row, 5, 1)

        self.auto_flatten_check = QCheckBox("默认启用自动整理文件夹（下载完成后扁平化嵌套目录）")
        self.auto_flatten_check.setChecked(bool(v["auto_flatten_enabled"]))
        page_lay.addWidget(self.auto_flatten_check)

        self.t2s_check = QCheckBox("启用繁简转换（下载完成后自动将繁体字幕和文件名转为简体）")
        self.t2s_check.setChecked(bool(v["traditional_to_simplified_enabled"]))
        page_lay.addWidget(self.t2s_check)

        # 自动采集（下载页功能）
        self.auto_collect_check = QCheckBox("启用自动采集（后台采集最新作品到「没有下载」页）")
        self.auto_collect_check.setChecked(bool(v["auto_collect_enabled"]))
        page_lay.addWidget(self.auto_collect_check)

        collect_grid = self._form_grid(page_lay)
        collect_grid.addWidget(QLabel("每日采集新作品上限:"), 0, 0)
        limit_row = QHBoxLayout()
        limit_row.setSpacing(8)
        self.daily_limit_spin = QSpinBox()
        self.daily_limit_spin.setRange(0, 100000)
        self.daily_limit_spin.setValue(int(v["daily_new_works_limit"]))
        limit_row.addWidget(self.daily_limit_spin)
        limit_row.addWidget(self._hint("(0 = 不限，达到上限当天暂停采集)"))
        limit_row.addStretch(1)
        collect_grid.addLayout(limit_row, 0, 1)

        collect_grid.addWidget(QLabel("头部追新间隔:"), 1, 0)
        head_row = QHBoxLayout()
        head_row.setSpacing(8)
        self.head_interval_spin = QSpinBox()
        self.head_interval_spin.setRange(10, 3600)
        self.head_interval_spin.setSuffix(" 秒")
        self.head_interval_spin.setValue(int(v["head_poll_interval"]))
        head_row.addWidget(self.head_interval_spin)
        head_row.addWidget(self._hint("(检查第 1 页新作品的时间间隔)"))
        head_row.addStretch(1)
        collect_grid.addLayout(head_row, 1, 1)

        page_lay.addStretch(1)

        self.pages.addWidget(page)

    def _create_queue_page(self):
        page = QWidget()
        page_lay = QVBoxLayout(page)
        page_lay.setContentsMargins(4, 4, 4, 4)
        page_lay.setSpacing(8)

        title = QLabel("队列设置")
        title.setFont(TITLE_BOLD)
        page_lay.addWidget(title)

        desc = QLabel("启用队列模式后，作品将按顺序下载，一个完成后再开始下一个。\n"
                      "适合网络受限或需要避免触发限流的场景。")
        desc.setStyleSheet(f"color: {_HINT};")
        desc.setFont(SMALL)
        page_lay.addWidget(desc)

        v = self.current_values
        grid = self._form_grid(page_lay)

        self.queue_mode_check = QCheckBox("启用队列模式")
        self.queue_mode_check.setChecked(bool(v["queue_mode"]))
        page_lay.addWidget(self.queue_mode_check)

        grid.addWidget(QLabel("最大同时下载:"), 0, 0)
        concurrent_row = QHBoxLayout()
        concurrent_row.setSpacing(8)
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 5)
        self.concurrent_spin.setValue(int(v["max_concurrent"]))
        concurrent_row.addWidget(self.concurrent_spin)
        concurrent_row.addWidget(self._hint("(队列模式下同时下载的作品数)"))
        concurrent_row.addStretch(1)
        grid.addLayout(concurrent_row, 0, 1)
        page_lay.addStretch(1)

        self.pages.addWidget(page)

    def _create_storage_page(self):
        page = QWidget()
        page_lay = QVBoxLayout(page)
        page_lay.setContentsMargins(4, 4, 4, 4)
        page_lay.setSpacing(8)

        title = QLabel("存储管理")
        title.setFont(TITLE_BOLD)
        page_lay.addWidget(title)

        v = self.current_values
        grid = self._form_grid(page_lay)

        grid.addWidget(QLabel("数据库目录:"), 0, 0)
        db_row = QHBoxLayout()
        db_row.setSpacing(8)
        self.db_dir_edit = QLineEdit(v["db_dir"])
        db_browse_btn = QPushButton("浏览")
        db_browse_btn.clicked.connect(self._browse_db_dir)
        db_row.addWidget(self.db_dir_edit)
        db_row.addWidget(db_browse_btn)
        grid.addLayout(db_row, 0, 1)
        grid.addWidget(self._hint("留空使用默认位置 (settings/)"), 1, 1)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #e0e0e0;")
        page_lay.addWidget(sep)

        cache_row = QHBoxLayout()
        cache_row.setSpacing(8)
        self.cache_label = QLabel(f"图片缓存大小: {self._get_cache_size()}")
        clear_btn = QPushButton("清除缓存")
        clear_btn.clicked.connect(self.clear_cache)
        cache_row.addWidget(self.cache_label)
        cache_row.addStretch(1)
        cache_row.addWidget(clear_btn)
        page_lay.addLayout(cache_row)

        page_lay.addWidget(self._hint("清除缓存将删除所有已下载的图片，程序会重新从网络加载。"))
        page_lay.addStretch(1)

        self.pages.addWidget(page)

    def _create_subtitle_page(self):
        page = QWidget()
        page_lay = QVBoxLayout(page)
        page_lay.setContentsMargins(4, 4, 4, 4)
        page_lay.setSpacing(8)

        title = QLabel("字幕管理")
        title.setFont(TITLE_BOLD)
        page_lay.addWidget(title)

        desc = QLabel("启用字幕转换后，下载的 VTT 字幕文件将自动转换为 LRC 格式。\n"
                      "转换后的字幕文件名会移除音频格式后缀（如 .mp3.vtt → .lrc）。")
        desc.setStyleSheet(f"color: {_HINT};")
        desc.setFont(SMALL)
        page_lay.addWidget(desc)

        grid = self._form_grid(page_lay)
        self.subtitle_convert_check = QCheckBox("启用 VTT 字幕自动转换为 LRC")
        self.subtitle_convert_check.setChecked(bool(self.current_values["subtitle_convert_enabled"]))
        page_lay.addWidget(self.subtitle_convert_check)

        grid.addWidget(QLabel("转换说明:"), 1, 0)
        info = QLabel("\u2022 VTT (Web Video Text Tracks) 是一种网页字幕格式\n"
                      "\u2022 LRC (Lyric) 是一种歌词文件格式，支持时间戳\n"
                      "\u2022 转换后字幕文件名会简化，便于管理\n"
                      "\u2022 原始 VTT 文件会在转换后自动删除")
        info.setStyleSheet(f"color: {_HINT};")
        info.setFont(SMALL)
        grid.addWidget(info, 2, 0, 1, 2)
        page_lay.addStretch(1)

        self.pages.addWidget(page)

    def _create_ai_page(self):
        # AI 内容较多，放滚动区域避免超出窗口高度
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        page = QWidget()
        page_lay = QVBoxLayout(page)
        page_lay.setContentsMargins(4, 4, 4, 4)
        page_lay.setSpacing(8)

        title = QLabel("AI 翻译设置")
        title.setFont(TITLE_BOLD)
        page_lay.addWidget(title)

        desc = QLabel("启用 AI 翻译后，可以使用 OpenAI 兼容的 API 翻译作品标题。\n"
                      "支持 DeepSeek、GPT 等模型。")
        desc.setStyleSheet(f"color: {_HINT};")
        desc.setFont(SMALL)
        page_lay.addWidget(desc)

        v = self.current_values
        grid = self._form_grid(page_lay)

        self.ai_enabled_check = QCheckBox("启用 AI 翻译")
        self.ai_enabled_check.setChecked(bool(v["ai_enabled"]))
        page_lay.addWidget(self.ai_enabled_check)

        grid.addWidget(QLabel("API Key:"), 1, 0)
        self.ai_key_edit = QLineEdit(v["ai_key"])
        self.ai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.ai_key_edit, 1, 1)

        grid.addWidget(QLabel("API 地址:"), 2, 0)
        self.ai_base_edit = QLineEdit(v["ai_base"])
        grid.addWidget(self.ai_base_edit, 2, 1)

        grid.addWidget(QLabel("模型名称:"), 3, 0)
        model_row = QHBoxLayout()
        model_row.setSpacing(8)
        self.ai_model_edit = QLineEdit(v["ai_model"])
        model_row.addWidget(self.ai_model_edit)
        model_row.addWidget(self._hint("(如 deepseek-chat, gpt-3.5-turbo)"))
        model_row.addStretch(1)
        grid.addLayout(model_row, 3, 1)

        self.ai_thinking_check = QCheckBox("启用思考模式（DeepSeek 推理模式，翻译更准确但响应更慢）")
        self.ai_thinking_check.setChecked(bool(v["ai_thinking_enabled"]))
        page_lay.addWidget(self.ai_thinking_check)

        self.ai_editable_check = QCheckBox("启用翻译编辑（允许手动修改翻译结果）")
        self.ai_editable_check.setChecked(bool(v["ai_translate_editable"]))
        page_lay.addWidget(self.ai_editable_check)
        page_lay.addStretch(1)

        scroll.setWidget(page)
        self.pages.addWidget(scroll)

    # ---------- 目录浏览 ----------
    def _browse_download_dir(self):
        initial = self.download_dir_edit.text().strip()
        if not os.path.isabs(initial):
            initial = os.path.join(_config._USER_ROOT, initial)
        if not os.path.isdir(initial):
            initial = os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "选择下载目录", initial)
        if path:
            self.download_dir_edit.setText(path)

    def _browse_db_dir(self):
        current = self.db_dir_edit.text().strip()
        initial = current if os.path.isabs(current) and os.path.isdir(current) else os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "选择数据库目录", initial)
        if path:
            self.db_dir_edit.setText(path)

    # ---------- 存储 ----------
    def _get_cache_size(self):
        try:
            # 复用 ImageCacheManager.get_stats（带 TTL 的磁盘大小缓存），避免全目录遍历
            if self.image_cache is not None:
                stats = self.image_cache.get_stats()
                return _fmt_size(int(stats.get("disk_size_mb", 0) * 1024 * 1024))
            cache_dir = _config.CACHE_DIR
            if not os.path.isdir(cache_dir):
                return "0 B"
            total = sum(os.path.getsize(os.path.join(cache_dir, f))
                        for f in os.listdir(cache_dir)
                        if os.path.isfile(os.path.join(cache_dir, f)))
            return _fmt_size(total)
        except Exception:
            return "未知"

    def clear_cache(self):
        ret = QMessageBox.question(
            self, "确认", "确定要清除所有图片缓存吗？\n清除后需要重新下载图片。")
        if ret != QMessageBox.StandardButton.Yes:
            return
        try:
            if self.image_cache is not None:
                self.image_cache.clear_memory_cache()
            cache_dir = _config.CACHE_DIR
            if os.path.isdir(cache_dir):
                for fname in os.listdir(cache_dir):
                    fpath = os.path.join(cache_dir, fname)
                    try:
                        if os.path.isfile(fpath):
                            os.remove(fpath)
                    except Exception:
                        pass
            self.cache_label.setText("图片缓存大小: 0 B")
            QMessageBox.information(self, "提示", "缓存已清除")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"清除缓存失败: {e}")

    # ---------- 保存 ----------
    def save_settings(self):
        new_download_dir = self.download_dir_edit.text().strip()
        if not new_download_dir:
            QMessageBox.critical(self, "错误", "下载目录不能为空")
            return

        new_rpc_url = self.aria2_edit.text().strip()
        new_db_dir = self.db_dir_edit.text().strip()
        new_download_method = "direct" if self.direct_radio.isChecked() else "aria2"
        new_direct_threads = self.threads_spin.value()
        new_queue_mode = self.queue_mode_check.isChecked()
        new_max_concurrent = self.concurrent_spin.value()
        new_ai_enabled = self.ai_enabled_check.isChecked()
        new_ai_key = self.ai_key_edit.text().strip()
        new_ai_base = self.ai_base_edit.text().strip()
        new_ai_model = self.ai_model_edit.text().strip()
        new_ai_thinking = self.ai_thinking_check.isChecked()
        new_ai_editable = self.ai_editable_check.isChecked()
        new_filename_filter = self.filter_edit.text().strip()
        new_title_max_len = self.title_len_spin.value()
        new_subtitle_convert = self.subtitle_convert_check.isChecked()
        new_auto_flatten = self.auto_flatten_check.isChecked()
        new_t2s = self.t2s_check.isChecked()
        new_auto_collect = self.auto_collect_check.isChecked()
        new_daily_limit = self.daily_limit_spin.value()
        new_head_interval = self.head_interval_spin.value()

        old_db_dir = self.cfg.get("db_dir", "")

        config_path = _config.CONFIG_PATH
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg.update({
                "aria2_rpc_url": new_rpc_url,
                "download_dir": new_download_dir,
                "db_dir": new_db_dir,
                "download_method": new_download_method,
                "direct_download_threads": new_direct_threads,
                "queue_mode": new_queue_mode,
                "max_concurrent_downloads": new_max_concurrent,
                "ai_translate_enabled": new_ai_enabled,
                "ai_api_key": new_ai_key,
                "ai_api_base_url": new_ai_base,
                "ai_model": new_ai_model,
                "ai_thinking_enabled": new_ai_thinking,
                "ai_translate_editable": new_ai_editable,
                "filename_filter_chars": new_filename_filter,
                "folder_title_max_len": new_title_max_len,
                "subtitle_convert_enabled": new_subtitle_convert,
                "auto_flatten_enabled": new_auto_flatten,
                "traditional_to_simplified_enabled": new_t2s,
                "auto_collect_enabled": new_auto_collect,
                "daily_new_works_limit": new_daily_limit,
                "head_poll_interval": new_head_interval,
            })
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
                f.flush()
        except PermissionError:
            QMessageBox.critical(self, "错误", "没有权限写入配置文件")
            return
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")
            return

        # 同步模块级常量（进程内立即生效，无需重启）
        _config.ARIA2_RPC_URL = new_rpc_url
        _config.DOWNLOAD_DIR = (new_download_dir if os.path.isabs(new_download_dir)
                                else os.path.join(_config._USER_ROOT, new_download_dir))
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
        _config.FOLDER_TITLE_MAX_LEN = new_title_max_len
        _config.SUBTITLE_CONVERT_ENABLED = new_subtitle_convert
        _config.AUTO_FLATTEN_ENABLED = new_auto_flatten
        _config.TRADITIONAL_TO_SIMPLIFIED_ENABLED = new_t2s
        _config.AUTO_COLLECT_ENABLED = new_auto_collect
        _config.DAILY_NEW_WORKS_LIMIT = new_daily_limit
        _config.HEAD_POLL_INTERVAL = new_head_interval

        from src.download.manager import DownloadManager
        DownloadManager().set_queue_mode(new_queue_mode, new_max_concurrent)

        # 通知采集线程应用新设置（跨线程 queued 调用，避免 timer 跨线程 start）
        parent = self.parent()
        if parent is not None and getattr(parent, "_collector", None) is not None:
            from PyQt6.QtCore import QMetaObject, Q_ARG, Qt as _Qt
            collector = parent._collector
            QMetaObject.invokeMethod(collector, "set_enabled",
                                     _Qt.ConnectionType.QueuedConnection,
                                     Q_ARG(bool, new_auto_collect))
            QMetaObject.invokeMethod(collector, "set_head_interval",
                                     _Qt.ConnectionType.QueuedConnection,
                                     Q_ARG(int, new_head_interval))

        translator = get_translator()
        if new_ai_enabled and new_ai_key:
            translator.update_config(new_ai_key, new_ai_base, new_ai_model, new_ai_thinking)

        # 数据库目录变更 → 迁移 works.db / download_history.db
        if new_db_dir != old_db_dir:
            def _resolve(d):
                if not d:
                    return os.path.join(_config._USER_ROOT, "settings")
                return d if os.path.isabs(d) else os.path.join(_config._USER_ROOT, d)

            resolved_new, resolved_old = _resolve(new_db_dir), _resolve(old_db_dir)
            if os.path.normpath(resolved_new) != os.path.normpath(resolved_old):
                try:
                    os.makedirs(resolved_new, exist_ok=True)
                    for db_name in ("works.db", "download_history.db"):
                        src = os.path.join(resolved_old, db_name)
                        dst = os.path.join(resolved_new, db_name)
                        if os.path.isfile(src) and not os.path.isfile(dst):
                            shutil.copy2(src, dst)
                except Exception:
                    logger.exception("迁移数据库目录失败")

        _config.DB_DIR = (new_db_dir if os.path.isabs(new_db_dir) and new_db_dir
                          else os.path.join(_config._USER_ROOT, new_db_dir) if new_db_dir
                          else os.path.join(_config._USER_ROOT, "settings"))
        _config.DB_PATH = os.path.join(_config.DB_DIR, "works.db")
        _config.DOWNLOAD_HISTORY_DB_PATH = os.path.join(_config.DB_DIR, "download_history.db")

        self.accept()
        if new_db_dir != old_db_dir:
            QMessageBox.information(self, "提示", "数据库目录已更改，请重启应用后生效")
        else:
            QMessageBox.information(self, "提示", "设置已保存")
