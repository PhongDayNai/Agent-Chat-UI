"""Input widgets: history combo box, spin boxes, text edits."""

from datetime import datetime
from math import ceil
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QImage, QPainter, QPixmap, QTextCursor, QTextOption
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QPlainTextEdit,
    QSizePolicy,
    QSpinBox,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QTextBrowser,
)

from constants import CLIPBOARD_IMAGE_DIR


def show_widget_toast(widget, text):
    window = widget.window() if widget is not None else None
    if window is not None and hasattr(window, "show_toast"):
        window.show_toast(text)


def link_hover_tooltip(anchor):
    from html import escape
    if anchor.startswith("copy-code:"):
        title = "Copy code"
        lines = ("Click to copy this code snippet.",)
    else:
        title = "Link"
        lines = ("Click to copy.", "Ctrl+click to open in browser.")
    body = "<br>".join(escape(line, quote=False) for line in lines)
    return (
        '<html><body style="margin:0;">'
        '<div style="width:210px; white-space:normal;">'
        f'<div style="font-weight:600; color:#f4f5f6; margin-bottom:4px;">{title}</div>'
        f'<div style="color:#c7cacf; line-height:1.35;">{body}</div>'
        "</div></body></html>"
    )


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

    def wheelEvent(self, event):
        event.ignore()

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


class NoWheelSpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)

    def wheelEvent(self, event):
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)

    def wheelEvent(self, event):
        event.ignore()


class AutoResizingTextEdit(QPlainTextEdit):
    send_requested = pyqtSignal()
    attachment_paths_pasted = pyqtSignal(list)

    def __init__(self, parent=None, max_lines=3):
        super().__init__(parent)
        self._min_lines = 1
        try:
            self._max_lines = max(1, int(max_lines))
        except (TypeError, ValueError):
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
        self.recalculate_height_bounds()
        self.textChanged.connect(self.update_height)
        self.textChanged.connect(self.keep_cursor_visible)
        self.cursorPositionChanged.connect(self.keep_cursor_visible)
        self.update_height()

    def keyPressEvent(self, event):
        if (
            event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down)
            and not event.modifiers()
        ):
            previous_position = self.textCursor().position()
            super().keyPressEvent(event)
            cursor = self.textCursor()
            if cursor.position() == previous_position:
                operation = (
                    QTextCursor.MoveOperation.StartOfLine
                    if event.key() == Qt.Key.Key_Up
                    else QTextCursor.MoveOperation.EndOfLine
                )
                cursor.movePosition(operation)
                self.setTextCursor(cursor)
            return

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
                return
            if not event.modifiers():
                self.send_requested.emit()
                return
        super().keyPressEvent(event)

    def set_max_lines(self, value):
        try:
            max_lines = int(value)
        except (TypeError, ValueError):
            max_lines = 3
        self._max_lines = max(1, max_lines)
        self.recalculate_height_bounds()
        self.update_height()

    def max_lines(self):
        return self._max_lines

    def recalculate_height_bounds(self):
        line_spacing = self.fontMetrics().lineSpacing()
        chrome_height = (self.frameWidth() * 2) + (self._vertical_inset * 2) + 8
        self._min_height = line_spacing * self._min_lines + chrome_height
        self._max_height = line_spacing * self._max_lines + chrome_height

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
        self.setMinimumWidth(0)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)
        self.setMouseTracking(True)
        self.setMaximumHeight(16777215)
        self.anchorClicked.connect(self.handle_anchor_clicked)
        self.update_height()

    def handle_anchor_clicked(self, url):
        from urllib.parse import unquote
        url_text = url.toString()
        if url_text.startswith("copy-code:"):
            QGuiApplication.clipboard().setText(unquote(url_text[len("copy-code:"):]))
            show_widget_toast(self, "Code copied")
            return
        from PyQt6.QtGui import QDesktopServices
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
            QDesktopServices.openUrl(url)
            return
        QGuiApplication.clipboard().setText(url.toString())
        show_widget_toast(self, "Link copied")

    def mouseMoveEvent(self, event):
        anchor = self.anchorAt(event.position().toPoint())
        self.viewport().setCursor(
            Qt.CursorShape.PointingHandCursor if anchor else Qt.CursorShape.IBeamCursor
        )
        self.setToolTip(link_hover_tooltip(anchor) if anchor else "")
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.viewport().unsetCursor()
        self.setToolTip("")
        super().leaveEvent(event)

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