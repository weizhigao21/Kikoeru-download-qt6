# -*- coding: utf-8 -*-
"""顶栏：tab 切换、返回/刷新、搜索、标签 chip、排序、状态标签。"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QPushButton,
                             QComboBox, QLineEdit, QSizePolicy)

from src.ui.qt.works_list import TAG_COLORS

SORT_ITEMS = [
    "下载时间最新", "下载时间最旧",
    "标题 A-Z", "标题 Z-A",
    "ID 从小到大", "ID 从大到小",
]

# chip 悬停加深色（与 TAG_COLORS 一一对应，用于颜色区分）
_CHIP_HOVER = {
    "#FFB74D": "#F57C00",
    "#81C784": "#43A047",
    "#64B5F6": "#1E88E5",
    "#E57373": "#E53935",
    "#BA68C8": "#8E24AA",
    "#4DB6AC": "#00897B",
}
# 厂商 chip 固定粉色系（对齐 tkinter 版厂商标签 #E91E63）
_CIRCLE_COLOR = "#E91E63"
_CIRCLE_HOVER = "#C2185B"


class TopBarWidget(QWidget):
    # 某个标签 chip 的「✕」被点击（参数：被移除的标签）
    tagRemoved = pyqtSignal(str)
    # 厂商 chip 的「✕」被点击
    circleRemoved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # 当前搜索条件（厂商 + 标签可共存，chips 并排显示）
        self._current_circle = None
        self._current_tags = []
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.tab_combo = QComboBox()
        self.tab_combo.addItems(["推荐作品", "最新收录", "下载作品"])
        self.tab_combo.setFixedWidth(110)
        lay.addWidget(self.tab_combo)

        self.back_btn = QPushButton("← 返回")
        self.back_btn.setFlat(True)
        self.back_btn.setEnabled(False)
        lay.addWidget(self.back_btn)

        self.refresh_btn = QPushButton("刷新")
        lay.addWidget(self.refresh_btn)

        # 搜索区（占 stretch 1）：内部在「搜索框 + 按钮」与「标签 chip」之间切换，
        # 容器本身始终占位 → 隐藏任一子控件都不会让顶栏其余控件塌缩变样
        self.search_area = QWidget()
        sa_lay = QHBoxLayout(self.search_area)
        sa_lay.setContentsMargins(0, 0, 0, 0)
        sa_lay.setSpacing(6)

        self.search_container = QWidget()
        s_lay = QHBoxLayout(self.search_container)
        s_lay.setContentsMargins(0, 0, 0, 0)
        s_lay.setSpacing(6)
        s_lay.addWidget(QLabel("搜索:"))
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("输入 RJ ID / 标题 / 标签 / 厂商...")
        s_lay.addWidget(self.search_entry, 1)
        self.search_btn = QPushButton("搜索")
        s_lay.addWidget(self.search_btn)
        sa_lay.addWidget(self.search_container, 1)

        # 标签 chips：点击标签后替代搜索框显示，多标签并排靠左，每个尾部带 ✕
        self.tag_chips_container = QWidget()
        tc_lay = QHBoxLayout(self.tag_chips_container)
        tc_lay.setContentsMargins(0, 0, 0, 0)
        tc_lay.setSpacing(4)
        self.tag_chips_container.hide()
        sa_lay.addWidget(self.tag_chips_container)

        lay.addWidget(self.search_area, 1)
        # 状态栏文本长短变化（如「正在搜索...」）会挤压唯一可伸缩的搜索区，
        # 给搜索区最小宽度避免顶栏其余控件（下载计数/状态栏）位置跳动
        self.search_area.setMinimumWidth(280)

        self.downloaded_count_label = QLabel("")
        self.downloaded_count_label.setObjectName("downloadedCountLabel")
        lay.addWidget(self.downloaded_count_label)

        self.hide_dl_btn = QPushButton("显示全部")
        self.hide_dl_btn.setFlat(True)
        lay.addWidget(self.hide_dl_btn)

        # 排序区（仅下载作品 tab 显示，包装成容器便于整体显隐）
        self.sort_container = QWidget()
        s_lay = QHBoxLayout(self.sort_container)
        s_lay.setContentsMargins(0, 0, 0, 0)
        s_lay.setSpacing(4)
        s_lay.addWidget(QLabel("排序:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(SORT_ITEMS)
        self.sort_combo.setFixedWidth(140)
        s_lay.addWidget(self.sort_combo)
        lay.addWidget(self.sort_container)
        self.sort_container.hide()

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        # 状态文本长短变化（如「正在搜索...」↔「第 X/Y 页 · N 条」）会改变
        # sizeHint 进而挤压搜索区/移动右侧控件；给最小宽度吸收差异，布局稳定
        self.status_label.setMinimumWidth(170)
        lay.addWidget(self.status_label)

    # ---------- 搜索条件 chips（厂商 chip + 标签 chips 可共存） ----------
    def _make_chip(self, text, color, hover):
        chip = QPushButton(f"{text} ✕")
        chip.setStyleSheet(f"""
            QPushButton {{
                background: {color}; color: white; border: none;
                border-radius: 10px; padding: 4px 12px;
            }}
            QPushButton:hover {{ background: {hover}; }}
        """)
        # Fixed：搜索框隐藏后 sa_lay 无伸缩项，Preferred 会被剩余空间拉伸占满
        chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        chip.setCursor(Qt.CursorShape.PointingHandCursor)
        return chip

    def _rebuild(self):
        """按当前搜索条件（厂商 + 标签）重建 chips；全空则恢复搜索框。"""
        lay = self.tag_chips_container.layout()
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if not self._current_circle and not self._current_tags:
            self.tag_chips_container.hide()
            self.search_container.show()
            return
        # 厂商 chip 在最前（粉色固定），随后标签 chips（色池循环上色，与列表/详情同色系）
        if self._current_circle:
            chip = self._make_chip(f"厂商: {self._current_circle}", _CIRCLE_COLOR, _CIRCLE_HOVER)
            chip.clicked.connect(lambda _=False: self.circleRemoved.emit())
            lay.addWidget(chip)
        for i, tag in enumerate(self._current_tags):
            color = TAG_COLORS[i % len(TAG_COLORS)]
            hover = _CHIP_HOVER.get(color, color)
            chip = self._make_chip(tag, color, hover)
            chip.clicked.connect(lambda _=False, t=tag: self.tagRemoved.emit(t))
            lay.addWidget(chip)
        # 吸收额外空间：QBoxLayout 无伸缩项时会把剩余空间均分给每个 chip 导致居中，
        # 尾部 addStretch 让 chips 全部靠左（对齐 tkinter 版紧贴刷新按钮）
        lay.addStretch(1)
        self.search_container.hide()
        self.tag_chips_container.show()

    def set_tag_chips(self, tags):
        """设置标签 chips（不影响厂商 chip，两者可共存）。"""
        self._current_tags = list(tags)
        self._rebuild()

    def set_circle_chip(self, circle):
        """设置厂商 chip（不影响标签 chips，两者可共存）。"""
        self._current_circle = circle
        self._rebuild()

    def clear_circle_chip(self):
        """移除厂商 chip；仍剩标签则继续显示标签 chips，全空则恢复搜索框。"""
        self._current_circle = None
        self._rebuild()

    def clear_tag_chips(self):
        """移除全部标签 chips；仍剩厂商 chip 则继续显示，全空则恢复搜索框。"""
        self._current_tags = []
        self._rebuild()