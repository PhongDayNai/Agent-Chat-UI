"""Dialog widgets: image gallery, file preview."""

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout


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