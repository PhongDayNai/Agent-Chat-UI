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


class AttachmentUrlMixin:
    def detect_attachment_type(self, path):
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type:
            if mime_type.startswith("image/"):
                return "image"
            if mime_type.startswith("video/"):
                return "video"
            if mime_type.startswith("audio/"):
                return "audio"
        suffix = Path(path).suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}:
            return "image"
        if suffix in {".mp4", ".mov", ".mkv", ".avi", ".webm"}:
            return "video"
        if suffix in {".wav", ".mp3", ".m4a", ".ogg", ".flac"}:
            return "audio"
        return "file"

    def is_text_preview_file(self, path):
        return Path(path).suffix.lower() in TEXT_PREVIEW_SUFFIXES

    def add_attachments(self):
        if not self.attachments_allowed_for_mode():
            self.set_status_message("File attachments are disabled for this character.")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Attach files",
            "",
            "Supported Files (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.pdf *.txt *.md *.doc *.docx *.csv *.json *.wav *.mp3 *.mp4 *.mov *.mkv);;All Files (*)",
        )
        self.add_attachment_paths(paths)

    def add_attachment_paths(self, paths):
        if not self.attachments_allowed_for_mode():
            self.set_status_message("File attachments are disabled for this character.")
            return
        if not paths:
            return
        added = False
        for path in paths:
            if not path or any(item["path"] == path for item in self.pending_attachments):
                continue
            self.pending_attachments.append(
                {
                    "path": path,
                    "name": Path(path).name,
                    "type": self.detect_attachment_type(path),
                }
            )
            added = True
        if added:
            self.refresh_attachment_summary()
            self.update_send_availability()

    def clear_attachments(self):
        self.pending_attachments = []
        self.refresh_attachment_summary()
        self.update_send_availability()

    def attachment_area_height(self):
        if not self.pending_attachments:
            return 58
        has_images = any(item["type"] == "image" for item in self.pending_attachments)
        return 122 if has_images else 58

    def refresh_attachment_summary(self):
        while self.attachments_layout.count():
            item = self.attachments_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self.pending_attachments:
            self.attachment_scroll.setFixedHeight(self.attachment_area_height())
            self.attachment_scroll.hide()
            return

        self.attachment_scroll.setFixedHeight(self.attachment_area_height())
        self.attachment_scroll.show()
        for attachment in self.pending_attachments:
            chip = AttachmentChip(attachment)
            chip.remove_requested.connect(self.remove_attachment)
            chip.preview_requested.connect(self.open_attachment_item)
            self.attachments_layout.addWidget(chip)

        self.attachments_layout.addStretch()

    def remove_attachment(self, path):
        self.pending_attachments = [item for item in self.pending_attachments if item["path"] != path]
        self.refresh_attachment_summary()
        self.update_send_availability()

    def open_attachment_item(self, clicked_path):
        image_paths = [item["path"] for item in self.pending_attachments if item["type"] == "image"]
        if clicked_path in image_paths:
            start_index = image_paths.index(clicked_path)
            dialog = ImageGalleryDialog(image_paths, start_index=start_index, parent=self)
            dialog.exec()
            return
        self.open_file_attachment(clicked_path)

    def open_file_attachment(self, path):
        if self.is_text_preview_file(path):
            dialog = FilePreviewDialog(path, parent=self)
            dialog.exec()
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))

    def encode_attachment(self, path):
        with open(path, "rb") as handle:
            return base64.b64encode(handle.read()).decode("utf-8")

    def image_data_url_for_prompt(self, path):
        suffix = Path(path).suffix.lower()
        mime_type = mimetypes.guess_type(path)[0] or "image/png"

        if suffix in {".png", ".jpg", ".jpeg"}:
            encoded = self.encode_attachment(path)
            return f"data:{mime_type};base64,{encoded}"

        image = QImage(path)
        if image.isNull():
            raise ValueError(f"Unable to decode image file: {Path(path).name}")

        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            buffer.close()
            raise ValueError(f"Unable to convert image file to PNG: {Path(path).name}")

        encoded = base64.b64encode(bytes(buffer.data())).decode("utf-8")
        buffer.close()
        return f"data:image/png;base64,{encoded}"

    def read_text_attachment(self, path):
        try:
            content = Path(path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
        return content

    def read_pdf_attachment(self, path):
        if PdfReader is None:
            return (
                "PDF extraction is unavailable because the optional dependency "
                "`pypdf` is not installed."
            )
        reader = PdfReader(path)
        parts = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                parts.append(f"[Page {page_number}]\n{text}")
            if sum(len(part) for part in parts) >= MAX_ATTACHMENT_TEXT_CHARS:
                break
        if not parts:
            return "No extractable text was found in this PDF."
        return "\n\n".join(parts)

    def attachment_text_for_prompt(self, attachment):
        path = attachment["path"]
        suffix = Path(path).suffix.lower()
        try:
            if suffix == ".pdf":
                content = self.read_pdf_attachment(path)
            elif self.is_text_preview_file(path):
                content = self.read_text_attachment(path)
            else:
                return ""
        except Exception as exc:
            return f"Unable to read file content: {exc}"

        content = content.strip()
        if len(content) > MAX_ATTACHMENT_TEXT_CHARS:
            content = content[:MAX_ATTACHMENT_TEXT_CHARS] + "\n\n[Truncated]"
        return content

    def detect_urls(self, text):
        urls = []
        seen = set()
        for match in URL_RE.finditer(text):
            url = match.group(0).rstrip(TRAILING_URL_PUNCTUATION)
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
            if len(urls) >= MAX_URLS_PER_MESSAGE:
                break
        return urls

    def fetch_url_bytes(self, url):
        with requests.get(
            url,
            timeout=URL_FETCH_TIMEOUT,
            stream=True,
            headers={"User-Agent": "agent-chat-ui/1.0"},
        ) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            chunks = []
            total = 0
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_URL_DOWNLOAD_BYTES:
                    raise ValueError("download exceeded the size limit")
                chunks.append(chunk)
            return b"".join(chunks), content_type, response.encoding

    def decode_url_text(self, data, encoding=None):
        for candidate in [encoding, "utf-8", "utf-8-sig", "latin-1"]:
            if not candidate:
                continue
            try:
                return data.decode(candidate)
            except (LookupError, UnicodeDecodeError):
                continue
        return data.decode("utf-8", errors="replace")

    def extract_pdf_text_bytes(self, data):
        if PdfReader is None:
            return "PDF extraction is unavailable because `pypdf` is not installed."
        reader = PdfReader(BytesIO(data))
        parts = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                parts.append(f"[Page {page_number}]\n{text}")
            if sum(len(part) for part in parts) >= MAX_URL_TEXT_CHARS:
                break
        if not parts:
            return "No extractable text was found in this PDF."
        return "\n\n".join(parts)

    def fetch_url_for_prompt(self, url):
        data, content_type, encoding = self.fetch_url_bytes(url)
        suffix = Path(url.split("?", 1)[0]).suffix.lower()

        image_mime_type = content_type if content_type.startswith("image/") else mimetypes.guess_type(url)[0]
        if image_mime_type and image_mime_type.startswith("image/"):
            encoded = base64.b64encode(data).decode("utf-8")
            return {
                "kind": "image",
                "url": url,
                "data_url": f"data:{image_mime_type};base64,{encoded}",
            }

        if content_type == "application/pdf" or suffix == ".pdf":
            text = self.extract_pdf_text_bytes(data)
            media_label = "PDF"
        else:
            raw_text = self.decode_url_text(data, encoding)
            looks_like_html = raw_text.lstrip().lower().startswith(("<!doctype html", "<html"))
            if "html" in content_type or suffix in {".htm", ".html"} or looks_like_html:
                extractor = HtmlTextExtractor()
                extractor.feed(raw_text)
                title = extractor.title
                text = extractor.text()
                if title:
                    text = f"Title: {title}\n\n{text}"
                media_label = "Web page"
            else:
                text = raw_text.strip()
                media_label = content_type or "Text"

        text = text.strip()
        if len(text) > MAX_URL_TEXT_CHARS:
            text = text[:MAX_URL_TEXT_CHARS] + "\n\n[Truncated]"
        if not text:
            text = "No readable text was found."
        return {
            "kind": "text",
            "url": url,
            "label": media_label,
            "text": text,
        }

    def fetch_urls_for_prompt(self, user_text):
        url_results = []
        for url in self.detect_urls(user_text):
            try:
                url_results.append(self.fetch_url_for_prompt(url))
            except Exception as exc:
                url_results.append(
                    {
                        "kind": "text",
                        "url": url,
                        "label": "Fetch error",
                        "text": f"Unable to fetch this URL: {exc}",
                    }
                )
        return url_results

    def attachments_allowed_for_mode(self):
        if self.active_mode != MODE_CHARACTER:
            return True
        return bool(self.active_character_capabilities().get("file_context"))

    def url_context_allowed_for_mode(self):
        if self.active_mode != MODE_CHARACTER:
            return True
        return bool(self.active_character_capabilities().get("url_context"))
