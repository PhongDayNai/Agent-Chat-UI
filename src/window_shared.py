"""Shared constants and small widgets for the main window."""

import html

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPainterPath, QPixmap, QRegion
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

TERMINAL_PERMISSION_DEFAULT = "default"
TERMINAL_PERMISSION_FULL_ACCESS = "full_access"
DEFAULT_TERMINAL_PERMISSIONS = ["pwd", "ls", "date", "whoami", "uname"]
DEFAULT_ASSISTANT_DEBOUNCE_ENABLED = True
DEFAULT_ASSISTANT_DEBOUNCE_INTERVAL_MS = 45
DEFAULT_COMPOSER_MAX_LINES = 3
MIN_COMPOSER_MAX_LINES = 1
MAX_COMPOSER_MAX_LINES = 20
TERMINAL_PERMISSION_COLORS = {
    TERMINAL_PERMISSION_DEFAULT: "#f2f3f5",
    TERMINAL_PERMISSION_FULL_ACCESS: "#d5c537",
}
SIDEBAR_DROPDOWN_TEXT_INSET = "  "
SIDEBAR_ELIDE_WIDTH = 320
COMPACT_LAYOUT_WIDTH = 900
COMPACT_LAYOUT_HEIGHT = 760
COMPACT_SIDEBAR_WIDTH = 420
COMPACT_SIDEBAR_MIN_WIDTH = 340
COMPACT_WINDOW_GUTTER = 0
CHARACTER_CARD_RATIOS = ("2:3", "3:2", "1:1", "9:16", "16:9")
DEFAULT_CHARACTER_CARD_RATIO = "2:3"
CHARACTER_CARD_MIN_WIDTH = 190
CHARACTER_CARD_MAX_WIDTH = 240
CHARACTER_CARD_MIN_HEIGHT = 270
CHARACTER_CARD_MAX_HEIGHT = 350
CHARACTER_CARD_RADIUS = 20


class ClippedSidebarFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.clip_radius = 24

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.apply_clip_mask()

    def apply_clip_mask(self):
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(0, 0, width, height),
            self.clip_radius,
            self.clip_radius,
        )
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))


class StatusBadge(QLabel):
    STATUS_DOT_COLORS = {
        "connected": "#70d56b",
        "ready": "#70d56b",
        "checking": "#c5a85b",
        "queued": "#c5a85b",
        "generating": "#c5a85b",
        "permission needed": "#c5a85b",
        "no models loaded": "#c5a85b",
        "disconnected": "#9aa0a6",
        "dismissed": "#9aa0a6",
        "stopped": "#9aa0a6",
        "request failed": "#e16b6b",
    }

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.RichText)
        if text:
            self.setText(text)

    def setText(self, text):
        label = str(text)
        dot_color = self.STATUS_DOT_COLORS.get(label.lower(), "#9aa0a6")
        safe_label = html.escape(label)
        super().setText(
            f"<span style='color:{dot_color};'>●</span>"
            f"<span style='color:#c8cdd2;'>&nbsp;{safe_label}</span>"
        )


