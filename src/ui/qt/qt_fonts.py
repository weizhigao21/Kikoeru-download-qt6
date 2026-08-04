# -*- coding: utf-8 -*-
"""Qt6 字体适配层。

字体族常量复用 tkinter 版 src/ui/fonts.py（UI_FONT_FAMILY 等），仅构造方式
从"字体元组"改为 QFont。字号/粗体语义与 tkinter 版保持一致。
"""
from PyQt6.QtGui import QFont

from src.ui.fonts import UI_FONT_FAMILY, MONO_FONT_FAMILY, EMOJI_FONT_FAMILY


def qfont(family: str, size: int, bold: bool = False) -> QFont:
    f = QFont(family)
    f.setPointSize(size)
    f.setBold(bold)
    return f


DEFAULT = qfont(UI_FONT_FAMILY, 10)    # 默认 UI 字体
DEFAULT_BOLD = qfont(UI_FONT_FAMILY, 10, True)
SMALL = qfont(UI_FONT_FAMILY, 9)       # 小字号
BODY = qfont(UI_FONT_FAMILY, 11)       # 正文（导航/搜索框/详情标题）
TITLE_BOLD = qfont(UI_FONT_FAMILY, 14, True)  # 模块大标题
MONO_ID = qfont(MONO_FONT_FAMILY, 9, True)    # 作品 ID 显示
EMOJI = qfont(EMOJI_FONT_FAMILY, 10)          # 📋 等特殊符号控件
