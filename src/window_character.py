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
from PyQt6.QtWidgets import QFileDialog, QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget, QWidgetAction

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

from constants import (
    APP_WORKSPACE, ARROW_DOWN_ICON_PATH, CLOSE_ICON_PATH, CONFIG_PATH, DEFAULT_PERMISSIONS_ICON_PATH,
    DEFAULT_SERVER_BASE_URL, FULL_ACCESS_ICON_PATH, LAYOUT_GRID_ICON_PATH, LAYOUT_LIST_ICON_PATH, LEGACY_CONFIG_PATH,
    MAX_ATTACHMENT_TEXT_CHARS, MAX_URL_DOWNLOAD_BYTES, MAX_URLS_PER_MESSAGE,
    MAX_URL_TEXT_CHARS, TEXT_PREVIEW_SUFFIXES, TRAILING_URL_PUNCTUATION,
    URL_FETCH_TIMEOUT, URL_RE, agent_terminal_prompt,
)
from html_utils import HtmlTextExtractor
from markdown_utils import normalize_terminal_fences, replace_terminal_command_tags
from characters import (
    CHARACTER_SORT_LABELS, DEFAULT_CHARACTER_PROFILES, character_avatar_url,
    character_poster_url, character_sort_label,
    filter_characters, get_active_character, get_effective_character_capabilities,
    is_character_favorite, normalize_character, normalize_character_profiles,
    normalize_character_sort_mode,
    set_character_capability, set_character_favorite, sort_characters,
)
from character_widgets import CharacterAccessPanel, CharacterPosterCard, CharacterSidebarHeroCard, render_svg_pixmap
from message_builder import build_messages
from modes import MODE_AGENT, MODE_CHARACTER, MODE_CHAT, normalize_mode
from widgets import AttachmentChip, FilePreviewDialog, ImageGalleryDialog, MessageCard, AssistantCodeBlock
from worker import ChatCompletionWorker
import key_storage

from window_shared import (
    CHARACTER_CARD_MAX_HEIGHT, CHARACTER_CARD_MAX_WIDTH, CHARACTER_CARD_MIN_HEIGHT,
    CHARACTER_CARD_MIN_WIDTH, CHARACTER_CARD_RATIOS, COMPACT_LAYOUT_HEIGHT, COMPACT_LAYOUT_WIDTH,
    COMPACT_SIDEBAR_MIN_WIDTH, COMPACT_SIDEBAR_WIDTH, COMPACT_WINDOW_GUTTER,
    DEFAULT_ASSISTANT_DEBOUNCE_ENABLED, DEFAULT_ASSISTANT_DEBOUNCE_INTERVAL_MS,
    DEFAULT_CHARACTER_CARD_RATIO, DEFAULT_COMPOSER_MAX_LINES,
    DEFAULT_TERMINAL_PERMISSIONS, MAX_COMPOSER_MAX_LINES, MIN_COMPOSER_MAX_LINES,
    SIDEBAR_DROPDOWN_TEXT_INSET, SIDEBAR_ELIDE_WIDTH, TERMINAL_PERMISSION_COLORS,
    TERMINAL_PERMISSION_DEFAULT, TERMINAL_PERMISSION_FULL_ACCESS, CharacterChoiceCard,
)


