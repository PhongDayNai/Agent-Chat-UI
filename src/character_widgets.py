"""Custom Character Mode widgets for Agent Chat UI v2.0."""

from __future__ import annotations

from PyQt6.QtCore import QByteArray, QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from characters import character_accent, character_role, should_render_full_poster
from constants import FILE_ICON_PATH, LINK_ICON_PATH, STAR_ICON_PATH, TERMINAL_ICON_PATH


def _qcolor(hex_value: str, alpha: int | None = None) -> QColor:
    color = QColor(hex_value)
    if alpha is not None:
        color.setAlpha(alpha)
    return color


def character_initials(character: dict) -> str:
    name = str((character or {}).get("name") or "AI").strip()
    parts = [part for part in name.split() if part]
    return "".join(part[0] for part in parts[:2]).upper() or "AI"


_SVG_CACHE: dict[tuple[str, str, str], QByteArray] = {}


def colored_svg_data(path, color: str, fill_color: str = "none") -> QByteArray:
    key = (str(path), color, fill_color)
    if key in _SVG_CACHE:
        return _SVG_CACHE[key]
    try:
        svg = path.read_text(encoding="utf-8") if hasattr(path, "read_text") else ""
    except OSError:
        svg = ""
    svg = svg.replace("currentColor", color)
    svg = svg.replace("#f2f3f5", color)
    if fill_color != "none":
        svg = svg.replace('fill="none"', f'fill="{fill_color}"')
    data = QByteArray(svg.encode("utf-8"))
    _SVG_CACHE[key] = data
    return data


def render_svg_pixmap(path, size: QSize, color: str, fill_color: str = "none") -> QPixmap:
    pixmap = QPixmap(size)
    pixmap.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(colored_svg_data(path, color, fill_color))
    if not renderer.isValid():
        return pixmap
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size.width(), size.height()))
    painter.end()
    return pixmap


def draw_svg_icon(painter: QPainter, path, rect: QRectF, color: str, fill_color: str = "none"):
    renderer = QSvgRenderer(colored_svg_data(path, color, fill_color))
    if renderer.isValid():
        renderer.render(painter, rect)


