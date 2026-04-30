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
from PyQt6.QtWidgets import QBoxLayout, QFileDialog, QFrame, QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton, QVBoxLayout, QWidget, QWidgetAction

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


class WorkspaceLayoutMixin:
    def resolve_workspace_path(self, value):
        path_text = str(value or "").strip()
        if path_text:
            path = Path(path_text).expanduser()
            if path.exists() and path.is_dir():
                return path
        return APP_WORKSPACE

    def apply_workspace_path(self):
        value = self.workspace_input.text().strip() if hasattr(self, "workspace_input") else ""
        if not value:
            self.workspace_path_config = ""
            self.workspace_path = APP_WORKSPACE
            self.save_config()
            self.refresh_workspace_ui()
            self.set_status_message(f"Workspace reset to default: {self.workspace_path}")
            return
        path = Path(value).expanduser()
        if not path.exists() or not path.is_dir():
            self.set_status_message(f"Workspace does not exist: {path}")
            return
        self.workspace_path_config = str(path)
        self.workspace_path = path
        self.save_config()
        self.refresh_workspace_ui()
        self.set_status_message(f"Workspace set to {self.workspace_path}")

    def choose_workspace(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select workspace",
            str(self.workspace_path),
        )
        if not directory:
            return False
        self.workspace_path_config = directory
        self.workspace_path = Path(directory)
        self.save_config()
        self.refresh_workspace_ui()
        self.set_status_message(f"Workspace set to {self.workspace_path}")
        return True

    def prompt_for_workspace_if_needed(self):
        if self.active_mode != MODE_AGENT:
            return
        if self.workspace_prompt_checked or self.workspace_path_config:
            return
        self.workspace_prompt_checked = True
        response = QMessageBox.question(
            self,
            "Select workspace",
            (
                "Choose a workspace folder for terminal commands?\n\n"
                f"If you skip, Agent Chat uses {APP_WORKSPACE} for this session."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if response == QMessageBox.StandardButton.Yes and self.choose_workspace():
            return
        self.refresh_workspace_ui()
        self.set_status_message(f"Using default workspace: {self.workspace_path}")

    def refresh_workspace_ui(self):
        if hasattr(self, "workspace_input"):
            self.workspace_input.blockSignals(True)
            self.workspace_input.setText(self.workspace_path_config)
            self.workspace_input.blockSignals(False)
        if hasattr(self, "workspace_detail"):
            text = f"Terminal commands run in: {self.workspace_path}"
            self.workspace_detail.setText(text)
            self.workspace_detail.setToolTip("")

    def configure_responsive_metrics(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        self.default_window_width = max(520, min(1180, available.width() - 40))
        self.default_window_height = max(420, min(820, available.height() - 40))
        self.sidebar_expanded_max_width = 380

    def is_compact_layout(self):
        return self.width() < COMPACT_LAYOUT_WIDTH or self.height() < COMPACT_LAYOUT_HEIGHT

    def target_sidebar_width(self):
        if self.is_compact_layout():
            available_width = max(COMPACT_SIDEBAR_MIN_WIDTH, self.width() - COMPACT_WINDOW_GUTTER)
            return min(COMPACT_SIDEBAR_WIDTH, available_width)
        return self.sidebar_expanded_max_width

    def apply_responsive_layout(self):
        compact = self.is_compact_layout()
        if compact == self.compact_layout_active:
            return
        self.compact_layout_active = compact
        if hasattr(self, "sidebar_actions_layout"):
            direction = (
                QBoxLayout.Direction.TopToBottom
                if compact
                else QBoxLayout.Direction.LeftToRight
            )
            self.sidebar_actions_layout.setDirection(direction)
            self.sidebar_actions_layout.setSpacing(8 if compact else 10)
        if hasattr(self, "advanced_panel"):
            self.advanced_panel.layout().setContentsMargins(0, 0, 0, 0)
        if hasattr(self, "sidebar_content"):
            self.sidebar_content.layout().setSpacing(12 if compact else 16)
        self.update_model_selector_text()

    def setup_auto_hide_scrollbar(self, scroll_area):
        scrollbar = scroll_area.verticalScrollBar()
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(850)
        timer.timeout.connect(lambda area=scroll_area: self.hide_auto_scrollbar(area))
        self.auto_scrollbar_timers[scroll_area] = timer
        scrollbar.valueChanged.connect(lambda _value, area=scroll_area: self.show_auto_scrollbar(area))

    def show_auto_scrollbar(self, scroll_area):
        scrollbar = scroll_area.verticalScrollBar()
        if scrollbar.maximum() <= 0:
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            return
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        timer = self.auto_scrollbar_timers.get(scroll_area)
        if timer is not None:
            timer.start()

    def hide_auto_scrollbar(self, scroll_area):
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
