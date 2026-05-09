"""Button and icon widgets."""

from pathlib import Path

from PyQt6.QtCore import QByteArray, QRectF, Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QLabel, QPushButton, QSizePolicy, QWidget

from constants import ARROW_RIGHT_ICON_PATH, PIN_ICON_PATH


def format_elapsed_time_text(elapsed):
    """Format elapsed seconds into human-readable string like '1h 30m 45s' or '45s'."""
    total_seconds = max(0, int(elapsed))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return "".join(parts)


def elided_text_lines(text, font, width, max_lines=2):
    """Elide text to fit within width, returning list of lines."""
    text = " ".join(str(text or "").split())
    if not text:
        return [""]
    metrics = QFontMetrics(font)
    width = int(width)
    if width < 120:
        width = 480
    if metrics.horizontalAdvance(text) <= width:
        return [text]
    if max_lines <= 1:
        return [metrics.elidedText(text, Qt.TextElideMode.ElideRight, width)]

    words = text.split(" ")
    lines = []
    index = 0
    while index < len(words) and len(lines) < max_lines:
        if len(lines) == max_lines - 1:
            lines.append(metrics.elidedText(
                " ".join(words[index:]), Qt.TextElideMode.ElideRight, width
            ))
            break
        line = words[index]
        index += 1
        while index < len(words):
            test_line = line + " " + words[index]
            if metrics.horizontalAdvance(test_line) <= width:
                line = test_line
                index += 1
            else:
                break
        lines.append(line)
    return lines


class PinIconButton(QPushButton):
    """A button with a pin icon that can be toggled."""

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
    """A button that renders an SVG icon with dynamic color."""

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


class RotatingSvgButton(SvgActionButton):
    """An SVG button that can rotate its icon."""

    def __init__(self, icon_path=None, parent=None):
        super().__init__(icon_path, parent)
        self.rotation_degrees = 0

    def set_rotation(self, degrees):
        self.rotation_degrees = degrees
        self.update()

    def paintEvent(self, event):
        QPushButton.paintEvent(self, event)
        if not self._svg_template:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().buttonText().color().name()
        svg = self._svg_template.replace("currentColor", color)
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        target = QRectF(self.rect().adjusted(8, 8, -8, -8))
        painter.translate(target.center())
        painter.rotate(self.rotation_degrees)
        painter.translate(-target.center())
        renderer.render(painter, target)


class ThinkingTitleLabel(QLabel):
    """A label that displays thinking phase title with shimmer animation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.title_text = "Analyzing request"
        self.shimmer_index = 0
        self.shimmer_active = False
        self._preferred_width = 0
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        font = self.font()
        font.setWeight(QFont.Weight.DemiBold)
        self.setFont(font)
        line_height = QFontMetrics(self.font()).lineSpacing()
        self.setMinimumHeight(line_height * 2 + 6)
        self.setMaximumHeight(line_height * 2 + 6)
        self.timer = QTimer(self)
        self.timer.setInterval(45)
        self.timer.timeout.connect(self.advance_shimmer)

    def set_title(self, text):
        text = (text or "").strip() or "Analyzing request"
        if text == self.title_text:
            return
        self.title_text = text
        self.shimmer_index = 0
        self.render_title()

    def set_shimmer_active(self, active):
        active = bool(active)
        if self.shimmer_active == active:
            return
        self.shimmer_active = active
        if active:
            self.timer.start()
        else:
            self.timer.stop()
            self.shimmer_index = 0
        self.render_title()

    def advance_shimmer(self):
        self.shimmer_index = (self.shimmer_index + 0.55) % max(1, len(self.title_text))
        self.render_title()

    def render_title(self):
        self.sync_height_to_lines()
        self.update()

    def title_lines(self):
        return elided_text_lines(self.title_text, self.font(), max(120, self.width()), max_lines=2)

    def sync_height_to_lines(self):
        line_count = max(1, len(self.title_lines()))
        line_height = QFontMetrics(self.font()).lineSpacing()
        height = line_height * line_count + 6
        if self.minimumHeight() != height or self.maximumHeight() != height:
            self.setMinimumHeight(height)
            self.setMaximumHeight(height)
            self.updateGeometry()

    def preferred_width_for(self, available):
        """Calculate preferred width for given available width."""
        lines = self.title_lines()
        if not lines:
            return 0
        metrics = QFontMetrics(self.font())
        return max(metrics.horizontalAdvance(line) for line in lines)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self.font())
        metrics = QFontMetrics(self.font())
        line_height = metrics.lineSpacing()
        baseline = metrics.ascent() + 2
        char_index = 0

        for line_index, line in enumerate(self.title_lines()):
            y = baseline + line_index * line_height
            if not self.shimmer_active:
                painter.setPen(QColor("#78818b"))
                painter.drawText(0, y, line)
                continue

            x = 0
            for char in line:
                distance = min(
                    abs(char_index - self.shimmer_index),
                    max(1, len(self.title_text)) - abs(char_index - self.shimmer_index),
                )
                opacity = max(0.3, 1.0 - distance * 0.4)
                color = QColor("#78818b")
                color.setAlphaF(opacity)
                painter.setPen(color)
                painter.drawText(x, y, char)
                x += metrics.horizontalAdvance(char)
                char_index += 1


class ThinkingPhaseHeader(QWidget):
    """Header widget for thinking/work phases with title, timer, and expand arrow."""

    toggled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("thinkingPhaseHeader")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.title_label = ThinkingTitleLabel()
        self.title_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.title_label.installEventFilter(self)
        layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.timer_label = QLabel("0s")
        self.timer_label.setObjectName("thinkingTimerLabel")
        self.timer_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.timer_label.installEventFilter(self)
        layout.addWidget(self.timer_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.arrow_button = RotatingSvgButton(ARROW_RIGHT_ICON_PATH)
        self.arrow_button.setObjectName("thinkingArrowButton")
        self.arrow_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.arrow_button.clicked.connect(self.toggled.emit)
        layout.addWidget(self.arrow_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch()

    def set_title(self, title):
        self.title_label.set_title(title)
        self.update_title_width()
        QTimer.singleShot(0, self.update_title_width)

    def set_elapsed_text(self, text):
        self.timer_label.setText(text)
        self.update_title_width()
        QTimer.singleShot(0, self.update_title_width)

    def set_expanded(self, expanded):
        self.arrow_button.set_rotation(90 if expanded else 0)

    def set_active(self, active):
        self.title_label.set_shimmer_active(active)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggled.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self.toggled.emit()
            return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_title_width()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_title_width()
        QTimer.singleShot(0, self.update_title_width)

    def update_title_width(self):
        reserved = self.timer_label.sizeHint().width() + self.arrow_button.width() + 28
        available = max(120, self.width() - reserved)
        title_width = min(available, self.title_label.preferred_width_for(available))
        self.title_label.setFixedWidth(max(24, title_width))
        self.title_label.render_title()