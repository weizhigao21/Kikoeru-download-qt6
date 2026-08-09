# -*- coding: utf-8 -*-
"""列表页虚拟化（阶段 1）：QListView + WorksListModel + WorkCardDelegate。

Model 只持有数据（QAbstractListModel），Delegate 用 QPainter 全绘制卡片；
Qt 内置虚拟化——仅实例化可见行，widget 数量恒定，滚动流畅。
"""
from PyQt6.QtCore import Qt, QAbstractListModel, QModelIndex, QRect, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPixmap
from PyQt6.QtWidgets import (QAbstractItemView, QListView, QMenu,
                             QStyledItemDelegate, QStyle)

from src.ui.qt.qt_fonts import BODY, SMALL, MONO_ID
from src.utils import normalize_rj_id

# 标签颜色池（与 tkinter 版 list_card TAG_COLORS 同风格）
TAG_COLORS = ["#FFB74D", "#81C784", "#64B5F6", "#E57373", "#BA68C8", "#4DB6AC"]


def tag_names(work):
    """提取作品标签名称列表（tags=[{i18n:{zh-cn:{name}}}]）。"""
    out = []
    for t in work.get("tags") or []:
        try:
            name = t["i18n"]["zh-cn"]["name"]
        except (KeyError, TypeError):
            name = None
        if name:
            out.append(name)
    return out


class WorksListModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._works = []
        self._translations: dict = {}  # work_id(数字) → 翻译标题（translations 表缓存）

    def set_translations(self, translations):
        self._translations = dict(translations or {})

    def set_translation(self, work_id, translated):
        """更新单个作品的翻译缓存（编辑/删除后保持 model 与 DB 一致）。"""
        key = str(work_id)
        if translated:
            self._translations[key] = translated
        else:
            self._translations.pop(key, None)

    def remove_translation(self, work_id):
        self._translations.pop(str(work_id), None)

    def translated_title(self, work):
        """返回该作品的翻译缓存标题（无缓存返回空串）。"""
        return self._translations.get(str(work.get("id", "")), "")

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._works)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._works)):
            return None
        if role == Qt.ItemDataRole.UserRole:
            return self._works[index.row()]
        return None

    def set_works(self, works):
        self.beginResetModel()
        self._works = list(works)
        self.endResetModel()

    def work_at(self, row):
        if 0 <= row < len(self._works):
            return self._works[row]
        return None

    def row_of(self, work):
        """返回 work 所在行；不在列表中返回 -1。"""
        try:
            return self._works.index(work)
        except ValueError:
            return -1

    def thumbnail_urls(self):
        return [w["thumbnailCoverUrl"] for w in self._works
                if w.get("thumbnailCoverUrl")]


