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
from PyQt6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton, QVBoxLayout, QWidget, QWidgetAction

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


class TerminalPermissionMixin:
    def normalize_agent_terminal_permission(self, value):
        value = str(value or "").strip().lower()
        if value == TERMINAL_PERMISSION_FULL_ACCESS:
            return TERMINAL_PERMISSION_FULL_ACCESS
        return TERMINAL_PERMISSION_DEFAULT

    def clean_default_permissions(self, values):
        cleaned = []
        if not isinstance(values, list):
            return list(DEFAULT_TERMINAL_PERMISSIONS)
        for value in values:
            command = str(value).strip()
            if not command or any(char.isspace() for char in command):
                continue
            if command not in cleaned:
                cleaned.append(command)
        return cleaned or list(DEFAULT_TERMINAL_PERMISSIONS)

    def terminal_permission_icon_path(self, permission):
        if permission == TERMINAL_PERMISSION_FULL_ACCESS:
            return FULL_ACCESS_ICON_PATH
        return DEFAULT_PERMISSIONS_ICON_PATH

    def terminal_permission_color(self, permission):
        return TERMINAL_PERMISSION_COLORS.get(permission, TERMINAL_PERMISSION_COLORS[TERMINAL_PERMISSION_DEFAULT])

    def tinted_svg_icon(self, icon_path, color, size=18, render_rect=None):
        try:
            content = Path(icon_path).read_text(encoding="utf-8")
        except OSError:
            return QIcon()
        svg = (
            content
            .replace("#000000", color)
            .replace("#000", color)
            .replace("#1C274C", color)
            .replace("#292D32", color)
        )
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        if render_rect is None:
            renderer.render(painter)
        else:
            renderer.render(painter, render_rect)
        painter.end()
        return QIcon(pixmap)

    def terminal_permission_icon(self, permission):
        return self.tinted_svg_icon(
            self.terminal_permission_icon_path(permission),
            self.terminal_permission_color(permission),
        )

    def terminal_permission_side_icon(self, permission):
        return self.tinted_svg_icon(
            self.terminal_permission_icon_path(permission),
            self.terminal_permission_color(permission),
            size=24,
            render_rect=QRectF(5, 2, 18, 18),
        )

    def set_agent_terminal_enabled(self, enabled):
        self.agent_terminal_enabled = bool(enabled)
        if not self.agent_terminal_enabled and self.pending_terminal_permission and self.worker is not None:
            self.worker.resolve_terminal_permission("reject")
            self.pending_terminal_permission = None
            if hasattr(self, "terminal_approval_banner"):
                self.terminal_approval_banner.hide()
        self.save_config()
        self.refresh_terminal_permission_ui()
        self.refresh_mode_ui()
        self.set_status_message(
            f"Terminal agent enabled. Commands run in {self.workspace_path}."
            if self.agent_terminal_enabled
            else "Terminal agent disabled."
        )

    def set_agent_terminal_permission(self, value):
        value = self.normalize_agent_terminal_permission(value)
        if self.agent_terminal_permission == value:
            self.refresh_terminal_permission_ui()
            return
        if (
            value == TERMINAL_PERMISSION_FULL_ACCESS
            and self.agent_terminal_permission != TERMINAL_PERMISSION_FULL_ACCESS
            and not self.confirm_full_access_terminal_permission()
        ):
            self.refresh_terminal_permission_ui()
            self.set_status_message("Full terminal access was not enabled.")
            return
        self.agent_terminal_permission = value
        self.save_config()
        self.refresh_terminal_permission_ui()
        self.set_status_message(f"Terminal permission set to {self.agent_terminal_permission_label()}.")

    def confirm_full_access_terminal_permission(self):
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Enable full terminal access?")
        dialog.setText("Full access lets the assistant run terminal commands without asking first.")
        dialog.setInformativeText(
            "Only enable this for workspaces and commands you trust. "
            "Default permissions will keep asking before commands outside the allowlist."
        )
        enable_button = dialog.addButton("Enable full access", QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
        dialog.exec()
        return dialog.clickedButton() == enable_button

    def agent_terminal_permission_label(self):
        if self.agent_terminal_permission == TERMINAL_PERMISSION_FULL_ACCESS:
            return "Full access"
        return "Default permissions"

    def show_terminal_permission_menu(self):
        if not hasattr(self, "terminal_permission_menu"):
            return
        self.refresh_terminal_permission_menu()
        self.terminal_permission_menu.exec(
            self.terminal_permission_button.mapToGlobal(self.terminal_permission_button.rect().bottomLeft())
        )

    def refresh_terminal_permission_menu(self):
        if not hasattr(self, "terminal_permission_menu"):
            return
        self.terminal_permission_menu.clear()
        self.add_terminal_permission_menu_item(
            self.terminal_permission_menu,
            "Default permissions",
            TERMINAL_PERMISSION_DEFAULT,
        )
        self.add_terminal_permission_menu_item(
            self.terminal_permission_menu,
            "Full access",
            TERMINAL_PERMISSION_FULL_ACCESS,
        )

    def refresh_side_terminal_permission_menu(self):
        if not hasattr(self, "side_terminal_permission_menu"):
            return
        self.side_terminal_permission_menu.clear()
        self.add_terminal_permission_menu_item(
            self.side_terminal_permission_menu,
            "Default permissions",
            TERMINAL_PERMISSION_DEFAULT,
        )
        self.add_terminal_permission_menu_item(
            self.side_terminal_permission_menu,
            "Full access",
            TERMINAL_PERMISSION_FULL_ACCESS,
        )

    def add_terminal_permission_menu_item(self, menu, label, permission):
        action = QWidgetAction(menu)
        button = QPushButton(label)
        button.setObjectName("terminalPermissionMenuItem")
        button.setIcon(self.terminal_permission_icon(permission))
        button.setProperty("fullAccess", permission == TERMINAL_PERMISSION_FULL_ACCESS)
        button.setProperty("selected", self.agent_terminal_permission == permission)
        button.clicked.connect(
            lambda _checked=False, value=permission: self.select_terminal_permission_from_menu(value)
        )
        action.setDefaultWidget(button)
        menu.addAction(action)

    def select_terminal_permission_from_menu(self, permission):
        self.set_agent_terminal_permission(permission)
        if hasattr(self, "terminal_permission_menu"):
            self.terminal_permission_menu.close()
        if hasattr(self, "side_terminal_permission_menu"):
            self.side_terminal_permission_menu.close()

    def refresh_terminal_permission_ui(self):
        label = self.agent_terminal_permission_label()
        effective_terminal_enabled = self.is_terminal_enabled_for_request()
        if hasattr(self, "terminal_permission_button"):
            suffix = " enabled" if effective_terminal_enabled else " disabled"
            self.terminal_permission_button.setText(label)
            self.terminal_permission_button.setIcon(self.terminal_permission_icon(self.agent_terminal_permission))
            self.terminal_permission_button.setToolTip(f"Terminal access is{suffix}.")
            self.terminal_permission_button.setProperty(
                "fullAccess",
                self.agent_terminal_permission == TERMINAL_PERMISSION_FULL_ACCESS,
            )
            self.terminal_permission_button.style().unpolish(self.terminal_permission_button)
            self.terminal_permission_button.style().polish(self.terminal_permission_button)
            self.terminal_permission_button.setEnabled(effective_terminal_enabled)
        if hasattr(self, "agent_terminal_checkbox"):
            self.agent_terminal_checkbox.blockSignals(True)
            self.agent_terminal_checkbox.setChecked(self.agent_terminal_enabled)
            self.agent_terminal_checkbox.blockSignals(False)
        if hasattr(self, "side_terminal_permission_button"):
            self.side_terminal_permission_button.setText(label)
            self.side_terminal_permission_button.setIcon(self.terminal_permission_side_icon(self.agent_terminal_permission))
            self.side_terminal_permission_button.setProperty(
                "fullAccess",
                self.agent_terminal_permission == TERMINAL_PERMISSION_FULL_ACCESS,
            )
            self.side_terminal_permission_button.style().unpolish(self.side_terminal_permission_button)
            self.side_terminal_permission_button.style().polish(self.side_terminal_permission_button)
            self.side_terminal_permission_button.setEnabled(effective_terminal_enabled)
        if hasattr(self, "default_permissions_detail"):
            allowed = ", ".join(self.default_permissions)
            self.default_permissions_detail.setText(f"Default commands: {allowed}")
            self.default_permissions_detail.setToolTip("")

    def is_terminal_enabled_for_request(self):
        if self.active_mode == MODE_AGENT:
            return bool(self.agent_terminal_enabled)
        if self.active_mode == MODE_CHARACTER:
            return bool(self.active_character_capabilities().get("terminal"))
        return False

    def on_terminal_permission_requested(self, command, command_key):
        should_focus_reply = self.assistant_reply_focus_active
        self.pending_terminal_permission = {
            "command": command,
            "command_key": command_key,
        }
        display_command = " ".join(command.split())
        if len(display_command) > 180:
            display_command = display_command[:177] + "..."
        self.terminal_approval_label.setText(f"Run terminal command?\n{display_command}")
        remember_label = f"Yes and don't ask again for this command {command_key or display_command}"
        self.terminal_approval_always_button.setText(remember_label)
        self.terminal_approval_always_button.setEnabled(bool(command_key))
        self.terminal_approval_banner.show()
        self.status_badge.setText("Permission needed")
        self.status_detail.setText("Terminal command is waiting for approval.")
        if should_focus_reply:
            self.scroll_to_assistant_reply()

    def resolve_terminal_permission(self, decision):
        if not self.pending_terminal_permission:
            return
        command_key = self.pending_terminal_permission.get("command_key", "")
        if decision == "allow_always" and command_key and command_key not in self.default_permissions:
            self.default_permissions.append(command_key)
            self.default_permissions = self.clean_default_permissions(self.default_permissions)
            self.save_config()
            self.refresh_terminal_permission_ui()
        self.terminal_approval_banner.hide()
        self.pending_terminal_permission = None
        if self.worker is not None and self.worker.isRunning():
            self.worker.resolve_terminal_permission(decision)
        if decision == "reject":
            self.status_badge.setText("Dismissed")
            self.status_detail.setText("Command dismissed. The model will continue without running it.")
        else:
            self.status_badge.setText("Generating")
            self.status_detail.setText("Terminal command approved.")

    def on_terminal_command_started(self, command, shell_name):
        should_focus_reply = self.assistant_reply_focus_active
        if self.current_assistant_card is not None:
            self.current_assistant_card.stop_loading()
            self.current_assistant_card.start_terminal_command(command, shell_name)
        if should_focus_reply:
            self.scroll_to_assistant_reply()

    def on_terminal_log_received(self, text):
        should_focus_reply = self.assistant_reply_focus_active
        if self.current_assistant_card is not None:
            self.current_assistant_card.stop_loading()
            self.current_assistant_card.append_terminal_log(text)
        if should_focus_reply:
            self.scroll_to_assistant_reply()

    def on_terminal_command_finished(self, status):
        should_focus_reply = self.assistant_reply_focus_active
        if self.current_assistant_card is not None:
            self.current_assistant_card.finish_terminal_command(status)
        if should_focus_reply:
            self.scroll_to_assistant_reply()
