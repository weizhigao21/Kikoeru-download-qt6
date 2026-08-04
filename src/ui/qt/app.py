# -*- coding: utf-8 -*-
"""Qt6 入口（v2.0.0 起为默认 UI，替代 tkinter 版 gui_app.py）。

运行：python app.py（或 python -m src.ui.qt.app）
"""
import logging
import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from src import VERSION
from src.ui.fonts import UI_FONT_FAMILY
from src.ui.qt.main_window import MainWindow
from src.ui.qt.styles import build_qss


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(threadName)s: %(message)s'
    )
    app = QApplication(sys.argv)
    app.setApplicationName(f"音声浏览下载 {VERSION}")
    app.setFont(QFont(UI_FONT_FAMILY, 10))   # 全局字体（微软雅黑 UI）
    app.setStyleSheet(build_qss())            # QSS 颜色/边框/圆角
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
