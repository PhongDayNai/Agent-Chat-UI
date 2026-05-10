"""Attachment widgets: image preview button, attachment chip."""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


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