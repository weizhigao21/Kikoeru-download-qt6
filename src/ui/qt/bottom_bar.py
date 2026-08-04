# -*- coding: utf-8 -*-
"""底栏：下载管理入口、下载任务条区域、翻页、设置（阶段 0 静态骨架）。"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QLineEdit, QFrame


class BottomBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.dl_mgr_btn = QPushButton("下载管理")
        lay.addWidget(self.dl_mgr_btn)

        # 下载任务条区域（阶段 3 填充活跃任务），无活跃任务时隐藏
        self.dl_task_frame = QFrame()
        self.dl_task_frame.setObjectName("dlTaskFrame")
        self.dl_task_frame.setFixedHeight(30)
        lay.addWidget(self.dl_task_frame)
        self.dl_task_frame.hide()

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
