#!/usr/bin/env python3
# HIVE Popup App — PyQt6 native window with QWebEngineView
# [CHANGE: claude-code | 2026-05-08]
# No browser. No Flask. No HTTP server. QWebChannel bridges JS↔Python.

import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, pyqtSlot
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView

SCRIPT_DIR = Path(__file__).resolve().parent
HTML_PATH = SCRIPT_DIR / "hive-popup-ui.html"


class HiveBridge(QObject):
    @pyqtSlot(str, result=str)
    def js_chat(self, json_str):
        from hive_backend import js_chat as fn
        return fn(json_str)

    @pyqtSlot(result=str)
    def js_list_chats(self):
        from hive_backend import js_list_chats as fn
        return fn()

    @pyqtSlot(str, result=str)
    def js_get_chat(self, chat_id):
        from hive_backend import js_get_chat as fn
        return fn(chat_id)

    @pyqtSlot(str, result=str)
    def js_save_chat(self, json_str):
        from hive_backend import js_save_chat as fn
        return fn(json_str)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("HIVE")

    # Dark palette
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(10, 10, 10))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(224, 224, 224))
    pal.setColor(QPalette.ColorRole.Base, QColor(17, 17, 17))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(26, 26, 46))
    pal.setColor(QPalette.ColorRole.Text, QColor(224, 224, 224))
    pal.setColor(QPalette.ColorRole.Button, QColor(17, 17, 17))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(224, 224, 224))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(0, 128, 255))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(pal)

    window = QMainWindow()
    window.setWindowTitle("HIVE")
    window.resize(1000, 680)

    view = QWebEngineView()
    channel = QWebChannel()
    bridge = HiveBridge()
    channel.registerObject("backend", bridge)
    view.page().setWebChannel(channel)

    html = HTML_PATH.read_text()
    view.setHtml(html, QUrl.fromLocalFile(str(SCRIPT_DIR)))

    window.setCentralWidget(view)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    sys.path.insert(0, str(SCRIPT_DIR))
    main()
