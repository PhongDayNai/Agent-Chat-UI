from __future__ import annotations

import base64
import html
import json
import mimetypes
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import requests
from PyQt6.QtCore import QByteArray, QBuffer, QEasingCurve, QEvent, QIODevice, QPoint, QPropertyAnimation, QRectF, QSize, QTimer, QUrl, Qt
from PyQt6.QtGui import QDesktopServices, QFontMetrics, QGuiApplication, QIcon, QImage, QPainter, QPixmap, QTransform
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton, QVBoxLayout, QWidget, QWidgetAction

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

from constants import (
    APP_WORKSPACE, ARROW_DOWN_ICON_PATH, CONFIG_PATH, DEFAULT_PERMISSIONS_ICON_PATH,
    DEFAULT_SERVER_BASE_URL, FULL_ACCESS_ICON_PATH, LEGACY_CONFIG_PATH,
    MAX_ATTACHMENT_TEXT_CHARS, MAX_URL_DOWNLOAD_BYTES, MAX_URLS_PER_MESSAGE,
    MAX_URL_TEXT_CHARS, TEXT_PREVIEW_SUFFIXES, TRAILING_URL_PUNCTUATION,
    URL_FETCH_TIMEOUT, URL_RE, agent_terminal_prompt,
)
from html_utils import HtmlTextExtractor
from markdown_utils import normalize_terminal_fences, replace_terminal_command_tags
from characters import (
    DEFAULT_CHARACTER_PROFILES, character_avatar_url, character_poster_url,
    filter_characters, get_active_character, get_effective_character_capabilities,
    is_character_favorite, normalize_character, normalize_character_profiles,
    set_character_capability, set_character_favorite, sort_characters,
)
from character_widgets import CharacterAccessPanel, CharacterSidebarHeroCard, render_svg_pixmap
from message_builder import build_messages
from modes import MODE_AGENT, MODE_CHARACTER, MODE_CHAT, normalize_mode
from widgets import AttachmentChip, FilePreviewDialog, ImageGalleryDialog, MessageCard, AssistantCodeBlock
from worker import ChatCompletionWorker
import key_storage

from window_shared import (
    CHARACTER_CARD_RATIOS, COMPACT_LAYOUT_HEIGHT, COMPACT_LAYOUT_WIDTH,
    COMPACT_SIDEBAR_MIN_WIDTH, COMPACT_SIDEBAR_WIDTH, COMPACT_WINDOW_GUTTER,
    DEFAULT_ASSISTANT_DEBOUNCE_ENABLED, DEFAULT_ASSISTANT_DEBOUNCE_INTERVAL_MS,
    DEFAULT_CHARACTER_CARD_RATIO, DEFAULT_COMPOSER_MAX_LINES,
    DEFAULT_TERMINAL_PERMISSIONS, MAX_COMPOSER_MAX_LINES, MIN_COMPOSER_MAX_LINES,
    SIDEBAR_DROPDOWN_TEXT_INSET, SIDEBAR_ELIDE_WIDTH, TERMINAL_PERMISSION_COLORS,
    TERMINAL_PERMISSION_DEFAULT, TERMINAL_PERMISSION_FULL_ACCESS, CharacterChoiceCard,
)


class SidebarMixin:
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
        if isinstance(getattr(self, "character_hero_card", None), CharacterSidebarHeroCard):
            self.character_hero_card.setFixedHeight(self.character_sidebar_hero_height())
        if hasattr(self, "character_overlay") and self.character_overlay.isVisible():
            self.position_character_overlay()

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
        self.pin_panel = checked
        self.pin_button.setProperty("pinned", checked)
        self.pin_button.style().unpolish(self.pin_button)
        self.pin_button.style().polish(self.pin_button)
        self.save_config()
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