class CharacterMixin:
    def build_character_overlay(self):
        self.character_overlay = QFrame(self.content_frame)
        self.character_overlay.setObjectName("characterOverlay")
        self.character_overlay.hide()
        self.character_overlay_layout_mode = "grid"
        overlay_layout = QVBoxLayout(self.character_overlay)
        overlay_layout.setContentsMargins(30, 24, 24, 0)
        overlay_layout.setSpacing(22)

        header = QHBoxLayout()
        header.setSpacing(12)
        title_column = QVBoxLayout()
        title_column.setSpacing(4)
        title = QLabel("Change character")
        title.setObjectName("overlayTitle")
        title_column.addWidget(title)
        subtitle = QLabel("Choose who you want to chat with")
        subtitle.setObjectName("overlaySubtitle")
        title_column.addWidget(subtitle)
        header.addLayout(title_column)
        header.addStretch()
        self.character_sort_button = QPushButton(character_sort_label(getattr(self, "character_sort_mode", "name_asc")))
        self.character_sort_button.setObjectName("characterSortButton")
        self.character_sort_button.setFixedSize(112, 40)
        self.character_sort_button.setIcon(QIcon(render_svg_pixmap(ARROW_DOWN_ICON_PATH, QSize(13, 13), "#9aa1aa")))
        self.character_sort_button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.character_sort_button.setToolTip("Sort characters")
        self.character_sort_menu = QMenu(self.character_sort_button)
        self.character_sort_menu.setObjectName("characterSortMenu")
        self.character_sort_actions = {}
        for sort_mode, label in CHARACTER_SORT_LABELS.items():
            action = self.character_sort_menu.addAction(label)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, value=sort_mode: self.set_character_sort_mode(value)
            )
            self.character_sort_actions[sort_mode] = action
        self.character_sort_button.clicked.connect(self.show_character_sort_menu)
        self.refresh_character_sort_ui()
        header.addWidget(self.character_sort_button, 0, Qt.AlignmentFlag.AlignTop)

        layout_toggle = QFrame()
        layout_toggle.setObjectName("characterLayoutToggle")
        layout_toggle.setFixedSize(76, 40)
        layout_toggle_layout = QHBoxLayout(layout_toggle)
        layout_toggle_layout.setContentsMargins(5, 5, 5, 5)
        layout_toggle_layout.setSpacing(4)

        self.character_layout_group = QButtonGroup(self)
        self.character_layout_group.setExclusive(True)

        self.character_grid_button = QPushButton("")
        self.character_grid_button.setObjectName("characterLayoutButton")
        self.character_grid_button.setCheckable(True)
        self.character_grid_button.setChecked(True)
        self.character_grid_button.setFixedSize(30, 30)
        self.character_grid_button.setToolTip("Grid view")
        self.character_grid_button.setIcon(QIcon(render_svg_pixmap(LAYOUT_GRID_ICON_PATH, QSize(18, 18), "#8b7cff")))
        self.character_layout_group.addButton(self.character_grid_button)
        layout_toggle_layout.addWidget(self.character_grid_button)

        self.character_list_button = QPushButton("")
        self.character_list_button.setObjectName("characterLayoutButton")
        self.character_list_button.setCheckable(True)
        self.character_list_button.setFixedSize(30, 30)
        self.character_list_button.setToolTip("List view")
        self.character_list_button.setIcon(QIcon(render_svg_pixmap(LAYOUT_LIST_ICON_PATH, QSize(18, 18), "#9aa1aa")))
        self.character_layout_group.addButton(self.character_list_button)
        layout_toggle_layout.addWidget(self.character_list_button)
        self.character_grid_button.clicked.connect(lambda: self.set_character_overlay_layout("grid"))
        self.character_list_button.clicked.connect(lambda: self.set_character_overlay_layout("list"))
        header.addWidget(layout_toggle, 0, Qt.AlignmentFlag.AlignTop)

        close_button = QPushButton("")
        close_button.setObjectName("overlayCloseButton")
        close_button.setFixedSize(40, 40)
        close_button.setIcon(QIcon(render_svg_pixmap(CLOSE_ICON_PATH, QSize(17, 17), "#c5c9d0")))
        close_button.setToolTip("Close")
        close_button.clicked.connect(self.hide_character_overlay)
        header.addWidget(close_button, 0, Qt.AlignmentFlag.AlignTop)
        overlay_layout.addLayout(header)

        self.character_overlay_scroll = QScrollArea()
        self.character_overlay_scroll.setObjectName("characterOverlayScroll")
        self.character_overlay_scroll.setWidgetResizable(True)
        self.character_overlay_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.character_overlay_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.character_overlay_body = QWidget()
        self.character_overlay_grid = QGridLayout(self.character_overlay_body)
        self.character_overlay_grid.setContentsMargins(0, 8, 14, 0)
        self.character_overlay_grid.setHorizontalSpacing(28)
        self.character_overlay_grid.setVerticalSpacing(30)
        self.character_overlay_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.character_overlay_scroll.setWidget(self.character_overlay_body)
        overlay_layout.addWidget(self.character_overlay_scroll, 1)

    def refresh_character_sort_ui(self):
        sort_mode = normalize_character_sort_mode(getattr(self, "character_sort_mode", "name_asc"))
        self.character_sort_mode = sort_mode
        if hasattr(self, "character_sort_button"):
            self.character_sort_button.setText(self.character_sort_button_label(sort_mode))
        for mode, action in getattr(self, "character_sort_actions", {}).items():
            action.setChecked(mode == sort_mode)

    def character_sort_button_label(self, sort_mode):
        label = character_sort_label(sort_mode)
        if sort_mode == "message_count":
            return "Messages"
        return label

    def show_character_sort_menu(self):
        if not hasattr(self, "character_sort_menu"):
            return
        self.refresh_character_sort_ui()
        self.character_sort_menu.setMinimumWidth(178)
        self.character_sort_menu.exec(
            self.character_sort_button.mapToGlobal(self.character_sort_button.rect().bottomLeft())
        )

    def set_character_sort_mode(self, sort_mode):
        sort_mode = normalize_character_sort_mode(sort_mode)
        if getattr(self, "character_sort_mode", "name_asc") == sort_mode:
            self.refresh_character_sort_ui()
            return
        self.character_sort_mode = sort_mode
        self.refresh_character_sort_ui()
        self.save_config()
        if hasattr(self, "character_overlay") and self.character_overlay.isVisible():
            self.populate_character_overlay()

    def set_character_overlay_layout(self, mode):
        mode = "list" if mode == "list" else "grid"
        if getattr(self, "character_overlay_layout_mode", "grid") == mode:
            self.refresh_character_layout_buttons()
            return
        self.character_overlay_layout_mode = mode
        self.refresh_character_layout_buttons()
        self.relayout_character_overlay_cards()

    def refresh_character_layout_buttons(self):
        mode = getattr(self, "character_overlay_layout_mode", "grid")
        if hasattr(self, "character_grid_button"):
            self.character_grid_button.setChecked(mode == "grid")
            self.character_grid_button.setIcon(QIcon(render_svg_pixmap(
                LAYOUT_GRID_ICON_PATH,
                QSize(18, 18),
                "#8b7cff" if mode == "grid" else "#9aa1aa",
            )))
        if hasattr(self, "character_list_button"):
            self.character_list_button.setChecked(mode == "list")
            self.character_list_button.setIcon(QIcon(render_svg_pixmap(
                LAYOUT_LIST_ICON_PATH,
                QSize(18, 18),
                "#8b7cff" if mode == "list" else "#9aa1aa",
            )))

    def refresh_character_ratio_menu(self):
        self.character_ratio_menu.clear()
        for ratio in CHARACTER_CARD_RATIOS:
            action = self.character_ratio_menu.addAction(ratio)
            action.setCheckable(True)
            action.setChecked(ratio == self.character_card_ratio)
            action.triggered.connect(
                lambda _checked=False, value=ratio: self.set_character_card_ratio(value)
            )

    def set_character_card_ratio(self, ratio):
        ratio = self.normalize_character_card_ratio(ratio)
        if ratio == self.character_card_ratio:
            return
        self.character_card_ratio = ratio
        if hasattr(self, "character_ratio_button"):
            self.character_ratio_button.setText(ratio)
        if hasattr(self, "character_overlay_grid"):
            for index in range(self.character_overlay_grid.count()):
                widget = self.character_overlay_grid.itemAt(index).widget()
                if isinstance(widget, CharacterChoiceCard):
                    widget.set_card_ratio(ratio)
        self.save_config()

    def character_overlay_card_width(self, columns):
        gap = self.character_overlay_grid.horizontalSpacing()
        if gap < 0:
            gap = self.character_overlay_grid.spacing()
        margins = self.character_overlay_grid.contentsMargins()
        available_width = self.character_overlay_scroll.viewport().width()
        if available_width <= 0:
            available_width = max(0, self.character_overlay.width() - 44)
        available_width = max(0, available_width - margins.left() - margins.right())
        if getattr(self, "character_overlay_layout_mode", "grid") == "list":
            return max(CHARACTER_CARD_MIN_WIDTH, available_width)
        fit_width = (available_width - gap * max(0, columns - 1)) // max(1, columns)
        return max(CHARACTER_CARD_MIN_WIDTH, min(CHARACTER_CARD_MAX_WIDTH, fit_width))

    def character_overlay_card_height(self, card_width):
        if getattr(self, "character_overlay_layout_mode", "grid") == "list":
            return 118
        target_height = round(card_width * 1.45)
        return max(CHARACTER_CARD_MIN_HEIGHT, min(CHARACTER_CARD_MAX_HEIGHT, target_height))

    def character_overlay_column_count(self, item_count):
        if item_count <= 0:
            return 1
        if getattr(self, "character_overlay_layout_mode", "grid") == "list":
            return 1
        gap = self.character_overlay_grid.horizontalSpacing()
        if gap < 0:
            gap = self.character_overlay_grid.spacing()
        margins = self.character_overlay_grid.contentsMargins()
        available_width = self.character_overlay_scroll.viewport().width()
        if available_width <= 0:
            available_width = max(0, self.character_overlay.width() - 44)
        available_width = max(0, available_width - margins.left() - margins.right())
        columns = max(1, (available_width + gap) // (CHARACTER_CARD_MIN_WIDTH + gap))
        return max(1, min(item_count, int(columns)))

    def relayout_character_overlay_cards(self):
        if not hasattr(self, "character_overlay_grid"):
            return
        cards = []
        while self.character_overlay_grid.count():
            item = self.character_overlay_grid.takeAt(0)
            widget = item.widget()
            if isinstance(widget, (CharacterPosterCard, CharacterChoiceCard)):
                cards.append(widget)
            elif widget is not None:
                widget.deleteLater()
        is_list = getattr(self, "character_overlay_layout_mode", "grid") == "list"
        self.character_overlay_grid.setHorizontalSpacing(0 if is_list else 28)
        self.character_overlay_grid.setVerticalSpacing(14 if is_list else 30)
        columns = self.character_overlay_column_count(len(cards))
        card_width = self.character_overlay_card_width(columns)
        for index, card in enumerate(cards):
            if isinstance(card, CharacterPosterCard):
                card.set_layout_mode("list" if is_list else "grid")
                card.setFixedWidth(card_width)
                card.setFixedHeight(self.character_overlay_card_height(card_width))
            elif isinstance(card, CharacterChoiceCard):
                card.setFixedWidth(card_width)
                card.update_card_height()
                card.apply_rounded_mask()
                card.position_content()
            self.character_overlay_grid.addWidget(
                card,
                index // columns,
                index % columns,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            )
        if cards:
            bottom_space = QWidget()
            bottom_space.setObjectName("characterOverlayBottomSpace")
            bottom_space.setFixedHeight(28)
            self.character_overlay_grid.addWidget(
                bottom_space,
                (len(cards) + columns - 1) // columns,
                0,
                1,
                columns,
            )

    def position_character_overlay(self):
        if not hasattr(self, "character_overlay"):
            return
        margin = 0
        self.character_overlay.setGeometry(
            margin,
            margin,
            max(0, self.content_frame.width() - margin * 2),
            max(0, self.content_frame.height() - margin * 2),
        )
        self.relayout_character_overlay_cards()

    def show_character_overlay(self):
        self.populate_character_overlay()
        self.position_character_overlay()
        self.character_overlay.raise_()
        self.character_overlay.show()
        QTimer.singleShot(0, self.position_character_overlay)

    def hide_character_overlay(self):
        if hasattr(self, "character_overlay"):
            self.character_overlay.hide()

    def populate_character_overlay(self):
        while self.character_overlay_grid.count():
            item = self.character_overlay_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        items = filter_characters(
            self.character_profiles.get("items", []),
            local_state=self.character_profiles.get("local_state", {}),
            query=getattr(self, "character_search_query", ""),
            favorites_only=getattr(self, "character_show_favorites_only", False),
            sort_mode=getattr(self, "character_sort_mode", "name_asc"),
        )
        active_id = self.character_profiles.get("active_character_id", "")
        for index, character in enumerate(items):
            pixmap, render_full_poster = self.character_pixmap_for(character, prefer_poster=True)
            card = CharacterPosterCard(
                character,
                pixmap,
                character.get("id") == active_id,
                render_full_poster,
            )
            card.set_shadow_mode("normal" if len(items) <= 20 else "light")
            card.selected.connect(self.select_character_from_overlay)
            self.character_overlay_grid.addWidget(card, 0, index)
        self.relayout_character_overlay_cards()

    def select_character_from_overlay(self, character_id):
        self.hide_character_overlay()
        self.select_character(character_id)

    def compact_source_url(self, url):
        parsed = urlparse(url if "://" in url else f"https://{url}")
        if parsed.netloc:
            return parsed.netloc
        return url.replace("https://", "").replace("http://", "").strip("/")[:32]

    def character_sidebar_hero_height(self):
        width = 0
        if hasattr(self, "character_hero_card"):
            width = self.character_hero_card.width()
        if width <= 0 and hasattr(self, "sidebar"):
            width = max(0, self.sidebar.width() - 48)
        if width <= 0:
            width = 296
        return max(180, min(280, round(width * 4 / 5)))

    def refresh_character_ui(self):
        character = self.active_character()
        local_state = self.character_profiles.get("local_state", {})
        if hasattr(self, "character_source_input"):
            self.character_source_input.blockSignals(True)
            self.character_source_input.setText(self.character_profiles.get("source_url", ""))
            self.character_source_input.blockSignals(False)
        if hasattr(self, "character_source_label"):
            source_url = self.character_profiles.get("source_url", "")
            self.character_source_label.setText(self.compact_source_url(source_url) if source_url else "No source")
            self.character_source_label.setToolTip(source_url)
        if hasattr(self, "character_picker_button"):
            self.character_picker_button.setVisible(bool(character))
            if character:
                if hasattr(self, "character_picker_label"):
                    self.character_picker_label.setText("Change character")
                self.character_picker_button.setToolTip("Choose another character")
                self.character_picker_button.setEnabled(True)
            else:
                if hasattr(self, "character_picker_label"):
                    self.character_picker_label.setText("Change character")
                self.character_picker_button.setToolTip("")
                self.character_picker_button.setEnabled(False)
        if hasattr(self, "character_hero_favorite_button"):
            favorite = bool(character and local_state.get(character.get("id"), {}).get("favorite"))
            self.character_hero_favorite_button.setText("★" if favorite else "☆")
            self.character_hero_favorite_button.setProperty("favorite", favorite)
            self.character_hero_favorite_button.setProperty("active", favorite)
            self.character_hero_favorite_button.setEnabled(bool(character))
            self.character_hero_favorite_button.style().unpolish(self.character_hero_favorite_button)
            self.character_hero_favorite_button.style().polish(self.character_hero_favorite_button)
        if hasattr(self, "character_source_panel"):
            self.character_source_panel.setVisible(True)
        if hasattr(self, "character_hero_card"):
            self.character_hero_card.setVisible(bool(character))
        if hasattr(self, "character_access_section"):
            self.character_access_section.setVisible(bool(character))
        if hasattr(self, "character_personality_section"):
            self.character_personality_section.setVisible(bool(character))
        if isinstance(getattr(self, "character_hero_card", None), CharacterSidebarHeroCard):
            if character:
                pixmap, render_full_poster = self.character_pixmap_for(character, prefer_poster=True)
                favorite = is_character_favorite(self.character_profiles, character.get("id"))
                self.character_hero_card.setFixedHeight(self.character_sidebar_hero_height())
                self.character_hero_card.set_character(
                    character,
                    pixmap,
                    favorite,
                    render_full_poster,
                )
            else:
                self.character_hero_card.set_character({}, QPixmap(), False, False)
        elif hasattr(self, "character_avatar_label"):
            self.position_character_hero_elements()
            self.refresh_character_avatar(character)
        if hasattr(self, "character_name_label"):
            if character:
                self.character_name_label.setText(character.get("name", "Character"))
            else:
                self.character_name_label.setText("")
        if hasattr(self, "character_style_label"):
            meta_parts = []
            if character and character.get("style"):
                meta_parts.append(character.get("style", "").title())
            if character and character.get("tags"):
                meta_parts.extend(character.get("tags", [])[:3])
            self.character_style_label.setText(" · ".join(meta_parts))
            self.character_style_label.setVisible(bool(meta_parts))
        if hasattr(self, "character_tags_label"):
            self.character_tags_label.setText("")
            self.character_tags_label.hide()
        if hasattr(self, "character_personality_label"):
            personality = character.get("description", "") if character else ""
            self.character_personality_label.setText(self.elide_multiline_text(personality, 92))
            self.character_personality_label.setToolTip(personality)
        if hasattr(self, "character_personality_view_button"):
            personality = character.get("description", "") if character else ""
            self.character_personality_view_button.setVisible(len(personality) > 92)
        if hasattr(self, "character_sync_label"):
            last_sync = self.character_profiles.get("last_sync")
            self.character_sync_label.setText(self.character_sync_text(last_sync))
            self.character_sync_label.setVisible(bool(last_sync))
        if hasattr(self, "character_prompt_heading"):
            self.character_prompt_heading.setVisible(bool(character))
        if hasattr(self, "character_prompt_preview"):
            if character:
                preview = character.get("system_prompt", "")
                if len(preview) > 180:
                    preview = preview[:177] + "..."
                self.character_prompt_preview.setText(preview)
            else:
                self.character_prompt_preview.setText("Sync character profiles from your server to start.")
        caps = self.active_character_capabilities()
        access_panel = getattr(self, "character_access_panel", None)
        if isinstance(access_panel, CharacterAccessPanel):
            access_panel.set_capabilities(caps)
            access_panel.setEnabled(bool(character))
        else:
            for key, checkbox_name in (
                ("file_context", "character_file_context_checkbox"),
                ("url_context", "character_url_context_checkbox"),
                ("terminal", "character_terminal_checkbox"),
            ):
                if hasattr(self, checkbox_name):
                    checkbox = getattr(self, checkbox_name)
                    checkbox.blockSignals(True)
                    checkbox.setChecked(bool(caps.get(key)))
                    checkbox.setEnabled(bool(character))
                    checkbox.blockSignals(False)
        if hasattr(self, "composer"):
            self.composer.setPlaceholderText(self.composer_placeholder())
        self.refresh_mode_ui()

    def elide_multiline_text(self, text, max_chars):
        text = " ".join(str(text or "").split())
        if len(text) <= max_chars:
            return text
        return text[: max(0, max_chars - 3)].rstrip() + "..."

    def character_sync_text(self, value):
        if not value:
            return "Not synced yet"
        try:
            timestamp = datetime.fromisoformat(str(value))
        except ValueError:
            return f"Synced {value}"
        now = datetime.now()
        day = "today" if timestamp.date() == now.date() else timestamp.strftime("%Y-%m-%d")
        return f"Synced {day} {timestamp.strftime('%H:%M')}"

    def show_character_personality(self):
        character = self.active_character()
        if not character:
            return
        QMessageBox.information(
            self,
            f"{character.get('name', 'Character')} personality",
            character.get("description", "") or "No personality text available.",
        )

    def refresh_character_tags(self, tags):
        while self.character_tags_layout.count():
            item = self.character_tags_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for tag in tags[:4]:
            chip = QLabel(str(tag))
            chip.setObjectName("characterTag")
            self.character_tags_layout.addWidget(chip)
        self.character_tags_layout.addStretch()
        self.character_tags_widget.setVisible(bool(tags))

    def refresh_character_avatar(self, character):
        if not hasattr(self, "character_avatar_label"):
            return
        self.character_avatar_label.clear()
        if not character:
            self.character_avatar_label.setText("No\navatar")
            return
        pixmap = self.character_avatar_pixmap(character)
        if pixmap and not pixmap.isNull():
            target_size = self.character_avatar_label.size()
            if target_size.width() <= 0 or target_size.height() <= 0:
                target_size = self.character_hero_card.size()
            self.character_avatar_label.setPixmap(
                pixmap.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            return
        initials = "".join(part[:1] for part in character.get("name", "").split()[:2]).upper()
        self.character_avatar_label.setText(initials or "AI")

    def position_character_hero_elements(self):
        if not hasattr(self, "character_hero_card"):
            return
        if isinstance(self.character_hero_card, CharacterSidebarHeroCard):
            return
        width = max(0, self.character_hero_card.width())
        height = max(0, self.character_hero_card.height())
        if width <= 0 or height <= 0:
            return
        self.character_avatar_label.setGeometry(0, 0, width, height)
        button_y = 12
        self.character_hero_favorite_button.setGeometry(width - 44, button_y, 32, 28)
        info_width = width
        info_height = 92
        self.character_hero_info.setGeometry(
            0,
            height - info_height,
            info_width,
            info_height,
        )
        self.character_avatar_label.lower()
        self.character_hero_info.raise_()
        self.character_hero_favorite_button.raise_()

    def character_pixmap_for(self, character, prefer_poster=True):
        if not character:
            return QPixmap(), False

        poster_url = character_poster_url(character)
        avatar_url = character_avatar_url(character)

        if prefer_poster and poster_url:
            return self.character_image_cache.request(poster_url), True
        if avatar_url:
            return self.character_image_cache.request(avatar_url), True
        return QPixmap(), False

    def on_character_pixmap_loaded(self, _url, _pixmap, _success):
        self.refresh_character_ui()
        if hasattr(self, "character_overlay") and self.character_overlay.isVisible():
            self.populate_character_overlay()

    def character_avatar_pixmap(self, character):
        avatar_url = character_avatar_url(character)
        if not avatar_url:
            return QPixmap()
        try:
            if avatar_url.startswith(("http://", "https://")):
                response = requests.get(avatar_url, timeout=8)
                response.raise_for_status()
                return self.pixmap_from_bytes(response.content, avatar_url)
        except Exception:
            return QPixmap()
        return QPixmap()

    def pixmap_from_path(self, path):
        try:
            data = path.read_bytes()
        except OSError:
            return QPixmap()
        return self.pixmap_from_bytes(data, str(path))

    def pixmap_from_bytes(self, data, source_name=""):
        if not data:
            return QPixmap()
        if source_name.lower().split("?", 1)[0].endswith(".svg") or data.lstrip().startswith(b"<svg"):
            pixmap = QPixmap(768, 768)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            renderer = QSvgRenderer(QByteArray(data))
            renderer.render(painter, QRectF(0, 0, 768, 768))
            painter.end()
            return pixmap
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        return pixmap

    def sync_characters(self):
        if not hasattr(self, "character_source_input"):
            return
        source_url = self.character_source_input.text().strip()
        if not source_url:
            self.set_status_message("Enter a character source URL.")
            return
        self.sync_characters_button.setEnabled(False)
        self.set_status_message("Syncing character profiles...")
        try:
            response = requests.get(source_url, timeout=20)
            response.raise_for_status()
            payload = response.json()
            raw_items = payload.get("characters", []) if isinstance(payload, dict) else []
            items = []
            seen_ids = set()
            for raw_item in raw_items:
                item = normalize_character(raw_item)
                if not item or item["id"] in seen_ids:
                    continue
                seen_ids.add(item["id"])
                items.append(item)
            if not items:
                raise ValueError("No valid characters found.")

            previous_state = self.character_profiles.get("local_state", {})
            active_id = self.character_profiles.get("active_character_id")
            if active_id not in seen_ids:
                active_id = items[0]["id"]
            self.character_profiles = {
                "source_url": source_url,
                "last_sync": datetime.now().isoformat(timespec="seconds"),
                "active_character_id": active_id,
                "items": items,
                "local_state": {
                    key: value for key, value in previous_state.items() if key in seen_ids
                },
            }
            self.save_config()
            self.refresh_character_ui()
            self.update_send_availability()
            self.set_status_message(f"Synced {len(items)} character profile(s).")
            self.show_toast("Characters synced")
        except Exception as exc:
            if self.character_profiles.get("items"):
                self.set_status_message(f"Could not sync characters. Using cached profiles. {exc}")
            else:
                self.set_status_message(f"No character profiles available. {exc}")
        finally:
            self.sync_characters_button.setEnabled(True)

    def show_character_menu(self):
        items = sort_characters(
            self.character_profiles.get("items", []),
            self.character_profiles.get("local_state", {}),
            getattr(self, "character_sort_mode", "name_asc"),
        )
        if not items:
            return
        if self.sidebar_pinned:
            self.show_character_overlay()
            return
        menu = QMenu(self)
        menu.setObjectName("historyMenu")
        active_id = self.character_profiles.get("active_character_id")
        local_state = self.character_profiles.get("local_state", {})
        for item in items:
            prefix = "★ " if local_state.get(item.get("id"), {}).get("favorite") else ""
            action = menu.addAction(prefix + item.get("name", "Character"))
            action.setEnabled(item.get("id") != active_id)
            if item.get("id") != active_id:
                action.triggered.connect(
                    lambda _checked=False, character_id=item.get("id"): self.select_character(character_id)
                )
        menu.exec(self.character_picker_button.mapToGlobal(self.character_picker_button.rect().bottomLeft()))

    def select_character(self, character_id):
        if not any(item.get("id") == character_id for item in self.character_profiles.get("items", [])):
            return
        if self.worker is not None and self.worker.isRunning():
            self.set_status_message("Wait for the current response before changing character.")
            return
        if self.has_existing_conversation_content():
            self.clear_chat()
        self.character_profiles["active_character_id"] = character_id
        self.save_config()
        self.refresh_character_ui()
        self.update_empty_state()
        self.update_send_availability()

    def toggle_active_character_favorite(self):
        character = self.active_character()
        if not character:
            return
        character_id = character.get("id")
        state = self.character_profiles.setdefault("local_state", {}).get(character_id, {})
        set_character_favorite(self.character_profiles, character_id, not state.get("favorite", False))
        self.save_config()
        self.refresh_character_ui()
        if hasattr(self, "character_overlay") and self.character_overlay.isVisible():
            self.populate_character_overlay()

    def increment_active_character_message_count(self):
        character = self.active_character()
        if not character:
            return
        try:
            current_count = int(character.get("message_count", 0))
        except (TypeError, ValueError):
            current_count = 0
        character["message_count"] = max(0, current_count) + 1
        self.save_config()
        self.refresh_character_ui()
        if hasattr(self, "character_overlay") and self.character_overlay.isVisible():
            self.populate_character_overlay()

    def set_active_character_capability(self, key, value):
        character = self.active_character()
        if not character:
            return
        set_character_capability(self.character_profiles, character.get("id"), key, value)
        if key == "file_context" and not value and self.pending_attachments:
            self.clear_attachments()
        self.save_config()
        self.refresh_character_ui()
        self.refresh_terminal_permission_ui()
        self.update_send_availability()

    def active_character(self):
        return get_active_character(self.character_profiles)

    def active_character_capabilities(self):
        character = self.active_character()
        if not character:
            return {}
        return get_effective_character_capabilities(
            character,
            self.character_profiles.get("local_state", {}),
        )