class CharacterChoiceCard(QFrame):
    selected = pyqtSignal(str)

    def __init__(self, character, pixmap=None, card_ratio=DEFAULT_CHARACTER_CARD_RATIO, parent=None):
        super().__init__(parent)
        self.character = character
        self.cover_pixmap = pixmap if pixmap and not pixmap.isNull() else QPixmap()
        self.card_height = 214
        self.card_ratio = self.normalize_card_ratio(card_ratio)
        self.collapsed_panel_height = 108
        self.expanded_panel_height = 168
        self.current_panel_height = self.collapsed_panel_height
        self.expanded = False
        self.panel_animation = None
        self.setObjectName("characterChoiceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(CHARACTER_CARD_MIN_WIDTH)
        self.setMaximumWidth(CHARACTER_CARD_MAX_WIDTH)
        self.setFixedHeight(self.card_height)

        self.cover_label = QLabel("", self)
        self.cover_label.setObjectName("characterChoiceCover")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if self.cover_pixmap.isNull():
            initials = "".join(part[:1] for part in character.get("name", "").split()[:2]).upper()
            self.cover_label.setText(initials or "AI")

        self.info_panel = QFrame(self)
        self.info_panel.setObjectName("characterChoiceInfo")
        info_layout = QVBoxLayout(self.info_panel)
        info_layout.setContentsMargins(14, 14, 14, 12)
        info_layout.setSpacing(5)
        info_layout.addStretch(1)

        self.name_label = QLabel(character.get("name", "Character"))
        self.name_label.setObjectName("characterChoiceName")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.name_label)

        meta_parts = []
        if character.get("style"):
            meta_parts.append(character.get("style", "").title())
        meta_parts.extend(character.get("tags", [])[:3])
        self.meta_label = QLabel(" · ".join(meta_parts))
        self.meta_label.setObjectName("characterChoiceMeta")
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.meta_label.setVisible(bool(meta_parts))
        info_layout.addWidget(self.meta_label)

        self.description_label = QLabel(character.get("description", ""))
        self.description_label.setObjectName("characterChoiceDescription")
        self.description_label.setWordWrap(True)
        self.description_label.hide()
        info_layout.addWidget(self.description_label)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_card_height()
        self.apply_rounded_mask()
        self.position_content()

    def normalize_card_ratio(self, value):
        ratio = str(value or DEFAULT_CHARACTER_CARD_RATIO).strip()
        return ratio if ratio in CHARACTER_CARD_RATIOS else DEFAULT_CHARACTER_CARD_RATIO

    def set_card_ratio(self, value):
        self.card_ratio = self.normalize_card_ratio(value)
        self.update_card_height()
        self.apply_rounded_mask()
        self.position_content()

    def update_card_height(self):
        width = max(0, self.width())
        if width <= 0:
            return
        ratio_width, ratio_height = (int(part) for part in self.card_ratio.split(":"))
        target_height = round(width * ratio_height / ratio_width)
        target_height = max(CHARACTER_CARD_MIN_HEIGHT, min(CHARACTER_CARD_MAX_HEIGHT, target_height))
        if target_height != self.card_height:
            self.card_height = target_height
            self.setFixedHeight(self.card_height)
            self.apply_rounded_mask()

    def apply_rounded_mask(self):
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(0, 0, width - 1, height - 1),
            CHARACTER_CARD_RADIUS,
            CHARACTER_CARD_RADIUS,
        )
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def position_content(self):
        width = max(0, self.width())
        height = max(0, self.height())
        if width <= 0 or height <= 0:
            return
        self.cover_label.setGeometry(0, 0, width, height)
        if not self.cover_pixmap.isNull():
            self.cover_label.setPixmap(
                self.cover_pixmap.scaled(
                    QSize(width, height),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        panel_height = int(self.current_panel_height)
        self.info_panel.setGeometry(0, height - panel_height, width, panel_height)
        self.cover_label.lower()
        self.info_panel.raise_()

    def animate_panel(self, target_height):
        if self.panel_animation is not None:
            self.panel_animation.stop()
        self.panel_animation = QPropertyAnimation(self.info_panel, b"minimumHeight", self)
        self.panel_animation.setDuration(220)
        self.panel_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.panel_animation.setStartValue(int(self.current_panel_height))
        self.panel_animation.setEndValue(target_height)
        self.panel_animation.valueChanged.connect(self.update_panel_height)
        self.panel_animation.finished.connect(lambda: self.update_panel_height(target_height))
        self.panel_animation.start()

    def update_panel_height(self, value):
        self.current_panel_height = int(value)
        self.position_content()

    def enterEvent(self, event):
        self.expanded = True
        self.setProperty("expanded", True)
        self.description_label.show()
        self.animate_panel(self.expanded_panel_height)
        self.position_content()
        self.style().unpolish(self)
        self.style().polish(self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.expanded = False
        self.setProperty("expanded", False)
        self.description_label.hide()
        self.animate_panel(self.collapsed_panel_height)
        self.position_content()
        self.style().unpolish(self)
        self.style().polish(self)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.character.get("id", ""))
        super().mousePressEvent(event)
