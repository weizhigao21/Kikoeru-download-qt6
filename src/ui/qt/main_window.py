# -*- coding: utf-8 -*-
"""主窗口（阶段 2）：顶栏 + 虚拟化列表 + 详情面板 + 底栏。

接入 DataWorker（分页/搜索/下载列表/详情懒加载）与 ThumbnailWorker（缩略图/大图），
全部异步结果通过 generation 校验丢弃过期批次。
功能对齐 tkinter 版：搜索（ID/关键词/厂商）、过滤（隐藏已下载）、
下载 tab 排序、详情操作（隐藏/刷新/删除记录）、搜索历史回退。
"""
import logging

from PyQt6.QtCore import QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QImage, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (QInputDialog, QMainWindow, QMessageBox, QWidget,
                             QVBoxLayout, QHBoxLayout)

from src import (VERSION, DB_PATH, CACHE_DIR, DOWNLOAD_HISTORY_DB_PATH,
                 ICON_PATH, MEMORY_CACHE_SIZE)
from src import config as _config
from src.api_client import get_api_client
from src.database import (DatabaseManager, DownloadHistoryManager,
                          PendingTaskManager, WorkTracksManager)
from src.database.cache import ImageCacheManager
from src.download.manager import DownloadManager
from src.download.models import TaskStatus
from src.services.translator import get_translator
from src.utils import normalize_rj_id
from src.ui.qt.top_bar import TopBarWidget
from src.ui.qt.bottom_bar import BottomBarWidget
from src.ui.qt.works_list import WorksListView
from src.ui.qt.detail_panel import DetailPanel
from src.ui.qt.workers import DataWorker, ThumbnailWorker

logger = logging.getLogger("qt_main_window")

TABS = ["recommend", "latest", "download"]
PAGE_SIZE = 20

# show_downloaded 模式（与 tkinter 版 config 常量一致）
SHOW_ALL = 1
HIDE_DOWNLOADED = 2
DOWNLOADED_TAB = 3