def cover_crop_pixmap(pixmap: QPixmap, target_size: QSize, focus_y: float = 0.42) -> QPixmap:
    if pixmap.isNull() or target_size.width() <= 0 or target_size.height() <= 0:
        return QPixmap()

    tw = target_size.width()
    th = target_size.height()
    sw = pixmap.width()
    sh = pixmap.height()

    target_ratio = tw / th
    source_ratio = sw / sh

    if source_ratio > target_ratio:
        crop_h = sh
        crop_w = int(sh * target_ratio)
        x = max(0, (sw - crop_w) // 2)
        y = 0
    else:
        crop_w = sw
        crop_h = int(sw / target_ratio)
        x = 0
        desired_center_y = int(sh * focus_y)
        y = max(0, min(sh - crop_h, desired_center_y - crop_h // 2))

    cropped = pixmap.copy(x, y, crop_w, crop_h)
    return cropped.scaled(target_size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)


class SwitchPill(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = bool(checked)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        checked = bool(checked)
        if self._checked == checked:
            return
        self._checked = checked
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self.toggled.emit(self._checked)
            self.update()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._checked = not self._checked
            self.toggled.emit(self._checked)
            self.update()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        track_color = QColor("#7c6cff") if self._checked else QColor("#111827")
        border_color = QColor("#7c6cff") if self._checked else QColor("#3b4658")
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(track_color)
        painter.drawRoundedRect(QRectF(rect), 12, 12)

        knob_size = 18
        x = rect.right() - knob_size - 2 if self._checked else rect.left() + 2
        knob_rect = QRect(x, rect.top() + 2, knob_size, knob_size)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff") if self._checked else QColor("#94a3b8"))
        painter.drawEllipse(knob_rect)


class CharacterPosterCard(QFrame):
    selected = pyqtSignal(str)

    def __init__(self, character=None, pixmap=None, selected=False, render_full_poster=None, parent=None):
        super().__init__(parent)
        self.character = character or {}
        self.pixmap = pixmap if pixmap and not pixmap.isNull() else QPixmap()
        self.is_selected = bool(selected)
        self.hovered = False
        self.focused = False
        self.radius = 22
        self.render_full_poster = should_render_full_poster(self.character) if render_full_poster is None else bool(render_full_poster)
        self.setObjectName("characterPosterCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(180, 250)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        self.apply_shadow()

    def apply_shadow(self, mode: str = "normal"):
        shadow = QGraphicsDropShadowEffect(self)
        if mode == "light":
            shadow.setBlurRadius(14)
            shadow.setOffset(0, 6)
            shadow.setColor(QColor(0, 0, 0, 90))
        else:
            shadow.setBlurRadius(34 if self.is_selected else 24)
            shadow.setOffset(0, 12)
            shadow.setColor(QColor(0, 0, 0, 145))
        self.setGraphicsEffect(shadow)

    def set_shadow_mode(self, mode: str):
        self.apply_shadow(mode)

    def set_character(self, character: dict, pixmap=None, selected=None, render_full_poster=None):
        self.character = character or {}
        self.pixmap = pixmap if pixmap and not pixmap.isNull() else QPixmap()
        if selected is not None:
            self.is_selected = bool(selected)
        self.render_full_poster = should_render_full_poster(self.character) if render_full_poster is None else bool(render_full_poster)
        self.apply_shadow()
        self.update()

    def set_selected(self, selected: bool):
        self.is_selected = bool(selected)
        self.apply_shadow()
        self.update()

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self.focused = True
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.focused = False
        self.update()
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.character.get("id", ""))
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.selected.emit(self.character.get("id", ""))
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = self.radius
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)

        painter.save()
        painter.setClipPath(path)
        self.paint_background(painter, rect)

        if not self.pixmap.isNull() and self.render_full_poster:
            painter.drawPixmap(rect, cover_crop_pixmap(self.pixmap, rect.size()))
        elif not self.pixmap.isNull():
            self.paint_avatar_fallback(painter, rect)
        else:
            self.paint_placeholder(painter, rect)

        painter.fillRect(rect, QColor(0, 0, 0, 18))
        self.paint_bottom_gradient(painter, rect)
        painter.restore()

        self.paint_border(painter, rect, radius)
        self.paint_selected_badge(painter, rect)
        self.paint_text_overlay(painter, rect)

    def paint_background(self, painter, rect):
        bg = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.bottomRight()))
        bg.setColorAt(0.0, QColor("#182235"))
        bg.setColorAt(0.55, QColor("#111827"))
        bg.setColorAt(1.0, QColor("#0b1018"))
        painter.fillRect(rect, bg)

    def paint_placeholder(self, painter, rect):
        gradient = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.bottomRight()))
        gradient.setColorAt(0.0, QColor("#1e293b"))
        gradient.setColorAt(0.55, QColor("#111827"))
        gradient.setColorAt(1.0, QColor("#0f172a"))
        painter.fillRect(rect, gradient)

        initials_rect = QRect(rect.center().x() - 44, rect.top() + max(62, rect.height() // 4), 88, 88)
        accent = _qcolor(character_accent(self.character))
        bg = QColor(accent)
        bg.setAlpha(44)
        border = QColor(accent)
        border.setAlpha(90)
        painter.setBrush(bg)
        painter.setPen(QPen(border, 1))
        painter.drawEllipse(initials_rect)
        painter.setPen(accent.lighter(140))
        font = painter.font()
        font.setPointSize(25)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(initials_rect, Qt.AlignmentFlag.AlignCenter, character_initials(self.character))

    def paint_avatar_fallback(self, painter, rect):
        self.paint_background(painter, rect)
        avatar_size = min(116, max(86, rect.width() // 3))
        avatar_rect = QRect(rect.center().x() - avatar_size // 2, rect.top() + 62, avatar_size, avatar_size)
        path = QPainterPath()
        path.addRoundedRect(QRectF(avatar_rect), 28, 28)
        painter.save()
        painter.setClipPath(path)
        painter.drawPixmap(avatar_rect, cover_crop_pixmap(self.pixmap, avatar_rect.size(), focus_y=0.42))
        painter.restore()
        accent = _qcolor(character_accent(self.character), 110)
        painter.setPen(QPen(accent, 2))
        painter.drawRoundedRect(QRectF(avatar_rect), 28, 28)

    def paint_bottom_gradient(self, painter, rect):
        gradient = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        gradient.setColorAt(0.00, QColor(7, 11, 20, 0))
        gradient.setColorAt(0.38, QColor(7, 11, 20, 28))
        gradient.setColorAt(0.70, QColor(7, 11, 20, 190))
        gradient.setColorAt(1.00, QColor(7, 11, 20, 248))
        painter.fillRect(rect, gradient)

    def paint_border(self, painter, rect, radius):
        if self.is_selected:
            border = QColor("#7c6cff")
            pen_width = 2
        elif self.focused:
            border = QColor("#22d3ee")
            pen_width = 2
        elif self.hovered:
            border = QColor("#4b5d7a")
            pen_width = 1
        else:
            border = QColor("#293448")
            pen_width = 1
        painter.setPen(QPen(border, pen_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(rect), radius, radius)
        if self.is_selected:
            glow_rect = rect.adjusted(3, 3, -3, -3)
            painter.setPen(QPen(QColor(124, 108, 255, 85), 1))
            painter.drawRoundedRect(QRectF(glow_rect), radius - 4, radius - 4)

    def paint_selected_badge(self, painter, rect):
        if not self.is_selected:
            return
        badge_rect = QRect(rect.right() - 54, rect.top() + 14, 40, 40)
        painter.setBrush(QColor("#7c6cff"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(badge_rect)
        painter.setPen(QColor("#ffffff"))
        font = painter.font()
        font.setPointSize(15)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, "✓")

    def paint_text_overlay(self, painter, rect):
        name = self.character.get("name", "Character")
        role = character_role(self.character)
        tags = self.character.get("tags", [])[:3]
        accent = _qcolor(character_accent(self.character))
        left = rect.left() + 26
        right = rect.right() - 24
        bottom = rect.bottom() - 24

        font = painter.font()
        font.setPointSize(20)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRect(left, bottom - 112, right - left, 40), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        role_width = min(metrics.horizontalAdvance(role) + 26, right - left)
        role_rect = QRect(left, bottom - 72, role_width, 30)
        role_bg = QColor(accent)
        role_bg.setAlpha(70)
        role_border = QColor(accent)
        role_border.setAlpha(105)
        painter.setBrush(role_bg)
        painter.setPen(QPen(role_border, 1))
        painter.drawRoundedRect(QRectF(role_rect), 9, 9)
        painter.setPen(accent.lighter(135))
        painter.drawText(role_rect, Qt.AlignmentFlag.AlignCenter, role)
        self.paint_tag_chips(painter, tags, left, right, bottom - 32)

    def paint_tag_chips(self, painter, tags, left, right, y):
        font = painter.font()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        x = left
        for tag in tags:
            label = str(tag).strip()
            if not label:
                continue
            width = metrics.horizontalAdvance(label) + 20
            if x + width > right:
                break
            tag_rect = QRect(x, y, width, 24)
            painter.setBrush(QColor(35, 42, 50, 166))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(tag_rect), 12, 12)
            painter.setPen(QColor("#e5e7eb"))
            painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, label)
            x += width + 6


class CharacterSidebarHeroCard(CharacterPosterCard):
    clicked = pyqtSignal()
    favorite_toggled = pyqtSignal(str)

    def __init__(self, character=None, pixmap=None, favorite=False, parent=None):
        super().__init__(character=character or {}, pixmap=pixmap, selected=False, parent=parent)
        self.favorite = bool(favorite)
        self.radius = 9
        self.setObjectName("characterSidebarHeroCard")
        self.setMinimumHeight(180)
        self.setMaximumHeight(280)

    def set_character(self, character: dict, pixmap=None, favorite: bool = False, render_full_poster=None):
        self.favorite = bool(favorite)
        super().set_character(character, pixmap, selected=False, render_full_poster=render_full_poster)

    def favorite_rect(self) -> QRectF:
        rect = QRectF(self.rect())
        size = 36.0
        return QRectF(rect.right() - 12.0 - size, rect.top() + 15.0, size, size)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.favorite_rect().contains(event.position()):
                self.favorite_toggled.emit(self.character.get("id", ""))
            else:
                self.clicked.emit()
            return
        super().mousePressEvent(event)

    def paint_border(self, painter, rect, radius):
        border = QColor("#4b5d7a") if self.hovered else QColor("#293448")
        painter.setPen(QPen(border, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(rect), radius, radius)

        highlight = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.left() + rect.width() * 0.72, rect.top() + rect.height() * 0.45))
        highlight.setColorAt(0.00, QColor(255, 255, 255, 95))
        highlight.setColorAt(0.18, QColor(124, 108, 255, 95))
        highlight.setColorAt(0.42, QColor(96, 165, 250, 42))
        highlight.setColorAt(1.00, QColor(96, 165, 250, 0))
        painter.setPen(QPen(highlight, 1.4))
        painter.drawRoundedRect(QRectF(rect.adjusted(1, 1, -1, -1)), radius, radius)

    def paint_bottom_gradient(self, painter, rect):
        super().paint_bottom_gradient(painter, rect)
        bloom = QRadialGradient(QPointF(rect.left() + 40, rect.top() + 22), 170)
        bloom.setColorAt(0.0, QColor(255, 255, 255, 42))
        bloom.setColorAt(0.28, QColor(124, 108, 255, 35))
        bloom.setColorAt(0.65, QColor(96, 165, 250, 12))
        bloom.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(rect, bloom)

    def paint_selected_badge(self, painter, rect):
        fav = self.favorite_rect()
        painter.setBrush(QColor(8, 12, 20, 176))
        painter.setPen(QPen(QColor(255, 255, 255, 45), 1.0))
        painter.drawEllipse(fav.adjusted(0.5, 0.5, -0.5, -0.5))

        icon_size = 18
        icon_center = fav.center()
        icon_rect = QRectF(
            icon_center.x() - icon_size / 2,
            icon_center.y() - icon_size / 2 - 0.9,
            icon_size,
            icon_size,
        )
        color = "#facc15" if self.favorite else "#cbd5e1"
        fill = "#facc15" if self.favorite else "none"
        draw_svg_icon(painter, STAR_ICON_PATH, icon_rect, color, fill)

    def paint_text_overlay(self, painter, rect):
        name = self.character.get("name", "Character")
        role = character_role(self.character)
        tags = self.character.get("tags", [])[:3]
        accent = _qcolor(character_accent(self.character))
        left = rect.left() + 18
        right = rect.right() - 18
        bottom = rect.bottom() - 9

        font = painter.font()
        font.setPointSize(18)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRect(left, bottom - 100, right - left, 34), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        role_width = min(metrics.horizontalAdvance(role) + 24, right - left)
        role_rect = QRect(left, bottom - 64, role_width, 28)

        role_bg = QColor(accent)
        role_bg.setAlpha(72)
        role_border = QColor(accent)
        role_border.setAlpha(105)
        painter.setBrush(role_bg)
        painter.setPen(QPen(role_border, 1))
        painter.drawRoundedRect(QRectF(role_rect), 9, 9)
        painter.setPen(accent.lighter(135))
        painter.drawText(role_rect, Qt.AlignmentFlag.AlignCenter, role)
        self.paint_tag_chips(painter, tags, left, right, bottom - 28)


class CharacterAccessRow(QFrame):
    toggled = pyqtSignal(str, bool)

    def __init__(self, key: str, title: str, description: str, icon_path, enabled: bool = False, parent=None):
        super().__init__(parent)
        self.key = key
        self.setObjectName("accessRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        icon_label = QLabel("")
        icon_label.setObjectName("accessIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedWidth(24)
        icon_label.setPixmap(render_svg_pixmap(icon_path, QSize(18, 18), "#c4b5fd"))

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(title)
        title_label.setObjectName("accessLabel")

        desc_label = QLabel(description)
        desc_label.setObjectName("accessDescription")
        desc_label.setWordWrap(True)

        text_col.addWidget(title_label)
        text_col.addWidget(desc_label)

        self.switch = SwitchPill(enabled)
        self.switch.toggled.connect(lambda value: self.toggled.emit(self.key, value))

        layout.addWidget(icon_label)
        layout.addLayout(text_col, 1)
        layout.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def set_checked(self, value: bool):
        self.switch.setChecked(value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.switch.setChecked(not self.switch.isChecked())
            self.toggled.emit(self.key, self.switch.isChecked())
        super().mousePressEvent(event)


class CharacterAccessPanel(QFrame):
    capability_toggled = pyqtSignal(str, bool)

    ACCESS_META = {
        "file_context": ("Files", "Read uploaded files", FILE_ICON_PATH),
        "url_context": ("Links", "Read pasted URLs", LINK_ICON_PATH),
        "terminal": ("Terminal tools", "Run local commands", TERMINAL_ICON_PATH),
        "mcp": ("MCP tools", "Use external MCP tools", "◇"),
    }

    def __init__(self, capabilities=None, show_mcp: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("accessPanel")
        self.rows: dict[str, CharacterAccessRow] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        capabilities = capabilities or {}

        for key in ("file_context", "url_context", "terminal", "mcp"):
            if key == "mcp" and not show_mcp:
                continue
            title, description, icon = self.ACCESS_META[key]
            row = CharacterAccessRow(key, title, description, icon, bool(capabilities.get(key, False)))
            row.toggled.connect(self.capability_toggled.emit)
            self.rows[key] = row
            layout.addWidget(row)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

    def set_capabilities(self, capabilities: dict):
        capabilities = capabilities or {}
        for key, row in self.rows.items():
            row.set_checked(bool(capabilities.get(key, False)))
