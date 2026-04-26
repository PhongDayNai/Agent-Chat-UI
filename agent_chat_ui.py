#!/usr/bin/env python3
"""
Minimal local chat desktop client with a chat-first PyQt6 UI.
"""

import base64
import json
import mimetypes
import re
import sys
import tempfile
from math import ceil
from datetime import datetime
from pathlib import Path

import requests
from PyQt6.QtCore import QByteArray, QBuffer, QEasingCurve, QEvent, QIODevice, QPropertyAnimation, QRectF, QThread, QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QGuiApplication, QIcon, QImage, QPainter, QPen, QPixmap, QTextOption, QTransform
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

APP_STYLE = """
QMainWindow {
    background: #0f1011;
}
QWidget {
    color: #e8eaed;
    background: transparent;
    font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 6px 0;
}
QScrollBar::handle:vertical {
    background: #2a2d30;
    min-height: 28px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #3c4044;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
    border: none;
}
QPushButton {
    border: 1px solid #2b2f33;
    border-radius: 12px;
    background: #17191b;
    color: #e8eaed;
    padding: 9px 14px;
    font-size: 11pt;
}
QPushButton:hover {
    background: #202326;
    border-color: #3a3f44;
}
QPushButton:pressed {
    background: #121416;
}
QPushButton:disabled {
    background: #141618;
    color: #5f6368;
    border-color: #24272a;
}
QPushButton#primaryButton {
    background: #f2f3f5;
    color: #111315;
    border-color: #f2f3f5;
    font-weight: 600;
}
QPushButton#primaryButton:hover {
    background: #ffffff;
    border-color: #ffffff;
}
QPushButton#dangerButton {
    background: #321c20;
    color: #ffd7dc;
    border-color: #60313a;
}
QPushButton#dangerButton:hover {
    background: #46262d;
}
QPushButton#ghostButton {
    background: transparent;
    border-color: #2a2d30;
}
QPushButton#ghostButton:hover {
    background: #181a1c;
}
QPushButton#tinyButton {
    padding: 6px 10px;
    border-radius: 10px;
    font-size: 10pt;
}
QPushButton#messageIconButton {
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
    padding: 0;
    border-radius: 9px;
    font-size: 12pt;
    font-weight: 700;
    background: #17191b;
    border: 1px solid #2a2d30;
    color: #cbd0d5;
}
QPushButton#messageIconButton:hover {
    background: #202326;
    border-color: #3a3f44;
    color: #ffffff;
}
QPushButton#secondaryButton {
    background: #17191b;
    border-color: #2b2f33;
}
QPushButton#secondaryButton:hover {
    background: #202326;
    border-color: #3a3f44;
}
QLabel#titleLabel {
    font-size: 21pt;
    font-weight: 700;
    color: #f4f5f6;
}
QLabel#subtleLabel {
    color: #8c9298;
    font-size: 10pt;
}
QLabel#sectionLabel {
    font-size: 10pt;
    font-weight: 600;
    color: #8c9298;
    letter-spacing: 0.03em;
}
QPushButton#fieldIconButton {
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    padding: 0;
    border-radius: 10px;
    font-size: 12pt;
    font-weight: 700;
    background: #17191b;
    border: 1px solid #2a2d30;
    color: #8c9298;
}
QPushButton#fieldIconButton:hover {
    background: #202326;
    border-color: #3a3f44;
    color: #e8eaed;
}
QPushButton#fieldIconButton[applied="true"] {
    color: #f2f3f5;
    border-color: #f2f3f5;
}
QLabel#statusBadge {
    background: #17191b;
    border: 1px solid #2a2d30;
    border-radius: 999px;
    padding: 6px 10px;
    font-size: 10pt;
    font-weight: 600;
}
QLabel#sessionPromptBadge {
    background: #141618;
    border: 1px solid #2a2d30;
    border-radius: 14px;
    padding: 8px 10px;
    color: #d7d9dc;
    font-size: 9.5pt;
    font-weight: 600;
}
QFrame#queueBanner {
    background: #181a1c;
    border: 1px solid #2d3135;
    border-radius: 16px;
}
QLabel#queueBadge {
    background: #f2f3f5;
    color: #111315;
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 9.5pt;
    font-weight: 700;
}
QLabel#queueBannerText {
    color: #d8dadd;
    font-size: 10pt;
    font-weight: 600;
}
QLabel#emptyTitle {
    font-size: 20pt;
    font-weight: 700;
    color: #f4f5f6;
}
QLabel#emptyBody {
    color: #9aa0a6;
    font-size: 11pt;
}
QFrame#sidebar {
    background: #111315;
    border: 1px solid #1d2023;
    border-radius: 24px;
}
QScrollArea#sidebarScroll {
    border: none;
    background: transparent;
}
QWidget#sidebarScrollBody {
    background: transparent;
}
QPushButton#sidebarMenuButton {
    background: #17191b;
    border: 1px solid #2a2d30;
    border-radius: 14px;
    min-width: 44px;
    max-width: 44px;
    min-height: 44px;
    max-height: 44px;
    padding: 0;
    font-size: 18pt;
    font-weight: 700;
    color: #d8dadd;
}
QPushButton#sidebarMenuButton:hover {
    background: #202326;
    border-color: #3a3f44;
}
QPushButton#pinButton {
    background: #17191b;
    border: 1px solid #2a2d30;
    border-radius: 14px;
    color: #8c9298;
    min-width: 44px;
    max-width: 44px;
    min-height: 44px;
    max-height: 44px;
    padding: 0;
    font-size: 15pt;
    font-weight: 700;
}
QPushButton#pinButton:hover {
    background: #202326;
    border-color: #3a3f44;
    color: #e8eaed;
}
QPushButton#pinButton[pinned="true"] {
    background: #202326;
    border-color: #f2f3f5;
    color: #f2f3f5;
}
QFrame#surface {
    background: #111315;
    border: 1px solid #1d2023;
    border-radius: 24px;
}
QFrame#panel {
    background: #151719;
    border: 1px solid #24272a;
    border-radius: 18px;
}
QFrame#composerFrame {
    background: transparent;
    border: none;
}
QFrame#composerCanvas {
    background: #111315;
    border: 1px solid #171a1d;
    border-radius: 24px;
}
QScrollArea#attachmentScroll {
    border: none;
    background: transparent;
}
QFrame#attachmentChip {
    background: #181a1c;
    border: 1px solid #2d3135;
    border-radius: 16px;
}
QFrame#imageChip {
    background: #181a1c;
    border: 1px solid #2d3135;
    border-radius: 18px;
}
QLabel#attachmentName {
    color: #e8eaed;
    font-size: 10pt;
}
QLabel#fileGlyph {
    color: #d8dadd;
    font-size: 14pt;
    font-weight: 700;
}
QPushButton#attachmentRemoveButton {
    background: rgba(10, 14, 18, 0.62);
    border: 1px solid rgba(255, 255, 255, 0.06);
    color: #eff5fb;
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
    padding: 0;
    font-size: 12pt;
    border-radius: 12px;
}
QPushButton#attachmentRemoveButton:hover {
    background: rgba(10, 14, 18, 0.9);
}
QPushButton#composerPlusButton {
    background: transparent;
    border: none;
    color: #8a8f94;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    padding: 0;
    font-size: 18pt;
    font-weight: 300;
}
QPushButton#composerPlusButton:hover {
    background: #1a1d20;
    border-radius: 16px;
    color: #d8dde2;
}
QPushButton#iconActionButton {
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    padding: 0;
    border-radius: 16px;
    font-size: 15pt;
    font-weight: 800;
}
QPushButton#iconActionButton[variant="send"] {
    background: #6f7378;
    color: #151719;
    border: 1px solid #6f7378;
}
QPushButton#iconActionButton[variant="send"]:hover {
    background: #f2f3f5;
    border-color: #f2f3f5;
}
QPushButton#iconActionButton[variant="send"]:disabled {
    background: #5f6368;
    color: #26292c;
    border-color: #5f6368;
}
QPushButton#iconActionButton[variant="send"]:enabled {
    background: #f2f3f5;
    color: #111315;
    border-color: #f2f3f5;
}
QPushButton#iconActionButton[variant="stop"] {
    background: #321c20;
    color: #ffc9d2;
    border: 1px solid #6f3342;
}
QPushButton#iconActionButton[variant="stop"]:hover {
    background: #5a2935;
}
QFrame#gallerySurface {
    background: #151719;
    border: 1px solid #2a2d30;
    border-radius: 24px;
}
QFrame#messageCard {
    border-radius: 22px;
    border: 1px solid #2a2d30;
}
QFrame#messageCard[user="true"] {
    background: #1d2023;
    border-color: #34383d;
}
QFrame#messageCard[user="false"] {
    background: #151719;
}
QFrame#messageCard[system="true"] {
    background: #181a1c;
    border-color: #33373b;
}
QLabel#roleLabel {
    font-size: 10pt;
    font-weight: 600;
    color: #f4f5f6;
}
QLabel#timeLabel {
    font-size: 9pt;
    color: #858b91;
}
QLabel#attachmentLabel {
    color: #d8dadd;
    font-size: 9.5pt;
    padding: 4px 0;
}
QLabel#toastLabel {
    background: #202326;
    border: 1px solid #3a3f44;
    border-radius: 10px;
    color: #f4f5f6;
    font-size: 10.5pt;
    font-weight: 600;
    padding: 9px 14px;
}
QPlainTextEdit#composerInput {
    background: transparent;
    border: none;
    border-radius: 0;
    font-size: 12pt;
    color: #e8eaed;
    padding: 0;
}
QPlainTextEdit#composerInput:focus {
    border: none;
}
QComboBox,
QPlainTextEdit,
QDoubleSpinBox,
QSpinBox {
    background: #151719;
    border: 1px solid #2a2d30;
    border-radius: 14px;
    color: #e8eaed;
    padding: 8px 10px;
    selection-background-color: #3a3f44;
}
QComboBox:focus,
QPlainTextEdit:focus,
QDoubleSpinBox:focus,
QSpinBox:focus {
    border-color: #f2f3f5;
}
QComboBox::drop-down {
    border: none;
    width: 28px;
}
QComboBox[historyAvailable="false"]::drop-down {
    width: 0px;
}
QComboBox QAbstractItemView {
    background: #151719;
    border: 1px solid #2a2d30;
    selection-background-color: #2a2d30;
    outline: none;
}
QPlainTextEdit {
    padding: 12px 14px;
    font-size: 11pt;
}
QTextBrowser {
    border: none;
    background: transparent;
    color: #e8eaed;
    font-size: 11pt;
}
"""

