# -*- coding: utf-8 -*-
"""Qt6 色板与 QSS 样式表（阶段 0 骨架）。

色板与 tkinter 版 gui_app_ui.py 的 COLORS 保持一致；QSS 由色板常量生成，
避免两处维护（QSS 本身不支持变量）。
"""
from typing import Dict

# 与 tkinter 版一致的色板
COLORS: Dict[str, str] = {
    "bg": "#f5f5f5",
    "card_bg": "#ffffff",
    "primary": "#1976D2",
    "primary_light": "#E3F2FD",
    "accent": "#FF9800",
    "success": "#4CAF50",
    "error": "#F44336",
    "text": "#333333",
    "text_secondary": "#666666",
    "text_hint": "#999999",
    "border": "#e0e0e0",
    "hover": "#e8e8e8",
}


def build_qss(colors: Dict[str, str] = None) -> str:
    """由色板生成 QSS 字符串。"""
    c = colors or COLORS
    return f"""
QMainWindow {{ background: {c["bg"]}; }}
QDialog {{ background: {c["bg"]}; }}

QPushButton {{
    background: {c["primary"]};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 5px 12px;
}}
QPushButton:hover {{ background: #1565C0; }}
QPushButton:pressed {{ background: #0D47A1; }}
QPushButton:disabled {{ background: {c["border"]}; color: {c["text_hint"]}; }}

/* 扁平按钮（返回/隐藏下载等次要操作） */
QPushButton[flat="true"] {{
    background: transparent;
    color: {c["primary"]};
    padding: 3px 8px;
}}
QPushButton[flat="true"]:hover {{ background: {c["primary_light"]}; }}

/* 设置对话框左侧导航按钮 */
QPushButton#navBtn {{
    background: transparent;
    color: {c["text"]};
    text-align: left;
    padding: 8px 14px;
    border: none;
    border-radius: 4px;
}}
QPushButton#navBtn:hover {{ background: {c["hover"]}; }}
QPushButton#navBtn:checked {{ background: #2196F3; color: white; }}

QLineEdit {{
    background: {c["card_bg"]};
    border: 1px solid {c["border"]};
    border-radius: 4px;
    padding: 4px 8px;
}}
QLineEdit:focus {{ border-color: {c["primary"]}; }}

QComboBox {{
    background: {c["card_bg"]};
    border: 1px solid {c["border"]};
    border-radius: 4px;
    padding: 4px 8px;
}}
QComboBox:hover {{ border-color: {c["primary"]}; }}

QLabel {{ background: transparent; color: {c["text"]}; }}

QFrame#listPlaceholder, QFrame#detailPlaceholder {{
    background: {c["card_bg"]};
    border: 1px solid {c["border"]};
    border-radius: 6px;
}}
QFrame#dlTaskFrame {{
    background: {c["card_bg"]};
    border: 1px solid {c["border"]};
    border-radius: 4px;
}}

/* 详情面板（objectName 选择器；不得在控件上 setStyleSheet，
   否则会中断全局 QSS 对子控件的级联，按钮等控件将失去样式） */
QScrollArea#detailPanel {{
    background: #f0f0f0;
    border: 1px solid {c["border"]};
    border-radius: 6px;
}}
QWidget#detailContent {{ background: #f0f0f0; }}
QLabel#sectionLabel {{ color: #999999; }}
QLabel#coverLabel {{ background: #e0e0e0; color: #999999; border-radius: 4px; }}
QLabel#idLabel {{ color: {c["primary"]}; }}
QLabel#circleLabel {{ color: #2196F3; }}
QLabel#editionsLabel {{ color: #888888; }}
QLabel#downloadedCountLabel {{ color: {c["text_secondary"]}; }}
QLabel#statusLabel {{ color: {c["text_hint"]}; }}

/* 表格/树列头 */
QHeaderView::section {{
    background: #f0f0f0;
    border: none;
    border-right: 1px solid {c["border"]};
    border-bottom: 1px solid {c["border"]};
    padding: 4px 8px;
    color: {c["text_secondary"]};
}}
"""