class MainWindow(QMainWindow):
    # 下载任务变化通知（observer 由轮询线程触发 → 信号 queued 回主线程）
    _downloads_changed = pyqtSignal()
    _translate_result = pyqtSignal(str, object, str)  # (原文标题, work, 翻译结果/None)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"音声浏览下载 {VERSION}")
        self.setWindowIcon(QIcon(ICON_PATH))  # settings/ui.ico（标题栏 + 任务栏 + 对话框）
        self.resize(1250, 800)
        # 详情面板固定 400px，最小窗口保证列表不被挤没
        self.setMinimumSize(900, 600)

        # 业务对象（与 tkinter 版共用同一套业务层）
        self.db = DatabaseManager(DB_PATH)
        self.download_history = DownloadHistoryManager(DOWNLOAD_HISTORY_DB_PATH)
        self.api = get_api_client()
        self.image_cache = ImageCacheManager(CACHE_DIR, MEMORY_CACHE_SIZE)
        self.pending_task_db = PendingTaskManager(DOWNLOAD_HISTORY_DB_PATH)
        self.tracks_db = WorkTracksManager(DOWNLOAD_HISTORY_DB_PATH)

        # 下载管理（单例，配置依赖 + 观察者 → 主线程信号）
        self.dl_manager = DownloadManager()
        self.dl_manager.set_download_history(self.download_history)
        self.dl_manager.set_pending_db(self.pending_task_db)
        self.dl_manager.set_tracks_cache(self.tracks_db)
        self.dl_manager.set_queue_mode(_config.QUEUE_MODE, _config.MAX_CONCURRENT_DOWNLOADS)
        self._downloads_changed.connect(self._on_downloads_changed)
        self.dl_manager.add_observer(self._downloads_changed.emit)
        self._last_done_ids = None

        # 翻译服务初始化（对齐 tkinter 版：把 config 同步给 translator 单例，
        # 否则 AI_API_KEY 等配置未生效，右键翻译会报"未配置 API Key"）。
        # 延迟到 _deferred_startup 空闲期执行（配置同步不影响窗口显示）。

        # 对话框引用（防重入/防 GC）
        self._dl_dialog = None
        self._dl_mgr_dialog = None
        self._settings_dialog = None

        # 导航状态
        self.current_tab = TABS[0]
        self.current_page = 1
        self.max_page = 1
        self.works = []
        self._nav_generation = 0

        # 下载相关状态
        self.downloaded_ids_cache = set()
        self._all_downloaded_works = []
        # 下载 tab 本地搜索结果缓存：None=未搜索（显示完整列表），[]=搜索无结果
        self._downloaded_search_result = None
        self._downloaded_page = 1
        self.show_downloaded = SHOW_ALL
        self._hide_downloaded = False
        self.sort_map = {
            "下载时间最新": "download_time_desc",
            "下载时间最旧": "download_time_asc",
            "标题 A-Z": "title_asc",
            "标题 Z-A": "title_desc",
            "ID 从小到大": "id_asc",
            "ID 从大到小": "id_desc",
        }

        # 搜索状态
        self.keyword_query = ""
        self.circle_query = ""
        self.current_tags = []
        self.search_history = []

        self._build_ui()
        self._setup_shortcuts()
        self._start_workers()
        # 非关键初始化延迟到事件循环空闲期（QTimer.singleShot(0)）：
        # 先让主窗口渲染出来、关闭启动画面，再执行 DB 查询/任务恢复等同步操作。
        QTimer.singleShot(0, self._deferred_startup)

    def _deferred_startup(self):
        """窗口显示后的延迟初始化：已下载集合 / 任务恢复 / 翻译配置 / 首页数据。"""
        self._load_downloaded_ids()
        self._restore_pending_tasks()
        self._init_translator()
        self._load_data(1)

    # ---------- UI ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.top_bar = TopBarWidget()
        layout.addWidget(self.top_bar)

        content = QHBoxLayout()
        content.setSpacing(10)
        self.list_view = WorksListView()
        self.detail_panel = DetailPanel(self.db)
        # 详情面板固定宽度（与 tkinter 版 400px 一致），列表占其余全部空间
        self.detail_panel.setFixedWidth(400)
        content.addWidget(self.list_view, 1)
        content.addWidget(self.detail_panel)
        layout.addLayout(content, 1)

        self.bottom_bar = BottomBarWidget()
        layout.addWidget(self.bottom_bar)

        # 顶栏事件
        self.top_bar.tab_combo.currentIndexChanged.connect(self._on_tab_changed)
        self.top_bar.refresh_btn.clicked.connect(self._refresh_data)
        self.top_bar.back_btn.clicked.connect(self._go_back)
        self.top_bar.search_btn.clicked.connect(self._do_search)
        self.top_bar.search_entry.returnPressed.connect(self._do_search)
        self.top_bar.tagRemoved.connect(self._on_tag_removed)
        self.top_bar.circleRemoved.connect(self._on_circle_removed)
        self.top_bar.hide_dl_btn.clicked.connect(self._toggle_hide_downloaded)
        self.top_bar.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        # 底栏事件
        self.bottom_bar.prev_btn.clicked.connect(lambda: self._navigate_search(self.current_page - 1))
        self.bottom_bar.next_btn.clicked.connect(lambda: self._navigate_search(self.current_page + 1))
        self.bottom_bar.go_btn.clicked.connect(self._on_go_page)
        self.page_entry.returnPressed.connect(self._on_go_page)
        self.bottom_bar.dl_mgr_btn.clicked.connect(self._open_download_manager_dialog)
        self.bottom_bar.settings_btn.clicked.connect(self._open_settings_dialog)
        # 列表事件
        self.list_view.clicked.connect(self._on_work_clicked)
        self.list_view.workDoubleClicked.connect(self._on_work_double_clicked)
        self.list_view.editionClicked.connect(self._on_edition_clicked)
        self.list_view.tagClicked.connect(self.search_by_tag)
        self.list_view.translationAction.connect(self._on_translation_action)
        self._translate_result.connect(self._on_translate_result)
        # 详情面板事件
        self.detail_panel.circleClicked.connect(self.search_by_circle)
        self.detail_panel.tagClicked.connect(self.search_by_tag)
        self.detail_panel.hideRequested.connect(self._on_hide_requested)
        self.detail_panel.refreshRequested.connect(self._on_refresh_requested)
        self.detail_panel.deleteRecordRequested.connect(self._on_delete_record_requested)

    # ---------- 快捷键 ----------
    def _setup_shortcuts(self):
        """全局快捷键：Ctrl+F 聚焦搜索、F5 刷新、Enter/双击打开下载窗口。"""
        self._shortcut_find = QShortcut(QKeySequence.StandardKey.Find, self)
        self._shortcut_find.activated.connect(self._focus_search)
        self._shortcut_refresh = QShortcut(QKeySequence("F5"), self)
        self._shortcut_refresh.activated.connect(self._refresh_data)
        # 列表键盘导航（方向键移动选中、Enter 激活）由 QListView 原生支持，
        # 激活（Enter/双击）走 activated 信号 → 打开下载窗口

    def _focus_search(self):
        self.top_bar.search_entry.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.top_bar.search_entry.selectAll()

    # ---------- 线程 ----------
    def _start_workers(self):
        self._data_thread = QThread(self)
        self._data_worker = DataWorker(self.db, self.api, self.download_history)
        self._data_worker.moveToThread(self._data_thread)
        self._data_worker.request.connect(self._data_worker.fetch_works)
        self._data_worker.search.connect(self._data_worker.do_search)
        self._data_worker.downloads.connect(self._data_worker.load_downloads)
        self._data_worker.work_detail.connect(self._data_worker.fetch_detail)
        self._data_worker.loaded.connect(self._on_data_loaded)
        self._data_worker.search_loaded.connect(self._on_search_loaded)
        self._data_worker.downloads_loaded.connect(self._on_downloads_loaded)
        self._data_worker.work_detail_loaded.connect(self._on_work_detail_loaded)
        self._data_worker.failed.connect(self._on_data_failed)
        self._data_thread.start()

        self._thumb_thread = QThread(self)
        self._thumb_worker = ThumbnailWorker(self.image_cache)
        self._thumb_worker.moveToThread(self._thumb_thread)
        self._thumb_worker.request.connect(self._thumb_worker.load)
        self._thumb_worker.detail_request.connect(self._thumb_worker.load_detail)
        self._thumb_worker.thumb_ready.connect(self._on_thumb_ready)
        self._thumb_worker.detail_ready.connect(self._on_detail_ready)
        self._thumb_thread.start()

    # ---------- 已下载集合 ----------
    def _load_downloaded_ids(self):
        try:
            self.downloaded_ids_cache = set()
            for rid in self.download_history.get_all_downloaded_rj_ids():
                normalized = normalize_rj_id(rid)
                if normalized:
                    self.downloaded_ids_cache.add(normalized)
            self._update_downloaded_count()
        except Exception:
            self.downloaded_ids_cache = set()
        # 同步到列表 delegate（版本 ✓ 标记）
        self.list_view.delegate().set_downloaded_ids(self.downloaded_ids_cache)
        self.list_view.viewport().update()

    def _update_downloaded_count(self):
        count = len(self.downloaded_ids_cache)
        self.top_bar.downloaded_count_label.setText(f"已下载 {count} 个作品" if count else "")

    def _is_downloaded(self, work):
        return normalize_rj_id(work.get("source_id", "")) in self.downloaded_ids_cache

    def _apply_filter(self, works):
        if self.show_downloaded == HIDE_DOWNLOADED:
            return [w for w in works
                    if normalize_rj_id(w.get("source_id", "")) not in self.downloaded_ids_cache]
        return works

    # ---------- 数据加载 ----------
    def _load_data(self, page=None):
        if page is None:
            page = self.current_page
        page = max(1, min(page, self.max_page))
        self.current_page = page
        self.page_entry.setText(str(page))
        self._nav_generation += 1
        gen = self._nav_generation
        self._set_status("加载中...")
        self._data_worker.request.emit(page, self.current_tab, gen)

    def _refresh_data(self):
        """刷新：清空搜索条件后重新加载当前 tab。"""
        self._clear_search_state()
        self.search_history.clear()
        if self.current_tab == "download":
            self._load_downloads()
        else:
            self._load_data(1)

    def _show_works(self, works, status_text):
        """公共展示：过滤 → model → 详情 → 缩略图 → 按钮状态。"""
        works = self._apply_filter(works)
        self.works = works
        self.model.set_works(works)
        self._sync_translations()
        self._set_status(status_text)
        self._request_thumbs()
        self._show_first_detail()
        self._update_nav_buttons()

    def _sync_translations(self):
        """批量读取当前列表的翻译缓存注入 model（对齐 tkinter 卡片翻译缓存显示）。"""
        try:
            ids = [str(w.get("id", "")) for w in self.works if w.get("id")]
            trans = self.db.get_translated_titles(ids) if ids else {}
        except Exception:
            logger.exception("读取翻译缓存失败")
            trans = {}
        self.model.set_translations(trans)

    def _request_thumbs(self):
        urls = self.model.thumbnail_urls()
        if urls:
            self._thumb_worker.request.emit(urls, self._nav_generation)

    def _show_first_detail(self):
        if self.works:
            self._show_detail(self.works[0])
        else:
            self.detail_panel.show_work(None, False)

    def _update_nav_buttons(self):
        if self.current_tab == "download":
            base = self._downloaded_search_result if self._downloaded_search_result is not None else self._all_downloaded_works
            total_pages = max(1, (len(base) + PAGE_SIZE - 1) // PAGE_SIZE) if base else 1
            self.bottom_bar.prev_btn.setEnabled(self._downloaded_page > 1)
            self.bottom_bar.next_btn.setEnabled(self._downloaded_page < total_pages)
        else:
            self.bottom_bar.prev_btn.setEnabled(self.current_page > 1 and bool(self.works))
            self.bottom_bar.next_btn.setEnabled(self.current_page < self.max_page and bool(self.works))

    # ---------- 数据回调 ----------
    def _on_data_loaded(self, gen, works, max_page):
        if gen != self._nav_generation:
            return
        self.max_page = max(max_page or 1, 1)
        self._show_works(works, f"第 {self.current_page}/{self.max_page} 页 · {len(works)} 条")

    def _on_search_loaded(self, gen, works, max_page, query_type, query):
        if gen != self._nav_generation:
            return
        self.max_page = max(max_page or 1, 1)
        # 注意：不能在这里重置 current_page/page_entry——`_search()` 已按请求页设置，
        # 重置会导致搜索翻页结果一返回就被打回第 1 页（下一页无法使用）
        desc = {"id": "RJ ID", "keyword": "关键词", "circle": "厂商", "tag": "标签", "combo": "厂商+标签"}.get(query_type, "搜索")
        if query_type == "combo":
            tags, circle = query
            query_text = f"{circle} + {' + '.join(tags)}"
        elif isinstance(query, (list, tuple)):
            query_text = " + ".join(query)
        else:
            query_text = query
        self._show_works(works, f"{desc}「{query_text}」第 {self.current_page}/{self.max_page} 页 · {len(works)} 条")

    def _on_downloads_loaded(self, gen, works, sort_key):
        if gen != self._nav_generation:
            return
        self._all_downloaded_works = works
        self._downloaded_search_result = None
        self._downloaded_page = 1
        self.page_entry.setText("1")
        # 从其他 tab 带过来的保留条件：加载完成后自动本地过滤
        if self.keyword_query or self.circle_query or self.current_tags:
            self._search_in_downloaded_works()
        else:
            self._show_downloaded_page()

    def _show_downloaded_page(self):
        base = self._downloaded_search_result if self._downloaded_search_result is not None else self._all_downloaded_works
        total = len(base)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self.max_page = total_pages
        start = (self._downloaded_page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        if self._downloaded_search_result is not None:
            status = f"已下载作品中搜索{self._downloaded_search_desc()}: {total} 个，第 {self._downloaded_page}/{total_pages} 页"
        else:
            status = f"已下载 {total} 个作品，第 {self._downloaded_page}/{total_pages} 页"
        self._show_works(base[start:end], status)
        self.page_entry.setText(str(self._downloaded_page))

    def _downloaded_search_desc(self):
        parts = []
        if self.current_tags:
            parts.append("标签「" + " + ".join(self.current_tags) + "」")
        if self.circle_query:
            parts.append("厂商「" + self.circle_query + "」")
        if self.keyword_query:
            parts.append("关键词「" + self.keyword_query + "」")
        return " + ".join(parts)

    def _on_data_failed(self, gen, error):
        if gen != self._nav_generation:
            return
        self._set_status(f"加载失败: {error[:80]}")

    def _on_thumb_ready(self, gen, url, rgb, w, h):
        if gen != self._nav_generation:
            return
        try:
            # QImage(bytes, ...) 共享外部缓冲；PyQt6 无 detach()，
            # copy() 为深拷贝，彻底摆脱 bytes 生命周期约束
            rgb_bytes = bytes(rgb)
            qimg = QImage(rgb_bytes, w, h, w * 3, QImage.Format.Format_RGB888)
            qimg = qimg.copy()
            pix = QPixmap.fromImage(qimg)
        except Exception:
            return
        self.delegate.set_thumb(url, pix)
        self.list_view.viewport().update()

    def _on_detail_ready(self, gen, rgb, w, h):
        if gen != self._nav_generation:
            return
        try:
            rgb_bytes = bytes(rgb)
            qimg = QImage(rgb_bytes, w, h, w * 3, QImage.Format.Format_RGB888)
            qimg = qimg.copy()
            pix = QPixmap.fromImage(qimg)
        except Exception:
            return
        self.detail_panel.set_cover(pix)

    def _on_work_detail_loaded(self, gen, data):
        if gen != self._nav_generation:
            return
        was_refreshing = getattr(self, "_detail_refreshing", False)
        self._detail_refreshing = False
        self.detail_panel.set_refreshing(False)
        if not data:
            return
        work = self.detail_panel.current_work()
        if work is None:
            return
        if was_refreshing:
            self._apply_full_refresh(work, data)
        else:
            self._merge_lazy_detail(work, data)

    # ---------- 详情 ----------
    def _show_detail(self, work):
        is_downloaded = self._is_downloaded(work)
        self.detail_panel.show_work(work, is_downloaded)

        url = work.get("mainCoverUrl") or work.get("thumbnailCoverUrl") or ""
        if url:
            self.detail_panel.set_cover_loading()
            self._thumb_worker.detail_request.emit(url, self._nav_generation)
        else:
            self.detail_panel.set_cover_none()

        # 懒加载缺失的声优/厂商
        circle = work.get("circle", {})
        has_circle = isinstance(circle, dict) and circle.get("name")
        has_vas = bool(work.get("vas"))
        if (not has_circle or not has_vas) and work.get("source_id"):
            self._data_worker.work_detail.emit(work["source_id"], self._nav_generation)

    def _merge_lazy_detail(self, work, data):
        """懒加载：仅补缺失的 vas / circle / 大图 URL。"""
        vas = data.get("vas", [])
        circle = data.get("circle", {})
        main_cover = data.get("mainCoverUrl", "")
        changed = False
        if vas and not work.get("vas"):
            work["vas"] = vas
            changed = True
        if isinstance(circle, dict) and circle.get("name") and not (work.get("circle") or {}).get("name"):
            work["circle"] = circle
            changed = True
        if main_cover and main_cover != work.get("mainCoverUrl"):
            work["mainCoverUrl"] = main_cover
            changed = True
        if changed:
            if self.current_tab == "recommend":
                self.db.update_works_cache(work, self.current_page)
            # 只刷新详情面板，避免重建 model 导致滚动位置重置
            self.detail_panel.show_work(work, self._is_downloaded(work))

    def _apply_full_refresh(self, work, data):
        """刷新信息：全量更新 work 并写回缓存。"""
        work.update({
            "title": data.get("title", work.get("title", "")),
            "thumbnailCoverUrl": data.get("thumbnailCoverUrl", ""),
            "mainCoverUrl": data.get("mainCoverUrl", ""),
            "tags": data.get("tags", []),
            "vas": data.get("vas", []),
            "circle": data.get("circle", {}),
            "other_language_editions_in_db": data.get("other_language_editions_in_db", []),
        })
        if self.current_tab == "recommend":
            self.db.update_works_cache(work, self.current_page)
        normalized = normalize_rj_id(work.get("source_id", ""))
        if normalized in self.downloaded_ids_cache:
            tag_list = [t["i18n"]["zh-cn"]["name"] for t in data.get("tags", [])
                        if t.get("i18n", {}).get("zh-cn")]
            self.download_history.update_work_detail(
                f"RJ{normalized}",
                thumbnail_url=data.get("thumbnailCoverUrl") or None,
                main_cover_url=data.get("mainCoverUrl") or None,
                tags=tag_list or None,
                vas=data.get("vas", []) or None,
                circle_data=data.get("circle", {}) or None,
                other_editions=data.get("other_language_editions_in_db", []) or None,
            )
        self.model.set_works(self.works)
        self._sync_translations()
        self._set_status("✓ 作品信息已刷新")
        self._show_detail(work)

    # ---------- 搜索 ----------
    def _clear_search_state(self):
        self.keyword_query = ""
        self.circle_query = ""
        self.current_tags = []
        self.top_bar.search_entry.clear()
        self.top_bar.clear_tag_chips()
        self.top_bar.clear_circle_chip()

    def _search_current_conditions(self, page):
        """按当前条件分发搜索：下载 tab 走本地数据库过滤；
        其余 tab：厂商+标签组合 → combo；仅厂商 → circle；仅标签 → tag。"""
        if self.current_tab == "download":
            # 下载 tab 只做本地数据库过滤，不调 API（切到最新/推荐才走 API 搜索）
            self._search_in_downloaded_works()
            return
        if self.circle_query and self.current_tags:
            self._search("combo", (list(self.current_tags), self.circle_query), page)
        elif self.circle_query:
            self._search("circle", self.circle_query, page)
        elif self.current_tags:
            self._search("tag", list(self.current_tags), page)
        else:
            self._restore_default_list(page)

    def _search_in_downloaded_works(self):
        """下载 tab 的本地数据库搜索（对齐 tkinter filter_mixin._search_in_downloaded_works）。

        在已加载的下载作品（_all_downloaded_works）上按 标签/厂商/关键词 组合过滤，
        不发起任何 API 请求。
        """
        filtered = []
        for work in self._all_downloaded_works or []:
            match = True
            title = work.get("title", "").lower()
            source_id = work.get("source_id", "")
            if self.current_tags:
                work_tags = []
                for tag in work.get("tags", []):
                    if isinstance(tag, dict) and tag.get("i18n", {}).get("zh-cn", {}).get("name"):
                        work_tags.append(tag["i18n"]["zh-cn"]["name"].lower())
                    elif isinstance(tag, str):
                        work_tags.append(tag.lower())
                for st in self.current_tags:
                    if st.lower() not in work_tags:
                        match = False
                        break
            if match and self.keyword_query:
                if self.keyword_query.lower() not in title and self.keyword_query.lower() not in source_id.lower():
                    match = False
            if match and self.circle_query:
                circle = work.get("circle", {})
                circle_name = circle.get("name", "").lower() if isinstance(circle, dict) else ""
                if self.circle_query.lower() not in circle_name:
                    match = False
            if match:
                filtered.append(work)
        self._downloaded_search_result = filtered
        self._downloaded_page = 1
        self.page_entry.setText("1")
        self._show_downloaded_page()

    def _restore_default_list(self, page=1):
        """无搜索条件时回到当前 tab 的默认列表（用户从哪个页面进来就回哪个页面）。"""
        if self.current_tab == "download":
            self._downloaded_search_result = None
            self._show_downloaded_page()
        else:
            self._load_data(page)

    def _do_search(self):
        text = self.top_bar.search_entry.text().strip()
        if not text:
            QMessageBox.information(self, "提示", "请输入搜索内容（RJ ID 或关键词）")
            return
        self.current_tags = []
        self.circle_query = ""
        self.top_bar.clear_tag_chips()
        self.top_bar.clear_circle_chip()
        numeric = text.replace("RJ", "").replace("rg", "").replace("RG", "")
        if numeric.isdigit():
            self.keyword_query = ""
            self._push_search_history({"type": "id", "query": text})
            self._search("id", text, 1)
        else:
            self.keyword_query = text
            self._push_search_history({"type": "keyword", "query": text})
            if self.current_tab == "download":
                # 下载 tab：本地数据库过滤；切到最新/推荐才走 API
                self._search_in_downloaded_works()
            else:
                self._search("keyword", text, 1)

    def _search(self, query_type, query, page):
        self.current_page = page
        self.page_entry.setText(str(page))
        self._nav_generation += 1
        gen = self._nav_generation
        self._set_status("正在搜索...")
        self._data_worker.search.emit(query_type, query, page, gen)

    def search_by_circle(self, circle_name):
        """按厂商搜索（详情面板厂商名点击触发，对齐 tkinter）。

        厂商 chip 与标签 chips 可共存：已选的标签不清理，组合过滤。
        """
        if not circle_name:
            return
        self.keyword_query = ""
        if not self.current_tags:
            self._push_search_history({"type": "circle", "query": circle_name})
        self.circle_query = circle_name
        self.top_bar.set_circle_chip(circle_name)
        self._search_current_conditions(1)

    def search_by_tag(self, tag):
        """按标签搜索（列表卡片 / 详情面板标签点击触发，对齐 tkinter）。

        支持多标签累积：重复点击不同标签追加到 current_tags 一起搜索；
        顶栏搜索框隐藏、显示标签 chips（每个带 ✕ 可移除），可与厂商 chip 共存。
        """
        if not tag:
            return
        self.keyword_query = ""
        if tag not in self.current_tags:
            self.current_tags.append(tag)
            self._push_search_history({"type": "tag", "query": list(self.current_tags)})
        self.top_bar.set_tag_chips(self.current_tags)
        self._search_current_conditions(1)

    def _on_circle_removed(self):
        """厂商 chip 的「✕」被点击：移除厂商条件；
        仍有标签则继续按标签搜索，否则回到进入搜索前的默认列表。"""
        self.circle_query = ""
        self.top_bar.clear_circle_chip()
        self._search_current_conditions(1)

    def _on_tag_removed(self, tag):
        """标签 chip 的「✕」被点击：移除该标签；
        仍有标签/厂商则继续搜索，否则回到默认列表。"""
        if tag in self.current_tags:
            self.current_tags.remove(tag)
        # 始终刷新标签 chips：空列表也会清掉该标签的 chip（避免残留）
        self.top_bar.set_tag_chips(self.current_tags)
        if self.current_tags or self.circle_query:
            self._search_current_conditions(1)
        else:
            self._clear_search_state()
            self._restore_default_list(1)

    def _on_edition_clicked(self, sid):
        """点击列表卡片中的"其他语言版本"标签 → 按版本 RJ ID 搜索（对齐 tkinter）。"""
        if not sid:
            return
        self.keyword_query = ""
        self.current_tags = []
        self.circle_query = ""
        self.top_bar.clear_tag_chips()
        self.top_bar.clear_circle_chip()
        self._set_status(f"正在搜索其他版本: {sid}...")
        self._push_search_history({"type": "id", "query": sid})
        self._search("id", sid, 1)

    def _navigate_search(self, page):
        """翻页时按当前搜索条件分发（下载 tab 走本地分页）。"""
        if self.current_tab == "download":
            base = self._downloaded_search_result if self._downloaded_search_result is not None else self._all_downloaded_works
            total_pages = max(1, (len(base) + PAGE_SIZE - 1) // PAGE_SIZE) if base else 1
            if 1 <= page <= total_pages:
                self._downloaded_page = page
                self._show_downloaded_page()
            return
        if self.keyword_query:
            self._search("keyword", self.keyword_query, page)
        elif self.circle_query or self.current_tags:
            self._search_current_conditions(page)
        else:
            self._load_data(page)

    # ---------- 搜索历史回退 ----------
    def _push_search_history(self, entry):
        self.search_history.append(entry)
        self.top_bar.back_btn.setEnabled(True)

    def _go_back(self):
        if not self.search_history:
            self._clear_search_state()
            if self.current_tab != "recommend":
                self.top_bar.tab_combo.setCurrentIndex(0)
            else:
                self._load_data(1)
            return
        self.search_history.pop()
        if not self.search_history:
            self.top_bar.back_btn.setEnabled(False)
            self._clear_search_state()
            if self.current_tab != "recommend":
                self.top_bar.tab_combo.setCurrentIndex(0)
            else:
                self._load_data(1)
            return
        prev = self.search_history[-1]
        t = prev.get("type")
        # 回退到历史搜索点：先清空当前所有搜索条件与 chips，再恢复目标状态
        self.current_tags = []
        self.circle_query = ""
        self.keyword_query = ""
        self.top_bar.clear_tag_chips()
        self.top_bar.clear_circle_chip()
        if t == "keyword":
            self.keyword_query = prev.get("query", "")
            self.top_bar.search_entry.setText(self.keyword_query)
            if self.current_tab == "download":
                self._search_in_downloaded_works()
            else:
                self._search("keyword", self.keyword_query, 1)
        elif t == "circle":
            self.circle_query = prev.get("query", "")
            self.top_bar.set_circle_chip(self.circle_query)
            self._search_current_conditions(1)
        elif t == "tag":
            self.current_tags = list(prev.get("query", []))
            self.top_bar.set_tag_chips(self.current_tags)
            self._search_current_conditions(1)
        elif t == "id":
            self._search("id", prev.get("query", ""), 1)

    # ---------- Tab / 过滤 / 排序 ----------
    def _on_tab_changed(self, idx):
        new_tab = TABS[idx]
        if new_tab == self.current_tab:
            return
        self.current_tab = new_tab
        self.current_page = 1
        self.max_page = 1
        # 保留搜索条件（关键词/厂商/标签与 chips）：切 tab 后用同一条件在新 tab 继续搜索
        self.search_history.clear()
        self.top_bar.back_btn.setEnabled(False)
        self._nav_generation += 1
        self._downloaded_search_result = None
        if new_tab == "download":
            self.show_downloaded = DOWNLOADED_TAB
            self.top_bar.sort_container.setVisible(True)
            self.top_bar.hide_dl_btn.setVisible(False)
            # 无条件加载完整列表；有保留条件则加载后由 _on_downloads_loaded 自动本地过滤
            self._load_downloads()
        else:
            self.top_bar.sort_container.setVisible(False)
            self.top_bar.hide_dl_btn.setVisible(True)
            self.show_downloaded = HIDE_DOWNLOADED if self._hide_downloaded else SHOW_ALL
            self.top_bar.hide_dl_btn.setText("隐藏下载" if self._hide_downloaded else "显示全部")
            # 有保留条件 → 按条件走 API 搜索；否则加载默认数据
            if self.keyword_query:
                self._search("keyword", self.keyword_query, 1)
            elif self.circle_query or self.current_tags:
                self._search_current_conditions(1)
            else:
                self._load_data(1)

    def _load_downloads(self):
        self._nav_generation += 1
        gen = self._nav_generation
        self._downloaded_search_result = None
        sort_key = self.sort_map.get(self.top_bar.sort_combo.currentText(), "download_time_desc")
        self._set_status("正在加载已下载作品信息...")
        self._data_worker.downloads.emit(sort_key, gen)

    def _toggle_hide_downloaded(self):
        if self.current_tab == "download":
            return
        self._hide_downloaded = not self._hide_downloaded
        if self._hide_downloaded:
            self.show_downloaded = HIDE_DOWNLOADED
            self.top_bar.hide_dl_btn.setText("隐藏下载")
        else:
            self.show_downloaded = SHOW_ALL
            self.top_bar.hide_dl_btn.setText("显示全部")
        self.current_page = 1
        self.page_entry.setText("1")
        self._navigate_search(1)

    def _on_sort_changed(self):
        if self.current_tab == "download" and self._all_downloaded_works:
            sort_key = self.sort_map.get(self.top_bar.sort_combo.currentText(), "download_time_desc")
            self._all_downloaded_works = self._sort_works(self._all_downloaded_works, sort_key)
            # 本地搜索状态：搜索结果同样按当前排序刷新
            if self._downloaded_search_result is not None:
                self._downloaded_search_result = self._sort_works(self._downloaded_search_result, sort_key)
            self._downloaded_page = 1
            self.page_entry.setText("1")
            self._show_downloaded_page()

    @staticmethod
    def _sort_works(works, sort_key):
        if sort_key == "download_time_desc":
            return list(works)
        if sort_key == "download_time_asc":
            return list(reversed(works))
        if sort_key == "title_asc":
            return sorted(works, key=lambda w: w.get("title", "").lower())
        if sort_key == "title_desc":
            return sorted(works, key=lambda w: w.get("title", "").lower(), reverse=True)
        if sort_key == "id_asc":
            return sorted(works, key=lambda w: w.get("source_id", ""))
        if sort_key == "id_desc":
            return sorted(works, key=lambda w: w.get("source_id", ""), reverse=True)
        return list(works)

    # ---------- 详情操作 ----------
    def _on_hide_requested(self, work):
        if work is None:
            return
        work_id = str(work.get("id", ""))
        self.db.hide_work(work_id)
        self._set_status(f"✓ 已隐藏: {work.get('title', '')[:20]}...")
        if work in self.works:
            self.works.remove(work)
        self.model.set_works(self.works)
        self._sync_translations()
        if self.works:
            self._show_detail(self.works[0])
        else:
            self.detail_panel.show_work(None, False)
            self._set_status("当前页没有数据")
        self._request_thumbs()

    def _on_refresh_requested(self, work):
        source_id = work.get("source_id", "") if work else ""
        if not source_id:
            return
        self.detail_panel.set_refreshing(True)
        self._detail_refreshing = True
        self._nav_generation += 1
        gen = self._nav_generation
        self._data_worker.work_detail.emit(source_id, gen)

    def _on_delete_record_requested(self, work):
        if work is None:
            return
        source_id = work.get("source_id", "")
        if not source_id:
            return
        title = work.get("title", "未知作品")
        ret = QMessageBox.question(
            self, "确认删除",
            f"确定要删除「{title[:30]}」的下载记录吗？\n（仅删除数据库记录，不影响已下载的文件）",
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        normalized = normalize_rj_id(source_id)
        self.download_history.delete_download(f"RJ{normalized}")
        self.downloaded_ids_cache.discard(normalized)
        self._update_downloaded_count()
        self._set_status(f"✓ 已删除下载记录: {title[:20]}...")
        if self.current_tab == "download":
            self._load_downloads()
        else:
            # 重新过滤当前列表（若该作品已不在列表，无需处理）
            if work in self.works:
                self.model.set_works(self.works)
                self._sync_translations()
            self.detail_panel.show_work(work, self._is_downloaded(work))

    # ---------- 交互 ----------
    def _on_go_page(self):
        try:
            p = int(self.page_entry.text().strip())
        except ValueError:
            return
        self._navigate_search(p)

    def _on_work_clicked(self, index):
        work = self.model.work_at(index.row())
        if work:
            self._show_detail(work)

    def _on_work_double_clicked(self, work):
        if work is None:
            return
        self._show_detail(work)
        self._open_download_dialog(work)

    # ---------- 翻译标题（列表右键菜单） ----------
    def _init_translator(self):
        """启动时把 config 里的 AI 配置同步给 translator 单例（对齐 tkinter 版）。"""
        if not _config.AI_TRANSLATE_ENABLED or not _config.AI_API_KEY:
            return
        try:
            translator = get_translator()
            translator.update_config(
                _config.AI_API_KEY,
                _config.AI_API_BASE_URL,
                _config.AI_MODEL,
                _config.AI_THINKING_ENABLED
            )
        except Exception as e:
            logger.exception("初始化翻译服务失败: %s", e)

    def _on_translation_action(self, action, work):
        """右键「翻译」子菜单动作分发。"""
        if work is None:
            return
        if action == "translate":
            self._on_translate_requested(work)
        elif action == "edit":
            self._edit_translation(work)
        elif action == "retranslate":
            self._retranslate(work)
        elif action == "delete":
            self._delete_translation(work)

    def _on_translate_requested(self, work):
        """右键「翻译标题」：先查缓存，未命中则异步翻译（回调在后台线程 → 信号回主线程）。"""
        original = work.get("_original_title") or work.get("title") or ""
        if not original.strip():
            return
        translator = get_translator()
        cached = translator.get_cached(original)
        if cached:
            self._apply_translation(work, cached)
            return
        self._translate_request(work)

    def _retranslate(self, work):
        """重新翻译：清空内存与 DB 缓存后强制走 API。"""
        original = work.get("_original_title") or work.get("title") or ""
        if not original.strip():
            return
        try:
            get_translator().invalidate(original)
        except Exception:
            logger.exception("清除翻译缓存失败: %s", original[:30])
        try:
            self.db.delete_translated_title(str(work.get("id", "")))
        except Exception:
            logger.exception("删除翻译记录失败")
        self._translate_request(work)

    def _translate_request(self, work):
        """发起异步翻译请求（回调经 _translate_result 信号回主线程）。"""
        original = work.get("_original_title") or work.get("title") or ""
        if not original.strip():
            return
        if not _config.AI_TRANSLATE_ENABLED or not _config.AI_API_KEY:
            self._set_status("未启用 AI 翻译，请先在「设置 → AI 翻译」中配置")
            return
        self._set_status("正在翻译标题...")

        def on_result(translated):
            self._translate_result.emit(original, work, translated)

        try:
            get_translator().translate(original, on_result)
        except Exception as e:
            logger.exception("翻译请求异常: %s", e)
            self._set_status(f"翻译请求失败：{e}")

    def _edit_translation(self, work):
        """手动编辑翻译结果（输入框 → 保存 → 刷新显示）。"""
        work_id = str(work.get("id", ""))
        if not work_id:
            return
        current = self.model.translated_title(work) or work.get("title", "")
        text, ok = QInputDialog.getMultiLineText(self, "编辑翻译", "翻译结果：", current)
        if not ok or not text.strip():
            return
        self._apply_translation(work, text.strip())
        self._set_status("✓ 翻译已更新")

    def _delete_translation(self, work):
        """删除翻译记录：恢复原文显示并刷新。"""
        work_id = str(work.get("id", ""))
        if not work_id:
            return
        self.db.delete_translated_title(work_id)
        # 恢复原文显示（若 work["title"] 已被翻译覆盖）
        if work.get("_original_title"):
            work["title"] = work.pop("_original_title")
        # 同步 model 缓存并刷新该行
        self.model.remove_translation(work_id)
        row = self.model.row_of(work)
        if row >= 0:
            idx = self.model.index(row)
            self.model.dataChanged.emit(idx, idx, [])
        # 刷新详情面板（若正显示该作品）
        if self.detail_panel.current_work() is work:
            self.detail_panel.show_work(work, self._is_downloaded(work))
        self._set_status("✓ 已删除翻译")

    def _on_translate_result(self, original, work, translated):
        if translated:
            self._apply_translation(work, translated)
            self._set_status("✓ 翻译完成")
        else:
            self._set_status("翻译失败，请检查 API 设置或网络连接")

    def _apply_translation(self, work, translated):
        """应用翻译：更新列表卡片标题、落库（translations 表）、刷新详情面板。"""
        try:
            if "_original_title" not in work:
                work["_original_title"] = work.get("title") or ""
            work["title"] = translated
            # 落库键必须与 detail_panel 查询一致：数字 id（对齐 tkinter 版）
            work_id = str(work.get("id", ""))
            if work_id:
                self.db.save_translated_title(work_id, translated)
                self.model.set_translation(work_id, translated)
            # 刷新列表行
            row = self.model.row_of(work)
            if row >= 0:
                idx = self.model.index(row)
                self.model.dataChanged.emit(idx, idx, [])
            # 刷新详情面板（若正显示该作品）
            if self.detail_panel.current_work() is work:
                self.detail_panel.show_work(work, self._is_downloaded(work))
        except Exception as e:
            logger.exception("应用翻译失败: %s", e)
            self._set_status(f"翻译应用失败：{e}")

    # ---------- 下载管理 ----------
    def _restore_pending_tasks(self):
        """启动恢复未完成任务（与 tkinter 版 _on_startup_restore 对齐）。"""
        try:
            count = self.dl_manager.restore_pending_tasks()
            if count > 0:
                self._set_status(f"已恢复 {count} 个未完成下载任务")
        except Exception:
            pass

    def _on_downloads_changed(self):
        """observer 由轮询线程触发 → pyqtSignal queued 回主线程。

        仅当完成/失败任务集合变化时才重查已下载 ID（避免每次进度更新打 DB）。
        """
        try:
            done_ids = {t.work_id for t in self.dl_manager.get_all_tasks()
                        if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)}
        except Exception:
            return
        if done_ids != self._last_done_ids:
            self._last_done_ids = done_ids
            self._load_downloaded_ids()

    def _open_download_dialog(self, work):
        """双击作品 → 下载选择对话框（每次新建，完成后清理引用）。

        display_title 传译文标题（翻译缓存优先，无译文回退原文），
        提交下载时目录名使用译文（对齐 tkinter 版 list_mixin._get_display_title）。
        """
        from src.ui.qt.download_dialog import DownloadDialog
        display = self.model.translated_title(work) or work.get("title", "")
        dlg = DownloadDialog(self, work, self.downloaded_ids_cache,
                             display_title=display, tracks_cache=self.tracks_db)
        self._dl_dialog = dlg
        dlg.finished.connect(lambda _r: setattr(self, "_dl_dialog", None))
        dlg.show()

    def _open_download_manager_dialog(self):
        """下载管理（单实例：已打开则置前）。"""
        from src.ui.qt.download_manager_dialog import DownloadManagerDialog
        if self._dl_mgr_dialog is not None:
            try:
                self._dl_mgr_dialog.raise_()
                self._dl_mgr_dialog.activateWindow()
                return
            except Exception:
                self._dl_mgr_dialog = None
        dlg = DownloadManagerDialog(self, self.dl_manager)
        self._dl_mgr_dialog = dlg
        dlg.finished.connect(lambda _r: setattr(self, "_dl_mgr_dialog", None))
        dlg.show()

    def _open_settings_dialog(self):
        """设置（单实例：已打开则置前）。"""
        from src.ui.qt.settings_dialog import SettingsDialog
        if self._settings_dialog is not None:
            try:
                self._settings_dialog.raise_()
                self._settings_dialog.activateWindow()
                return
            except Exception:
                self._settings_dialog = None
        dlg = SettingsDialog(self, image_cache=self.image_cache)
        self._settings_dialog = dlg
        dlg.finished.connect(lambda _r: setattr(self, "_settings_dialog", None))
        dlg.show()

    def _set_status(self, text):
        self.top_bar.status_label.setText(text)

    # ---------- 属性 ----------
    @property
    def model(self):
        return self.list_view.model()

    @property
    def delegate(self):
        return self.list_view.delegate()

    @property
    def page_entry(self):
        return self.bottom_bar.page_entry

    # ---------- 关闭清理 ----------
    def closeEvent(self, event):
        try:
            self.dl_manager.remove_observer(self._downloads_changed.emit)
        except Exception:
            pass
        if self._data_thread is not None:
            self._data_thread.quit()
            self._data_thread.wait(2000)
        if self._thumb_thread is not None:
            self._thumb_thread.quit()
            self._thumb_thread.wait(2000)
        for mgr in (self.db, self.download_history, self.pending_task_db, self.tracks_db):
            try:
                mgr.close_all()
            except Exception:
                pass
        super().closeEvent(event)