MARKDOWN_STYLESHEET = """
body {
    color: #e8eaed;
    font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
    font-size: 15px;
    line-height: 1.55;
}
p {
    margin: 0 0 10px 0;
}
h1, h2, h3, h4 {
    color: #f4f5f6;
    margin: 12px 0 8px 0;
}
ul, ol {
    margin-top: 6px;
    margin-bottom: 10px;
}
blockquote {
    color: #c7cacf;
    border-left: 3px solid #3a3f44;
    margin: 10px 0;
    padding-left: 12px;
}
pre {
    background: #0f1011;
    border: 1px solid #2a2d30;
    border-radius: 14px;
    padding: 12px;
    white-space: pre-wrap;
    font-family: "IBM Plex Mono", "Consolas", monospace;
}
code {
    background: #0f1011;
    border: 1px solid #2a2d30;
    border-radius: 8px;
    padding: 2px 5px;
    font-family: "IBM Plex Mono", "Consolas", monospace;
}
a {
    color: #f2f3f5;
    text-decoration: none;
}
"""

DEFAULT_SERVER_BASE_URL = "http://localhost:8080"
CONFIG_PATH = Path(__file__).with_name("config.json")
PIN_ICON_PATH = Path(__file__).with_name("assets") / "ic_pin.svg"
ARROW_UP_ICON_PATH = Path(__file__).with_name("assets") / "ic_arrow_up.svg"
STOP_ICON_PATH = Path(__file__).with_name("assets") / "ic_stop.svg"
COPY_ICON_PATH = Path(__file__).with_name("assets") / "ic_copy.svg"
RETRY_ICON_PATH = Path(__file__).with_name("assets") / "ic_retry.svg"
CLIPBOARD_IMAGE_DIR = Path(tempfile.gettempdir()) / "agent_chat_ui_clipboard"
TEXT_PREVIEW_SUFFIXES = {
    ".txt", ".md", ".json", ".csv", ".py", ".kt", ".js", ".ts", ".tsx", ".jsx",
    ".html", ".css", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".log",
    ".sh", ".bash", ".zsh", ".bat", ".ps1", ".java", ".c", ".cpp", ".h", ".hpp",
    ".sql", ".toml", ".rs",
}
MAX_ATTACHMENT_TEXT_CHARS = 12000
MAX_URLS_PER_MESSAGE = 4
URL_RE = re.compile(r"https?://[^\s<>\]\)\"']+", re.IGNORECASE)
TRAILING_URL_PUNCTUATION = ".,;:!?)]}\"'"


class DeletableHistoryDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.delete_margin = 10
        self.delete_width = 24

    def delete_rect(self, option):
        return option.rect.adjusted(
            option.rect.width() - self.delete_width - self.delete_margin,
            4,
            -self.delete_margin,
            -4,
        )

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        value = index.data(Qt.ItemDataRole.UserRole) or index.data(Qt.ItemDataRole.DisplayRole) or ""
        text_rect = option.rect.adjusted(10, 0, self.delete_width + self.delete_margin + 12, 0)
        metrics = option.fontMetrics
        text = metrics.elidedText(str(value), Qt.TextElideMode.ElideRight, text_rect.width())

        painter.save()
        painter.setPen(option.palette.text().color())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(option.palette.mid().color())
        painter.drawText(
            self.delete_rect(option),
            Qt.AlignmentFlag.AlignCenter,
            "×",
        )
        painter.restore()


class DeletableHistoryComboBox(QComboBox):
    item_delete_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history_available = True
        self.setItemDelegate(DeletableHistoryDelegate(self))
        self.view().viewport().installEventFilter(self)
        self.setProperty("historyAvailable", True)

    def set_history_items(self, values):
        current = self.currentData() or self.currentText()
        self.blockSignals(True)
        self.clear()
        for value in values:
            display_value = " ".join(value.split())
            if len(display_value) > 90:
                display_value = display_value[:87] + "..."
            self.addItem(display_value, value)
        if current:
            index = self.findData(current)
            if index >= 0:
                self.setCurrentIndex(index)
        self.blockSignals(False)

    def current_history_value(self):
        return self.currentData() or self.currentText()

    def set_history_available(self, available):
        self._history_available = available
        self.setProperty("historyAvailable", available)
        self.style().unpolish(self)
        self.style().polish(self)

    def showPopup(self):
        if not self._history_available:
            return
        super().showPopup()

    def eventFilter(self, watched, event):
        if watched == self.view().viewport() and event.type() == QEvent.Type.MouseButtonRelease:
            index = self.view().indexAt(event.position().toPoint())
            if index.isValid():
                option = QStyleOptionViewItem()
                option.rect = self.view().visualRect(index)
                delegate = self.itemDelegate()
                if hasattr(delegate, "delete_rect") and delegate.delete_rect(option).contains(event.position().toPoint()):
                    value = index.data(Qt.ItemDataRole.UserRole) or index.data(Qt.ItemDataRole.DisplayRole) or ""
                    self.hidePopup()
                    self.item_delete_requested.emit(str(value))
                    return True
        return super().eventFilter(watched, event)


class PinIconButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("")
        self.setCheckable(True)
        self._svg_template = self.load_svg_template()

    def load_svg_template(self):
        try:
            content = PIN_ICON_PATH.read_text(encoding="utf-8")
        except OSError:
            return ""
        return content.replace("#1C274C", "currentColor")

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._svg_template:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().buttonText().color().name()
        svg = self._svg_template.replace("currentColor", color)
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        target = QRectF(self.rect().adjusted(11, 11, -11, -11))
        renderer.render(painter, target)


class SvgActionButton(QPushButton):
    def __init__(self, icon_path=None, parent=None):
        super().__init__(parent)
        self.setText("")
        self._svg_template = ""
        self.set_icon_path(icon_path)

    def set_icon_path(self, icon_path):
        try:
            content = Path(icon_path).read_text(encoding="utf-8") if icon_path else ""
        except OSError:
            content = ""
        self._svg_template = (
            content
            .replace("#000000", "currentColor")
            .replace("#000", "currentColor")
            .replace("#1C274C", "currentColor")
            .replace("#292D32", "currentColor")
        )
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._svg_template:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().buttonText().color().name()
        svg = self._svg_template.replace("currentColor", color)
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        target = QRectF(self.rect().adjusted(8, 8, -8, -8))
        renderer.render(painter, target)


