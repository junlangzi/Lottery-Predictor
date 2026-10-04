# -*- coding: utf-8 -*-
# Module: modules/news_widget.py
# Contains: NewsFetcherWorker, ScrollingNewsWidget

import logging

try:
    from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QSizePolicy
    from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal, QThread, QPropertyAnimation, QPoint
    from PyQt5.QtGui import QFont, QColor, QPainter, QRegion
except ImportError:
    pass

class NewsFetcherWorker(QObject):
    """Worker tải nội dung tin tức từ URL."""
    news_received = pyqtSignal(list)

    def run(self):
        url = "https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/news.txt"
        try:
            import requests
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                raw_text = response.text
                lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
                self.news_received.emit(lines)
            else:
                self.news_received.emit([f"Không thể tải tin tức (Code {response.status_code})"])
        except Exception as e:
            self.news_received.emit([f"Lỗi tải tin tức: {e}"])


class ScrollingNewsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        
        self.setObjectName("NewsTicker")
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        self.setStyleSheet("""
            #NewsTicker { background-color: transparent; }
            QLabel { background-color: transparent; }
            QMenu { background-color: #ffffff; color: #000000; border: 1px solid #cccccc; }
            QMenu::item { background-color: transparent; padding: 4px 20px; color: #000000; }
            QMenu::item:selected { background-color: #0078d7; color: #ffffff; }
            QToolTip { border: 1px solid #888888; background-color: #ffffff; color: #000000; }
        """)
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel(self)
        self.label.setTextFormat(Qt.RichText)
        self.label.setOpenExternalLinks(True) 
        self.label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        
        font = self.label.font()
        font.setPointSize(10)
        self.label.setFont(font)
        
        self.news_items = []
        self.px_pos = 0
        self.speed = 1 
        self.separator = "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;✦&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.scroll_text)
        self.timer_interval = 25
        
    def set_news(self, lines):
        if not lines:
            self.label.setText("Chưa có tin tức.")
            self.news_items = []
            return

        self.news_items = lines
        
        full_tooltip_text = """
        <div style='background-color: #ffffff; color: #000000; padding: 5px; font-size: 10pt;'>
            <b style='color: #d63384;'>TIN TỨC:</b>
            <hr style='border: 1px solid #ccc;'>
            <ul style='margin-left: -15px;'>
        """
        for line in lines:
            full_tooltip_text += f"<li>{line}</li><br>"
        full_tooltip_text += "</ul></div>"
        
        self.label.setToolTip(full_tooltip_text)
        
        self.update_display_text()
        self.timer.start(self.timer_interval)

    def update_display_text(self):
        """Nối tất cả tin thành 1 chuỗi dài với dấu ngăn cách và hiển thị."""
        if not self.news_items:
            return

        processed_lines = []
        for line in self.news_items:
            processed_lines.append(f"<span style='color: #000000; font-weight: 500;'>{line}</span>")
        
        full_html = self.separator.join(processed_lines)
        
        self.label.setText(full_html)
        self.label.adjustSize()
        
        self.px_pos = self.width()
        self.label.move(self.px_pos, (self.height() - self.label.height()) // 2)

    def next_news(self):
        """Đảo danh sách: Đưa tin đầu xuống cuối -> Tin thứ 2 sẽ chạy ngay lập tức."""
        if not self.news_items or len(self.news_items) < 2: return
        
        first_item = self.news_items.pop(0)
        self.news_items.append(first_item)
        
        self.update_display_text()

    def prev_news(self):
        """Đảo danh sách: Đưa tin cuối lên đầu -> Tin đó sẽ chạy ngay lập tức."""
        if not self.news_items or len(self.news_items) < 2: return
        
        last_item = self.news_items.pop()
        self.news_items.insert(0, last_item)
        
        self.update_display_text()

    def scroll_text(self):
        if not self.news_items: return
        
        self.px_pos -= self.speed
        self.label.move(self.px_pos, (self.height() - self.label.height()) // 2)
        
        if self.px_pos < -self.label.width():
            self.px_pos = self.width()

    def resizeEvent(self, event):
        self.setMask(QRegion(self.rect()))
        self.label.move(self.px_pos, (self.height() - self.label.height()) // 2)
        super().resizeEvent(event)

    def enterEvent(self, event):
        self.timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.news_items:
            self.timer.start(self.timer_interval)
        super().leaveEvent(event)
