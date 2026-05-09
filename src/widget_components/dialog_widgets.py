"""Dialog widgets for image gallery and file preview."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from styles import MARKDOWN_STYLESHEET


class ImageGalleryDialog(QDialog):
    """Dialog for browsing multiple images with navigation."""

    def __init__(self, image_paths, start_index=0, parent=None):
        super().__init__(parent)
        self.image_paths = image_paths
        self.current_index = start_index
        self.setWindowTitle("Image Gallery")
        self.setMinimumSize(640, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(False)
        layout.addWidget(self.image_label)

        self._update_image()

    def _update_image(self):
        if 0 <= self.current_index < len(self.image_paths):
            pixmap = QPixmap(self.image_paths[self.current_index])
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.image_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.image_label.setPixmap(scaled)

    def go_to_index(self, index):
        if 0 <= index < len(self.image_paths):
            self.current_index = index
            self._update_image()


class FilePreviewDialog(QDialog):
    """Dialog for previewing file content (text or images)."""

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle(Path(file_path).name)
        self.setMinimumSize(640, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.text_browser = QLabel()
        self.text_browser.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.text_browser.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.text_browser)

        self._load_content()

    def _load_content(self):
        path = Path(self.file_path)
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico"}:
            pixmap = QPixmap(self.file_path)
            if not pixmap.isNull():
                for i in reversed(range(self.layout().count())):
                    widget = self.layout().itemAt(i).widget()
                    if widget == self.text_browser:
                        self.layout().removeWidget(widget)
                        widget.deleteLater()
                        break
                image_label = QLabel()
                image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                image_label.setPixmap(pixmap.scaled(
                    self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                ))
                self.layout().addWidget(image_label)
        else:
            try:
                content = path.read_text(encoding="utf-8")
                self.text_browser.setText(content)
            except UnicodeDecodeError:
                self.text_browser.setText("[Binary file]")
            except OSError:
                self.text_browser.setText("[File not found]")