class WorkCardDelegate(QStyledItemDelegate):
    # 对齐 tkinter 版显示尺寸：真实封面为 4:3（240x180 / 560x420），
    # 绘制框取 4:3（180x135），等比适配后边缘贴合、无白边、不裁剪
    CARD_H = 155
    THUMB_W = 180
    THUMB_H = 135
    TITLE_LINE_H = 26  # 标题每行高度（超出 1 行时卡片额外增高）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thumbs = {}   # url -> QPixmap（主线程更新）
        self._fm_title = QFontMetrics(BODY)
        self._downloaded_ids = set()  # 规范化后的已下载 RJ ID（用于版本 ✓ 标记）

    def set_thumb(self, url, pixmap):
        self._thumbs[url] = pixmap

    def set_downloaded_ids(self, ids):
        self._downloaded_ids = set(ids)

    # ---------- ID 显示 ----------
    def _is_work_downloaded(self, work):
        """作品是否已下载（按规范化 RJ ID 判断）。"""
        sid = work.get("source_id")
        return bool(sid) and normalize_rj_id(sid) in self._downloaded_ids

    def id_display(self, work):
        """ID 显示文本与颜色：已下载 → 绿色 + 括号「已下载」标注，未下载 → 蓝色。"""
        sid = str(work.get("source_id") or "")
        if self._is_work_downloaded(work):
            return f"{sid}（已下载）", "#2E7D32"
        return sid, "#1976D2"

    # ---------- 其他语言版本 ----------
    def edition_items(self, work):
        """构建版本条目 [(text, color, sid)]，对齐 tkinter：已下载绿色✓、未下载紫色。"""
        out = []
        for ed in work.get("other_language_editions_in_db") or []:
            ed_id = ed.get("source_id")
            if not ed_id:
                continue
            lang = ed.get("lang", "")
            is_dl = normalize_rj_id(ed_id) in self._downloaded_ids
            out.append((
                f"✓{lang}:{ed_id}" if is_dl else f"{lang}:{ed_id}",
                "#2E7D32" if is_dl else "#9C27B0",
                ed_id,
            ))
        return out

    def edition_layout(self, work, rect, extra):
        """计算版本标签绘制位置（与 ID 同行水平摆放，对齐 tkinter id_frame），返回 [(text, color, sid, QRect)]。paint 与命中检测共用。"""
        fm = QFontMetrics(SMALL)
        out = []
        # 紧跟 ID 文本之后水平摆放（ID 用 MONO_ID 绘制于 y=48 行，已下载含「（已下载）」标注）
        id_text, _ = self.id_display(work)
        id_w = QFontMetrics(MONO_ID).horizontalAdvance(id_text)
        x = rect.left() + 8 + self.THUMB_W + 12 + id_w + 12
        y = rect.top() + 48 + extra
        for text, color, sid in self.edition_items(work):
            w = fm.horizontalAdvance(text)
            if x + w > rect.right() - 8:
                break
            out.append((text, color, sid, QRect(x, y, w, 18)))
            x += w + 10
        return out

    def tag_layout(self, work, rect, extra):
        """计算标签绘制位置，返回 [(tag, QRect)]。paint 与命中检测共用。"""
        fm = QFontMetrics(SMALL)
        x = rect.left() + 8 + self.THUMB_W + 12
        y = rect.top() + 96 + extra
        h = 22
        out = []
        for tag in tag_names(work)[:12]:
            w = fm.horizontalAdvance(tag) + 16
            if x + w > rect.right() - 8:
                break
            out.append((tag, QRect(x, y, w, h)))
            x += w + 6
        return out

    # ---------- 标题换行 ----------
    def _title_line_count(self, text, width):
        """计算标题在给定宽度下占几行（最多按 2 行处理）。"""
        if not text:
            return 1
        br = self._fm_title.boundingRect(
            QRect(0, 0, max(width, 1), 10000), int(Qt.TextFlag.TextWordWrap), text)
        lines = max(1, (br.height() + self._fm_title.height() - 1) // self._fm_title.height())
        return min(lines, 2)

    def _fit_prefix_len(self, text, width):
        """二分求单行能容纳的最长字符数；优先在空格处断行（CJK 逐字）。"""
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._fm_title.horizontalAdvance(text[:mid]) <= width:
                lo = mid
            else:
                hi = mid - 1
        if lo >= len(text):
            return lo
        space = text.rfind(" ", 0, lo)
        if space > 0:
            return space + 1
        return max(lo, 1)

    def _draw_title(self, painter, rect, text):
        """标题：≤2 行自动换行，超过 2 行则第二行尾部省略号。"""
        fm = self._fm_title
        width = rect.width()
        br = fm.boundingRect(QRect(0, 0, max(width, 1), 10000),
                             int(Qt.TextFlag.TextWordWrap), text)
        lines = max(1, (br.height() + fm.height() - 1) // fm.height())
        if lines <= 2:
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignLeft
                                       | Qt.AlignmentFlag.AlignVCenter
                                       | Qt.TextFlag.TextWordWrap), text)
            return
        # 超过两行：第一行铺满，第二行省略号
        n1 = self._fit_prefix_len(text, width)
        line1 = text[:n1].rstrip()
        line2 = fm.elidedText(text[n1:].lstrip(), Qt.TextElideMode.ElideRight, width)
        y = rect.top()
        painter.drawText(QRect(rect.left(), y, width, fm.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, line1)
        painter.drawText(QRect(rect.left(), y + fm.height(), width, fm.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, line2)

    def _display_title(self, work, index):
        """标题显示：优先翻译缓存（对齐 tkinter 卡片），无缓存用原始标题。"""
        model = index.model()
        if model is not None:
            getter = getattr(model, "translated_title", None)
            if getter is not None:
                t = getter(work)
                if t:
                    return t
        return work.get("title") or ""

    def sizeHint(self, option, index):
        work = index.data(Qt.ItemDataRole.UserRole)
        h = self.CARD_H
        if isinstance(work, dict):
            width = option.rect.width() if (option.rect.isValid() and option.rect.width() > 0) else 600
            title_w = width - 8 - self.THUMB_W - 12 - 8
            if self._title_line_count(self._display_title(work, index), title_w) > 1:
                h += self.TITLE_LINE_H
        return QSize(0, h)

    def paint(self, painter, option, index):
        work = index.data(Qt.ItemDataRole.UserRole)
        if not work:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = option.rect

        # 背景（hover / 选中 / 默认）
        if option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(r, QColor("#E3F2FD"))
        elif option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(r, QColor("#BBDEFB"))
        else:
            painter.fillRect(r, QColor("#FFFFFF"))

        # 封面（未就绪时灰色占位）：等比缩放适配横向区域，不拉伸变形
        url = work.get("thumbnailCoverUrl")
        pix = self._thumbs.get(url) if url else None
        tr = QRect(r.left() + 8, r.top() + 8, self.THUMB_W, self.THUMB_H)
        if pix is not None and not pix.isNull():
            ps = pix.size()
            scale = min(self.THUMB_W / ps.width(), self.THUMB_H / ps.height())
            dw = max(1, int(ps.width() * scale))
            dh = max(1, int(ps.height() * scale))
            dx = tr.left() + (self.THUMB_W - dw) // 2
            dy = tr.top() + (self.THUMB_H - dh) // 2
            painter.drawPixmap(QRect(dx, dy, dw, dh), pix)
        else:
            painter.fillRect(tr, QColor("#EEEEEE"))
            painter.setPen(QColor("#BBBBBB"))
            painter.drawText(tr, Qt.AlignmentFlag.AlignCenter, "…")

        text_left = r.left() + 8 + self.THUMB_W + 12
        title_w = r.right() - text_left - 8

        # 标题（≤2 行自动换行，超长最后一行省略号）
        title = self._display_title(work, index)
        extra = (self._title_line_count(title, title_w) - 1) * self.TITLE_LINE_H
        painter.setFont(BODY)
        painter.setPen(QColor("#333333"))
        self._draw_title(painter, QRect(text_left, r.top() + 12, title_w, 26 + extra), title)

        # ID（等宽字体；已下载 → 绿色 + 括号「已下载」，未下载 → 蓝色）
        id_text, id_color = self.id_display(work)
        painter.setFont(MONO_ID)
        painter.setPen(QColor(id_color))
        painter.drawText(QRect(text_left, r.top() + 48 + extra, 340, 18),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, id_text)

        # 其他语言版本（同 tkinter：已下载绿色✓、未下载紫色，可点击搜索）
        painter.setFont(SMALL)
        for text, color, _sid, er in self.edition_layout(work, r, extra):
            painter.setPen(QColor(color))
            painter.drawText(er, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)

        # 标签（圆角矩形）
        painter.setFont(SMALL)
        for i, (tag, tr) in enumerate(self.tag_layout(work, r, extra)):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(TAG_COLORS[i % len(TAG_COLORS)]))
            painter.drawRoundedRect(tr, 5, 5)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(tr, Qt.AlignmentFlag.AlignCenter, tag)


class WorksListView(QListView):
    workDoubleClicked = pyqtSignal(object)
    editionClicked = pyqtSignal(str)
    tagClicked = pyqtSignal(str)
    # 右键菜单「翻译」子菜单动作：("translate"/"edit"/"retranslate"/"delete", work)
    translationAction = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(WorkCardDelegate(self))
        self.setModel(WorksListModel(self))
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSpacing(2)
        # activated 在 Enter 键与双击时都会触发（不同时触发 doubleClicked），
        # 保证键盘 Enter 与鼠标双击走同一条打开下载窗口的路径，且不会重复打开
        self.activated.connect(self._on_activated)
        # 右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    def set_works(self, works, scroll_to_top=False):
        """替换列表数据。scroll_to_top=True 时滚动条回到顶部（翻页/搜索/刷新场景）；
        局部刷新（详情刷新/隐藏/删除记录）传 False 保持当前滚动位置。"""
        self.model().set_works(works)
        if scroll_to_top:
            # model reset 后 view 布局可能下一帧才稳定，延迟一帧保证滚动生效
            QTimer.singleShot(0, self.scrollToTop)

    def _on_activated(self, index):
        work = self.model().work_at(index.row())
        if work:
            self.workDoubleClicked.emit(work)

    def _on_context_menu(self, pos):
        """右键作品弹出菜单：主菜单「翻译」→ hover 展开子菜单
        （翻译标题 / 编辑翻译 / 重新翻译 / 删除翻译）。"""
        index = self.indexAt(pos)
        work = self.model().work_at(index.row()) if index.isValid() else None
        if not work:
            return
        menu = QMenu(self)
        sub = menu.addMenu("翻译")
        act_translate = sub.addAction("翻译标题")
        act_edit = sub.addAction("编辑翻译")
        act_retranslate = sub.addAction("重新翻译")
        act_delete = sub.addAction("删除翻译")
        # 仅当已有翻译缓存时才允许编辑/删除
        has_translation = bool(self.model().translated_title(work)) or bool(work.get("_original_title"))
        act_edit.setEnabled(has_translation)
        act_delete.setEnabled(has_translation)
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen == act_translate:
            self.translationAction.emit("translate", work)
        elif chosen == act_edit:
            self.translationAction.emit("edit", work)
        elif chosen == act_retranslate:
            self.translationAction.emit("retranslate", work)
        elif chosen == act_delete:
            self.translationAction.emit("delete", work)

    def mousePressEvent(self, event):
        # 点击"其他语言版本"标签 → 版本搜索；点击标签 → 标签搜索（均不改变选中行）
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            idx = self.indexAt(pos)
            if idx.isValid():
                tag = self._tag_at(idx, pos)
                if tag:
                    self.tagClicked.emit(tag)
                    return
                sid = self._edition_sid_at(idx, pos)
                if sid:
                    self.editionClicked.emit(sid)
                    return
        super().mousePressEvent(event)

    def _title_extra(self, work, index):
        """卡片标题占用的额外行高偏移（与 paint 完全一致：译文优先）。"""
        d = self.delegate()
        r = self.visualRect(index)
        title_w = r.width() - 8 - d.THUMB_W - 12 - 8
        title = d._display_title(work, index)
        return (d._title_line_count(title, title_w) - 1) * d.TITLE_LINE_H

    def _tag_at(self, index, pos):
        work = index.data(Qt.ItemDataRole.UserRole)
        if not work:
            return None
        d = self.delegate()
        r = self.visualRect(index)
        extra = self._title_extra(work, index)
        for tag, tr in d.tag_layout(work, r, extra):
            if tr.contains(pos):
                return tag
        return None

    def _edition_sid_at(self, index, pos):
        work = index.data(Qt.ItemDataRole.UserRole)
        if not work:
            return None
        d = self.delegate()
        r = self.visualRect(index)
        extra = self._title_extra(work, index)
        for _text, _color, sid, er in d.edition_layout(work, r, extra):
            if er.contains(pos):
                return sid
        return None

    def delegate(self):
        """返回 WorkCardDelegate（QListView 用 itemDelegate()，此处提供便捷访问）。"""
        return self.itemDelegate()
