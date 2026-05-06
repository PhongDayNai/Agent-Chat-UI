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
    CODE_STICKY_CONTENT_PADDING, CODE_STICKY_HEADER_HEIGHT,
    MAX_AGENT_TERMINAL_STEPS, MAX_ATTACHMENT_TEXT_CHARS,
    MAX_OUTPUT_TOKENS,
    MAX_URL_DOWNLOAD_BYTES, MAX_URLS_PER_MESSAGE,
    MAX_URL_TEXT_CHARS, TEXT_PREVIEW_SUFFIXES, TRAILING_URL_PUNCTUATION,
    TERMINAL_OUTPUT_LIMIT, TERMINAL_TIMEOUT_SECONDS, URL_FETCH_TIMEOUT,
    URL_RE, agent_terminal_prompt,
)
from html_utils import HtmlTextExtractor
from markdown_utils import normalize_terminal_fences, replace_terminal_command_tags
from characters import (
    DEFAULT_CHARACTER_PROFILES, character_avatar_url, character_poster_url,
    filter_characters, get_active_character, get_effective_character_capabilities,
    is_character_favorite, normalize_character, normalize_character_profiles,
    normalize_character_sort_mode,
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


class ConfigMixin:
    def load_config(self):
        default_config = {
            "server": {
                "enabled": True,
                "base_url": DEFAULT_SERVER_BASE_URL,
                "base_urls": [DEFAULT_SERVER_BASE_URL],
            },
            "active_mode": MODE_CHAT,
            "session_prompt": {
                "enabled": True,
                "value": "",
                "history": [],
            },
            "api_keys": {
                "enabled": True,
                "selected_id": "",
                "allow_plaintext_fallback": False,
                "items": [],
            },
            "character_profiles": dict(DEFAULT_CHARACTER_PROFILES),
            "agent_terminal": {
                "enabled": True,
                "permission": TERMINAL_PERMISSION_DEFAULT,
                "default_permissions": list(DEFAULT_TERMINAL_PERMISSIONS),
            },
            "workspace": {
                "path": "",
            },
            "sampling": {
                "enabled": True,
                "temperature": 0.7,
                "top_p": 0.9,
                "top_k": 40,
            },
            "assistant_rendering": {
                "enabled": True,
                "debounce_enabled": DEFAULT_ASSISTANT_DEBOUNCE_ENABLED,
                "debounce_interval_ms": DEFAULT_ASSISTANT_DEBOUNCE_INTERVAL_MS,
            },
            "limits": {
                "max_attachment_text_chars": MAX_ATTACHMENT_TEXT_CHARS,
                "code_sticky_header_height": CODE_STICKY_HEADER_HEIGHT,
                "code_sticky_content_padding": CODE_STICKY_CONTENT_PADDING,
                "max_urls_per_message": MAX_URLS_PER_MESSAGE,
                "max_url_download_bytes": MAX_URL_DOWNLOAD_BYTES,
                "max_url_text_chars": MAX_URL_TEXT_CHARS,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "terminal_output_limit": TERMINAL_OUTPUT_LIMIT,
                "url_fetch_timeout": URL_FETCH_TIMEOUT,
                "terminal_timeout_seconds": TERMINAL_TIMEOUT_SECONDS,
                "max_agent_terminal_steps": MAX_AGENT_TERMINAL_STEPS,
            },
            "ui": {
                "enabled": True,
                "show_thinking": False,
                "pin_panel": False,
                "advanced_controls_expanded": True,
                "chat_controls_expanded": True,
                "context_usage": {
                    MODE_CHAT: False,
                    MODE_CHARACTER: False,
                    MODE_AGENT: True,
                },
                "composer_max_lines": DEFAULT_COMPOSER_MAX_LINES,
                "character_card_ratio": DEFAULT_CHARACTER_CARD_RATIO,
                "character_sort_mode": "name_asc",
            },
        }
        config_path = CONFIG_PATH if CONFIG_PATH.exists() else LEGACY_CONFIG_PATH
        if not config_path.exists():
            return default_config
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return default_config
        if not isinstance(payload, dict):
            return default_config
        return self.normalize_config(payload, default_config)

    def save_config(self):
        payload = {
            "active_mode": self.active_mode,
            "server": {
                "enabled": self.server_enabled,
                "base_url": self.base_url,
                "base_urls": self.base_url_history,
            },
            "session_prompt": {
                "enabled": self.session_prompt_enabled,
                "value": self.current_session_prompt_value(),
                "history": self.session_prompt_history,
            },
            "api_keys": {
                "enabled": self.api_keys_enabled,
                "selected_id": self.selected_api_key_id,
                "allow_plaintext_fallback": False,
                "items": self.api_keys,
            },
            "character_profiles": self.character_profiles,
            "agent_terminal": {
                "enabled": self.agent_terminal_enabled,
                "permission": self.agent_terminal_permission,
                "default_permissions": self.default_permissions,
            },
            "workspace": {
                "path": self.workspace_path_config if hasattr(self, "workspace_path_config") else "",
            },
            "sampling": {
                "enabled": self.sampling_enabled,
                "temperature": self.temperature_spin.value() if hasattr(self, "temperature_spin") else 0.7,
                "top_p": self.top_p_spin.value() if hasattr(self, "top_p_spin") else 0.9,
                "top_k": self.top_k_spin.value() if hasattr(self, "top_k_spin") else 40,
            },
            "assistant_rendering": {
                "enabled": self.assistant_rendering_enabled,
                "debounce_enabled": self.assistant_debounce_enabled,
                "debounce_interval_ms": (
                    self.debounce_interval_spin.value()
                    if hasattr(self, "debounce_interval_spin")
                    else self.assistant_debounce_interval_ms
                ),
            },
            "limits": {
                "max_attachment_text_chars": self.limit_spin_value(
                    "max_attachment_text_chars_spin",
                    self.max_attachment_text_chars,
                ),
                "code_sticky_header_height": self.limit_spin_value(
                    "code_sticky_header_height_spin",
                    self.code_sticky_header_height,
                ),
                "code_sticky_content_padding": self.limit_spin_value(
                    "code_sticky_content_padding_spin",
                    self.code_sticky_content_padding,
                ),
                "max_urls_per_message": self.limit_spin_value(
                    "max_urls_per_message_spin",
                    self.max_urls_per_message,
                ),
                "max_url_download_bytes": self.limit_spin_value(
                    "max_url_download_bytes_spin",
                    self.max_url_download_bytes,
                ),
                "max_url_text_chars": self.limit_spin_value(
                    "max_url_text_chars_spin",
                    self.max_url_text_chars,
                ),
                "max_output_tokens": self.limit_spin_value(
                    "max_output_tokens_spin",
                    self.max_output_tokens,
                ),
                "terminal_output_limit": self.limit_spin_value(
                    "terminal_output_limit_spin",
                    self.terminal_output_limit,
                ),
                "url_fetch_timeout": self.limit_spin_value(
                    "url_fetch_timeout_spin",
                    self.url_fetch_timeout,
                ),
                "terminal_timeout_seconds": self.limit_spin_value(
                    "terminal_timeout_seconds_spin",
                    self.terminal_timeout_seconds,
                ),
                "max_agent_terminal_steps": self.limit_spin_value(
                    "max_agent_terminal_steps_spin",
                    self.max_agent_terminal_steps,
                    unlimited_attribute="max_agent_terminal_steps_unlimited_checkbox",
                ),
            },
            "ui": {
                "enabled": True,
                "show_thinking": (
                    self.show_thinking_checkbox.isChecked()
                    if hasattr(self, "show_thinking_checkbox")
                    else self.show_thinking
                ),
                "pin_panel": self.sidebar_pinned,
                "advanced_controls_expanded": self.advanced_controls_config_expanded,
                "chat_controls_expanded": self.composer_expanded,
                "context_usage": self.context_usage_enabled_by_mode,
                "composer_max_lines": (
                    self.composer_max_lines_spin.value()
                    if hasattr(self, "composer_max_lines_spin")
                    else self.composer_max_lines
                ),
                "character_card_ratio": self.character_card_ratio,
                "character_sort_mode": self.character_sort_mode,
            },
        }
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with CONFIG_PATH.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
        except OSError as exc:
            self.set_status_message(f"Could not save config: {exc}")

    def normalize_config(self, payload, default_config):
        server_payload = payload.get("server") if isinstance(payload.get("server"), dict) else {}
        session_payload = payload.get("session_prompt") if isinstance(payload.get("session_prompt"), dict) else {}
        api_keys_payload = payload.get("api_keys") if isinstance(payload.get("api_keys"), dict) else {}
        terminal_payload = payload.get("agent_terminal") if isinstance(payload.get("agent_terminal"), dict) else {}
        workspace_payload = payload.get("workspace") if isinstance(payload.get("workspace"), dict) else {}
        sampling_payload = payload.get("sampling") if isinstance(payload.get("sampling"), dict) else {}
        rendering_payload = (
            payload.get("assistant_rendering")
            if isinstance(payload.get("assistant_rendering"), dict)
            else {}
        )
        limits_payload = payload.get("limits") if isinstance(payload.get("limits"), dict) else {}
        ui_payload = payload.get("ui") if isinstance(payload.get("ui"), dict) else {}
        mode = normalize_mode(payload.get("active_mode", default_config.get("active_mode", MODE_CHAT)))
        if mode != payload.get("active_mode", default_config.get("active_mode", MODE_CHAT)):
            self.config_needs_save = True
        if "active_mode" not in payload:
            self.config_needs_save = True
        if "character_profiles" not in payload:
            self.config_needs_save = True
        if "limits" not in payload:
            self.config_needs_save = True

        return {
            "active_mode": mode,
            "server": {
                **default_config["server"],
                **server_payload,
                "base_url": server_payload.get("base_url", payload.get("base_url", default_config["server"]["base_url"])),
                "base_urls": server_payload.get("base_urls", payload.get("base_urls", default_config["server"]["base_urls"])),
            },
            "session_prompt": {
                **default_config["session_prompt"],
                **session_payload,
                "enabled": session_payload.get("enabled", payload.get("session_prompt_enabled", default_config["session_prompt"]["enabled"])),
                "value": session_payload.get("value", payload.get("session_prompt", default_config["session_prompt"]["value"])),
                "history": session_payload.get("history", payload.get("session_prompts", default_config["session_prompt"]["history"])),
            },
            "api_keys": {
                **default_config["api_keys"],
                **api_keys_payload,
                **self.normalize_api_keys_config(api_keys_payload, default_config["api_keys"]),
            },
            "character_profiles": normalize_character_profiles(
                payload.get("character_profiles", default_config["character_profiles"])
            ),
            "agent_terminal": {
                **default_config["agent_terminal"],
                **terminal_payload,
                "enabled": terminal_payload.get("enabled", payload.get("agent_terminal_enabled", default_config["agent_terminal"]["enabled"])),
                "permission": terminal_payload.get("permission", payload.get("agent_terminal_permission", default_config["agent_terminal"]["permission"])),
                "default_permissions": terminal_payload.get("default_permissions", payload.get("default_permissions", default_config["agent_terminal"]["default_permissions"])),
            },
            "workspace": {
                **default_config["workspace"],
                **workspace_payload,
                "path": workspace_payload.get("path", payload.get("workspace_path", default_config["workspace"]["path"])),
            },
            "sampling": {
                **default_config["sampling"],
                **sampling_payload,
                "temperature": sampling_payload.get("temperature", payload.get("temperature", default_config["sampling"]["temperature"])),
                "top_p": sampling_payload.get("top_p", payload.get("top_p", default_config["sampling"]["top_p"])),
                "top_k": sampling_payload.get("top_k", payload.get("top_k", default_config["sampling"]["top_k"])),
            },
            "assistant_rendering": {
                **default_config["assistant_rendering"],
                **rendering_payload,
            },
            "limits": self.normalize_limits_config(limits_payload, default_config["limits"]),
            "ui": {
                **default_config["ui"],
                **ui_payload,
                "advanced_controls_expanded": bool(
                    ui_payload.get(
                        "advanced_controls_expanded",
                        default_config["ui"]["advanced_controls_expanded"],
                    )
                ),
                "chat_controls_expanded": bool(
                    ui_payload.get(
                        "chat_controls_expanded",
                        ui_payload.get(
                            "composer_controls_expanded",
                            default_config["ui"]["chat_controls_expanded"],
                        ),
                    )
                ),
                "composer_max_lines": ui_payload.get(
                    "composer_max_lines",
                    payload.get("composer_max_lines", default_config["ui"]["composer_max_lines"]),
                ),
                "context_usage": self.normalize_context_usage_config(
                    ui_payload.get(
                        "context_usage",
                        default_config["ui"]["context_usage"],
                    )
                ),
                "character_card_ratio": self.normalize_character_card_ratio(
                    ui_payload.get(
                        "character_card_ratio",
                        default_config["ui"]["character_card_ratio"],
                    )
                ),
                "character_sort_mode": normalize_character_sort_mode(
                    ui_payload.get(
                        "character_sort_mode",
                        default_config["ui"]["character_sort_mode"],
                    )
                ),
            },
        }

    def limit_spin_value(self, attribute, fallback, unlimited_attribute=None):
        if unlimited_attribute is not None:
            unlimited_widget = getattr(self, unlimited_attribute, None)
            if unlimited_widget is not None and unlimited_widget.isChecked():
                return -1
        widget = getattr(self, attribute, None)
        return int(widget.value()) if widget is not None else int(fallback)

    def normalize_limit_int(self, value, default, minimum, maximum):
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            self.config_needs_save = True
            return int(default)
        if normalized < minimum or normalized > maximum:
            self.config_needs_save = True
            return max(minimum, min(maximum, normalized))
        return normalized

    def normalize_limits_config(self, payload, defaults):
        return {
            "max_attachment_text_chars": self.normalize_limit_int(
                payload.get("max_attachment_text_chars", defaults["max_attachment_text_chars"]),
                defaults["max_attachment_text_chars"],
                1000,
                200000,
            ),
            "code_sticky_header_height": self.normalize_limit_int(
                payload.get("code_sticky_header_height", defaults["code_sticky_header_height"]),
                defaults["code_sticky_header_height"],
                28,
                120,
            ),
            "code_sticky_content_padding": self.normalize_limit_int(
                payload.get("code_sticky_content_padding", defaults["code_sticky_content_padding"]),
                defaults["code_sticky_content_padding"],
                0,
                64,
            ),
            "max_urls_per_message": self.normalize_limit_int(
                payload.get("max_urls_per_message", defaults["max_urls_per_message"]),
                defaults["max_urls_per_message"],
                0,
                50,
            ),
            "max_url_download_bytes": self.normalize_limit_int(
                payload.get("max_url_download_bytes", defaults["max_url_download_bytes"]),
                defaults["max_url_download_bytes"],
                1024,
                100 * 1024 * 1024,
            ),
            "max_url_text_chars": self.normalize_limit_int(
                payload.get("max_url_text_chars", defaults["max_url_text_chars"]),
                defaults["max_url_text_chars"],
                1000,
                500000,
            ),
            "max_output_tokens": self.normalize_limit_int(
                payload.get("max_output_tokens", defaults["max_output_tokens"]),
                defaults["max_output_tokens"],
                1,
                200000,
            ),
            "terminal_output_limit": self.normalize_limit_int(
                payload.get("terminal_output_limit", defaults["terminal_output_limit"]),
                defaults["terminal_output_limit"],
                1000,
                500000,
            ),
            "url_fetch_timeout": self.normalize_limit_int(
                payload.get("url_fetch_timeout", defaults["url_fetch_timeout"]),
                defaults["url_fetch_timeout"],
                1,
                300,
            ),
            "terminal_timeout_seconds": self.normalize_limit_int(
                payload.get("terminal_timeout_seconds", defaults["terminal_timeout_seconds"]),
                defaults["terminal_timeout_seconds"],
                1,
                3600,
            ),
            "max_agent_terminal_steps": self.normalize_limit_int(
                payload.get("max_agent_terminal_steps", defaults["max_agent_terminal_steps"]),
                defaults["max_agent_terminal_steps"],
                -1,
                100,
            ),
        }

    def normalize_character_card_ratio(self, value):
        ratio = str(value or DEFAULT_CHARACTER_CARD_RATIO).strip()
        return ratio if ratio in CHARACTER_CARD_RATIOS else DEFAULT_CHARACTER_CARD_RATIO

    def normalize_context_usage_config(self, value):
        defaults = {
            MODE_CHAT: False,
            MODE_CHARACTER: False,
            MODE_AGENT: True,
        }
        if not isinstance(value, dict):
            return defaults
        return {
            mode: bool(value.get(mode, enabled))
            for mode, enabled in defaults.items()
        }

    def normalize_api_keys_config(self, payload, default_config):
        items = []
        changed = False
        raw_items = payload.get("items", default_config.get("items", []))
        if isinstance(raw_items, list):
            for raw_item in raw_items:
                if not isinstance(raw_item, dict):
                    changed = True
                    continue
                raw_item = dict(raw_item)
                raw_key_id = str(raw_item.get("id", "")).strip()
                if raw_key_id and any(item["id"] == raw_key_id for item in items):
                    if str(raw_item.get("storage", "")).strip().lower() == "keyring" and not str(raw_item.get("value", "")).strip():
                        self.api_key_storage_warnings.append(
                            f"Skipped duplicate keychain id for API key '{raw_item.get('name', 'Unnamed')}'. Re-enter the key."
                        )
                        changed = True
                        continue
                    raw_item["id"] = uuid.uuid4().hex
                    changed = True
                normalized_item, item_changed = self.normalize_api_key_item(raw_item)
                changed = changed or item_changed
                if not normalized_item:
                    continue
                key_id = normalized_item["id"]
                if any(item["id"] == key_id for item in items):
                    normalized_item["id"] = uuid.uuid4().hex
                    if normalized_item.get("storage") == "keyring":
                        self.api_key_storage_warnings.append(
                            f"Skipped duplicate keychain id for API key '{normalized_item.get('name', 'Unnamed')}'. Re-enter the key."
                        )
                        continue
                    changed = True
                items.append(normalized_item)

        selected_id = str(payload.get("selected_id", default_config.get("selected_id", ""))).strip()
        if selected_id and not any(item["id"] == selected_id for item in items):
            selected_id = ""
            changed = True
        if "allow_plaintext_fallback" not in payload:
            changed = True
        self.config_needs_save = self.config_needs_save or changed
        return {
            "enabled": bool(payload.get("enabled", default_config.get("enabled", True))),
            "selected_id": selected_id,
            "allow_plaintext_fallback": False,
            "items": items,
        }

    def normalize_api_key_item(self, raw_item):
        name = str(raw_item.get("name", "")).strip()
        if not name:
            return None, True
        key_id = str(raw_item.get("id", "")).strip() or uuid.uuid4().hex
        storage = str(raw_item.get("storage", "")).strip().lower()
        value = str(raw_item.get("value", "")).strip()
        changed = raw_item.get("id") != key_id or raw_item.get("name") != name

        if value:
            try:
                key_storage.set_api_key_secret(key_id, value)
            except key_storage.KeyStorageError as exc:
                self.api_key_storage_warnings.append(
                    f"Keychain unavailable; API key '{name}' remains in local config."
                )
                return {"id": key_id, "name": name, "storage": "plaintext", "value": value}, True
            return {"id": key_id, "name": name, "storage": "keyring"}, True

        if storage == "keyring":
            return {"id": key_id, "name": name, "storage": "keyring"}, changed

        if storage == "plaintext":
            return None, True

        return None, True

    def normalize_composer_max_lines(self, value):
        try:
            numeric_value = int(value)
        except (TypeError, ValueError):
            numeric_value = DEFAULT_COMPOSER_MAX_LINES
        return max(MIN_COMPOSER_MAX_LINES, min(MAX_COMPOSER_MAX_LINES, numeric_value))

    def clean_history(self, values, normalizer=None):
        cleaned = []
        if not isinstance(values, list):
            return cleaned
        for value in values:
            if not isinstance(value, str):
                continue
            value = value.strip()
            if normalizer is not None:
                value = normalizer(value)
            if value and value not in cleaned:
                cleaned.append(value)
        return cleaned

    def normalize_debounce_interval(self, value):
        try:
            interval = int(value)
        except (TypeError, ValueError):
            interval = DEFAULT_ASSISTANT_DEBOUNCE_INTERVAL_MS
        return max(0, min(1000, interval))

    def add_history_value(self, values, value):
        value = value.strip()
        if not value:
            return values
        return [value] + [item for item in values if item != value]

    def set_elided_label_text(self, label, text, width=SIDEBAR_ELIDE_WIDTH):
        text = str(text or "")
        metrics = QFontMetrics(label.font())
        elided = metrics.elidedText(text, Qt.TextElideMode.ElideRight, width)
        label.setText(elided)
        label.setToolTip(text if elided != text else "")

    def current_session_prompt_value(self):
        if self.session_prompt_locked:
            return self.session_system_prompt
        if hasattr(self, "system_prompt_input"):
            return self.system_prompt_input.toPlainText().strip()
        return self.initial_session_prompt
