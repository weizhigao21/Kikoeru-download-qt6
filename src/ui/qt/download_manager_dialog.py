# -*- coding: utf-8 -*-
"""下载管理对话框（阶段 3，替代 tkinter 版 gui_download_manager.py）。

QTabWidget 切换「正在下载 / 已完成」；正在下载用 QTableView + 自定义模型，
进度列 delegate 绘制进度条，操作列 indexWidget 放置 重试/取消 按钮；
observer 在轮询线程被调用，通过信号跨线程调度回主线程刷新。
"""
import logging

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QHeaderView,
                             QLabel, QMessageBox, QPushButton, QStyledItemDelegate,
                             QTabWidget, QTableView, QVBoxLayout, QWidget)

from src.download.models import TaskStatus
from src.ui.qt.qt_fonts import TITLE_BOLD

logger = logging.getLogger(__name__)

_COLORS = {
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

# 状态映射：_status_view 和 _action_for 共用（v1.55.0 风格）
_STATUS_MAP = {
    (TaskStatus.SUBMITTING, TaskStatus.DOWNLOADING): ("\u25cf 下载中", "primary"),
    (TaskStatus.QUEUED,): ("\u25cb 等待下载", "accent"),
    (TaskStatus.FAILED,): ("\u2717 失败", "error"),
}


def _status_view(task):
    """返回 (状态文本, 颜色)。"""
    status_text = task.status.value if hasattr(task.status, "value") else str(task.status)
    color_key = "text_hint"
    for keys, (text, key) in _STATUS_MAP.items():
        if task.status in keys:
            status_text, color_key = text, key
            break
    return status_text, _COLORS.get(color_key, _COLORS["text_hint"])


def _action_for(task):
    """操作列动作：failed → retry；进行中 → cancel；其余 None。"""
    if task.status == TaskStatus.FAILED:
        return "retry"
    if task.status in (TaskStatus.SUBMITTING, TaskStatus.DOWNLOADING, TaskStatus.QUEUED):
        return "cancel"
    return None


def _fmt_speed(bps):
    if bps < 1024:
        return f"{bps} B/s"
    if bps < 1048576:
        return f"{bps / 1024:.1f} KB/s"
    return f"{bps / 1048576:.1f} MB/s"


class _ProgressDelegate(QStyledItemDelegate):
    """进度列：圆角进度条 + 百分比文字（total_bytes 未知时显示状态文字）。"""

    def paint(self, painter, option, index):
        task = index.data(Qt.ItemDataRole.UserRole)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(4, 8, -4, -8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#E0E0E0"))
        painter.drawRoundedRect(rect, 4, 4)
        pct = 0
        if task and task.total_bytes > 0:
            pct = min(int(task.completed_bytes * 100 / task.total_bytes), 100)
            if pct > 0:
                fill = QRect(rect.x(), rect.y(), int(rect.width() * pct / 100), rect.height())
                painter.setBrush(QColor(_COLORS["primary"]))
                painter.drawRoundedRect(fill, 4, 4)
        if task and task.total_bytes > 0:
            text = f"{pct}%"
        elif task and task.status == TaskStatus.SUBMITTING:
            text = "提交中"
        else:
            text = "下载中"
        painter.setPen(QColor("#333333"))
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


class _ActiveTaskModel(QAbstractTableModel):
    HEADERS = ["状态", "ID", "标题", "进度", "速度", "操作"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks = []

    def set_tasks(self, tasks):
        self.beginResetModel()
        self._tasks = list(tasks)
        self.endResetModel()

    def task_at(self, row):
        return self._tasks[row] if 0 <= row < len(self._tasks) else None

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._tasks)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        task = self._tasks[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.UserRole:
            return task
        if role == Qt.ItemDataRole.ForegroundRole:
            if col == 0:
                return QColor(_status_view(task)[1])
            if col == 1:
                return QColor(_COLORS["primary"])
            if col == 4:
                return QColor(_COLORS["text_hint"])
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return _status_view(task)[0]
            if col == 1:
                w = task.work_id
                return w[:11] if len(w) > 11 else w
            if col == 2:
                t = task.title
                return t[:35] if len(t) > 35 else t
            if col == 4:
                return _fmt_speed(task.speed) if task.speed > 0 else ""
        return None


class _DoneTaskModel(QAbstractTableModel):
    HEADERS = ["", "ID", "标题"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks = []

    def set_tasks(self, tasks):
        self.beginResetModel()
        self._tasks = list(tasks)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._tasks)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        task = self._tasks[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return "\u2713"
            if col == 1:
                w = task.work_id
                return w[:12] if len(w) > 12 else w
            if col == 2:
                t = task.title
                return t[:50] if len(t) > 50 else t
        if role == Qt.ItemDataRole.ForegroundRole:
            if col == 0:
                return QColor(_COLORS["success"])
            if col == 1:
                return QColor(_COLORS["success"])
            return None
        return None


class DownloadManagerDialog(QDialog):
    """下载任务管理：正在下载（进度/速度/取消/重试）+ 已完成（✓ 列表）。"""

    _refresh_requested = pyqtSignal()  # observer 线程 → 主线程刷新

    def __init__(self, parent, dl_manager):
        super().__init__(parent)
        self.dl_manager = dl_manager

        self.setWindowTitle("下载管理")
        self.resize(850, 520)
        self.setModal(False)

        self._last_active_ids = None
        self._last_done_ids = None
        self._row_actions = {}  # work_id -> action（决定按钮，动作变化时重建）

        self._build_ui()
        self._refresh_requested.connect(self._refresh)
        self.dl_manager.add_observer(self._schedule_refresh)
        self._refresh()

    def _schedule_refresh(self):
        """observer 在轮询线程被调用；信号 emit 线程安全，queued 回主线程。"""
        self._refresh_requested.emit()

    # ---------- UI ----------
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        title = QLabel("下载任务管理")
        title.setFont(TITLE_BOLD)
        lay.addWidget(title)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {_COLORS['text_hint']};")
        lay.addWidget(self.count_label)

        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)

        # 正在下载
        active_tab = QWidget()
        active_lay = QVBoxLayout(active_tab)
        active_lay.setContentsMargins(4, 8, 4, 4)
        self.active_table = QTableView()
        self.active_table.setModel(_ActiveTaskModel(self))
        self._setup_table(self.active_table)
        self.active_table.setColumnWidth(0, 90)
        self.active_table.setColumnWidth(1, 100)
        self.active_table.setColumnWidth(2, 260)
        self.active_table.setColumnWidth(3, 130)
        self.active_table.setColumnWidth(4, 90)
        self.active_table.setColumnWidth(5, 70)
        self.active_table.setItemDelegateForColumn(3, _ProgressDelegate(self.active_table))
        self.active_table.horizontalHeader().setStretchLastSection(False)
        active_lay.addWidget(self.active_table)
        self.active_empty = QLabel("暂无进行中的下载任务")
        self.active_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.active_empty.setStyleSheet(f"color: {_COLORS['text_hint']};")
        active_lay.addWidget(self.active_empty)
        self.tabs.addTab(active_tab, "正在下载")

        # 已完成
        done_tab = QWidget()
        done_lay = QVBoxLayout(done_tab)
        done_lay.setContentsMargins(4, 8, 4, 4)
        self.done_table = QTableView()
        self.done_table.setModel(_DoneTaskModel(self))
        self._setup_table(self.done_table)
        self.done_table.setColumnWidth(0, 40)
        self.done_table.setColumnWidth(1, 100)
        done_lay.addWidget(self.done_table)
        self.done_empty = QLabel("暂无已完成记录")
        self.done_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.done_empty.setStyleSheet(f"color: {_COLORS['text_hint']};")
        done_lay.addWidget(self.done_empty)
        self.tabs.addTab(done_tab, "已完成")

        bottom = QHBoxLayout()
        self.t2s_btn = QPushButton("繁简转换")
        self.t2s_btn.setToolTip("对已完成任务的目录重新执行繁体转简体（文件名+字幕内容）")
        self.t2s_btn.clicked.connect(self._on_t2s_clicked)
        bottom.addWidget(self.t2s_btn)
        bottom.addStretch(1)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        lay.addLayout(bottom)

    def _on_t2s_clicked(self):
        """手动对已完成任务目录重新执行繁简转换（解决自动转换漏转/被中断的存量文件）。"""
        try:
            from src import config as _config
            if not _config.TRADITIONAL_TO_SIMPLIFIED_ENABLED:
                QMessageBox.information(self, "提示", "繁简转换未在设置中开启，请先在「设置」中启用。")
                return
            started = self.dl_manager.reprocess_t2s()
            if started:
                self.t2s_btn.setEnabled(False)
                self.t2s_btn.setText("转换中…")
                self.count_label.setText(self.count_label.text() + "  |  繁简转换进行中")
                QTimer.singleShot(3000, self._restore_t2s_btn)
            else:
                QMessageBox.information(self, "提示", "没有可转换的已完成任务目录。")
        except Exception as e:
            logger.exception("[繁简] 手动转换启动失败")
            QMessageBox.warning(self, "错误", f"启动繁简转换失败: {e}")

    def _restore_t2s_btn(self):
        self.t2s_btn.setEnabled(True)
        self.t2s_btn.setText("繁简转换")

    @staticmethod
    def _setup_table(table):
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setHighlightSections(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

    # ---------- 刷新 ----------
    def _refresh(self):
        try:
            tasks = self.dl_manager.get_all_tasks()
        except Exception:
            return
        active_tasks = [t for t in tasks
                        if t.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)]
        done_tasks = [t for t in tasks if t.status == TaskStatus.COMPLETED]

        self.count_label.setText(f"正在下载: {len(active_tasks)}  |  已完成: {len(done_tasks)}")

        active_ids = {t.work_id for t in active_tasks}
        if active_ids != self._last_active_ids:
            self._rebuild_active(active_tasks)
            self._last_active_ids = active_ids
        else:
            self._touch_active(active_tasks)

        done_ids = {t.work_id for t in done_tasks}
        if done_ids != self._last_done_ids:
            self._rebuild_done(done_tasks)
            self._last_done_ids = done_ids

    def _rebuild_active(self, active_tasks):
        model = self.active_table.model()
        model.set_tasks(active_tasks)
        self.active_table.viewport().update()
        self._sync_active_buttons()
        self.active_empty.setVisible(not active_tasks)
        self.active_table.setVisible(bool(active_tasks))

    def _touch_active(self, active_tasks):
        """任务集合未变：进度/速度/状态就地刷新（model 持有同一批 task 对象，data() 读实时值）。"""
        self.active_table.viewport().update()
        self._sync_active_buttons()

    def _sync_active_buttons(self):
        model = self.active_table.model()
        changed = False
        new_actions = {}
        for row in range(model.rowCount()):
            task = model.task_at(row)
            if task is None:
                continue
            action = _action_for(task)
            new_actions[task.work_id] = action
            if self._row_actions.get(task.work_id) != action:
                changed = True
        # 按钮动作变化 → 重建模型并重设按钮（简单可靠）
        if changed:
            self._row_actions = new_actions
            tasks = [model.task_at(r) for r in range(model.rowCount())]
            model.set_tasks(tasks)
            self.active_table.viewport().update()
            self._install_buttons()

    def _install_buttons(self):
        model = self.active_table.model()
        for row in range(model.rowCount()):
            task = model.task_at(row)
            if task is None:
                continue
            action = _action_for(task)
            idx = model.index(row, 5)
            if action == "retry":
                btn = QPushButton("重试")
                btn.clicked.connect(lambda _=False, wid=task.work_id: self.dl_manager.retry(wid))
            elif action == "cancel":
                btn = QPushButton("取消")
                btn.clicked.connect(lambda _=False, wid=task.work_id: self.dl_manager.cancel(wid))
            else:
                btn = QPushButton("—")
                btn.setEnabled(False)
            self.active_table.setIndexWidget(idx, btn)

    def _rebuild_done(self, done_tasks):
        sorted_done = sorted(done_tasks, key=lambda x: x.completed_at or 0, reverse=True)
        self.done_table.model().set_tasks(sorted_done[:100])
        self.done_table.viewport().update()
        self.done_empty.setVisible(not sorted_done)
        self.done_table.setVisible(bool(sorted_done))

    # ---------- 关闭 ----------
    def closeEvent(self, event):
        self._on_close()
        super().closeEvent(event)

    def accept(self):
        self._on_close()
        super().accept()

    def reject(self):
        self._on_close()
        super().reject()

    def _on_close(self):
        try:
            self.dl_manager.remove_observer(self._schedule_refresh)
        except Exception:
            pass
