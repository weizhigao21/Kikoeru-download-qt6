# -*- coding: utf-8 -*-
"""下载选择对话框（阶段 3，替代 tkinter 版 gui_download.py）。

QTreeView + 自定义 TracksModel 展示作品文件树；
三层查询加载 tracks（DB 缓存 → API → 落库）；全选/取消全选按文件夹递归；
下载选中叶子节点，提交到 DownloadManager。
"""
import logging
import threading

from PyQt6.QtCore import QAbstractItemModel, QItemSelectionModel, QModelIndex, QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                             QTreeView, QVBoxLayout, QAbstractItemView)

from src.api_client import get_api_client
from src.download.manager import DownloadManager
from src.utils import format_duration, format_size, normalize_rj_id
from src.ui.qt.qt_fonts import DEFAULT

logger = logging.getLogger(__name__)

# 节点类型 → 显示图标
_ICONS = {
    "folder": "\U0001F4C1",   # 📁
    "audio": "\U0001F3B5",    # 🎵
    "image": "\U0001F5BC\uFE0F",  # 🖼️
    "text": "\U0001F4C4",     # 📄
    "unknown": "\U0001F4E6",  # 📦
}


class TracksModel(QAbstractItemModel):
    """tracks JSON（list/dict）→ 树模型；节点 dict 作为 internalPointer，父映射预建。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root: list = []
        self._parent_map: dict = {}  # id(node) -> parent node or None
        self._row_map: dict = {}     # id(node) -> 在兄弟列表中的行号（parent() 查表用）

    def _children(self, node):
        if node is None:
            return self._root
        return node.get("children", []) if isinstance(node, dict) else []

    def set_tracks(self, data):
        self.beginResetModel()
        if isinstance(data, dict):
            self._root = [data]
        else:
            self._root = list(data or [])

        def walk(nodes, parent):
            for i, n in enumerate(nodes):
                self._parent_map[id(n)] = parent
                self._row_map[id(n)] = i
                if isinstance(n, dict) and n.get("children"):
                    walk(n["children"], n)

        self._parent_map = {}
        self._row_map = {}
        walk(self._root, None)
        self.endResetModel()

    def index(self, row, column, parent=QModelIndex()):
        kids = self._children(self._node(parent))
        if 0 <= row < len(kids) and 0 <= column < self.columnCount(parent):
            return self.createIndex(row, column, kids[row])
        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        p = self._parent_map.get(id(index.internalPointer()))
        if p is None:
            return QModelIndex()
        # 预建行号映射，避免大文件树下线性扫描找父节点行号
        row = self._row_map.get(id(p), 0)
        return self.createIndex(row, 0, p)

    def rowCount(self, parent=QModelIndex()):
        if parent.column() > 0:
            return 0
        return len(self._children(self._node(parent)))

    def columnCount(self, parent=QModelIndex()):
        return 3

    def hasChildren(self, parent=QModelIndex()):
        if not parent.isValid():
            return bool(self._root)
        return bool(parent.internalPointer().get("children"))

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ["名称", "文件大小", "时间"][section] if 0 <= section < 3 else None
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        node = index.internalPointer()
        if not isinstance(node, dict):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            col = index.column()
            if col == 0:
                return f"{_ICONS.get(node.get('type', 'unknown'), _ICONS['unknown'])} {node.get('title', '')}"
            if col == 1:
                return format_size(node.get("size", 0))
            if col == 2:
                return format_duration(node.get("duration", 0)) if node.get("duration") else ""
        return None

    def _node(self, index):
        if not index.isValid():
            return None
        return index.internalPointer()

    def node_path(self, index):
        """从根到该节点的目录路径（对齐 tkinter 版 item_folder_path）。

        只拼接 type=="folder" 的节点：叶子（audio/image/text）自身不算路径，
        根级叶子返回空串（文件直接放作品目录），根级文件夹 → "文件夹名/"。
        """
        parts = []
        cur = index
        while cur.isValid():
            node = cur.internalPointer()
            if node.get("type") == "folder":
                parts.append(node.get("title", ""))
            p = self._parent_map.get(id(node))
            cur = cur.parent() if p is not None else QModelIndex()
        path = "/".join(reversed(parts))
        return path + "/" if path else ""


class _TracksLoader(QObject):
    """tracks 异步加载容器：daemon 线程拉 API，loaded/failed 信号（queued）回主线程。"""

    loaded = pyqtSignal(object)
    failed = pyqtSignal(str)


class DownloadDialog(QDialog):
    def __init__(self, parent, work, downloaded_ids_cache=None, display_title=None, tracks_cache=None):
        super().__init__(parent)
        self.work = work
        self.display_title = display_title
        self.downloaded_ids_cache = downloaded_ids_cache
        self.tracks_cache = tracks_cache
        self.tracks_data = None
        self._updating_selection = False
        self._prev_selection = set()

        source_id = work.get("source_id", "")
        show_title = display_title if display_title else work.get("title", source_id)
        self.setWindowTitle(f"下载 - {show_title[:30]}...")
        self.resize(700, 600)
        self.setModal(True)

        self._build_ui()
        self._start_loader()
        self._load_tracks(force_refresh=False)

    # ---------- UI ----------
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        self.status_label = QLabel("正在加载文件列表...")
        lay.addWidget(self.status_label)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self.select_all)
        toolbar.addWidget(self.select_all_btn)
        self.select_none_btn = QPushButton("取消全选")
        self.select_none_btn.clicked.connect(self.select_none)
        toolbar.addWidget(self.select_none_btn)
        self.download_btn = QPushButton("下载选中")
        self.download_btn.clicked.connect(self.start_download)
        toolbar.addWidget(self.download_btn)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._on_refresh_tracks)
        toolbar.addWidget(self.refresh_btn)
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #666666;")
        toolbar.addWidget(self.progress_label)
        toolbar.addStretch(1)
        lay.addLayout(toolbar)

        self.tree = QTreeView()
        self.tree.setModel(TracksModel(self))
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setFont(DEFAULT)
        self.tree.header().setStretchLastSection(True)
        self.tree.header().setSectionResizeMode(0, self.tree.header().ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, self.tree.header().ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, self.tree.header().ResizeMode.ResizeToContents)
        self.tree.expandAll()
        lay.addWidget(self.tree, 1)

        self.tree.selectionModel().selectionChanged.connect(self._on_selection_changed)

    # ---------- 加载 ----------
    def _start_loader(self):
        self._loader = _TracksLoader(self)
        self._loader.loaded.connect(self._on_tracks_loaded)
        self._loader.failed.connect(self._on_tracks_failed)

    def _load_tracks(self, force_refresh=False):
        source_id = self.work.get("source_id", "")
        if not source_id:
            self.status_label.setText("无作品 ID，无法加载文件列表")
            return
        # 第一层：DB 缓存（非强制刷新时命中即展示，避免打 API）
        if not force_refresh and self.tracks_cache is not None:
            cached = self.tracks_cache.get_tracks(source_id)
            if cached is not None:
                self.tracks_data = cached
                logger.info("[tracks] 命中 DB 缓存 (source_id=%s)", source_id)
                self._display_tree()
                return
        self.status_label.setText("正在加载文件列表..." if not force_refresh else "正在刷新文件列表...")
        self.refresh_btn.setEnabled(False)
        threading.Thread(target=self._fetch_tracks_worker, args=(source_id,), daemon=True).start()

    def _fetch_tracks_worker(self, source_id):
        try:
            data = get_api_client().fetch_tracks(source_id)
            self._loader.loaded.emit(data)  # 跨线程 emit → queued 回主线程
        except Exception as e:
            self._loader.failed.emit(str(e))

    def _on_refresh_tracks(self):
        self._load_tracks(force_refresh=True)

    def _on_tracks_loaded(self, data):
        self.refresh_btn.setEnabled(True)
        self.tracks_data = data
        # 第三层：落库
        source_id = self.work.get("source_id", "")
        if data is not None and self.tracks_cache is not None:
            try:
                self.tracks_cache.save_tracks(source_id, data, self.work.get("title", ""))
            except Exception:
                logger.exception("[tracks] save_tracks 失败: %s", source_id)
        self._display_tree()

    def _on_tracks_failed(self, error):
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"加载失败: {error}")
        QMessageBox.critical(self, "错误", f"加载失败: {error}")

    def _display_tree(self):
        # 重建前清空旧选中状态（避免 selectionChanged 引用旧索引）
        self._updating_selection = True
        try:
            self.tree.selectionModel().clearSelection()
        finally:
            self._updating_selection = False
        self._prev_selection = set()
        self.tree.model().set_tracks(self.tracks_data)
        self.tree.expandAll()
        self.status_label.setText("文件列表加载完成" if self.tracks_data else "文件列表为空")
        self.progress_label.setText("已选择: 0 个文件")

    # ---------- 选择 ----------
    def _selected_indexes(self):
        return [i for i in self.tree.selectionModel().selectedIndexes() if i.column() == 0]

    def _leaf_count(self):
        return sum(1 for i in self._selected_indexes() if not self.tree.model().hasChildren(i))

    def _update_leaf_count(self):
        self.progress_label.setText(f"已选择: {self._leaf_count()} 个文件")

    def _set_children_selected(self, parent_idx, select):
        flags = QItemSelectionModel.SelectionFlag.Select if select else QItemSelectionModel.SelectionFlag.Deselect
        flags |= QItemSelectionModel.SelectionFlag.Rows
        sel = self.tree.selectionModel()
        model = self.tree.model()

        def visit(idx):
            for row in range(model.rowCount(idx)):
                child = model.index(row, 0, idx)
                sel.select(child, flags)
                if model.hasChildren(child):
                    visit(child)

        visit(parent_idx)

    def _on_selection_changed(self, selected, deselected):
        if self._updating_selection:
            return
        self._updating_selection = True
        try:
            model = self.tree.model()
            for idx in deselected.indexes():
                if idx.column() == 0 and model.hasChildren(idx):
                    self._set_children_selected(idx, False)
            for idx in selected.indexes():
                if idx.column() == 0 and model.hasChildren(idx):
                    self._set_children_selected(idx, True)
        finally:
            self._updating_selection = False
        self._update_leaf_count()

    def select_all(self):
        self._updating_selection = True
        try:
            sel = self.tree.selectionModel()
            sel.select(self.tree.model().index(0, 0, QModelIndex()),
                       QItemSelectionModel.SelectionFlag.Select
                       | QItemSelectionModel.SelectionFlag.Rows)
            self._select_descendants(self.tree.model().index(0, 0, QModelIndex()))
            # 递归全选其余顶层节点
            model = self.tree.model()
            for row in range(1, model.rowCount()):
                idx = model.index(row, 0, QModelIndex())
                sel.select(idx, QItemSelectionModel.SelectionFlag.Select
                           | QItemSelectionModel.SelectionFlag.Rows)
                self._select_descendants(idx)
        finally:
            self._updating_selection = False
        self._update_leaf_count()

    def _select_descendants(self, parent_idx):
        sel = self.tree.selectionModel()
        model = self.tree.model()
        for row in range(model.rowCount(parent_idx)):
            child = model.index(row, 0, parent_idx)
            sel.select(child, QItemSelectionModel.SelectionFlag.Select
                       | QItemSelectionModel.SelectionFlag.Rows)
            if model.hasChildren(child):
                self._select_descendants(child)

    def select_none(self):
        self._updating_selection = True
        try:
            self.tree.selectionModel().clearSelection()
        finally:
            self._updating_selection = False
        self.progress_label.setText("已选择: 0 个文件")

    # ---------- 下载 ----------
    def _selected_files(self):
        """收集选中叶子节点 → (files, leaf_count)。"""
        files = []
        seen = set()
        model = self.tree.model()
        for idx in self._selected_indexes():
            if model.hasChildren(idx):
                continue
            node = idx.internalPointer()
            if id(node) in seen:
                continue
            seen.add(id(node))
            url = node.get("mediaDownloadUrl") or node.get("mediaStreamUrl")
            if url:
                files.append({
                    "url": url,
                    "filename": node.get("title", "未命名"),
                    "subfolder": model.node_path(idx),
                })
        return files, len(seen)

    def start_download(self):
        files, leaf_count = self._selected_files()
        if leaf_count == 0:
            QMessageBox.warning(self, "提示", "请选择要下载的文件")
            return
        if not files:
            QMessageBox.warning(self, "提示", "未找到可下载的文件链接")
            return

        source_id = self.work.get("source_id", "")
        if source_id and self.downloaded_ids_cache is not None:
            self.downloaded_ids_cache.add(normalize_rj_id(source_id))

        submit_work = dict(self.work)
        if self.display_title:
            submit_work["title"] = self.display_title

        DownloadManager().submit(submit_work, files)

        self.status_label.setText(f"\u2713 已提交 {len(files)} 个文件到下载队列")
        self.progress_label.setText("")
        self.download_btn.setEnabled(False)
        self.download_btn.setText("已提交")
        QTimer.singleShot(2000, self.accept)