class AutoResizingTextEdit(QPlainTextEdit):
    send_requested = pyqtSignal()
    attachment_paths_pasted = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._min_lines = 1
        self._max_lines = 3
        self._horizontal_inset = 14
        self._vertical_inset = 4
        self.setObjectName("composerInput")
        self.setPlaceholderText("Ask for follow-up changes")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setTabChangesFocus(False)
        self.setCenterOnScroll(False)
        self.setViewportMargins(
            self._horizontal_inset,
            self._vertical_inset,
            self._horizontal_inset,
            self._vertical_inset,
        )
        self.document().setDocumentMargin(0)
        line_spacing = self.fontMetrics().lineSpacing()
        chrome_height = (self.frameWidth() * 2) + (self._vertical_inset * 2) + 8
        self._min_height = line_spacing * self._min_lines + chrome_height
        self._max_height = line_spacing * self._max_lines + chrome_height
        self.textChanged.connect(self.update_height)
        self.textChanged.connect(self.keep_cursor_visible)
        self.cursorPositionChanged.connect(self.keep_cursor_visible)
        self.update_height()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
                return
            if not event.modifiers():
                self.send_requested.emit()
                return
        super().keyPressEvent(event)

    def canInsertFromMimeData(self, source):
        if self.extract_attachment_paths(source):
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        paths = self.extract_attachment_paths(source)
        if paths:
            self.attachment_paths_pasted.emit(paths)
            return
        super().insertFromMimeData(source)

    def extract_attachment_paths(self, source):
        if source is None:
            return []

        paths = []
        if source.hasImage():
            image = source.imageData()
            normalized_image = self.normalize_clipboard_image(image)
            if normalized_image is not None and not normalized_image.isNull():
                saved_path = self.save_clipboard_image(normalized_image)
                if saved_path:
                    paths.append(saved_path)
                    return paths

        if source.hasUrls():
            for url in source.urls():
                local_path = url.toLocalFile()
                if not local_path:
                    continue
                suffix = Path(local_path).suffix.lower()
                if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}:
                    paths.append(local_path)
        return paths

    def normalize_clipboard_image(self, image):
        if isinstance(image, QPixmap):
            image = image.toImage()
        if not isinstance(image, QImage) or image.isNull():
            return None

        normalized = image.convertToFormat(QImage.Format.Format_ARGB32)
        normalized.setDevicePixelRatio(1.0)
        return normalized.copy()

    def save_clipboard_image(self, image):
        CLIPBOARD_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = CLIPBOARD_IMAGE_DIR / f"pasted_image_{timestamp}.png"
        return str(path) if image.save(str(path), "PNG") else ""

    def showEvent(self, event):
        super().showEvent(event)
        self.update_height()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_height()
        self.keep_cursor_visible()

    def update_height(self):
        viewport_width = max(0, self.viewport().width())
        if viewport_width:
            self.document().setTextWidth(viewport_width)

        chrome_height = (self.frameWidth() * 2) + (self._vertical_inset * 2) + 8
        doc = self.document()
        first_block = doc.firstBlock()
        last_block = doc.lastBlock()
        if first_block.isValid() and last_block.isValid():
            first_rect = self.blockBoundingGeometry(first_block)
            last_rect = self.blockBoundingGeometry(last_block)
            content_height = ceil(last_rect.bottom() - first_rect.top())
        else:
            content_height = self.fontMetrics().lineSpacing()
        content_height = max(self.fontMetrics().lineSpacing(), content_height)
        target = max(self._min_height, min(self._max_height, content_height + chrome_height))

        self.setMinimumHeight(target)
        self.setMaximumHeight(target)

        policy = (
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if content_height + chrome_height > self._max_height
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setVerticalScrollBarPolicy(policy)
        self.updateGeometry()
        self.keep_cursor_visible()

    def keep_cursor_visible(self):
        self.ensureCursorVisible()


class AutoHeightTextBrowser(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.document().documentLayout().documentSizeChanged.connect(self.update_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setOpenExternalLinks(True)
        self.setMaximumHeight(16777215)
        self.update_height()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sync_text_width()
        self.update_height()

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_text_width()
        self.update_height()

    def sync_text_width(self):
        width = max(0, self.viewport().width() - 4)
        if width:
            self.document().setTextWidth(width)

    def update_height(self, *_args):
        self.sync_text_width()
        doc_height = int(self.document().size().height())
        margins = self.contentsMargins().top() + self.contentsMargins().bottom()
        target = max(36, doc_height + margins + 8)
        self.setMinimumHeight(target)
        self.resize(self.width(), target)
        self.updateGeometry()

    def sizeHint(self):
        hint = super().sizeHint()
        doc_height = int(self.document().size().height())
        margins = self.contentsMargins().top() + self.contentsMargins().bottom()
        hint.setHeight(max(36, doc_height + margins + 8))
        return hint

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        doc_height = int(self.document().size().height())
        margins = self.contentsMargins().top() + self.contentsMargins().bottom()
        hint.setHeight(max(36, doc_height + margins + 8))
        return hint


class ImagePreviewButton(QPushButton):
    clicked_preview = pyqtSignal()

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("imageChip")
        self.setToolTip(Path(path).name)
        self.setFlat(True)
        self.setStyleSheet("")
        self.setFixedSize(88, 88)
        self.clicked.connect(self.clicked_preview.emit)
        self.refresh_pixmap()

    def refresh_pixmap(self):
        pixmap = QPixmap(self.path)
        if pixmap.isNull():
            self.setText("Image")
            return
        scaled = pixmap.scaled(
            76,
            76,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setIconSize(scaled.size())
        self.setIcon(QIcon(scaled))


class AttachmentChip(QFrame):
    remove_requested = pyqtSignal(str)
    preview_requested = pyqtSignal(str)

    def __init__(self, attachment, removable=True, parent=None):
        super().__init__(parent)
        self.attachment = attachment
        self.removable = removable
        self.preview = None
        self.remove_button = None
        self.name_label = None
        self.setObjectName("attachmentChip")

        if attachment["type"] == "image":
            self.setObjectName("imageChip")
            self.setFixedSize(106, 106)
            self.preview = ImagePreviewButton(attachment["path"], self)
            self.preview.clicked_preview.connect(lambda: self.preview_requested.emit(self.attachment["path"]))

            self.remove_button = QPushButton("×", self)
            self.remove_button.setObjectName("attachmentRemoveButton")
            self.remove_button.setFixedSize(24, 24)
            self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self.attachment["path"]))
            self.remove_button.setVisible(removable)
            self.setToolTip(attachment["name"])
        else:
            self.setMinimumWidth(180)
            self.setMaximumWidth(280)
            self.setFixedHeight(46)
            layout = QHBoxLayout(self)
            layout.setContentsMargins(10, 4, 10, 4)
            layout.setSpacing(16)

            icon = QLabel(self.file_glyph())
            icon.setObjectName("fileGlyph")
            icon.setFixedWidth(28)
            layout.addWidget(icon)

            self.name_label = QLabel()
            self.name_label.setObjectName("attachmentName")
            self.name_label.setWordWrap(False)
            self.name_label.setFixedHeight(18)
            self.name_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.name_label.setMinimumWidth(0)
            layout.addWidget(self.name_label, 1)

            if removable:
                remove_button = QPushButton("×")
                remove_button.setObjectName("attachmentRemoveButton")
                remove_button.setFixedSize(20, 20)
                remove_button.clicked.connect(lambda: self.remove_requested.emit(self.attachment["path"]))
                layout.addWidget(remove_button)

            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip(attachment["name"])
            self.refresh_file_name()

    def file_glyph(self):
        suffix = Path(self.attachment["name"]).suffix.lower()
        glyphs = {
            ".csv": "CSV",
            ".json": "JSN",
            ".md": "MD",
            ".pdf": "PDF",
            ".doc": "DOC",
            ".docx": "DOC",
            ".xls": "XLS",
            ".xlsx": "XLS",
            ".ppt": "PPT",
            ".pptx": "PPT",
            ".py": "PY",
            ".kt": "KT",
            ".zip": "ZIP",
        }
        return glyphs.get(suffix, "TXT")

    def mousePressEvent(self, event):
        if self.attachment["type"] != "image" and event.button() == Qt.MouseButton.LeftButton:
            self.preview_requested.emit(self.attachment["path"])
            event.accept()
            return
        super().mousePressEvent(event)

    def refresh_file_name(self):
        if self.attachment["type"] == "image" or self.name_label is None:
            return
        available_width = max(80, self.name_label.width() or 220)
        elided = self.fontMetrics().elidedText(
            self.attachment["name"],
            Qt.TextElideMode.ElideRight,
            available_width,
        )
        self.name_label.setText(elided)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_file_name()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.attachment["type"] != "image":
            self.refresh_file_name()
            return
        if self.preview is not None:
            preview_size = self.preview.size()
            self.preview.move(
                (self.width() - preview_size.width()) // 2,
                (self.height() - preview_size.height()) // 2,
            )
        if self.remove_button is not None:
            button_margin = 6
            self.remove_button.move(
                self.width() - self.remove_button.width() - button_margin,
                button_margin,
            )


class ImageGalleryDialog(QDialog):
    def __init__(self, image_paths, start_index=0, parent=None):
        super().__init__(parent)
        self.image_paths = image_paths
        self.current_index = start_index
        self.current_pixmap = QPixmap()

        self.setWindowTitle("Image Preview")
        self.resize(980, 760)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        surface = QFrame()
        surface.setObjectName("gallerySurface")
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(18, 18, 18, 18)
        surface_layout.setSpacing(12)

        header = QHBoxLayout()
        self.title_label = QLabel("")
        self.title_label.setObjectName("titleLabel")
        header.addWidget(self.title_label, 1)

        close_button = QPushButton("Close")
        close_button.setObjectName("ghostButton")
        close_button.clicked.connect(self.accept)
        header.addWidget(close_button)
        surface_layout.addLayout(header)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(520)
        surface_layout.addWidget(self.image_label, 1)

        controls = QHBoxLayout()
        self.prev_button = QPushButton("← Previous")
        self.prev_button.clicked.connect(self.show_previous)
        controls.addWidget(self.prev_button)

        controls.addStretch()

        self.counter_label = QLabel("")
        self.counter_label.setObjectName("subtleLabel")
        controls.addWidget(self.counter_label)

        controls.addStretch()

        self.next_button = QPushButton("Next →")
        self.next_button.clicked.connect(self.show_next)
        controls.addWidget(self.next_button)
        surface_layout.addLayout(controls)

        root.addWidget(surface)
        self.update_view()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.render_current_image()

    def render_current_image(self):
        if self.current_pixmap.isNull():
            self.image_label.setText("Unable to preview this image.")
            return
        scaled = self.current_pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def update_view(self):
        image_path = self.image_paths[self.current_index]
        self.current_pixmap = QPixmap(image_path)
        self.title_label.setText(Path(image_path).name)
        self.counter_label.setText(f"{self.current_index + 1} / {len(self.image_paths)}")
        self.prev_button.setEnabled(len(self.image_paths) > 1)
        self.next_button.setEnabled(len(self.image_paths) > 1)
        self.render_current_image()

    def show_previous(self):
        self.current_index = (self.current_index - 1) % len(self.image_paths)
        self.update_view()

    def show_next(self):
        self.current_index = (self.current_index + 1) % len(self.image_paths)
        self.update_view()


class FilePreviewDialog(QDialog):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self.setWindowTitle(self.path.name)
        self.resize(980, 760)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        surface = QFrame()
        surface.setObjectName("gallerySurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel(self.path.name)
        title.setObjectName("titleLabel")
        header.addWidget(title, 1)

        open_external = QPushButton("Open Externally")
        open_external.setObjectName("ghostButton")
        open_external.clicked.connect(self.open_externally)
        header.addWidget(open_external)

        close_button = QPushButton("Close")
        close_button.setObjectName("ghostButton")
        close_button.clicked.connect(self.accept)
        header.addWidget(close_button)
        layout.addLayout(header)

        self.viewer = QPlainTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.viewer, 1)

        root.addWidget(surface)
        self.load_content()

    def load_content(self):
        try:
            content = self.path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = self.path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            content = f"Unable to open file.\n\n{exc}"
        self.viewer.setPlainText(content)

    def open_externally(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path)))


class ChatCompletionWorker(QThread):
    token_received = pyqtSignal(str)
    thinking_received = pyqtSignal(str)
    generation_started = pyqtSignal()
    generation_finished = pyqtSignal(bool, bool, str, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stop_requested = False
        self.base_url = DEFAULT_SERVER_BASE_URL
        self.messages = []
        self.model_name = ""
        self.temperature = 0.7
        self.top_p = 0.9
        self.top_k = 40
        self.full_response = ""
        self.full_thinking = ""

    def configure(self, base_url, model_name, messages, temperature, top_p, top_k):
        self.base_url = base_url
        self.model_name = model_name
        self.messages = messages
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k

    def run(self):
        self.stop_requested = False
        self.full_response = ""
        self.full_thinking = ""
        self.generation_started.emit()

        payload = {
            "model": self.model_name,
            "messages": self.messages,
            "stream": True,
            "max_tokens": 1024,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }

        success = False
        stopped = False

        try:
            chat_url = f"{self.base_url}/v1/chat/completions"
            with requests.post(chat_url, json=payload, stream=True, timeout=120) as response:
                if response.status_code != 200:
                    detail = response.text.strip() or f"HTTP {response.status_code}"
                    self.error_occurred.emit(f"Request failed: {detail}")
                    self.generation_finished.emit(False, False, self.full_response, self.full_thinking)
                    return

                for line in response.iter_lines():
                    if self.stop_requested:
                        stopped = True
                        break
                    if not line:
                        continue
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="ignore")
                    if not line.startswith("data: "):
                        continue
                    line = line[6:]
                    if line == "[DONE]":
                        success = True
                        break
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    delta = data.get("choices", [{}])[0].get("delta", {})
                    thinking = delta.get("reasoning_content", "")
                    if thinking:
                        self.full_thinking += thinking
                        self.thinking_received.emit(thinking)
                    token = delta.get("content", "")
                    if token:
                        self.full_response += token
                        self.token_received.emit(token)
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit(f"OpenAI-compatible server is not reachable at {self.base_url}.")
        except requests.exceptions.Timeout:
            self.error_occurred.emit("The request timed out.")
        except Exception as exc:
            self.error_occurred.emit(f"Unexpected error: {exc}")

        self.generation_finished.emit(success, stopped, self.full_response, self.full_thinking)

    def stop(self):
        self.stop_requested = True


