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


class ServerSettingsMixin:
    def refresh_server_state(self):
        self.status_badge.setText("Checking")
        self.status_detail.setText(f"Refreshing server state from {self.base_url}.")
        self.model_selector.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.apply_url_button.setEnabled(False)
        self.server_connected = False
        self.refresh_connection_settings_ui()

        try:
            health_url = self.build_server_url("/health")
            models_url = self.build_server_url("/v1/models")
            headers = self.auth_headers()
            health_response = requests.get(health_url, headers=headers, timeout=2)
            if health_response.status_code not in (200, 404):
                self.set_disconnected_state(f"OpenAI-compatible server health returned HTTP {health_response.status_code}.")
                return

            response = requests.get(models_url, headers=headers, timeout=2)
            if response.status_code != 200:
                self.set_disconnected_state(f"OpenAI-compatible server returned HTTP {response.status_code}.")
                return

            payload = response.json()
            model_items = payload.get("data", [])
            self.model_metadata = {
                item.get("id", ""): item
                for item in model_items
                if item.get("id")
            }
            self.runtime_context_window = self.fetch_runtime_context_window(headers)
            models = [item.get("id", "") for item in model_items if item.get("id")]
            self.available_models = models
            self.populate_models(models)

            if models:
                self.server_connected = True
                self.server_url_editing = False
                self.api_key_editing = False
                self.status_badge.setText("Connected")
                self.status_detail.setText(f"{len(models)} model(s) available from {self.base_url}.")
            else:
                self.status_badge.setText("No models loaded")
                self.status_detail.setText(f"Start OpenAI-compatible server with a loaded model at {self.base_url}.")
        except requests.exceptions.ConnectionError:
            self.set_disconnected_state(f"OpenAI-compatible server is not reachable at {self.base_url}.")
        except Exception as exc:
            self.set_disconnected_state(f"Failed to refresh models: {exc}")
        finally:
            self.refresh_button.setEnabled(True)
            self.update_base_url_input_state()
            self.refresh_api_key_ui()
            self.refresh_connection_settings_ui()
            self.update_send_availability()
            self.refresh_chat_header()

    def fetch_runtime_context_window(self, headers):
        for path, parser in (
            ("/slots", self.parse_slots_context_window),
            ("/props", self.parse_props_context_window),
        ):
            try:
                response = requests.get(self.build_server_url(path), headers=headers, timeout=2)
            except Exception:
                continue
            if response.status_code != 200:
                continue
            value = parser(response.json())
            if value:
                return value
        return self.model_context_window(self.current_model_name())

    def parse_slots_context_window(self, payload):
        if not isinstance(payload, list):
            return 0
        for slot in payload:
            if not isinstance(slot, dict):
                continue
            value = self.normalize_context_window_value(slot.get("n_ctx"))
            if value:
                return value
        return 0

    def parse_props_context_window(self, payload):
        if not isinstance(payload, dict):
            return 0
        settings = payload.get("default_generation_settings")
        if isinstance(settings, dict):
            value = self.normalize_context_window_value(settings.get("n_ctx"))
            if value:
                return value
        return 0

    def normalize_context_window_value(self, value):
        try:
            numeric_value = int(value)
        except (TypeError, ValueError):
            return 0
        return max(0, numeric_value)

    def model_context_window(self, model_name):
        item = self.model_metadata.get(model_name) if hasattr(self, "model_metadata") else None
        if not isinstance(item, dict):
            return 0
        candidates = [
            item.get("context_length"),
            item.get("max_context_length"),
            item.get("max_model_len"),
            item.get("n_ctx"),
        ]
        meta = item.get("meta")
        if isinstance(meta, dict):
            candidates.extend(
                [
                    meta.get("n_ctx"),
                    meta.get("n_ctx_train"),
                    meta.get("context_length"),
                    meta.get("max_context_length"),
                    meta.get("max_model_len"),
                ]
            )
        for candidate in candidates:
            value = self.normalize_context_window_value(candidate)
            if value:
                return value
        return 0

    def populate_models(self, models):
        current_text = self.current_model_name()
        if models:
            if current_text and current_text in models:
                self.set_selected_model_name(current_text)
            else:
                self.set_selected_model_name(models[0])
        else:
            self.set_selected_model_name("")
        self.model_selector.setEnabled(bool(models))

    def set_disconnected_state(self, detail):
        self.server_connected = False
        self.available_models = []
        self.model_metadata = {}
        self.runtime_context_window = 0
        self.set_selected_model_name("")
        self.model_selector.setEnabled(False)
        self.status_badge.setText("Disconnected")
        self.status_detail.setText(detail)
        self.refresh_connection_settings_ui()

    def current_model_name(self):
        return self.selected_model_name.strip()

    def set_selected_model_name(self, model_name):
        self.selected_model_name = model_name.strip()
        self.update_model_selector_text()
        self.refresh_chat_header()
        self.update_send_availability()

    def update_model_selector_text(self):
        if not hasattr(self, "model_selector"):
            return
        if self.selected_model_name:
            metrics = QFontMetrics(self.model_selector.font())
            sidebar_button_width = self.target_sidebar_width() - 48
            actual_button_width = self.model_selector.width()
            if actual_button_width > 0:
                sidebar_button_width = min(sidebar_button_width, actual_button_width)
            available_width = sidebar_button_width - 54
            display_name = metrics.elidedText(
                self.selected_model_name,
                Qt.TextElideMode.ElideRight,
                max(80, available_width),
            )
            self.model_selector.setText(f"{SIDEBAR_DROPDOWN_TEXT_INSET}{display_name}")
            self.model_selector.setToolTip(self.selected_model_name)
        else:
            self.model_selector.setText(f"{SIDEBAR_DROPDOWN_TEXT_INSET}Select model")
            self.model_selector.setToolTip("Select model")

    def refresh_model_menu(self):
        if not hasattr(self, "model_menu"):
            return
        self.model_menu.clear()
        current = self.current_model_name()
        for model in self.available_models:
            action = self.model_menu.addAction(model)
            action.setCheckable(True)
            action.setChecked(model == current)
            action.triggered.connect(lambda _checked=False, value=model: self.select_model(value))

    def select_model(self, model_name):
        self.set_selected_model_name(model_name)
        if hasattr(self, "model_menu"):
            self.model_menu.close()

    def normalize_base_url(self, raw_value):
        value = raw_value.strip()
        if not value:
            return ""
        if "://" not in value:
            value = f"http://{value}"
        return value.rstrip("/")

    def build_server_url(self, path):
        return f"{self.base_url}{path}"

    def current_api_key_item(self):
        selected_id = self.selected_api_key_id.strip()
        if not selected_id:
            return None
        for item in self.api_keys:
            if item.get("id") == selected_id:
                return item
        return None

    def pending_api_key_item(self):
        pending_id = self.pending_api_key_id.strip()
        if not pending_id:
            return None
        for item in self.api_keys:
            if item.get("id") == pending_id:
                return item
        return None

    def current_api_key_value(self):
        item = self.current_api_key_item()
        if not item:
            return ""
        if item.get("storage") == "keyring":
            try:
                return key_storage.get_api_key_secret(item.get("id", "")).strip()
            except key_storage.KeyStorageError as exc:
                self.api_key_storage_warnings.append(str(exc))
                return ""
        return str(item.get("value", "")).strip()

    def auth_headers(self):
        api_key = self.current_api_key_value()
        if not api_key:
            return {}
        return {"Authorization": f"Bearer {api_key}"}

    def refresh_api_key_ui(self):
        pending_item = self.pending_api_key_item()
        if pending_item:
            pending_label = str(pending_item.get("name", "")).strip()
            selected_text = pending_label
            history_tooltip = f"Selection: {pending_label}"
        elif self.pending_api_key_id:
            self.pending_api_key_id = ""
            selected_text = "No API key"
            history_tooltip = "Selection: No API key"
        else:
            selected_text = "No API key"
            history_tooltip = "Selection: No API key"
        applied = self.pending_api_key_id == self.selected_api_key_id
        detail = self.api_key_detail_text(pending_item, applied)
        if hasattr(self, "api_key_active_badge"):
            self.set_elided_label_text(self.api_key_active_badge, selected_text)
        if hasattr(self, "api_key_detail"):
            self.set_elided_label_text(self.api_key_detail, detail)
        if hasattr(self, "api_key_history_button"):
            self.api_key_history_button.setEnabled(bool(self.api_keys))
            self.api_key_history_button.setToolTip(history_tooltip)
        if hasattr(self, "apply_api_key_button"):
            self.apply_api_key_button.setProperty("applied", applied)
            self.apply_api_key_button.setToolTip(
                "Selection is already applied" if applied else "Apply selected API key"
            )
            self.apply_api_key_button.style().unpolish(self.apply_api_key_button)
            self.apply_api_key_button.style().polish(self.apply_api_key_button)
        if hasattr(self, "new_api_key_button"):
            self.new_api_key_button.setText("Hide new key" if self.new_api_key_panel_expanded else "New key")
        if hasattr(self, "api_keys_section"):
            self.set_sidebar_section_visible(self.api_keys_section, self.api_keys_enabled)
        self.refresh_connection_settings_ui()

    def refresh_connection_settings_ui(self):
        if hasattr(self, "base_url_input"):
            url_current = self.normalize_base_url(self.base_url_input.currentText())
        else:
            url_current = self.base_url
        url_applied = bool(url_current) and url_current == self.base_url
        api_applied = self.pending_api_key_id == self.selected_api_key_id
        connection_collapsed = (
            self.server_connected
            and url_applied
            and api_applied
            and not self.server_url_editing
            and not self.api_key_editing
        )
        expected_expanded = self.advanced_controls_config_expanded if connection_collapsed else True
        if self.advanced_expanded != expected_expanded:
            self.set_advanced_panel_expanded(expected_expanded, animate=False, persist=False)
        if self.advanced_expanded:
            if hasattr(self, "server_section"):
                self.set_sidebar_section_visible(self.server_section, self.server_enabled)
            if hasattr(self, "api_keys_section"):
                self.set_sidebar_section_visible(self.api_keys_section, self.api_keys_enabled)
        if hasattr(self, "new_api_key_panel") and connection_collapsed:
            self.new_api_key_panel_expanded = False
            self.new_api_key_panel.hide()

    def toggle_advanced_panel(self):
        expanded = not self.advanced_expanded
        self.server_url_editing = expanded
        self.api_key_editing = expanded
        if expanded:
            if hasattr(self, "server_section"):
                self.set_sidebar_section_visible(self.server_section, self.server_enabled)
            if hasattr(self, "api_keys_section"):
                self.set_sidebar_section_visible(self.api_keys_section, self.api_keys_enabled)
        self.set_advanced_panel_expanded(expanded)

    def set_advanced_panel_expanded(self, expanded, animate=True, persist=True):
        expanded = bool(expanded)
        if self.advanced_expanded == expanded:
            if not animate and hasattr(self, "advanced_body"):
                self.advanced_body.setVisible(expanded)
                self.advanced_body.setMaximumHeight(16777215)
            self.update_advanced_collapse_icon()
            return
        self.advanced_expanded = expanded
        if hasattr(self, "advanced_body"):
            if animate:
                self.animate_advanced_body(expanded)
            else:
                self.advanced_body.setVisible(expanded)
                self.advanced_body.setMaximumHeight(16777215)
        self.update_advanced_collapse_icon()
        if persist:
            self.advanced_controls_config_expanded = expanded
            self.save_config()

    def update_advanced_collapse_icon(self):
        if hasattr(self, "advanced_collapse_button"):
            pixmap = render_svg_pixmap(ARROW_DOWN_ICON_PATH, QSize(16, 16), "#8c9298")
            if self.advanced_expanded:
                pixmap = pixmap.transformed(
                    QTransform().rotate(180),
                    Qt.TransformationMode.SmoothTransformation,
                )
            self.advanced_collapse_button.setIcon(QIcon(pixmap))
            self.advanced_collapse_button.setToolTip(
                "Collapse advanced controls" if self.advanced_expanded else "Expand advanced controls"
            )

    def animate_advanced_body(self, expanded):
        if not hasattr(self, "advanced_body"):
            return
        if self.advanced_body_animation is not None:
            self.advanced_body_animation.stop()
        if expanded:
            self.advanced_body.show()
            self.advanced_body.setMaximumHeight(0)
            start_height = 0
            end_height = max(1, self.advanced_body.sizeHint().height())
        else:
            start_height = max(1, self.advanced_body.height())
            end_height = 0
        self.advanced_body_animation = QPropertyAnimation(self.advanced_body, b"maximumHeight", self)
        self.advanced_body_animation.setDuration(220)
        self.advanced_body_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.advanced_body_animation.setStartValue(start_height)
        self.advanced_body_animation.setEndValue(end_height)
        self.advanced_body_animation.finished.connect(
            lambda expanded=expanded: self.finish_advanced_body_animation(expanded)
        )
        self.advanced_body_animation.start()

    def finish_advanced_body_animation(self, expanded):
        if not hasattr(self, "advanced_body"):
            return
        if expanded:
            self.advanced_body.setMaximumHeight(16777215)
        else:
            self.advanced_body.hide()
            self.advanced_body.setMaximumHeight(16777215)

    def toggle_composer_panel(self):
        self.set_composer_panel_expanded(not self.composer_expanded)

    def set_composer_panel_expanded(self, expanded, animate=True, persist=True):
        expanded = bool(expanded)
        if self.composer_expanded == expanded:
            if not animate and hasattr(self, "composer_body"):
                self.composer_body.setVisible(expanded)
                self.composer_body.setMaximumHeight(16777215)
            self.update_composer_collapse_icon()
            return
        self.composer_expanded = expanded
        if hasattr(self, "composer_body"):
            if animate:
                self.animate_composer_body(expanded)
            else:
                self.composer_body.setVisible(expanded)
                self.composer_body.setMaximumHeight(16777215)
        self.update_composer_collapse_icon()
        if persist:
            self.save_config()

    def update_composer_collapse_icon(self):
        if hasattr(self, "composer_collapse_button"):
            pixmap = render_svg_pixmap(ARROW_DOWN_ICON_PATH, QSize(16, 16), "#8c9298")
            if self.composer_expanded:
                pixmap = pixmap.transformed(
                    QTransform().rotate(180),
                    Qt.TransformationMode.SmoothTransformation,
                )
            self.composer_collapse_button.setIcon(QIcon(pixmap))
            self.composer_collapse_button.setToolTip(
                "Collapse chat controls" if self.composer_expanded else "Expand chat controls"
            )

    def animate_composer_body(self, expanded):
        if not hasattr(self, "composer_body"):
            return
        if self.composer_body_animation is not None:
            self.composer_body_animation.stop()
        if expanded:
            self.composer_body.show()
            self.composer_body.setMaximumHeight(0)
            start_height = 0
            end_height = max(1, self.composer_body.sizeHint().height())
        else:
            start_height = max(1, self.composer_body.height())
            end_height = 0
        self.composer_body_animation = QPropertyAnimation(self.composer_body, b"maximumHeight", self)
        self.composer_body_animation.setDuration(220)
        self.composer_body_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.composer_body_animation.setStartValue(start_height)
        self.composer_body_animation.setEndValue(end_height)
        self.composer_body_animation.finished.connect(
            lambda expanded=expanded: self.finish_composer_body_animation(expanded)
        )
        self.composer_body_animation.start()

    def finish_composer_body_animation(self, expanded):
        if not hasattr(self, "composer_body"):
            return
        if expanded:
            self.composer_body.setMaximumHeight(16777215)
        else:
            self.composer_body.hide()
            self.composer_body.setMaximumHeight(16777215)

    def edit_connection_settings(self):
        self.server_url_editing = True
        self.api_key_editing = True
        self.refresh_api_key_ui()
        if hasattr(self, "base_url_input"):
            self.base_url_input.setFocus()

    def api_key_detail_text(self, item, applied):
        action_text = "Applied to requests." if applied else "Press ✓ to apply this selection to requests."
        if not item:
            return action_text
        if item.get("storage") == "keyring":
            try:
                secret = key_storage.get_api_key_secret(item.get("id", ""))
            except key_storage.KeyStorageError:
                return "OS keychain unavailable. Re-enable keychain or re-enter the API key."
            if not secret:
                return "Secret not found in keychain. Re-enter the API key."
            return f"Stored in OS keychain. {action_text}"
        return f"Stored in local config plaintext. {action_text}"

    def show_api_key_storage_warning(self):
        if not self.api_key_storage_warnings:
            return
        warning = self.api_key_storage_warnings[-1]
        self.set_status_message(warning)

    def show_api_key_menu(self):
        if not self.api_keys:
            return
        menu = QMenu(self)
        menu.setObjectName("historyMenu")
        current_id = self.pending_api_key_id

        no_key_action = menu.addAction("No API key")
        no_key_action.setEnabled(bool(current_id))
        if current_id:
            no_key_action.triggered.connect(lambda _checked=False: self.stage_api_key(""))

        for item in self.api_keys:
            key_id = item.get("id", "")
            name = item.get("name", "")
            action = menu.addAction(name)
            is_current = key_id == current_id
            action.setEnabled(not is_current)
            if not is_current:
                action.triggered.connect(lambda _checked=False, value=key_id: self.stage_api_key(value))

        delete_menu = menu.addMenu("Delete saved key")
        for item in self.api_keys:
            key_id = item.get("id", "")
            name = item.get("name", "")
            action = delete_menu.addAction(name)
            action.triggered.connect(lambda _checked=False, value=key_id: self.delete_api_key(value))

        menu.exec(self.api_key_history_button.mapToGlobal(self.api_key_history_button.rect().bottomLeft()))

    def stage_api_key(self, key_id):
        key_id = str(key_id or "").strip()
        if key_id and not any(item.get("id") == key_id for item in self.api_keys):
            return
        self.pending_api_key_id = key_id
        self.refresh_api_key_ui()

    def apply_selected_api_key(self):
        if self.pending_api_key_id and not any(item.get("id") == self.pending_api_key_id for item in self.api_keys):
            self.pending_api_key_id = ""
        if self.selected_api_key_id == self.pending_api_key_id:
            self.refresh_api_key_ui()
            return
        self.selected_api_key_id = self.pending_api_key_id
        self.refresh_api_key_ui()
        self.save_config()
        item = self.current_api_key_item()
        label = item.get("name", "") if item else "No API key"
        self.set_status_message(f"Applied API key: {label}")
        self.show_toast("API key applied")
        self.refresh_server_state()

    def save_new_api_key(self):
        name = self.api_key_name_input.text().strip() if hasattr(self, "api_key_name_input") else ""
        value = self.api_key_value_input.text().strip() if hasattr(self, "api_key_value_input") else ""
        if not name:
            message = "Enter a name for this API key."
            self.set_status_message(message)
            if hasattr(self, "api_key_detail"):
                self.api_key_detail.setText(message)
            if hasattr(self, "api_key_name_input"):
                self.api_key_name_input.setFocus()
            return
        if not value:
            message = "Enter an API key."
            self.set_status_message(message)
            if hasattr(self, "api_key_detail"):
                self.api_key_detail.setText(message)
            if hasattr(self, "api_key_value_input"):
                self.api_key_value_input.setFocus()
            return

        existing_item = next((item for item in self.api_keys if item.get("name") == name), None)
        key_id = existing_item.get("id", "") if existing_item else uuid.uuid4().hex
        try:
            key_storage.set_api_key_secret(key_id, value)
        except key_storage.KeyStorageError as exc:
            message = f"Could not save API key to OS keychain: {exc}"
            self.set_status_message(message)
            if hasattr(self, "api_key_detail"):
                self.api_key_detail.setText(message)
            return

        if existing_item:
            existing_item["storage"] = "keyring"
            existing_item.pop("value", None)
            self.pending_api_key_id = existing_item["id"]
        else:
            item = {"id": key_id, "name": name, "storage": "keyring"}
            self.api_keys.insert(0, item)
            self.pending_api_key_id = item["id"]

        self.selected_api_key_id = self.pending_api_key_id
        self.api_key_name_input.clear()
        self.api_key_value_input.clear()
        self.set_new_api_key_panel_expanded(False)
        self.refresh_api_key_ui()
        self.save_config()
        self.set_status_message(f"API key saved: {name}")
        self.show_toast("API key saved")
        self.refresh_server_state()

    def delete_api_key(self, key_id):
        key_id = str(key_id or "").strip()
        if not key_id:
            return
        deleted_item = next((item for item in self.api_keys if item.get("id") == key_id), None)
        was_selected = self.selected_api_key_id == key_id
        self.api_keys = [item for item in self.api_keys if item.get("id") != key_id]
        if deleted_item and deleted_item.get("storage") == "keyring":
            try:
                key_storage.delete_api_key_secret(key_id)
            except key_storage.KeyStorageError as exc:
                self.api_key_storage_warnings.append(str(exc))
        if was_selected:
            self.selected_api_key_id = ""
        if self.pending_api_key_id == key_id:
            self.pending_api_key_id = self.selected_api_key_id
        self.refresh_api_key_ui()
        self.save_config()
        if self.api_key_storage_warnings:
            self.show_api_key_storage_warning()
        if was_selected:
            self.refresh_server_state()

    def toggle_new_api_key_panel(self):
        self.set_new_api_key_panel_expanded(not self.new_api_key_panel_expanded)

    def set_new_api_key_panel_expanded(self, expanded):
        expanded = bool(expanded)
        if not hasattr(self, "new_api_key_panel"):
            return
        if self.new_api_key_panel_expanded == expanded:
            self.refresh_api_key_ui()
            return
        self.new_api_key_panel_expanded = expanded
        self.animate_new_api_key_panel(expanded)
        self.refresh_api_key_ui()
        if expanded and hasattr(self, "api_key_name_input"):
            QTimer.singleShot(230, self.api_key_name_input.setFocus)

    def animate_new_api_key_panel(self, expanded):
        if self.new_api_key_panel_animation is not None:
            self.new_api_key_panel_animation.stop()
        if expanded:
            self.new_api_key_panel.show()
            self.new_api_key_panel.setMaximumHeight(0)
            start_height = 0
            end_height = max(1, self.new_api_key_panel.sizeHint().height())
        else:
            start_height = max(1, self.new_api_key_panel.height())
            end_height = 0
        self.new_api_key_panel_animation = QPropertyAnimation(self.new_api_key_panel, b"maximumHeight", self)
        self.new_api_key_panel_animation.setDuration(220)
        self.new_api_key_panel_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.new_api_key_panel_animation.setStartValue(start_height)
        self.new_api_key_panel_animation.setEndValue(end_height)
        self.new_api_key_panel_animation.finished.connect(
            lambda expanded=expanded: self.finish_new_api_key_panel_animation(expanded)
        )
        self.new_api_key_panel_animation.start()

    def finish_new_api_key_panel_animation(self, expanded):
        if expanded:
            self.new_api_key_panel.setMaximumHeight(16777215)
        else:
            self.new_api_key_panel.hide()
            self.new_api_key_panel.setMaximumHeight(16777215)

    def on_base_url_text_changed(self, _text):
        self.update_base_url_input_state()

    def update_base_url_input_state(self):
        if not hasattr(self, "apply_url_button"):
            return
        current = self.normalize_base_url(self.base_url_input.currentText())
        applied = bool(current) and current == self.base_url
        self.apply_url_button.setProperty("applied", applied)
        self.apply_url_button.setEnabled(bool(current))
        self.apply_url_button.style().unpolish(self.apply_url_button)
        self.apply_url_button.style().polish(self.apply_url_button)
        if hasattr(self, "base_url_history_button"):
            self.base_url_history_button.setEnabled(bool(self.base_url_history))

    def refresh_base_url_history_ui(self):
        self.base_url_input.setCurrentText(self.base_url)
        self.base_url_input.set_history_available(False)
        self.update_base_url_input_state()

    def refresh_session_prompt_history_ui(self):
        if hasattr(self, "session_prompt_history_button"):
            self.session_prompt_history_button.setEnabled(bool(self.session_prompt_history))

    def select_base_url_history_index(self, index):
        value = self.base_url_input.itemData(index) or self.base_url_input.itemText(index)
        self.select_base_url_history(value)

    def select_base_url_history(self, value):
        value = self.normalize_base_url(value)
        if not value:
            return
        self.base_url_input.setCurrentText(value)
        self.update_base_url_input_state()

    def delete_base_url_history_item(self, value):
        value = self.normalize_base_url(value)
        self.base_url_history = [item for item in self.base_url_history if item != value]
        if not self.base_url_history:
            self.base_url_history = [DEFAULT_SERVER_BASE_URL]
        if self.base_url == value:
            self.base_url = self.base_url_history[0]
            self.base_url_detail.setText(f"Base URL for OpenAI-compatible server: {self.base_url}")
        self.refresh_base_url_history_ui()
        self.save_config()

    def show_base_url_history_menu(self):
        current = self.normalize_base_url(self.base_url_input.currentText())
        if not self.base_url_history:
            return

        menu = QMenu(self)
        menu.setObjectName("historyMenu")
        for value in self.base_url_history:
            action = menu.addAction(value)
            is_current = self.normalize_base_url(value) == current
            action.setEnabled(not is_current)
            if not is_current:
                action.triggered.connect(lambda _checked=False, url=value: self.select_base_url_history(url))

        delete_menu = menu.addMenu("Delete saved URL")
        for value in self.base_url_history:
            action = delete_menu.addAction(value)
            action.triggered.connect(lambda _checked=False, url=value: self.delete_base_url_history_item(url))

        menu.exec(self.base_url_history_button.mapToGlobal(self.base_url_history_button.rect().bottomLeft()))

    def select_session_prompt_history(self, value):
        if self.session_prompt_locked:
            self.set_status_message("Start a new session before changing the active session prompt.")
            return
        self.system_prompt_input.setPlainText(value)
        self.refresh_session_prompt_ui()
        self.save_config()

    def delete_session_prompt_history_item(self, value):
        value = value.strip()
        self.session_prompt_history = [item for item in self.session_prompt_history if item != value]
        if self.current_session_prompt_value() == value and not self.session_prompt_locked:
            self.system_prompt_input.clear()
        self.refresh_session_prompt_history_ui()
        self.save_config()

    def show_session_prompt_history_menu(self):
        if not self.session_prompt_history:
            return

        current = self.current_session_prompt_value()
        menu = QMenu(self)
        menu.setObjectName("historyMenu")
        for value in self.session_prompt_history:
            display_value = " ".join(value.split())
            if len(display_value) > 90:
                display_value = display_value[:87] + "..."
            action = menu.addAction(display_value)
            is_current = value == current
            action.setEnabled(not is_current)
            if not is_current:
                action.triggered.connect(lambda _checked=False, prompt=value: self.select_session_prompt_history(prompt))

        delete_menu = menu.addMenu("Delete saved prompt")
        for value in self.session_prompt_history:
            display_value = " ".join(value.split())
            if len(display_value) > 90:
                display_value = display_value[:87] + "..."
            action = delete_menu.addAction(display_value)
            action.triggered.connect(lambda _checked=False, prompt=value: self.delete_session_prompt_history_item(prompt))

        menu.exec(self.session_prompt_history_button.mapToGlobal(self.session_prompt_history_button.rect().bottomLeft()))

    def apply_base_url(self):
        value = self.normalize_base_url(self.base_url_input.currentText())
        if not value:
            self.set_status_message("Enter a valid server URL.")
            return
        self.base_url = value
        self.base_url_history = self.add_history_value(self.base_url_history, value)
        self.base_url_input.setCurrentText(value)
        self.base_url_detail.setText(f"Base URL for OpenAI-compatible server: {value}")
        self.refresh_base_url_history_ui()
        self.update_base_url_input_state()
        self.save_config()
        self.show_toast("Server URL applied")
        self.refresh_server_state()
