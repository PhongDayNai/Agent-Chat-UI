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
from PyQt6.QtGui import QDesktopServices, QFontMetrics, QGuiApplication, QIcon, QImage, QMovie, QPainter, QPixmap, QTransform
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
    URL_FETCH_TIMEOUT, URL_RE, agent_terminal_prompt, ARROW_UP_ICON_PATH, STOP_ICON_PATH,
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
from modes import MODE_AGENT, MODE_CHARACTER, MODE_CHAT, MODE_LABELS, normalize_mode
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


class ChatFlowMixin:
    def update_send_availability(self):
        has_text = bool(self.composer.toPlainText().strip()) or bool(self.pending_attachments)
        has_model = bool(self.available_models) and bool(self.current_model_name())
        character_ready = self.active_mode != MODE_CHARACTER or self.active_character() is not None
        busy = self.worker is not None and self.worker.isRunning()
        if has_text:
            self.configure_send_action_button("send", enabled=has_model and character_ready)
        elif busy:
            self.configure_send_action_button("stop", enabled=True)
        else:
            self.configure_send_action_button("send", enabled=False)
        self.model_selector.setEnabled(bool(self.available_models) and not busy)
        self.attach_button.setEnabled(self.attachments_allowed_for_mode())
        self.clear_attachments_button.setEnabled(bool(self.pending_attachments))
        self.refresh_queue_ui()

    def configure_send_action_button(self, mode, enabled):
        icon_path = STOP_ICON_PATH if mode == "stop" else ARROW_UP_ICON_PATH
        tooltip = "Stop" if mode == "stop" else "Send"
        self.send_button.setProperty("variant", mode)
        self.send_button.setToolTip(tooltip)
        self.send_button.setEnabled(enabled)
        self.send_button.set_icon_path(icon_path)
        self.send_button.style().unpolish(self.send_button)
        self.send_button.style().polish(self.send_button)

    def handle_send_action_button(self):
        if self.send_button.property("variant") == "stop":
            self.stop_generation()
            return
        self.send_message()

    def refresh_queue_ui(self):
        count = len(self.message_queue)
        if count == 0:
            self.queue_label.setText("Queue empty")
            self.queue_badge.setText("0")
            self.queue_banner_text.setText("No queued messages.")
            self.queue_banner.hide()
            return
        noun = "message" if count == 1 else "messages"
        self.queue_label.setText(f"{count} queued {noun}")
        self.queue_badge.setText(str(count))
        self.queue_banner_text.setText(
            f"{count} queued {noun}. New messages will send automatically in order."
        )
        self.queue_banner.show()

    def has_existing_conversation_content(self):
        return (
            bool(self.history)
            or self.messages_layout.count() > 0
            or self.current_assistant_card is not None
            or bool(self.message_queue)
        )

    def make_submission(self, user_text, attachments):
        if self.active_mode == MODE_CHARACTER and self.active_character() is None:
            raise ValueError("Select a character before sending.")
        prompt_text = user_text.strip()
        if attachments and not self.attachments_allowed_for_mode():
            raise ValueError("File attachments are disabled for this character.")
        should_fetch_urls = bool(prompt_text and self.url_context_allowed_for_mode())
        self.set_status_message("Reading links..." if should_fetch_urls and self.detect_urls(prompt_text) else "Preparing message...")
        url_inputs = self.fetch_urls_for_prompt(prompt_text) if should_fetch_urls else []
        attachment_only_prompt = self.attachment_only_prompt(attachments) if attachments and not prompt_text else ""
        user_message = self.build_user_message(prompt_text, attachments, url_inputs, attachment_only_prompt)
        if prompt_text:
            user_display = prompt_text
        elif attachments:
            user_display = attachment_only_prompt
        else:
            user_display = ""
        return {
            "user_text": prompt_text,
            "attachments": attachments,
            "url_inputs": url_inputs,
            "user_message": user_message,
            "user_display": user_display,
            "model_name": self.current_model_name(),
        }

    def attachment_only_prompt(self, attachments):
        if self.previous_user_has_matching_attachment_category(attachments):
            return "Refer to this:"
        return "Sent attachments."

    def previous_user_has_matching_attachment_category(self, attachments):
        current_categories = self.attachment_categories(attachments)
        if not current_categories:
            return False
        previous_categories = self.previous_user_attachment_categories()
        return bool(current_categories & previous_categories)

    def previous_user_attachment_categories(self):
        if not hasattr(self, "messages_layout"):
            return set()
        for index in range(self.messages_layout.count() - 1, -1, -1):
            item = self.messages_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if not isinstance(widget, MessageCard) or widget.role != "user":
                continue
            return self.attachment_categories(widget.attachments)
        return set()

    def attachment_categories(self, attachments):
        categories = set()
        for item in attachments:
            category = self.attachment_category(item)
            if category:
                categories.add(category)
        return categories

    def attachment_category(self, attachment):
        attachment_type = str(attachment.get("type", "")).strip().lower()
        if attachment_type in {"image", "video", "audio"}:
            return attachment_type
        suffix = Path(str(attachment.get("path", ""))).suffix.lower()
        if suffix in {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".kt", ".java", ".c", ".cpp",
            ".h", ".hpp", ".rs", ".sh", ".bash", ".zsh", ".bat", ".ps1",
            ".sql", ".html", ".css",
        }:
            return "code"
        if suffix in {
            ".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".json", ".xml",
            ".yaml", ".yml", ".ini", ".cfg", ".conf", ".log", ".toml",
        }:
            return "document"
        return attachment_type or "file"

    def try_make_submission(self, user_text, attachments):
        try:
            return self.make_submission(user_text, attachments)
        except ValueError as exc:
            self.set_status_message(str(exc))
            return None

    def enqueue_current_input(self):
        user_text = self.composer.toPlainText().strip()
        attachments = list(self.pending_attachments)
        if not user_text and not attachments:
            return False

        model_name = self.current_model_name()
        if not model_name:
            self.set_status_message("Select a model before sending.")
            return False

        submission = self.try_make_submission(user_text, attachments)
        if submission is None:
            return False
        self.message_queue.append(submission)
        self.composer.clear()
        self.clear_attachments()
        self.status_badge.setText("Queued")
        queued_count = len(self.message_queue)
        noun = "message" if queued_count == 1 else "messages"
        self.status_detail.setText(f"Added to queue. {queued_count} queued {noun}.")
        self.refresh_queue_ui()
        self.composer.setFocus()
        return True

    def process_submission(self, submission):
        if self.active_mode != MODE_CHARACTER:
            self.lock_session_prompt_if_needed()
        self.last_submitted_user_text = submission["user_text"]
        self.pending_user_text = submission["user_text"]
        self.pending_user_message = submission["user_message"]

        self.add_message("user", submission["user_display"], attachments=submission["attachments"])

        self.current_assistant_card = self.add_message(
            "assistant",
            "",
            retry_text=submission["user_text"],
        )
        self.current_assistant_card.start_loading()
        self.start_assistant_reply_focus(self.current_assistant_card)

        queue_count = len(self.message_queue)
        suffix = f" {queue_count} queued." if queue_count else ""
        self.status_badge.setText("Generating")
        self.status_detail.setText(f"Streaming from {submission['model_name']}.{suffix}")

        messages = self.build_messages_payload(submission["user_message"])
        if messages is None:
            self.set_status_message("Select a character before sending.")
            self.current_assistant_card.stop_loading()
            self.current_assistant_card.update_text("_Select a character before sending._")
            self.update_send_availability()
            return
        self.context_usage_prompt_tokens = self.estimate_messages_tokens(messages)
        self.context_usage_completion_tokens = 0
        self.context_usage_completion_text = ""
        self.context_usage_completion_loading = True
        self.refresh_chat_header()

        self.worker = ChatCompletionWorker(self)
        self.worker.configure(
            base_url=self.base_url,
            model_name=submission["model_name"],
            messages=messages,
            temperature=self.temperature_spin.value(),
            top_p=self.top_p_spin.value(),
            top_k=self.top_k_spin.value(),
            api_key=self.current_api_key_value(),
            agent_terminal_enabled=self.is_terminal_enabled_for_request(),
            agent_terminal_permission=self.effective_terminal_permission_for_request(),
            default_permissions=self.default_permissions,
            terminal_cwd=str(self.workspace_path),
        )
        self.worker.token_received.connect(self.on_token_received)
        self.worker.thinking_received.connect(self.on_thinking_received)
        self.worker.terminal_command_started.connect(self.on_terminal_command_started)
        self.worker.terminal_log_received.connect(self.on_terminal_log_received)
        self.worker.terminal_command_finished.connect(self.on_terminal_command_finished)
        self.worker.terminal_permission_requested.connect(self.on_terminal_permission_requested)
        self.worker.generation_started.connect(self.on_generation_started)
        self.worker.generation_finished.connect(self.on_generation_finished)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()
        self.update_send_availability()

    def process_next_queued_message(self):
        if self.worker is not None and self.worker.isRunning():
            return
        if not self.message_queue:
            self.refresh_queue_ui()
            return
        submission = self.message_queue.pop(0)
        self.refresh_queue_ui()
        self.process_submission(submission)

    def has_session_messages(self):
        return bool(self.history)

    def apply_session_prompt(self):
        if not self.session_prompt_enabled:
            self.set_status_message("Enable session prompt before applying it.")
            return
        if self.has_session_messages() or (self.worker is not None and self.worker.isRunning()):
            self.set_status_message("Start a new session before changing the active session prompt.")
            return
        value = self.system_prompt_input.toPlainText().strip()
        if not value:
            self.set_status_message("Enter a session prompt before applying it.")
            return
        self.session_system_prompt = value
        self.session_prompt_locked = True
        self.session_prompt_history = self.add_history_value(self.session_prompt_history, value)
        self.refresh_session_prompt_history_ui()
        self.refresh_session_prompt_ui()
        self.save_config()
        self.set_status_message("Session prompt saved.")
        self.show_toast("Session prompt saved")

    def lock_session_prompt_if_needed(self):
        if self.session_prompt_locked:
            return
        if not self.session_prompt_enabled:
            self.session_system_prompt = ""
            self.session_prompt_locked = False
            self.refresh_session_prompt_ui()
            return
        self.session_system_prompt = self.system_prompt_input.toPlainText().strip()
        if self.session_system_prompt:
            self.session_prompt_history = self.add_history_value(
                self.session_prompt_history,
                self.session_system_prompt,
            )
            self.refresh_session_prompt_history_ui()
            self.save_config()
        self.session_prompt_locked = True
        self.refresh_session_prompt_ui()

    def unlock_session_prompt(self):
        if self.has_session_messages() or (self.worker is not None and self.worker.isRunning()):
            self.set_status_message("Start a new session before changing the active session prompt.")
            return
        self.session_prompt_locked = False
        self.session_system_prompt = ""
        self.refresh_session_prompt_ui()

    def clear_session_prompt_text(self):
        if self.has_session_messages() or (self.worker is not None and self.worker.isRunning()):
            self.set_status_message("Start a new session before clearing the active session prompt.")
            return
        self.system_prompt_input.clear()
        self.session_system_prompt = ""
        self.session_prompt_locked = False
        self.save_config()
        self.refresh_session_prompt_ui()

    def refresh_session_prompt_ui(self):
        draft_text = self.system_prompt_input.toPlainText().strip()
        active_text = self.session_system_prompt if self.session_prompt_locked else draft_text
        if not self.session_prompt_enabled:
            active_text = ""
        preview = active_text if active_text else "No session prompt"
        if len(preview) > 140:
            preview = preview[:137] + "..."

        self.system_prompt_input.setReadOnly(self.session_prompt_locked)
        self.system_prompt_input.setEnabled(self.session_prompt_enabled)
        self.session_prompt_badge.setText(preview)

        if not self.session_prompt_enabled:
            self.session_prompt_detail.setText("Session prompt group is disabled.")
        elif self.session_prompt_locked:
            self.session_prompt_detail.setText(
                "Locked for the current session. Start a new session to change it."
            )
        elif draft_text:
            self.session_prompt_detail.setText(
                "Draft prompt ready. It will lock in on the first send of the next session."
            )
        else:
            self.session_prompt_detail.setText(
                "Leave blank for a normal session, or write an instruction that should persist for the whole session."
            )

        self.unlock_prompt_button.setVisible(self.session_prompt_locked)
        self.clear_prompt_button.setEnabled(bool(draft_text) and self.session_prompt_enabled and not self.session_prompt_locked)
        self.apply_prompt_button.setEnabled(bool(draft_text) and self.session_prompt_enabled and not self.session_prompt_locked)
        self.apply_prompt_button.setProperty("applied", self.session_prompt_locked)
        self.apply_prompt_button.style().unpolish(self.apply_prompt_button)
        self.apply_prompt_button.style().polish(self.apply_prompt_button)
        if hasattr(self, "session_prompt_section"):
            self.session_prompt_section.setVisible(
                self.session_prompt_enabled and self.active_mode != MODE_CHARACTER
            )
        self.refresh_session_prompt_history_ui()

    def build_user_message(self, user_text, attachments, url_inputs=None, attachment_only_prompt=""):
        url_inputs = url_inputs or []
        if not attachments and not url_inputs:
            return {"role": "user", "content": user_text}

        prompt = user_text or attachment_only_prompt or "Describe the attached inputs."
        content = [{"type": "text", "text": prompt}]
        attachment_sections = []
        url_sections = []

        for item in url_inputs:
            if item["kind"] == "image":
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": item["data_url"]},
                    }
                )
                url_sections.append(f"Image URL fetched: {item['url']}")
            else:
                url_sections.append(
                    f"URL: {item['url']}\nType: {item['label']}\n```text\n{item['text']}\n```"
                )

        for item in attachments:
            if item["type"] == "image":
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": self.image_data_url_for_prompt(item["path"])},
                    }
                )
            else:
                extracted = self.attachment_text_for_prompt(item)
                if extracted:
                    attachment_sections.append(
                        f"File: {item['name']}\n```text\n{extracted}\n```"
                    )
                else:
                    attachment_sections.append(
                        f"File attached: {item['name']} (binary or unsupported for inline extraction)."
                    )
        if url_sections:
            content[0]["text"] = (
                f"{content[0]['text']}\n\nFetched URL contents:\n\n" + "\n\n".join(url_sections)
            )
        if attachment_sections:
            content[0]["text"] = (
                f"{content[0]['text']}\n\nAttached file contents:\n\n" + "\n\n".join(attachment_sections)
            )
        return {"role": "user", "content": content}

    def build_messages_payload(self, user_message):
        return build_messages(
            self.request_config_snapshot(),
            self.history,
            user_message,
            terminal_instruction=(
                agent_terminal_prompt(self.workspace_path)
                if self.is_terminal_enabled_for_request()
                else None
            ),
        )

    def request_config_snapshot(self):
        return {
            "active_mode": self.active_mode,
            "session_prompt": {
                "enabled": self.session_prompt_enabled,
                "value": self.session_system_prompt,
                "history": self.session_prompt_history,
            },
            "character_profiles": self.character_profiles,
            "agent_terminal": {
                "enabled": self.agent_terminal_enabled,
                "permission": self.agent_terminal_permission,
                "default_permissions": self.default_permissions,
            },
            "workspace": {
                "path": str(self.workspace_path),
            },
        }

    def refresh_chat_header(self):
        if not hasattr(self, "chat_title_label"):
            return
        title, subtitle = self.chat_header_text()
        self.chat_title_label.setText(title)
        self.chat_subtitle_label.setText(subtitle)

        enabled = self.context_usage_enabled_for_mode()
        if hasattr(self, "context_usage_checkbox"):
            self.context_usage_checkbox.blockSignals(True)
            self.context_usage_checkbox.setChecked(enabled)
            self.context_usage_checkbox.blockSignals(False)
        if hasattr(self, "context_usage_toggle_label"):
            self.context_usage_toggle_label.setText(f"Show usage in {MODE_LABELS[self.active_mode]} mode")

        context_window = self.active_context_window()
        current_tokens = self.context_usage_prompt_tokens + self.context_usage_completion_tokens
        if hasattr(self, "context_usage_frame"):
            self.context_usage_frame.setVisible(enabled)
            self.context_usage_frame.setToolTip(
                self.context_usage_tooltip(
                    self.context_usage_prompt_tokens,
                    self.context_usage_completion_tokens,
                    context_window,
                )
            )
        if hasattr(self, "context_usage_label"):
            self.context_usage_label.setText(
                f"Context {self.format_token_amount(current_tokens)} / {self.format_token_amount(context_window)}"
            )
        loading_active = enabled and self.context_usage_completion_loading
        if hasattr(self, "context_usage_new_tokens_label"):
            self.context_usage_new_tokens_label.setText(str(self.context_usage_completion_tokens))
            self.context_usage_new_tokens_label.setVisible(not loading_active)
        if hasattr(self, "context_usage_loading_label"):
            self.context_usage_loading_label.setVisible(loading_active)
        if hasattr(self, "context_usage_loading_movie"):
            if loading_active:
                if self.context_usage_loading_movie.state() != QMovie.MovieState.Running:
                    self.context_usage_loading_movie.start()
            else:
                self.context_usage_loading_movie.stop()
        if hasattr(self, "context_usage_detail"):
            self.context_usage_detail.setText(self.context_usage_detail_text(context_window))

    def chat_header_text(self):
        if self.active_mode == MODE_AGENT:
            return "Agent", f"Workspace: {self.workspace_path}"
        if self.active_mode == MODE_CHARACTER:
            character = self.active_character()
            if character:
                return character.get("name", "Character"), "Character chat"
            return "Character", "Select a character to start"
        return "Chat", "General conversation"

    def active_context_window(self):
        runtime_value = self.normalize_context_window_value(getattr(self, "runtime_context_window", 0))
        if runtime_value:
            return runtime_value
        return self.model_context_window(self.current_model_name())

    def context_usage_tooltip(self, prompt_tokens, completion_tokens, context_window):
        new_tokens = "loading" if self.context_usage_completion_loading else str(completion_tokens)
        return (
            "context "
            f"{self.format_token_amount(prompt_tokens)} + {new_tokens}"
            f"/{self.format_token_amount(context_window)}"
        )

    def context_usage_detail_text(self, context_window):
        if not self.context_usage_enabled_for_mode():
            return "Hidden for this mode."
        if context_window:
            return f"Runtime context window: {self.format_token_amount(context_window)} tokens."
        return "Runtime context window: unknown."

    def format_token_amount(self, value):
        value = self.normalize_context_window_value(value)
        if not value:
            return "--"
        if value >= 1000:
            return f"{value / 1000:.1f}k"
        return str(value)

    def estimate_messages_tokens(self, messages):
        total = 0
        for message in messages:
            total += 4
            total += self.count_content_tokens(message.get("content", ""))
        return total

    def count_content_tokens(self, content):
        if isinstance(content, str):
            return self.count_text_tokens(content)
        if isinstance(content, list):
            total = 0
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    total += self.count_text_tokens(item.get("text", ""))
                elif item.get("type") == "image_url":
                    total += 256
                else:
                    total += 64
            return total
        return self.count_text_tokens(str(content))

    def count_text_tokens(self, text):
        text = str(text or "")
        if not text:
            return 0
        for counter in (
            self.server_tokenize_text,
            self.local_tokenize_text,
            self.estimate_text_tokens,
        ):
            value = counter(text)
            if value is not None:
                return value
        return 0

    def server_tokenize_text(self, text):
        try:
            response = requests.post(
                self.build_server_url("/tokenize"),
                json={"content": text},
                headers=self.auth_headers(),
                timeout=8,
            )
        except Exception:
            return None
        if response.status_code != 200:
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        tokens = payload.get("tokens") if isinstance(payload, dict) else None
        if not isinstance(tokens, list):
            return None
        return len(tokens)

    def local_tokenize_text(self, text):
        try:
            import tiktoken
        except ImportError:
            return None
        model_name = self.current_model_name()
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except Exception:
            try:
                encoding = tiktoken.get_encoding("cl100k_base")
            except Exception:
                return None
        try:
            return len(encoding.encode(text))
        except Exception:
            return None

    def estimate_text_tokens(self, text):
        text = str(text or "")
        if not text:
            return None
        return max(1, round(len(text) / 4))

    def send_message(self):
        if self.worker is not None and self.worker.isRunning():
            self.enqueue_current_input()
            return

        user_text = self.composer.toPlainText().strip()
        attachments = list(self.pending_attachments)
        if not user_text and not attachments:
            return

        model_name = self.current_model_name()
        if not model_name:
            self.set_status_message("Select a model before sending.")
            return

        submission = self.try_make_submission(user_text, attachments)
        if submission is None:
            return
        self.composer.clear()
        self.clear_attachments()
        self.process_submission(submission)

    def retry_message(self, user_text):
        if self.worker is not None and self.worker.isRunning():
            self.composer.setPlainText(user_text)
            self.composer.moveCursor(self.composer.textCursor().MoveOperation.End)
            self.enqueue_current_input()
            return
        self.composer.setPlainText(user_text)
        self.composer.moveCursor(self.composer.textCursor().MoveOperation.End)
        self.send_message()

    def on_generation_started(self):
        self.update_send_availability()

    def on_token_received(self, token):
        should_focus_reply = self.assistant_reply_focus_active
        self.context_usage_completion_text += token
        self.refresh_chat_header()
        if self.current_assistant_card is not None:
            self.current_assistant_card.stop_loading()
            if not self.current_assistant_card.raw_text:
                self.current_assistant_card.update_text(token)
            else:
                self.current_assistant_card.append_text(token)
        if should_focus_reply:
            self.scroll_to_assistant_reply()

    def on_thinking_received(self, token):
        should_focus_reply = self.assistant_reply_focus_active
        if self.current_assistant_card is not None:
            self.current_assistant_card.append_thinking(token, self.show_thinking_checkbox.isChecked())
        if should_focus_reply:
            self.scroll_to_assistant_reply()

    def on_generation_finished(self, success, stopped, full_response, _full_thinking):
        if self.current_assistant_card is not None:
            self.current_assistant_card.flush_pending_render()
            self.current_assistant_card.stop_loading()
        self.context_usage_completion_text = full_response or self.context_usage_completion_text
        self.context_usage_completion_tokens = self.count_text_tokens(self.context_usage_completion_text)
        self.context_usage_completion_loading = False
        self.refresh_chat_header()
        self.stop_assistant_reply_focus()
        if hasattr(self, "terminal_approval_banner"):
            self.terminal_approval_banner.hide()
        self.pending_terminal_permission = None
        if success and self.pending_user_message and full_response.strip():
            self.history.append(self.pending_user_message)
            clean_response = normalize_terminal_fences(
                replace_terminal_command_tags(full_response)
            ).strip()
            self.history.append({"role": "assistant", "content": clean_response or full_response})
            if self.active_mode == MODE_CHARACTER:
                self.increment_active_character_message_count()
            self.status_badge.setText("Ready")
            self.status_detail.setText("Response completed.")
        elif stopped:
            self.status_badge.setText("Stopped")
            self.status_detail.setText("Generation stopped. The partial answer was not added to context.")
            if self.current_assistant_card and not full_response.strip():
                self.current_assistant_card.update_text("_Stopped before any response arrived._")
        else:
            if self.current_assistant_card and not full_response.strip():
                self.current_assistant_card.update_text("_No response received._")

        self.pending_user_text = None
        self.pending_user_message = None
        self.current_assistant_card = None
        self.worker = None
        self.process_next_queued_message()
        self.update_send_availability()
        self.composer.setFocus()

    def on_error(self, message):
        self.context_usage_completion_loading = False
        self.refresh_chat_header()
        self.stop_assistant_reply_focus()
        if hasattr(self, "terminal_approval_banner"):
            self.terminal_approval_banner.hide()
        self.pending_terminal_permission = None
        self.status_badge.setText("Request failed")
        self.status_detail.setText(message)
        self.add_message("system", message)
        self.process_next_queued_message()

    def stop_generation(self):
        self.stop_assistant_reply_focus()
        if self.pending_terminal_permission and self.worker is not None:
            self.worker.resolve_terminal_permission("reject")
        if hasattr(self, "terminal_approval_banner"):
            self.terminal_approval_banner.hide()
        self.pending_terminal_permission = None
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()

    def add_message(self, role, text, retry_text=None, attachments=None):
        timestamp = datetime.now().strftime("%H:%M")
        card = MessageCard(
            role=role,
            text=text,
            timestamp=timestamp,
            retry_text=retry_text,
            attachments=attachments,
            render_debounce_enabled=self.assistant_debounce_enabled,
            render_debounce_interval_ms=self.assistant_debounce_interval_ms,
        )
        card.retry_requested.connect(self.retry_message)
        card.image_preview_requested.connect(self.open_message_image_gallery)
        card.file_preview_requested.connect(self.open_file_attachment)
        self.messages_layout.addWidget(card)
        self.update_empty_state()
        self.scroll_to_bottom()
        return card

    def open_message_image_gallery(self, image_paths, start_index):
        if not image_paths:
            return
        dialog = ImageGalleryDialog(image_paths, start_index=start_index, parent=self)
        dialog.exec()

    def set_status_message(self, text):
        self.status_badge.setText("Notice")
        self.status_detail.setText(text)

    def update_thinking_visibility(self, *_args):
        visible = self.show_thinking_checkbox.isChecked()
        self.show_thinking = visible
        self.save_config()
        for index in range(self.messages_layout.count()):
            item = self.messages_layout.itemAt(index)
            widget = item.widget()
            if isinstance(widget, MessageCard):
                widget.set_thinking_visibility(visible)

    def update_empty_state(self):
        if hasattr(self, "empty_title") and hasattr(self, "empty_body"):
            if self.active_mode == MODE_AGENT:
                self.empty_title.setText("Ready for local agent work")
                self.empty_body.setText("Choose a workspace, enable terminal access, then ask for changes.")
            elif self.active_mode == MODE_CHARACTER:
                character = self.active_character()
                if character:
                    self.empty_title.setText(f"Chat with {character.get('name', 'Character')}")
                    self.empty_body.setText(
                        character.get("greeting")
                        or "Start a conversation with the selected character."
                    )
                else:
                    self.empty_title.setText("No character selected")
                    self.empty_body.setText("Sync character profiles from your server to start.")
            else:
                self.empty_title.setText("Start a new conversation")
                self.empty_body.setText("Ask anything, attach files, or provide URL context.")
        self.empty_state.setVisible(self.messages_layout.count() == 0)

    def update_sticky_code_header(self, *_args):
        if self.sticky_code_header is None or not hasattr(self, "scroll_area"):
            return

        active_block = None
        active_geometry = None
        viewport = self.scroll_area.viewport()
        header_height = self.sticky_code_header.height()

        for code_block in self.messages_container.findChildren(AssistantCodeBlock):
            top_left = code_block.mapTo(viewport, QPoint(0, 0))
            top = top_left.y()
            bottom = top + code_block.height()
            if top <= 0 and bottom > header_height:
                active_block = code_block
                active_geometry = (
                    max(0, top_left.x()),
                    0,
                    min(code_block.width(), viewport.width() - max(0, top_left.x())),
                    header_height,
                )
                break

        if active_block is None or active_geometry is None or active_geometry[2] <= 0:
            self.sticky_code_header.hide()
            self.sticky_code_header.set_code_block(None)
            return

        self.sticky_code_header.set_code_block(active_block)
        self.sticky_code_header.setGeometry(*active_geometry)
        self.sticky_code_header.raise_()
        self.sticky_code_header.show()

    def eventFilter(self, watched, event):
        if hasattr(self, "scroll_area") and watched == self.scroll_area.viewport() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
        ):
            QTimer.singleShot(0, self.update_sticky_code_header)
        for scroll_area in tuple(getattr(self, "auto_scrollbar_timers", {}).keys()):
            if watched in (scroll_area.viewport(), scroll_area.verticalScrollBar()):
                if event.type() in (
                    QEvent.Type.Wheel,
                    QEvent.Type.MouseButtonPress,
                    QEvent.Type.MouseMove,
                    QEvent.Type.MouseButtonRelease,
                    QEvent.Type.KeyPress,
                ):
                    self.show_auto_scrollbar(scroll_area)
                elif event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
                    QTimer.singleShot(0, lambda area=scroll_area: self.hide_auto_scrollbar(area))
        if (
            hasattr(self, "character_hero_card")
            and watched == self.character_hero_card
            and event.type() in (QEvent.Type.Resize, QEvent.Type.Show)
        ):
            QTimer.singleShot(0, self.position_character_hero_elements)
            QTimer.singleShot(0, lambda: self.refresh_character_avatar(self.active_character()))
        if (
            self.worker is not None
            and self.worker.isRunning()
            and self.current_assistant_card is not None
            and watched in (self.scroll_area.viewport(), self.scroll_area.verticalScrollBar())
            and event.type() in (
                QEvent.Type.Wheel,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonDblClick,
                QEvent.Type.MouseMove,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.KeyPress,
            )
        ):
            event_type = event.type()
            self.assistant_reply_scroll_interaction_active = True
            if event_type == QEvent.Type.Wheel:
                wheel_delta = event.angleDelta().y() or event.pixelDelta().y()
                if wheel_delta > 0:
                    self.assistant_reply_scroll_away_requested = True
            if event_type == QEvent.Type.KeyPress and event.key() in (
                Qt.Key.Key_Down,
                Qt.Key.Key_PageDown,
                Qt.Key.Key_End,
            ):
                self.assistant_reply_scroll_away_requested = False
            if event_type == QEvent.Type.KeyPress and event.key() in (
                Qt.Key.Key_Up,
                Qt.Key.Key_PageUp,
                Qt.Key.Key_Home,
            ):
                self.assistant_reply_scroll_away_requested = True
            self.stop_assistant_reply_focus()
            if event_type in (
                QEvent.Type.Wheel,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.KeyPress,
            ):
                self.reconcile_assistant_reply_follow_after_scroll()
        return super().eventFilter(watched, event)

    def start_assistant_reply_focus(self, card):
        self.assistant_reply_focus_card = card
        self.assistant_reply_focus_active = True
        self.assistant_reply_scroll_away_requested = False
        self.scroll_to_assistant_reply()

    def stop_assistant_reply_focus(self):
        self.assistant_reply_focus_active = False
        self.assistant_reply_focus_card = None

    def update_assistant_reply_follow_state(self, *_args):
        scrollbar = self.scroll_area.verticalScrollBar()
        self.assistant_reply_last_scroll_max = scrollbar.maximum()
        if self.current_assistant_card is None:
            return
        if self.worker is None or not self.worker.isRunning():
            return
        if self.assistant_reply_focus_active:
            return
        if getattr(self, "assistant_reply_scroll_away_requested", False):
            if self.is_chat_scrolled_to_bottom(threshold=2):
                self.assistant_reply_scroll_away_requested = False
                self.start_assistant_reply_focus(self.current_assistant_card)
            return
        if self.is_chat_scrolled_to_bottom(threshold=48):
            self.assistant_reply_scroll_away_requested = False
            self.start_assistant_reply_focus(self.current_assistant_card)

    def update_assistant_reply_follow_range(self, _minimum, maximum):
        scrollbar = self.scroll_area.verticalScrollBar()
        previous_maximum = getattr(self, "assistant_reply_last_scroll_max", 0)
        was_at_bottom = previous_maximum - scrollbar.value() <= 64
        self.assistant_reply_last_scroll_max = maximum
        if self.current_assistant_card is None:
            return
        if self.worker is None or not self.worker.isRunning():
            return
        if getattr(self, "assistant_reply_scroll_interaction_active", False):
            return
        if getattr(self, "assistant_reply_scroll_away_requested", False):
            if self.is_chat_scrolled_to_bottom(threshold=2):
                self.assistant_reply_scroll_away_requested = False
                self.start_assistant_reply_focus(self.current_assistant_card)
            return
        if self.assistant_reply_focus_active or was_at_bottom:
            self.start_assistant_reply_focus(self.current_assistant_card)

    def reconcile_assistant_reply_follow_after_scroll(self):
        def reconcile():
            try:
                if self.current_assistant_card is None:
                    return
                if self.worker is None or not self.worker.isRunning():
                    return
                if (
                    not getattr(self, "assistant_reply_scroll_away_requested", False)
                    and self.is_chat_scrolled_to_bottom(threshold=64)
                ):
                    self.start_assistant_reply_focus(self.current_assistant_card)
                else:
                    self.stop_assistant_reply_focus()
            finally:
                self.assistant_reply_scroll_interaction_active = False

        QTimer.singleShot(80, reconcile)

    def handle_assistant_reply_content_changed(self, card):
        if not self.assistant_reply_focus_active:
            return
        if self.assistant_reply_focus_card is not card:
            return
        self.scroll_to_assistant_reply()

    def scroll_to_assistant_reply(self):
        card = self.assistant_reply_focus_card
        if card is None:
            return

        def apply_scroll():
            if not self.assistant_reply_focus_active or self.assistant_reply_focus_card is not card:
                return
            scrollbar = self.scroll_area.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

        QTimer.singleShot(0, apply_scroll)

    def is_chat_scrolled_to_bottom(self, threshold=24):
        scrollbar = self.scroll_area.verticalScrollBar()
        return scrollbar.maximum() - scrollbar.value() <= threshold

    def scroll_to_bottom(self):
        QTimer.singleShot(
            0,
            lambda: self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            ),
        )

    def clear_chat(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.history = []
        self.pending_user_text = None
        self.pending_user_message = None
        self.pending_terminal_permission = None
        self.context_usage_prompt_tokens = 0
        self.context_usage_completion_tokens = 0
        self.context_usage_completion_text = ""
        self.context_usage_completion_loading = False
        self.stop_assistant_reply_focus()
        if hasattr(self, "terminal_approval_banner"):
            self.terminal_approval_banner.hide()
        self.message_queue = []
        previous_prompt = self.session_system_prompt or self.system_prompt_input.toPlainText().strip()
        self.session_system_prompt = ""
        self.session_prompt_locked = False
        self.system_prompt_input.setPlainText(previous_prompt)
        self.current_assistant_card = None
        self.clear_attachments()
        self.status_badge.setText("Ready")
        self.status_detail.setText("New session started.")
        if self.sticky_code_header is not None:
            self.sticky_code_header.hide()
            self.sticky_code_header.set_code_block(None)
        self.refresh_session_prompt_ui()
        self.refresh_queue_ui()
        self.update_empty_state()
        self.update_send_availability()
        self.refresh_chat_header()