class MessageCard(QFrame):
    retry_requested = pyqtSignal(str)
    image_preview_requested = pyqtSignal(list, int)
    file_preview_requested = pyqtSignal(str)

    def __init__(self, role, text="", timestamp=None, retry_text=None, attachments=None, parent=None):
        super().__init__(parent)
        self.role = role
        self.raw_text = text
        self.thinking_text = ""
        self.retry_text = retry_text
        self.loading_step = 0
        self.attachments = attachments or []

        self.setObjectName("messageCard")
        self.setProperty("user", role == "user")
        self.setProperty("system", role == "system")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMaximumHeight(16777215)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(18, 16, 18, 16)
        outer_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        self.role_label = QLabel(self.role_title())
        self.role_label.setObjectName("roleLabel")
        header_layout.addWidget(self.role_label)

        self.time_label = QLabel(timestamp or self.now_text())
        self.time_label.setObjectName("timeLabel")
        header_layout.addWidget(self.time_label)
        header_layout.addStretch()

        self.copy_button = None
        self.retry_button = None
        if role in {"assistant", "user"}:
            self.copy_button = SvgActionButton(COPY_ICON_PATH)
            self.copy_button.setObjectName("messageIconButton")
            self.copy_button.setToolTip("Copy")
            self.copy_button.clicked.connect(self.copy_text)
            header_layout.addWidget(self.copy_button)

        if role == "assistant":
            self.retry_button = SvgActionButton(RETRY_ICON_PATH)
            self.retry_button.setObjectName("messageIconButton")
            self.retry_button.setToolTip("Retry")
            self.retry_button.clicked.connect(self.emit_retry)
            header_layout.addWidget(self.retry_button)

        outer_layout.addLayout(header_layout)

        if role == "assistant":
            self.body = AutoHeightTextBrowser()
            self.body.document().setDefaultStyleSheet(MARKDOWN_STYLESHEET)
            self.body.setMaximumHeight(16777215)

            self.thinking_label = QLabel("Thinking")
            self.thinking_label.setObjectName("sectionLabel")
            self.thinking_label.hide()
            outer_layout.addWidget(self.thinking_label)

            self.thinking_body = AutoHeightTextBrowser()
            self.thinking_body.document().setDefaultStyleSheet(MARKDOWN_STYLESHEET)
            self.thinking_body.setMaximumHeight(16777215)
            self.thinking_body.hide()
            outer_layout.addWidget(self.thinking_body)

            self.loading_timer = QTimer(self)
            self.loading_timer.setInterval(320)
            self.loading_timer.timeout.connect(self.advance_loading_frame)
        else:
            self.body = QLabel()
            self.body.setWordWrap(True)
            self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.body.setStyleSheet("font-size: 11pt; line-height: 1.45; color: #e8eaed;")

        outer_layout.addWidget(self.body)
        self.attachments_widget = None
        self.attachments_layout = None
        if role == "user":
            self.attachments_widget = QWidget()
            self.attachments_layout = QHBoxLayout(self.attachments_widget)
            self.attachments_layout.setContentsMargins(0, 2, 0, 0)
            self.attachments_layout.setSpacing(10)
            self.attachments_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.attachments_widget.hide()
            outer_layout.addWidget(self.attachments_widget)
        self.update_text(text)
        self.refresh_attachments()

    def now_text(self):
        return datetime.now().strftime("%H:%M")

    def role_title(self):
        return {
            "user": "You",
            "assistant": "Assistant",
            "system": "Status",
        }.get(self.role, self.role.title())

    def update_text(self, text):
        self.raw_text = text
        if self.role == "assistant":
            try:
                self.body.setMarkdown(text or "…")
            except Exception:
                self.body.setPlainText(text or "…")
            self.body.update_height()
        else:
            self.body.setText(text)

    def refresh_attachments(self):
        if self.role != "user" or self.attachments_layout is None:
            return

        while self.attachments_layout.count():
            item = self.attachments_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self.attachments:
            self.attachments_widget.hide()
            return

        image_attachments = [item for item in self.attachments if item.get("type") == "image"]
        image_paths = [item["path"] for item in image_attachments]
        image_index = 0
        for attachment in self.attachments:
            if attachment.get("type") == "image":
                preview = ImagePreviewButton(attachment["path"])
                preview.clicked_preview.connect(
                    lambda image_paths=image_paths, index=image_index: self.image_preview_requested.emit(image_paths, index)
                )
                self.attachments_layout.addWidget(preview)
                image_index += 1
            else:
                chip = AttachmentChip(attachment, removable=False)
                chip.preview_requested.connect(self.file_preview_requested.emit)
                self.attachments_layout.addWidget(chip)

        self.attachments_layout.addStretch()
        self.attachments_widget.show()

    def append_text(self, token):
        self.update_text(self.raw_text + token)

    def append_thinking(self, token, visible):
        if self.role != "assistant":
            return
        self.thinking_text += token
        has_thinking = bool(self.thinking_text.strip())
        self.thinking_label.setVisible(visible and has_thinking)
        self.thinking_body.setVisible(visible and has_thinking)
        if visible and has_thinking:
            try:
                self.thinking_body.setMarkdown(self.thinking_text)
            except Exception:
                self.thinking_body.setPlainText(self.thinking_text)
            self.thinking_body.update_height()

    def set_thinking_visibility(self, visible):
        if self.role != "assistant":
            return
        has_thinking = bool(self.thinking_text.strip())
        self.thinking_label.setVisible(visible and has_thinking)
        self.thinking_body.setVisible(visible and has_thinking)

    def start_loading(self):
        if self.role != "assistant":
            return
        self.loading_step = 0
        self.update_loading_text()
        self.loading_timer.start()

    def stop_loading(self):
        if self.role != "assistant":
            return
        self.loading_timer.stop()

    def advance_loading_frame(self):
        self.loading_step = (self.loading_step + 1) % 4
        if not self.raw_text.strip():
            self.update_loading_text()

    def update_loading_text(self):
        dots = "." * (self.loading_step + 1)
        self.body.setPlainText(dots)
        self.body.update_height()

    def copy_text(self):
        QGuiApplication.clipboard().setText(self.raw_text)
        show_widget_toast(self, "Message copied")

    def emit_retry(self):
        if self.retry_text:
            self.retry_requested.emit(self.retry_text)


def show_widget_toast(widget, text):
    window = widget.window() if widget is not None else None
    if window is not None and hasattr(window, "show_toast"):
        window.show_toast(text)


class AgentChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.current_assistant_card = None
        self.history = []
        self.last_submitted_user_text = ""
        self.pending_user_text = None
        self.pending_user_message = None
        self.session_system_prompt = ""
        self.session_prompt_locked = False
        self.pending_attachments = []
        self.message_queue = []
        self.available_models = []
        self.base_url = DEFAULT_SERVER_BASE_URL
        self.config = self.load_config()
        configured_base_url = self.normalize_base_url(self.config.get("base_url", ""))
        if configured_base_url:
            self.base_url = configured_base_url
        self.base_url_history = self.clean_history(
            self.config.get("base_urls", []),
            normalizer=self.normalize_base_url,
        )
        self.base_url_history = self.add_history_value(self.base_url_history, self.base_url)
        self.session_prompt_history = self.clean_history(self.config.get("session_prompts", []))
        self.initial_session_prompt = str(self.config.get("session_prompt", "")).strip()
        if self.initial_session_prompt:
            self.session_prompt_history = self.add_history_value(
                self.session_prompt_history,
                self.initial_session_prompt,
            )
        self.advanced_expanded = False
        self.sidebar_pinned = False
        self.sidebar_open = False
        self.sidebar_collapsed_width = 68
        self.sidebar_scrollbar_allowance = 24
        self.sidebar_expanded_max_width = 380
        self.default_window_width = 1180
        self.default_window_height = 820
        self.toast_label = None
        self.toast_timer = None

        self.configure_responsive_metrics()

        self.setWindowTitle("Agent Chat")
        self.setStyleSheet(APP_STYLE)
        self.resize(self.default_window_width, self.default_window_height)
        self.setMinimumSize(520, 420)

        self.build_ui()
        QApplication.instance().focusChanged.connect(self.on_focus_changed)
        QTimer.singleShot(0, self.refresh_server_state)

    def load_config(self):
        default_config = {
            "base_url": DEFAULT_SERVER_BASE_URL,
            "base_urls": [DEFAULT_SERVER_BASE_URL],
            "session_prompt": "",
            "session_prompts": [],
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
        }
        if not CONFIG_PATH.exists():
            return default_config
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return default_config
        if not isinstance(payload, dict):
            return default_config
        return {**default_config, **payload}

    def save_config(self):
        payload = {
            "base_url": self.base_url,
            "base_urls": self.base_url_history,
            "session_prompt": self.current_session_prompt_value(),
            "session_prompts": self.session_prompt_history,
            "temperature": self.temperature_spin.value() if hasattr(self, "temperature_spin") else 0.7,
            "top_p": self.top_p_spin.value() if hasattr(self, "top_p_spin") else 0.9,
            "top_k": self.top_k_spin.value() if hasattr(self, "top_k_spin") else 40,
        }
        try:
            with CONFIG_PATH.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
        except OSError as exc:
            self.set_status_message(f"Could not save config.json: {exc}")

    def clean_history(self, values, normalizer=None):
        cleaned = []
        if not isinstance(values, list):
            return cleaned
        for value in values:
            if not isinstance(value, str):
                continue
            value = value.strip()
            if normalizer is not None:
                value = normalizer(value)
            if value and value not in cleaned:
                cleaned.append(value)
        return cleaned

    def add_history_value(self, values, value):
        value = value.strip()
        if not value:
            return values
        return [value] + [item for item in values if item != value]

    def current_session_prompt_value(self):
        if self.session_prompt_locked:
            return self.session_system_prompt
        if hasattr(self, "system_prompt_input"):
            return self.system_prompt_input.toPlainText().strip()
        return self.initial_session_prompt

    def configure_responsive_metrics(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        self.default_window_width = max(520, min(1180, available.width() - 40))
        self.default_window_height = max(420, min(820, available.height() - 40))
        self.sidebar_expanded_max_width = max(320, min(420, int(available.width() * 0.4)))

    def target_sidebar_width(self):
        available_width = self.width() or self.default_window_width
        responsive_width = int(available_width * 0.34)
        content_width = max(300, min(self.sidebar_expanded_max_width, responsive_width))
        return content_width + self.sidebar_scrollbar_allowance

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        self.sidebar = self.build_sidebar()
        root.addWidget(self.sidebar)

        self.content_frame = QFrame()
        self.content_frame.setObjectName("surface")
        self.content_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.content_frame.setMinimumWidth(0)
        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setMinimumWidth(0)
        content_layout.addWidget(self.scroll_area)

        self.chat_surface = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_surface)
        self.chat_layout.setContentsMargins(26, 26, 26, 26)
        self.chat_layout.setSpacing(16)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.empty_state = self.build_empty_state()
        self.chat_layout.addWidget(self.empty_state)
        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(0, 0, 0, 0)
        self.messages_layout.setSpacing(16)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.addWidget(self.messages_container)
        self.chat_layout.addStretch()

        self.scroll_area.setWidget(self.chat_surface)

        self.composer_frame = self.build_composer()
        self.composer_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.composer_frame.setMinimumWidth(0)
        content_stack = QVBoxLayout()
        content_stack.setContentsMargins(0, 0, 0, 0)
        content_stack.setSpacing(12)
        content_stack.addWidget(self.content_frame, 1)
        content_stack.addWidget(self.composer_frame)
        root.addLayout(content_stack, 1)

        self.build_toast()
        self.refresh_session_prompt_ui()
        self.update_empty_state()
        self.update_send_availability()

    def build_toast(self):
        self.toast_label = QLabel("", self)
        self.toast_label.setObjectName("toastLabel")
        self.toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_label.hide()

        self.toast_timer = QTimer(self)
        self.toast_timer.setSingleShot(True)
        self.toast_timer.setInterval(1800)
        self.toast_timer.timeout.connect(self.hide_toast)

    def show_toast(self, text):
        if self.toast_label is None:
            return
        self.toast_label.setText(text)
        self.toast_label.adjustSize()
        self.position_toast()
        self.toast_label.raise_()
        self.toast_label.show()
        if self.toast_timer is not None:
            self.toast_timer.start()

    def hide_toast(self):
        if self.toast_label is not None:
            self.toast_label.hide()

    def position_toast(self):
        if self.toast_label is None:
            return
        margin = 18
        x = max(margin, (self.width() - self.toast_label.width()) // 2)
        y = max(margin, self.height() - self.toast_label.height() - margin)
        self.toast_label.move(x, y)

    def build_sidebar(self):
        frame = QFrame()
        frame.setObjectName("sidebar")
        frame.setMinimumWidth(self.sidebar_collapsed_width)
        frame.setMaximumWidth(self.sidebar_collapsed_width)
        frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        frame.enterEvent = self.sidebar_enter_event
        frame.leaveEvent = self.sidebar_leave_event

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        self.sidebar_menu_button = QPushButton("☰")
        self.sidebar_menu_button.setObjectName("sidebarMenuButton")
        self.sidebar_menu_button.setToolTip("Menu")
        self.sidebar_menu_button.clicked.connect(self.toggle_sidebar)
        header_row.addWidget(self.sidebar_menu_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.pin_button = PinIconButton()
        self.pin_button.setObjectName("pinButton")
        self.pin_button.setToolTip("Pin panel")
        self.pin_button.toggled.connect(self.toggle_sidebar_pin)
        self.pin_button.hide()
        header_row.addWidget(self.pin_button, 0, Qt.AlignmentFlag.AlignLeft)
        header_row.addStretch()
        layout.addLayout(header_row)

        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setObjectName("sidebarScroll")
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.sidebar_content = QWidget()
        self.sidebar_content.setObjectName("sidebarScrollBody")
        self.sidebar_content.setMinimumWidth(0)
        content_layout = QVBoxLayout(self.sidebar_content)
        content_layout.setContentsMargins(0, 0, 10, 0)
        content_layout.setSpacing(16)

        title = QLabel("Agent Chat")
        title.setObjectName("titleLabel")
        content_layout.addWidget(title)

        subtitle = QLabel("Model, sampling, and session controls.")
        subtitle.setObjectName("subtleLabel")
        subtitle.setWordWrap(True)
        content_layout.addWidget(subtitle)

        self.status_badge = QLabel("Checking server…")
        self.status_badge.setObjectName("statusBadge")
        content_layout.addWidget(self.status_badge)

        self.status_detail = QLabel("")
        self.status_detail.setObjectName("subtleLabel")
        self.status_detail.setWordWrap(True)
        content_layout.addWidget(self.status_detail)

        self.model_selector = QComboBox()
        self.model_selector.setEditable(False)
        self.model_selector.currentTextChanged.connect(self.update_send_availability)
        content_layout.addWidget(self.model_selector)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("ghostButton")
        self.refresh_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.refresh_button.clicked.connect(self.refresh_server_state)
        buttons_row.addWidget(self.refresh_button)

        self.clear_button = QPushButton("New session")
        self.clear_button.setObjectName("ghostButton")
        self.clear_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.clear_button.clicked.connect(self.clear_chat)
        buttons_row.addWidget(self.clear_button)
        content_layout.addLayout(buttons_row)

        self.advanced_panel = self.build_advanced_panel()
        content_layout.addWidget(self.advanced_panel)
        content_layout.addStretch()

        self.sidebar_scroll.setWidget(self.sidebar_content)
        layout.addWidget(self.sidebar_scroll, 1)
        self.sidebar_scroll.hide()

        self.sidebar_hover_timer = QTimer(self)
        self.sidebar_hover_timer.setSingleShot(True)
        self.sidebar_hover_timer.setInterval(250)
        self.sidebar_hover_timer.timeout.connect(self.expand_sidebar)

        self.sidebar_animation = QPropertyAnimation(frame, b"minimumWidth", self)
        self.sidebar_animation.setDuration(460)
        self.sidebar_animation.setEasingCurve(QEasingCurve.Type.InOutQuart)
        self.sidebar_animation.valueChanged.connect(self.sync_sidebar_width)
        return frame

    def build_advanced_panel(self):
        frame = QFrame()
        frame.setObjectName("panel")
        frame.setMinimumWidth(0)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(16)

        heading = QLabel("Advanced controls")
        heading.setObjectName("sectionLabel")
        layout.addWidget(heading)

        server_heading = QLabel("Server URL")
        server_heading.setObjectName("sectionLabel")
        layout.addWidget(server_heading)

        server_row = QHBoxLayout()
        server_row.setSpacing(8)

        self.base_url_input = DeletableHistoryComboBox()
        self.base_url_input.setEditable(True)
        self.base_url_input.set_history_items(self.base_url_history)
        self.base_url_input.set_history_available(bool(self.base_url_history))
        self.base_url_input.setCurrentText(self.base_url)
        self.base_url_input.setPlaceholderText("http://localhost:8080")
        self.base_url_input.lineEdit().returnPressed.connect(self.apply_base_url)
        self.base_url_input.currentTextChanged.connect(self.on_base_url_text_changed)
        self.base_url_input.activated.connect(self.select_base_url_history_index)
        self.base_url_input.item_delete_requested.connect(self.delete_base_url_history_item)
        server_row.addWidget(self.base_url_input, 1)

        self.apply_url_button = QPushButton("✓")
        self.apply_url_button.setObjectName("fieldIconButton")
        self.apply_url_button.setToolTip("Apply server URL")
        self.apply_url_button.setProperty("applied", True)
        self.apply_url_button.clicked.connect(self.apply_base_url)
        server_row.addWidget(self.apply_url_button)
        layout.addLayout(server_row)

        self.base_url_detail = QLabel(f"Base URL for OpenAI-compatible server: {self.base_url}")
        self.base_url_detail.setObjectName("subtleLabel")
        self.base_url_detail.setWordWrap(True)
        layout.addWidget(self.base_url_detail)

        session_heading = QLabel("Session prompt")
        session_heading.setObjectName("sectionLabel")
        session_header_row = QHBoxLayout()
        session_header_row.setContentsMargins(0, 0, 0, 0)
        session_header_row.setSpacing(8)
        session_header_row.addWidget(session_heading)
        session_header_row.addStretch()

        self.session_prompt_history_button = QPushButton("▾")
        self.session_prompt_history_button.setObjectName("fieldIconButton")
        self.session_prompt_history_button.setToolTip("Select saved session prompt")
        self.session_prompt_history_button.clicked.connect(self.show_session_prompt_history_menu)
        session_header_row.addWidget(self.session_prompt_history_button)

        self.apply_prompt_button = QPushButton("✓")
        self.apply_prompt_button.setObjectName("fieldIconButton")
        self.apply_prompt_button.setToolTip("Apply current session prompt")
        self.apply_prompt_button.clicked.connect(self.apply_session_prompt)
        session_header_row.addWidget(self.apply_prompt_button)
        layout.addLayout(session_header_row)

        self.system_prompt_input = QPlainTextEdit()
        self.system_prompt_input.setPlaceholderText("Optional instruction to lock in for this session.")
        self.system_prompt_input.setFixedHeight(92)
        if self.initial_session_prompt:
            self.system_prompt_input.setPlainText(self.initial_session_prompt)
        self.system_prompt_input.textChanged.connect(self.refresh_session_prompt_ui)
        layout.addWidget(self.system_prompt_input)

        self.session_prompt_badge = QLabel("")
        self.session_prompt_badge.setObjectName("sessionPromptBadge")
        self.session_prompt_badge.setWordWrap(True)
        layout.addWidget(self.session_prompt_badge)

        self.session_prompt_detail = QLabel("")
        self.session_prompt_detail.setObjectName("subtleLabel")
        self.session_prompt_detail.setWordWrap(True)
        layout.addWidget(self.session_prompt_detail)

        prompt_actions = QHBoxLayout()
        prompt_actions.setSpacing(10)

        self.unlock_prompt_button = QPushButton("Edit draft")
        self.unlock_prompt_button.setObjectName("secondaryButton")
        self.unlock_prompt_button.clicked.connect(self.unlock_session_prompt)
        prompt_actions.addWidget(self.unlock_prompt_button)

        self.clear_prompt_button = QPushButton("Clear prompt")
        self.clear_prompt_button.setObjectName("ghostButton")
        self.clear_prompt_button.clicked.connect(self.clear_session_prompt_text)
        prompt_actions.addWidget(self.clear_prompt_button)
        prompt_actions.addStretch()
        layout.addLayout(prompt_actions)

        thinking_row = QHBoxLayout()
        thinking_row.setSpacing(10)

        thinking_label = QLabel("Reasoning")
        thinking_label.setObjectName("sectionLabel")
        thinking_row.addWidget(thinking_label)

        self.show_thinking_checkbox = QCheckBox("Show thinking")
        self.show_thinking_checkbox.setChecked(False)
        self.show_thinking_checkbox.toggled.connect(self.update_thinking_visibility)
        thinking_row.addWidget(self.show_thinking_checkbox)
        thinking_row.addStretch()
        layout.addLayout(thinking_row)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(10)
        preset_label = QLabel("Presets")
        preset_label.setObjectName("sectionLabel")
        preset_row.addWidget(preset_label)

        self.precise_button = QPushButton("Precise")
        self.precise_button.clicked.connect(lambda: self.apply_preset("precise"))
        preset_row.addWidget(self.precise_button)

        self.balanced_button = QPushButton("Balanced")
        self.balanced_button.clicked.connect(lambda: self.apply_preset("balanced"))
        preset_row.addWidget(self.balanced_button)

        self.creative_button = QPushButton("Creative")
        self.creative_button.clicked.connect(lambda: self.apply_preset("creative"))
        preset_row.addWidget(self.creative_button)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        sampling_layout = QFormLayout()
        sampling_layout.setSpacing(12)
        sampling_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setDecimals(2)
        self.temperature_spin.setSingleStep(0.05)
        self.temperature_spin.setValue(float(self.config.get("temperature", 0.7)))
        self.temperature_spin.valueChanged.connect(lambda _value: self.save_config())
        sampling_layout.addRow("Temperature", self.temperature_spin)

        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setRange(0.0, 1.0)
        self.top_p_spin.setDecimals(2)
        self.top_p_spin.setSingleStep(0.05)
        self.top_p_spin.setValue(float(self.config.get("top_p", 0.9)))
        self.top_p_spin.valueChanged.connect(lambda _value: self.save_config())
        sampling_layout.addRow("Top P", self.top_p_spin)

        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(1, 200)
        self.top_k_spin.setValue(int(self.config.get("top_k", 40)))
        self.top_k_spin.valueChanged.connect(lambda _value: self.save_config())
        sampling_layout.addRow("Top K", self.top_k_spin)
        layout.addLayout(sampling_layout)

        return frame

    def build_empty_state(self):
        frame = QFrame()
        frame.setObjectName("panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        title = QLabel("Ready for a better local chat loop")
        title.setObjectName("emptyTitle")
        layout.addWidget(title)

        body = QLabel(
            "Pick a model, set an optional session prompt, then start chatting."
        )
        body.setObjectName("emptyBody")
        body.setWordWrap(True)
        layout.addWidget(body)

        actions = QHBoxLayout()
        actions.setSpacing(10)

        refresh = QPushButton("Refresh models")
        refresh.clicked.connect(self.refresh_server_state)
        actions.addWidget(refresh)

        clear = QPushButton("New session")
        clear.setObjectName("ghostButton")
        clear.clicked.connect(self.clear_chat)
        actions.addWidget(clear)
        actions.addStretch()
        layout.addLayout(actions)
        return frame

    def build_composer(self):
        frame = QFrame()
        frame.setObjectName("composerFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 0, 10, 10)
        layout.setSpacing(0)

        canvas = QFrame()
        canvas.setObjectName("composerCanvas")
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(14, 12, 10, 8)
        canvas_layout.setSpacing(8)

        self.attachment_scroll = QScrollArea()
        self.attachment_scroll.setObjectName("attachmentScroll")
        self.attachment_scroll.setWidgetResizable(True)
        self.attachment_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.attachment_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.attachment_scroll.setFixedHeight(58)

        self.attachments_wrap = QWidget()
        self.attachments_layout = QHBoxLayout(self.attachments_wrap)
        self.attachments_layout.setContentsMargins(0, 0, 0, 0)
        self.attachments_layout.setSpacing(10)
        self.attachments_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.attachment_scroll.setWidget(self.attachments_wrap)
        self.attachment_scroll.hide()
        canvas_layout.addWidget(self.attachment_scroll)

        self.queue_banner = QFrame()
        self.queue_banner.setObjectName("queueBanner")
        queue_layout = QHBoxLayout(self.queue_banner)
        queue_layout.setContentsMargins(12, 10, 12, 10)
        queue_layout.setSpacing(10)

        self.queue_badge = QLabel("0")
        self.queue_badge.setObjectName("queueBadge")
        queue_layout.addWidget(self.queue_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.queue_banner_text = QLabel("Queue empty")
        self.queue_banner_text.setObjectName("queueBannerText")
        self.queue_banner_text.setWordWrap(True)
        queue_layout.addWidget(self.queue_banner_text, 1)

        self.queue_banner.hide()
        canvas_layout.addWidget(self.queue_banner)

        self.composer = AutoResizingTextEdit()
        self.composer.send_requested.connect(self.send_message)
        self.composer.attachment_paths_pasted.connect(self.add_attachment_paths)
        self.composer.textChanged.connect(self.update_send_availability)
        canvas_layout.addWidget(self.composer)

        footer_row = QHBoxLayout()
        footer_row.setSpacing(12)

        self.attach_button = QPushButton("+")
        self.attach_button.setObjectName("composerPlusButton")
        self.attach_button.setToolTip("Add files")
        self.attach_button.clicked.connect(self.add_attachments)
        footer_row.addWidget(self.attach_button)

        self.composer_hint = QLabel("Shift+Enter for newline")
        self.composer_hint.setObjectName("subtleLabel")
        self.composer_hint.hide()

        self.queue_label = QLabel("Queue empty")
        self.queue_label.setObjectName("subtleLabel")
        self.queue_label.hide()

        footer_row.addStretch()

        self.clear_attachments_button = QPushButton("Clear files")
        self.clear_attachments_button.setObjectName("ghostButton")
        self.clear_attachments_button.clicked.connect(self.clear_attachments)
        self.clear_attachments_button.hide()
        footer_row.addWidget(self.clear_attachments_button)

        self.send_button = SvgActionButton(ARROW_UP_ICON_PATH)
        self.send_button.setObjectName("iconActionButton")
        self.send_button.setProperty("variant", "send")
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setToolTip("Send")
        self.send_button.clicked.connect(self.handle_send_action_button)
        footer_row.addWidget(self.send_button)

        canvas_layout.addLayout(footer_row)
        layout.addWidget(canvas)
        return frame

    def apply_preset(self, preset):
        if preset == "precise":
            self.temperature_spin.setValue(0.2)
            self.top_p_spin.setValue(0.85)
            self.top_k_spin.setValue(30)
        elif preset == "creative":
            self.temperature_spin.setValue(1.0)
            self.top_p_spin.setValue(0.97)
            self.top_k_spin.setValue(80)
        else:
            self.temperature_spin.setValue(0.7)
            self.top_p_spin.setValue(0.9)
            self.top_k_spin.setValue(40)
        self.show_toast(f"{preset.title()} preset applied")

    def detect_attachment_type(self, path):
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type:
            if mime_type.startswith("image/"):
                return "image"
            if mime_type.startswith("video/"):
                return "video"
            if mime_type.startswith("audio/"):
                return "audio"
        suffix = Path(path).suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}:
            return "image"
        if suffix in {".mp4", ".mov", ".mkv", ".avi", ".webm"}:
            return "video"
        if suffix in {".wav", ".mp3", ".m4a", ".ogg", ".flac"}:
            return "audio"
        return "file"

    def is_text_preview_file(self, path):
        return Path(path).suffix.lower() in TEXT_PREVIEW_SUFFIXES

    def add_attachments(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Attach files",
            "",
            "Supported Files (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.pdf *.txt *.md *.doc *.docx *.csv *.json *.wav *.mp3 *.mp4 *.mov *.mkv);;All Files (*)",
        )
        self.add_attachment_paths(paths)

    def add_attachment_paths(self, paths):
        if not paths:
            return
        added = False
        for path in paths:
            if not path or any(item["path"] == path for item in self.pending_attachments):
                continue
            self.pending_attachments.append(
                {
                    "path": path,
                    "name": Path(path).name,
                    "type": self.detect_attachment_type(path),
                }
            )
            added = True
        if added:
            self.refresh_attachment_summary()
            self.update_send_availability()

    def clear_attachments(self):
        self.pending_attachments = []
        self.refresh_attachment_summary()
        self.update_send_availability()

    def attachment_area_height(self):
        if not self.pending_attachments:
            return 58
        has_images = any(item["type"] == "image" for item in self.pending_attachments)
        return 122 if has_images else 58

    def refresh_attachment_summary(self):
        while self.attachments_layout.count():
            item = self.attachments_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self.pending_attachments:
            self.attachment_scroll.setFixedHeight(self.attachment_area_height())
            self.attachment_scroll.hide()
            return

        self.attachment_scroll.setFixedHeight(self.attachment_area_height())
        self.attachment_scroll.show()
        for attachment in self.pending_attachments:
            chip = AttachmentChip(attachment)
            chip.remove_requested.connect(self.remove_attachment)
            chip.preview_requested.connect(self.open_attachment_item)
            self.attachments_layout.addWidget(chip)

        self.attachments_layout.addStretch()

    def remove_attachment(self, path):
        self.pending_attachments = [item for item in self.pending_attachments if item["path"] != path]
        self.refresh_attachment_summary()
        self.update_send_availability()

    def open_attachment_item(self, clicked_path):
        image_paths = [item["path"] for item in self.pending_attachments if item["type"] == "image"]
        if clicked_path in image_paths:
            start_index = image_paths.index(clicked_path)
            dialog = ImageGalleryDialog(image_paths, start_index=start_index, parent=self)
            dialog.exec()
            return
        self.open_file_attachment(clicked_path)

    def open_file_attachment(self, path):
        if self.is_text_preview_file(path):
            dialog = FilePreviewDialog(path, parent=self)
            dialog.exec()
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))

    def encode_attachment(self, path):
        with open(path, "rb") as handle:
            return base64.b64encode(handle.read()).decode("utf-8")

    def image_data_url_for_prompt(self, path):
        suffix = Path(path).suffix.lower()
        mime_type = mimetypes.guess_type(path)[0] or "image/png"

        if suffix in {".png", ".jpg", ".jpeg"}:
            encoded = self.encode_attachment(path)
            return f"data:{mime_type};base64,{encoded}"

        image = QImage(path)
        if image.isNull():
            raise ValueError(f"Unable to decode image file: {Path(path).name}")

        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            buffer.close()
            raise ValueError(f"Unable to convert image file to PNG: {Path(path).name}")

        encoded = base64.b64encode(bytes(buffer.data())).decode("utf-8")
        buffer.close()
        return f"data:image/png;base64,{encoded}"

    def read_text_attachment(self, path):
        try:
            content = Path(path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
        return content

    def read_pdf_attachment(self, path):
        if PdfReader is None:
            return (
                "PDF extraction is unavailable because the optional dependency "
                "`pypdf` is not installed."
            )
        reader = PdfReader(path)
        parts = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                parts.append(f"[Page {page_number}]\n{text}")
            if sum(len(part) for part in parts) >= MAX_ATTACHMENT_TEXT_CHARS:
                break
        if not parts:
            return "No extractable text was found in this PDF."
        return "\n\n".join(parts)

    def attachment_text_for_prompt(self, attachment):
        path = attachment["path"]
        suffix = Path(path).suffix.lower()
        try:
            if suffix == ".pdf":
                content = self.read_pdf_attachment(path)
            elif self.is_text_preview_file(path):
                content = self.read_text_attachment(path)
            else:
                return ""
        except Exception as exc:
            return f"Unable to read file content: {exc}"

        content = content.strip()
        if len(content) > MAX_ATTACHMENT_TEXT_CHARS:
            content = content[:MAX_ATTACHMENT_TEXT_CHARS] + "\n\n[Truncated]"
        return content

    def detect_urls(self, text):
        urls = []
        seen = set()
        for match in URL_RE.finditer(text):
            url = match.group(0).rstrip(TRAILING_URL_PUNCTUATION)
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
            if len(urls) >= MAX_URLS_PER_MESSAGE:
                break
        return urls

    def sidebar_enter_event(self, event):
        self.sidebar_hover_timer.start()
        event.accept()

    def sidebar_leave_event(self, event):
        self.sidebar_hover_timer.stop()
        QTimer.singleShot(120, self.collapse_sidebar_if_idle)
        event.accept()

    def sidebar_has_active_interaction(self):
        if self.sidebar.underMouse() or self.sidebar_scroll.underMouse() or self.sidebar_content.underMouse():
            return True

        focus_widget = QApplication.focusWidget()
        if focus_widget is not None and (
            focus_widget == self.sidebar or self.sidebar.isAncestorOf(focus_widget)
        ):
            return True

        if any(child.hasFocus() for child in self.sidebar.findChildren(QWidget)):
            return True

        for combo in self.sidebar.findChildren(QComboBox):
            view = combo.view()
            if view is not None and (view.isVisible() or view.underMouse()):
                return True

        return False

    def collapse_sidebar_if_idle(self):
        if self.sidebar_pinned:
            return
        if self.sidebar_has_active_interaction():
            return
        self.collapse_sidebar()

    def on_focus_changed(self, _old, _new):
        if not self.sidebar_open or self.sidebar_pinned:
            return
        QTimer.singleShot(0, self.collapse_sidebar_if_idle)

    def sync_sidebar_width(self, value):
        width = int(value)
        self.sidebar.setMinimumWidth(width)
        self.sidebar.setMaximumWidth(width)

    def expand_sidebar(self):
        self.sidebar_open = True
        self.pin_button.show()
        self.sidebar_scroll.show()
        self.animate_sidebar(self.target_sidebar_width())

    def collapse_sidebar(self):
        self.sidebar_open = False
        self.pin_button.hide()
        self.animate_sidebar(self.sidebar_collapsed_width)

    def toggle_sidebar(self):
        if self.sidebar_open:
            if self.sidebar_pinned:
                self.pin_button.setChecked(False)
            else:
                self.collapse_sidebar()
            return
        self.expand_sidebar()

    def toggle_sidebar_pin(self, checked):
        self.sidebar_pinned = checked
        self.pin_button.setProperty("pinned", checked)
        self.pin_button.style().unpolish(self.pin_button)
        self.pin_button.style().polish(self.pin_button)
        if checked:
            self.expand_sidebar()
        else:
            self.collapse_sidebar_if_idle()

    def animate_sidebar(self, target_width):
        self.sidebar_animation.stop()
        self.sidebar_animation.setStartValue(self.sidebar.width())
        self.sidebar_animation.setEndValue(target_width)
        self.sidebar_animation.start()
        if target_width == self.sidebar_collapsed_width:
            self.sidebar_animation.finished.connect(self.finish_sidebar_collapse)
        else:
            try:
                self.sidebar_animation.finished.disconnect(self.finish_sidebar_collapse)
            except TypeError:
                pass

    def finish_sidebar_collapse(self):
        if self.sidebar.width() <= self.sidebar_collapsed_width:
            self.sidebar_scroll.hide()
        try:
            self.sidebar_animation.finished.disconnect(self.finish_sidebar_collapse)
        except TypeError:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.sidebar_open:
            self.sync_sidebar_width(self.target_sidebar_width())
        self.position_toast()

    def refresh_server_state(self):
        self.status_badge.setText("Checking OpenAI-compatible server…")
        self.status_detail.setText(f"Refreshing server state from {self.base_url}.")
        self.model_selector.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.apply_url_button.setEnabled(False)

        try:
            health_url = self.build_server_url("/health")
            models_url = self.build_server_url("/v1/models")
            health_response = requests.get(health_url, timeout=2)
            if health_response.status_code != 200:
                self.set_disconnected_state(f"OpenAI-compatible server health returned HTTP {health_response.status_code}.")
                return

            response = requests.get(models_url, timeout=2)
            if response.status_code != 200:
                self.set_disconnected_state(f"OpenAI-compatible server returned HTTP {response.status_code}.")
                return

            payload = response.json()
            models = [item.get("id", "") for item in payload.get("data", []) if item.get("id")]
            self.available_models = models
            self.populate_models(models)

            if models:
                self.status_badge.setText("Connected")
                self.status_detail.setText(f"{len(models)} model(s) available from {self.base_url}.")
            else:
                self.status_badge.setText("No models loaded")
                self.status_detail.setText(f"Start OpenAI-compatible server with a loaded model at {self.base_url}.")
        except requests.exceptions.ConnectionError:
            self.set_disconnected_state(f"OpenAI-compatible server is not reachable at {self.base_url}.")
        except Exception as exc:
            self.set_disconnected_state(f"Failed to refresh models: {exc}")
        finally:
            self.refresh_button.setEnabled(True)
            self.update_base_url_input_state()
            self.update_send_availability()

    def populate_models(self, models):
        current_text = self.model_selector.currentText().strip()
        self.model_selector.blockSignals(True)
        self.model_selector.clear()
        if models:
            self.model_selector.addItems(models)
            if current_text and current_text in models:
                self.model_selector.setCurrentText(current_text)
        self.model_selector.blockSignals(False)
        self.model_selector.setEnabled(bool(models))

    def set_disconnected_state(self, detail):
        self.available_models = []
        self.model_selector.blockSignals(True)
        self.model_selector.clear()
        self.model_selector.blockSignals(False)
        self.model_selector.setEnabled(False)
        self.status_badge.setText("Disconnected")
        self.status_detail.setText(detail)

    def normalize_base_url(self, raw_value):
        value = raw_value.strip()
        if not value:
            return ""
        if "://" not in value:
            value = f"http://{value}"
        return value.rstrip("/")

    def build_server_url(self, path):
        return f"{self.base_url}{path}"

    def on_base_url_text_changed(self, _text):
        self.update_base_url_input_state()

    def update_base_url_input_state(self):
        if not hasattr(self, "apply_url_button"):
            return
        current = self.normalize_base_url(self.base_url_input.currentText())
        applied = bool(current) and current == self.base_url
        self.apply_url_button.setProperty("applied", applied)
        self.apply_url_button.setEnabled(bool(current))
        self.apply_url_button.style().unpolish(self.apply_url_button)
        self.apply_url_button.style().polish(self.apply_url_button)

    def refresh_base_url_history_ui(self):
        self.base_url_input.set_history_items(self.base_url_history)
        self.base_url_input.setCurrentText(self.base_url)
        self.base_url_input.set_history_available(bool(self.base_url_history))

    def refresh_session_prompt_history_ui(self):
        if hasattr(self, "session_prompt_history_button"):
            self.session_prompt_history_button.setEnabled(bool(self.session_prompt_history))

    def select_base_url_history_index(self, index):
        value = self.base_url_input.itemData(index) or self.base_url_input.itemText(index)
        self.select_base_url_history(value)

    def select_base_url_history(self, value):
        value = self.normalize_base_url(value)
        if not value:
            return
        self.base_url_input.setCurrentText(value)
        self.apply_base_url()

    def delete_base_url_history_item(self, value):
        value = self.normalize_base_url(value)
        self.base_url_history = [item for item in self.base_url_history if item != value]
        if not self.base_url_history:
            self.base_url_history = [DEFAULT_SERVER_BASE_URL]
        if self.base_url == value:
            self.base_url = self.base_url_history[0]
            self.base_url_detail.setText(f"Base URL for OpenAI-compatible server: {self.base_url}")
        self.refresh_base_url_history_ui()
        self.save_config()

    def select_session_prompt_history(self, value):
        if self.session_prompt_locked:
            self.set_status_message("Start a new session before changing the active session prompt.")
            return
        self.system_prompt_input.setPlainText(value)
        self.refresh_session_prompt_ui()
        self.save_config()

    def delete_session_prompt_history_item(self, value):
        value = value.strip()
        self.session_prompt_history = [item for item in self.session_prompt_history if item != value]
        if self.current_session_prompt_value() == value and not self.session_prompt_locked:
            self.system_prompt_input.clear()
        self.refresh_session_prompt_history_ui()
        self.save_config()

    def show_session_prompt_history_menu(self):
        if not self.session_prompt_history:
            return

        menu = QMenu(self)
        for value in self.session_prompt_history:
            display_value = " ".join(value.split())
            if len(display_value) > 90:
                display_value = display_value[:87] + "..."
            action = menu.addAction(display_value)
            action.triggered.connect(lambda _checked=False, prompt=value: self.select_session_prompt_history(prompt))

        delete_menu = menu.addMenu("Delete saved prompt")
        for value in self.session_prompt_history:
            display_value = " ".join(value.split())
            if len(display_value) > 90:
                display_value = display_value[:87] + "..."
            action = delete_menu.addAction(display_value)
            action.triggered.connect(lambda _checked=False, prompt=value: self.delete_session_prompt_history_item(prompt))

        menu.exec(self.session_prompt_history_button.mapToGlobal(self.session_prompt_history_button.rect().bottomLeft()))

    def apply_base_url(self):
        value = self.normalize_base_url(self.base_url_input.currentText())
        if not value:
            self.set_status_message("Enter a valid server URL.")
            return
        self.base_url = value
        self.base_url_history = self.add_history_value(self.base_url_history, value)
        self.base_url_input.setCurrentText(value)
        self.base_url_detail.setText(f"Base URL for OpenAI-compatible server: {value}")
        self.refresh_base_url_history_ui()
        self.update_base_url_input_state()
        self.save_config()
        self.show_toast("Server URL applied")
        self.refresh_server_state()

    def update_send_availability(self):
        has_text = bool(self.composer.toPlainText().strip()) or bool(self.pending_attachments)
        has_model = bool(self.available_models) and bool(self.model_selector.currentText().strip())
        busy = self.worker is not None and self.worker.isRunning()
        if has_text:
            self.configure_send_action_button("send", enabled=has_model)
        elif busy:
            self.configure_send_action_button("stop", enabled=True)
        else:
            self.configure_send_action_button("send", enabled=False)
        self.model_selector.setEnabled(bool(self.available_models) and not busy)
        self.attach_button.setEnabled(True)
        self.clear_attachments_button.setEnabled(bool(self.pending_attachments))
        self.refresh_queue_ui()

    def configure_send_action_button(self, mode, enabled):
        icon_path = STOP_ICON_PATH if mode == "stop" else ARROW_UP_ICON_PATH
        tooltip = "Stop" if mode == "stop" else "Send"
        self.send_button.setProperty("variant", mode)
        self.send_button.setToolTip(tooltip)
        self.send_button.setEnabled(enabled)
        self.send_button.set_icon_path(icon_path)
        self.send_button.style().unpolish(self.send_button)
        self.send_button.style().polish(self.send_button)

    def handle_send_action_button(self):
        if self.send_button.property("variant") == "stop":
            self.stop_generation()
            return
        self.send_message()

    def refresh_queue_ui(self):
        count = len(self.message_queue)
        if count == 0:
            self.queue_label.setText("Queue empty")
            self.queue_badge.setText("0")
            self.queue_banner_text.setText("No queued messages.")
            self.queue_banner.hide()
            return
        noun = "message" if count == 1 else "messages"
        self.queue_label.setText(f"{count} queued {noun}")
        self.queue_badge.setText(str(count))
        self.queue_banner_text.setText(
            f"{count} queued {noun}. New messages will send automatically in order."
        )
        self.queue_banner.show()

    def make_submission(self, user_text, attachments):
        prompt_text = user_text.strip()
        self.set_status_message("Preparing message...")
        user_message = self.build_user_message(prompt_text, attachments)
        user_display = prompt_text or "Sent attachments."
        if attachments:
            names = ", ".join(item["name"] for item in attachments)
            user_display = f"{user_display}\n\nAttachments: {names}"
        return {
            "user_text": prompt_text,
            "attachments": attachments,
            "user_message": user_message,
            "user_display": user_display,
            "model_name": self.model_selector.currentText().strip(),
        }

    def try_make_submission(self, user_text, attachments):
        try:
            return self.make_submission(user_text, attachments)
        except ValueError as exc:
            self.set_status_message(str(exc))
            return None

    def enqueue_current_input(self):
        user_text = self.composer.toPlainText().strip()
        attachments = list(self.pending_attachments)
        if not user_text and not attachments:
            return False

        model_name = self.model_selector.currentText().strip()
        if not model_name:
            self.set_status_message("Select a model before sending.")
            return False

        submission = self.try_make_submission(user_text, attachments)
        if submission is None:
            return False
        self.message_queue.append(submission)
        self.composer.clear()
        self.clear_attachments()
        self.status_badge.setText("Queued")
        queued_count = len(self.message_queue)
        noun = "message" if queued_count == 1 else "messages"
        self.status_detail.setText(f"Added to queue. {queued_count} queued {noun}.")
        self.refresh_queue_ui()
        self.composer.setFocus()
        return True

    def process_submission(self, submission):
        self.lock_session_prompt_if_needed()
        self.last_submitted_user_text = submission["user_text"]
        self.pending_user_text = submission["user_text"]
        self.pending_user_message = submission["user_message"]

        self.add_message("user", submission["user_display"], attachments=submission["attachments"])

        self.current_assistant_card = self.add_message(
            "assistant",
            "",
            retry_text=submission["user_text"],
        )
        self.current_assistant_card.start_loading()

        queue_count = len(self.message_queue)
        suffix = f" {queue_count} queued." if queue_count else ""
        self.status_badge.setText("Generating")
        self.status_detail.setText(f"Streaming from {submission['model_name']}.{suffix}")

        self.worker = ChatCompletionWorker(self)
        self.worker.configure(
            base_url=self.base_url,
            model_name=submission["model_name"],
            messages=self.build_messages_payload(submission["user_message"]),
            temperature=self.temperature_spin.value(),
            top_p=self.top_p_spin.value(),
            top_k=self.top_k_spin.value(),
        )
        self.worker.token_received.connect(self.on_token_received)
        self.worker.thinking_received.connect(self.on_thinking_received)
        self.worker.generation_started.connect(self.on_generation_started)
        self.worker.generation_finished.connect(self.on_generation_finished)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()
        self.update_send_availability()

    def process_next_queued_message(self):
        if self.worker is not None and self.worker.isRunning():
            return
        if not self.message_queue:
            self.refresh_queue_ui()
            return
        submission = self.message_queue.pop(0)
        self.refresh_queue_ui()
        self.process_submission(submission)

    def has_session_messages(self):
        return bool(self.history)

    def apply_session_prompt(self):
        if self.has_session_messages() or (self.worker is not None and self.worker.isRunning()):
            self.set_status_message("Start a new session before changing the active session prompt.")
            return
        value = self.system_prompt_input.toPlainText().strip()
        if not value:
            self.set_status_message("Enter a session prompt before applying it.")
            return
        self.session_prompt_history = self.add_history_value(self.session_prompt_history, value)
        self.refresh_session_prompt_history_ui()
        self.refresh_session_prompt_ui()
        self.save_config()
        self.set_status_message("Session prompt saved to config.json.")
        self.show_toast("Session prompt saved")

    def lock_session_prompt_if_needed(self):
        if self.session_prompt_locked:
            return
        self.session_system_prompt = self.system_prompt_input.toPlainText().strip()
        if self.session_system_prompt:
            self.session_prompt_history = self.add_history_value(
                self.session_prompt_history,
                self.session_system_prompt,
            )
            self.refresh_session_prompt_history_ui()
            self.save_config()
        self.session_prompt_locked = True
        self.refresh_session_prompt_ui()

    def unlock_session_prompt(self):
        if self.has_session_messages() or (self.worker is not None and self.worker.isRunning()):
            self.set_status_message("Start a new session before changing the active session prompt.")
            return
        self.session_prompt_locked = False
        self.session_system_prompt = ""
        self.refresh_session_prompt_ui()

    def clear_session_prompt_text(self):
        if self.has_session_messages() or (self.worker is not None and self.worker.isRunning()):
            self.set_status_message("Start a new session before clearing the active session prompt.")
            return
        self.system_prompt_input.clear()
        self.session_system_prompt = ""
        self.session_prompt_locked = False
        self.save_config()
        self.refresh_session_prompt_ui()

    def refresh_session_prompt_ui(self):
        draft_text = self.system_prompt_input.toPlainText().strip()
        active_text = self.session_system_prompt if self.session_prompt_locked else draft_text
        preview = active_text if active_text else "No session prompt"
        if len(preview) > 140:
            preview = preview[:137] + "..."

        self.system_prompt_input.setReadOnly(self.session_prompt_locked)
        self.session_prompt_badge.setText(preview)

        if self.session_prompt_locked:
            self.session_prompt_detail.setText(
                "Locked for the current session. Start a new session to change it."
            )
        elif draft_text:
            self.session_prompt_detail.setText(
                "Draft prompt ready. It will lock in on the first send of the next session."
            )
        else:
            self.session_prompt_detail.setText(
                "Leave blank for a normal session, or write an instruction that should persist for the whole session."
            )

        self.unlock_prompt_button.setVisible(self.session_prompt_locked)
        self.clear_prompt_button.setEnabled(bool(draft_text) and not self.session_prompt_locked)
        self.apply_prompt_button.setEnabled(bool(draft_text) and not self.session_prompt_locked)
        self.apply_prompt_button.setProperty("applied", self.session_prompt_locked)
        self.apply_prompt_button.style().unpolish(self.apply_prompt_button)
        self.apply_prompt_button.style().polish(self.apply_prompt_button)
        self.refresh_session_prompt_history_ui()

    def build_user_message(self, user_text, attachments):
        if not attachments:
            return {"role": "user", "content": user_text}

        prompt = user_text or "Describe the attached inputs."
        content = [{"type": "text", "text": prompt}]
        attachment_sections = []
        for item in attachments:
            if item["type"] == "image":
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": self.image_data_url_for_prompt(item["path"])},
                    }
                )
            else:
                extracted = self.attachment_text_for_prompt(item)
                if extracted:
                    attachment_sections.append(
                        f"File: {item['name']}\n```text\n{extracted}\n```"
                    )
                else:
                    attachment_sections.append(
                        f"File attached: {item['name']} (binary or unsupported for inline extraction)."
                    )
        if attachment_sections:
            content[0]["text"] = (
                f"{content[0]['text']}\n\nAttached file contents:\n\n" + "\n\n".join(attachment_sections)
            )
        return {"role": "user", "content": content}

    def build_messages_payload(self, user_message):
        messages = []
        if self.session_system_prompt:
            messages.append({"role": "system", "content": self.session_system_prompt})
        messages.extend(self.history)
        messages.append(user_message)
        return messages

    def send_message(self):
        if self.worker is not None and self.worker.isRunning():
            self.enqueue_current_input()
            return

        user_text = self.composer.toPlainText().strip()
        attachments = list(self.pending_attachments)
        if not user_text and not attachments:
            return

        model_name = self.model_selector.currentText().strip()
        if not model_name:
            self.set_status_message("Select a model before sending.")
            return

        submission = self.try_make_submission(user_text, attachments)
        if submission is None:
            return
        self.composer.clear()
        self.clear_attachments()
        self.process_submission(submission)

    def retry_message(self, user_text):
        if self.worker is not None and self.worker.isRunning():
            self.composer.setPlainText(user_text)
            self.composer.moveCursor(self.composer.textCursor().MoveOperation.End)
            self.enqueue_current_input()
            return
        self.composer.setPlainText(user_text)
        self.composer.moveCursor(self.composer.textCursor().MoveOperation.End)
        self.send_message()

    def on_generation_started(self):
        self.update_send_availability()

    def on_token_received(self, token):
        if self.current_assistant_card is not None:
            self.current_assistant_card.stop_loading()
            if not self.current_assistant_card.raw_text:
                self.current_assistant_card.update_text(token)
            else:
                self.current_assistant_card.append_text(token)
        self.scroll_to_bottom()

    def on_thinking_received(self, token):
        if self.current_assistant_card is not None:
            self.current_assistant_card.append_thinking(token, self.show_thinking_checkbox.isChecked())
        self.scroll_to_bottom()

    def on_generation_finished(self, success, stopped, full_response, _full_thinking):
        if self.current_assistant_card is not None:
            self.current_assistant_card.stop_loading()
        if success and self.pending_user_message and full_response.strip():
            self.history.append(self.pending_user_message)
            self.history.append({"role": "assistant", "content": full_response})
            self.status_badge.setText("Ready")
            self.status_detail.setText("Response completed.")
        elif stopped:
            self.status_badge.setText("Stopped")
            self.status_detail.setText("Generation stopped. The partial answer was not added to context.")
            if self.current_assistant_card and not full_response.strip():
                self.current_assistant_card.update_text("_Stopped before any response arrived._")
        else:
            if self.current_assistant_card and not full_response.strip():
                self.current_assistant_card.update_text("_No response received._")

        self.pending_user_text = None
        self.pending_user_message = None
        self.current_assistant_card = None
        self.worker = None
        self.process_next_queued_message()
        self.update_send_availability()
        self.composer.setFocus()

    def on_error(self, message):
        self.status_badge.setText("Request failed")
        self.status_detail.setText(message)
        self.add_message("system", message)
        self.process_next_queued_message()

    def stop_generation(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()

    def add_message(self, role, text, retry_text=None, attachments=None):
        timestamp = datetime.now().strftime("%H:%M")
        card = MessageCard(
            role=role,
            text=text,
            timestamp=timestamp,
            retry_text=retry_text,
            attachments=attachments,
        )
        card.retry_requested.connect(self.retry_message)
        card.image_preview_requested.connect(self.open_message_image_gallery)
        card.file_preview_requested.connect(self.open_file_attachment)
        self.messages_layout.addWidget(card)
        self.update_empty_state()
        self.scroll_to_bottom()
        return card

    def open_message_image_gallery(self, image_paths, start_index):
        if not image_paths:
            return
        dialog = ImageGalleryDialog(image_paths, start_index=start_index, parent=self)
        dialog.exec()

    def set_status_message(self, text):
        self.status_badge.setText("Notice")
        self.status_detail.setText(text)

    def update_thinking_visibility(self, *_args):
        visible = self.show_thinking_checkbox.isChecked()
        for index in range(self.messages_layout.count()):
            item = self.messages_layout.itemAt(index)
            widget = item.widget()
            if isinstance(widget, MessageCard):
                widget.set_thinking_visibility(visible)

    def update_empty_state(self):
        self.empty_state.setVisible(self.messages_layout.count() == 0)

    def scroll_to_bottom(self):
        QTimer.singleShot(
            0,
            lambda: self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            ),
        )

    def clear_chat(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.history = []
        self.pending_user_text = None
        self.pending_user_message = None
        self.message_queue = []
        previous_prompt = self.session_system_prompt or self.system_prompt_input.toPlainText().strip()
        self.session_system_prompt = ""
        self.session_prompt_locked = False
        self.system_prompt_input.setPlainText(previous_prompt)
        self.current_assistant_card = None
        self.clear_attachments()
        self.status_badge.setText("Ready")
        self.status_detail.setText("New session started.")
        self.refresh_session_prompt_ui()
        self.refresh_queue_ui()
        self.update_empty_state()
        self.update_send_availability()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("IBM Plex Sans", 10))

    window = AgentChatWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
