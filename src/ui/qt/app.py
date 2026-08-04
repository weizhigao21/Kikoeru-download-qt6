# -*- coding: utf-8 -*-
"""Qt6 入口（v2.0.0 起为默认 UI，替代 tkinter 版 gui_app.py）。

运行：python app.py（或 python -m src.ui.qt.app）
"""
import logging
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QSplashScreen

from src import VERSION
from src.ui.fonts import UI_FONT_FAMILY
from src.ui.qt.main_window import MainWindow
from src.ui.qt.styles import build_qss


def _create_splash():
    """绘制并显示启动画面（深色底 + 应用名 + 版本），避免主窗口初始化期间黑屏等待。"""
    pixmap = QPixmap(640, 360)
    pixmap.fill(QColor("#1e1e2e"))
    painter = QPainter(pixmap)
    try:
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont(UI_FONT_FAMILY, 26, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "音声浏览下载")
        painter.setPen(QColor("#8a8a9a"))
        painter.setFont(QFont(UI_FONT_FAMILY, 13))
        painter.drawText(pixmap.rect().adjusted(0, 60, 0, -120),
                         Qt.AlignmentFlag.AlignCenter, VERSION)
    finally:
        painter.end()
    splash = QSplashScreen(pixmap)
    splash.show()
    return splash


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(threadName)s: %(message)s'
    )
    app = QApplication(sys.argv)
    app.setApplicationName(f"音声浏览下载 {VERSION}")
    app.setFont(QFont(UI_FONT_FAMILY, 10))   # 全局字体（微软雅黑 UI）
    app.setStyleSheet(build_qss())            # QSS 颜色/边框/圆角

    splash = _create_splash()
    app.processEvents()  # 立即绘制启动画面，主窗口初始化期间用户有反馈

    win = MainWindow()
    win.show()
    splash.finish(win)  # 主窗口完全显示后关闭启动画面
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
