# -*- coding: utf-8 -*-
"""详情面板（阶段 2）：QScrollArea 完整字段展示 + 操作按钮。

字段对齐 tkinter 版 detail_mixin.py：
标题（译/原切换 + 复制）、封面大图、标签（圆角 flow）、ID（复制）、
厂商（点击触发搜索）、声优、其他语言版本、隐藏/刷新/删除下载记录。
"""
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QSize
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPixmap
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QPushButton,
                             QScrollArea, QVBoxLayout, QWidget)

from src.ui.qt.qt_fonts import BODY, EMOJI, MONO_ID, SMALL
from src.ui.qt.works_list import TAG_COLORS, tag_names


class CircleLabel(QLabel):
    """可点击的厂商标签（触发按厂商搜索）。"""
    clicked = pyqtSignal(str)

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.text())
        super().mousePressEvent(event)


class FlowTags(QWidget):
    """圆角标签流式布局：按当前宽度自动换行绘制，点击标签发出 tagClicked。"""
    tagClicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tags = []
        self._tag_h = 22
        self._min_h = 26
        self.setMouseTracking(True)  # 悬停标签时切换手型光标

    def set_tags(self, tags):
        self._tags = list(tags)
        self.updateGeometry()
        self.update()

    def _tag_rects(self):
        """计算标签绘制位置，返回 [(tag, QRect)]。paint 与命中检测共用。"""
        fm = QFontMetrics(SMALL)
        rects = []
        x, y = 0, 0
        gap = 4
        for tag in self._tags:
            w = fm.horizontalAdvance(tag) + 16
            if x + w > self.width() and x > 0:
                x = 0
                y += self._tag_h + gap
            rects.append((tag, QRect(x, y, w, self._tag_h)))
            x += w + 6
        return rects

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            for tag, r in self._tag_rects():
                if r.contains(pos):
                    self.tagClicked.emit(tag)
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        hover = any(r.contains(pos) for _tag, r in self._tag_rects())
        self.setCursor(Qt.CursorShape.PointingHandCursor if hover
                       else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def _measure(self):
        fm = QFontMetrics(SMALL)
        x, y = 0, 0
        gap = 4
        for i, tag in enumerate(self._tags):
            w = fm.horizontalAdvance(tag) + 16
            if x + w > self.width() and x > 0:
                x = 0
                y += self._tag_h + gap
            x += w + 6
        return y + self._tag_h + 2

    def sizeHint(self):
        return QSize(0, max(self._min_h, self._measure()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateGeometry()  # 宽度变化后重算高度

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i, (tag, r) in enumerate(self._tag_rects()):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(TAG_COLORS[i % len(TAG_COLORS)]))
            p.drawRoundedRect(r, 5, 5)
            p.setPen(QColor("#FFFFFF"))
            p.setFont(SMALL)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, tag)
        p.end()


class DetailPanel(QScrollArea):
    """详情面板：展示当前选中作品的完整信息并发出操作请求信号。"""
    circleClicked = pyqtSignal(str)
    tagClicked = pyqtSignal(str)
    hideRequested = pyqtSignal(object)
    refreshRequested = pyqtSignal(object)
    deleteRecordRequested = pyqtSignal(object)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self._db = db
        self._work = None
        self._original_title = ""
        self._translated_title = ""
        self._show_translated = False
        self._refreshing = False

        self.setWidgetResizable(True)
        self.setObjectName("detailPanel")  # 样式统一走全局 QSS（styles.py）
        self._build_ui()

    # ---------- UI ----------
    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setFont(SMALL)
        lbl.setObjectName("sectionLabel")
        return lbl

    def _build_ui(self):
        self._content = QWidget()
        self._content.setObjectName("detailContent")
        self.setWidget(self._content)
        lay = QVBoxLayout(self._content)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(6)

        # 标题
        lay.addWidget(self._section_label("标题:"))
        title_row = QWidget()
        tr = QHBoxLayout(title_row)
        tr.setContentsMargins(0, 0, 0, 0)
        tr.setSpacing(4)
        self.title_label = QLabel("")
        self.title_label.setWordWrap(True)
        self.title_label.setFont(BODY)
        tr.addWidget(self.title_label, 1)
        self.toggle_btn = QPushButton("译")
        self.toggle_btn.setFlat(True)
        self.toggle_btn.setFixedWidth(28)
        self.toggle_btn.clicked.connect(self._toggle_title)
        self.toggle_btn.hide()
        tr.addWidget(self.toggle_btn)
        self.copy_title_btn = QPushButton("📋")
        self.copy_title_btn.setFlat(True)
        self.copy_title_btn.setFont(EMOJI)
        self.copy_title_btn.clicked.connect(self._copy_title)
        tr.addWidget(self.copy_title_btn)
        lay.addWidget(title_row)

        # 封面
        lay.addWidget(self._section_label("封面:"))
        self.cover_label = QLabel("")
        self.cover_label.setMinimumHeight(180)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setObjectName("coverLabel")
        lay.addWidget(self.cover_label)

        # 标签
        lay.addWidget(self._section_label("标签:"))
        self.tags_widget = FlowTags()
        self.tags_widget.tagClicked.connect(self.tagClicked.emit)
        lay.addWidget(self.tags_widget)

        # ID
        lay.addWidget(self._section_label("ID:"))
        id_row = QWidget()
        ir = QHBoxLayout(id_row)
        ir.setContentsMargins(0, 0, 0, 0)
        ir.setSpacing(4)
        self.id_label = QLabel("")
        self.id_label.setFont(MONO_ID)
        self.id_label.setObjectName("idLabel")
        ir.addWidget(self.id_label)
        self.copy_id_btn = QPushButton("📋")
        self.copy_id_btn.setFlat(True)
        self.copy_id_btn.setFont(EMOJI)
        self.copy_id_btn.clicked.connect(self._copy_id)
        ir.addWidget(self.copy_id_btn)
        ir.addStretch(1)
        lay.addWidget(id_row)

        # 厂商
        lay.addWidget(self._section_label("厂商:"))
        self.circle_label = CircleLabel("")
        self.circle_label.setWordWrap(True)
        self.circle_label.setObjectName("circleLabel")
        self.circle_label.clicked.connect(self.circleClicked.emit)
        lay.addWidget(self.circle_label)

        # 声优
        lay.addWidget(self._section_label("声优:"))
        self.cv_label = QLabel("")
        self.cv_label.setWordWrap(True)
        lay.addWidget(self.cv_label)

        # 其他语言版本
        lay.addWidget(self._section_label("其他语言版本:"))
        self.editions_label = QLabel("")
        self.editions_label.setWordWrap(True)
        self.editions_label.setObjectName("editionsLabel")
        lay.addWidget(self.editions_label)

        lay.addSpacing(10)
        self.hide_btn = QPushButton("隐藏此作品")
        self.hide_btn.clicked.connect(lambda: self.hideRequested.emit(self._work))
        lay.addWidget(self.hide_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        self.refresh_btn = QPushButton("刷新信息")
        self.refresh_btn.clicked.connect(lambda: self.refreshRequested.emit(self._work))
        lay.addWidget(self.refresh_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        self.delete_record_btn = QPushButton("删除下载记录")
        self.delete_record_btn.clicked.connect(lambda: self.deleteRecordRequested.emit(self._work))
        lay.addWidget(self.delete_record_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        self.delete_record_btn.hide()
        lay.addStretch(1)

    # ---------- 展示 ----------
    def current_work(self):
        return self._work

    def is_refreshing(self):
        return self._refreshing

    def set_refreshing(self, value):
        self._refreshing = value
        if value:
            self.refresh_btn.setEnabled(False)
            self.refresh_btn.setText("刷新中...")
        else:
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText("刷新信息")

    def show_work(self, work, is_downloaded):
        """展示作品详情（封面由 MainWindow 异步驱动，不在此处理）。"""
        self._work = work
        if work is None:
            self._reset_empty()
            return

        title = work.get("title", "无标题")
        self._original_title = title
        self._translated_title = ""
        self._show_translated = False

        work_id = str(work.get("id", ""))
        if work_id:
            cached = self._db.get_translated_title(work_id)
            if cached:
                self._translated_title = cached
                self._show_translated = True
                self.title_label.setText(cached)
                self.toggle_btn.setText("原")
                self.toggle_btn.show()
            else:
                self.title_label.setText(title)
                self.toggle_btn.hide()
        else:
            self.title_label.setText(title)
            self.toggle_btn.hide()

        self.id_label.setText(f"ID: {work.get('source_id', '')}")

        circle = work.get("circle", {})
        circle_name = circle.get("name", "") if isinstance(circle, dict) else ""
        self.circle_label.setText(circle_name if circle_name else "  无厂商信息")
        self.circle_label.setEnabled(bool(circle_name))

        vas = work.get("vas", [])
        if vas:
            self.cv_label.setText(", ".join(va.get("name", "") for va in vas if va.get("name")))
        else:
            self.cv_label.setText("  无声优信息")

        self.tags_widget.set_tags(tag_names(work))

        editions = work.get("other_language_editions_in_db", [])
        if editions:
            self.editions_label.setText("\n".join(
                f"  [{e.get('lang', '')}] {e.get('title', '')} (ID: {e.get('source_id', '')})"
                for e in editions))
        else:
            self.editions_label.setText("  无其他语言版本")

        self.delete_record_btn.setVisible(is_downloaded)
        self.set_refreshing(False)

    def _reset_empty(self):
        self.title_label.setText("未选择作品")
        self.toggle_btn.hide()
        self.cover_label.setFixedSize(360, 200)
        self.cover_label.setPixmap(QPixmap())
        self.cover_label.setText("未选择作品")
        self.tags_widget.set_tags([])
        self.id_label.setText("")
        self.circle_label.setText("")
        self.cv_label.setText("")
        self.editions_label.setText("")
        self.delete_record_btn.hide()
        self.set_refreshing(False)

    # ---------- 封面 ----------
    def set_cover(self, pix):
        if pix is None or pix.isNull():
            self.cover_label.setText("加载失败")
            return
        # 宽度撑满面板、高度按源图等比自适应（真实封面 4:3 → 约 360x270）。
        # 把标签尺寸钉死为图片尺寸，避免布局压缩导致图片被裁剪、边缘露出背景色
        scale = 360 / pix.width()
        tw = int(pix.width() * scale)
        th = int(pix.height() * scale)
        scaled = pix.scaled(tw, th, Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
        self.cover_label.setFixedSize(tw, th)
        self.cover_label.setPixmap(scaled)
        self.cover_label.setText("")

    def set_cover_loading(self):
        self.cover_label.setFixedSize(360, 200)
        self.cover_label.setPixmap(QPixmap())
        self.cover_label.setText("加载中...")

    def set_cover_none(self):
        self.cover_label.setFixedSize(360, 200)
        self.cover_label.setPixmap(QPixmap())
        self.cover_label.setText("无封面")

    # ---------- 操作 ----------
    def _toggle_title(self):
        if self._show_translated:
            self._show_translated = False
            self.title_label.setText(self._original_title)
            self.toggle_btn.setText("译")
        else:
            self._show_translated = True
            self.title_label.setText(self._translated_title)
            self.toggle_btn.setText("原")

    def _copy_title(self):
        text = self._translated_title if (self._show_translated and self._translated_title) else self._original_title
        if text:
            QApplication.clipboard().setText(text)

    def _copy_id(self):
        if self._work:
            sid = self._work.get("source_id", "")
            if sid:
                QApplication.clipboard().setText(sid)
