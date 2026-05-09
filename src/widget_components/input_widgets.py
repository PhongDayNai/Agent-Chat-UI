"""Input widgets - combo boxes, text edits, spin boxes."""

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QPlainTextEdit,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTextBrowser,
)


class DeletableHistoryDelegate(QStyledItemDelegate):
    """Delegate for history combo box with delete button."""

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
    """Combo box with deletable history items."""

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
    """Spin box that ignores mouse wheel events."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)

    def wheelEvent(self, event):
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """Double spin box that ignores mouse wheel events."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)

    def wheelEvent(self, event):
        event.ignore()


class AutoResizingTextEdit(QPlainTextEdit):
    """Plain text edit that auto-resizes based on content."""

    send_requested = pyqtSignal()
    attachment_paths_pasted = pyqtSignal(list)

    def __init__(self, parent=None, max_lines=3):
        super().__init__(parent)
        self.max_lines = max_lines
        self.document().setIndentWidth(0)
        self.document().setTextWidth(self.document().idealWidth())
        self.setProperty("is_multiline_input", True)
        self.setProperty("sendable", True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMaximumHeight(self.sizeHint().height())
        self.textChanged.connect(self._handle_text_change)
        self._suppress_resize = False

    def _handle_text_change(self):
        if self._suppress_resize:
            return
        self._resize_to_content()

    def _resize_to_content(self):
        document_size = self.document().size()
        line_count = max(1, int(document_size.height()))
        if self.max_lines and line_count > self.max_lines:
            line_count = self.max_lines
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        else:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        fm = self.fontMetrics()
        line_height = fm.lineSpacing()
        content_height = line_height * line_count + self.contentsMargins().top() + self.contentsMargins().bottom() + 6

        if self.maximumHeight() != content_height:
            self._suppress_resize = True
            self.setMaximumHeight(content_height)
            self._suppress_resize = False
            self.updateGeometry()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            event.accept()
            self.send_requested.emit()
        else:
            super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        if source.hasImage():
            image = source.imageData()
            if image:
                from pathlib import Path
                from datetime import datetime
                temp_dir = Path.home() / ".cache" / "acu" / "clipboard"
                temp_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                image_path = temp_dir / f"clipboard_{timestamp}.png"
                image.save(str(image_path))
                self.attachment_paths_pasted.emit([str(image_path)])
                return
        super().insertFromMimeData(source)


class AutoHeightTextBrowser(QTextBrowser):
    """Text browser that auto-resizes to content height."""

    def __init__(self, parent=None, max_height=None):
        super().__init__(parent)
        self._max_height = max_height or 300
        self.setOpenExternalLinks(True)
        self.setProperty("user", False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.document().setIndentWidth(0)
        self.textChanged.connect(self._update_height)

    def _update_height(self):
        height = min(self.document().size().height() + 20, self._max_height)
        if height != self.maximumHeight():
            self.setMaximumHeight(height)
            self.updateGeometry()

    def setSource(self, source):
        super().setSource(source)
        self._update_height()

    def update_height(self):
        self._update_height()