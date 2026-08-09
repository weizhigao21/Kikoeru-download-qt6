# -*- coding: utf-8 -*-
"""底栏：下载任务条区域、下载管理入口、翻页、设置。

任务条采用增量更新策略（对齐下载管理窗口）：
任务集合变化时重建行，进度变化只刷新值，避免每帧重建控件导致闪烁。
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QPushButton, QLineEdit,
                             QFrame, QProgressBar, QSizePolicy, QVBoxLayout)

from src.ui.qt.qt_fonts import SMALL, MONO_ID

# 底部任务条最多显示的行数（超出折叠为 "+N 个任务"）
MAX_TASK_ROWS = 3

# 非下载中状态的文案
_STATUS_TEXT = {
    "submitting": "提交中",
    "queued": "排队中",
    "converting": "转换中",
}


def _task_visible(task):
    """任务条是否显示该任务（排除已完成的终态）。"""
    status = task.status.value if hasattr(task.status, "value") else str(task.status)
    return status not in ("completed", "failed", "cancelled")


class _TaskRow(QWidget):
    """单任务行：ID + 进度条 + 状态/速度。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 1, 6, 1)
        lay.setSpacing(8)

        self.id_label = QLabel("")
        self.id_label.setFont(MONO_ID)
        self.id_label.setFixedWidth(118)
        lay.addWidget(self.id_label)

        self.bar = QProgressBar()
        self.bar.setFixedHeight(14)
        self.bar.setTextVisible(False)
        lay.addWidget(self.bar, 1)

        self.info_label = QLabel("")
        self.info_label.setFont(SMALL)
        self.info_label.setFixedWidth(92)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.info_label)

    def update_task(self, task):
        """刷新单行进度（总大小未知时显示忙碌动画/状态文字）。"""
        status = task.status.value if hasattr(task.status, "value") else str(task.status)
        if status in _STATUS_TEXT:
            self.info_label.setText(_STATUS_TEXT[status])
            self.bar.setRange(0, 0)  # 忙碌动画
            return
        total = task.total_bytes
        completed = task.completed_bytes
        if total > 0:
            self.bar.setRange(0, total)
            self.bar.setValue(min(completed, total))
            pct = min(int(completed * 100 / total), 100)
            speed = f"{task.speed / 1024:.0f}K/s" if task.speed > 0 else ""
            self.info_label.setText(f"{pct}% {speed}".strip())
        else:
            self.bar.setRange(0, 0)
            self.info_label.setText("下载中")


class BottomBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.dl_mgr_btn = QPushButton("下载管理")
        lay.addWidget(self.dl_mgr_btn)

        # 下载任务条区域（有活跃任务时显示，增量更新）
        self.dl_task_frame = QFrame()
        self.dl_task_frame.setObjectName("dlTaskFrame")
        self.dl_task_frame.setSizePolicy(QSizePolicy.Policy.Expanding,
                                         QSizePolicy.Policy.Fixed)
        self._task_lay = QVBoxLayout(self.dl_task_frame)
        self._task_lay.setContentsMargins(2, 2, 2, 2)
        self._task_lay.setSpacing(2)
        self._more_label = QLabel("")
        self._more_label.setFont(SMALL)
        self._more_label.hide()
        self._task_lay.addWidget(self._more_label)
        lay.addWidget(self.dl_task_frame)
        self.dl_task_frame.hide()

        # 当前显示的任务 id 列表（用于判断集合是否变化）
        self._active_ids = None
        self._rows = {}  # work_id -> _TaskRow

        # 翻页控件组：两侧等弹性伸缩，水平居中在底栏中部
        lay.addStretch(1)

        self.prev_btn = QPushButton("← 上一页")
        self.prev_btn.setFlat(True)
        self.prev_btn.setEnabled(False)
        lay.addWidget(self.prev_btn)

        lay.addWidget(QLabel("页码:"))
        self.page_entry = QLineEdit("1")
        self.page_entry.setFixedWidth(60)
        self.page_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.page_entry)

        self.go_btn = QPushButton("跳转")
        lay.addWidget(self.go_btn)

        self.next_btn = QPushButton("下一页 →")
        self.next_btn.setFlat(True)
        self.next_btn.setEnabled(False)
        lay.addWidget(self.next_btn)

        lay.addStretch(1)

        self.settings_btn = QPushButton("设置")
        lay.addWidget(self.settings_btn)

    # ---------- 任务条 ----------
    def set_active_tasks(self, tasks):
        """增量刷新任务条：任务集合变化时重建行，否则只刷新进度值。

        Args:
            tasks: DownloadManager.get_all_tasks() 的结果（含全部状态）。
        """
        active = [t for t in tasks if _task_visible(t)]
        active.sort(key=lambda t: t.work_id)
        ids = [t.work_id for t in active]

        if ids == self._active_ids:
            # 集合未变：就地刷新进度（避免重建控件闪烁）
            for t in active:
                row = self._rows.get(t.work_id)
                if row is not None:
                    row.update_task(t)
            return

        # 集合变化：重建
        self._active_ids = ids
        for w in list(self._rows.values()):
            w.deleteLater()
        self._rows.clear()

        if not active:
            self.dl_task_frame.hide()
            return

        for t in active[:MAX_TASK_ROWS]:
            row = _TaskRow(self.dl_task_frame)
            row.id_label.setText((t.work_id or "")[:14] or (t.title or "")[:14])
            row.update_task(t)
            self._task_lay.addWidget(row)
            self._rows[t.work_id] = row

        extra = len(active) - MAX_TASK_ROWS
        if extra > 0:
            self._more_label.setText(f"+{extra} 个任务")
            self._more_label.show()
        else:
            self._more_label.hide()

        self.dl_task_frame.show()
