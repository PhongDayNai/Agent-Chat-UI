"""Reusable Qt widgets used by the chat window."""

from datetime import datetime
from math import ceil
from pathlib import Path

from PyQt6.QtCore import QByteArray, QEvent, QRectF, QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QGuiApplication, QIcon, QImage, QPainter, QPixmap, QTextOption
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from constants import COPY_ICON_PATH, PIN_ICON_PATH, RETRY_ICON_PATH
from styles import MARKDOWN_STYLESHEET

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
