"""Main application window."""

import base64
import json
import mimetypes
from datetime import datetime
from io import BytesIO
from pathlib import Path

import requests
from PyQt6.QtCore import QByteArray, QBuffer, QEasingCurve, QEvent, QIODevice, QPoint, QPropertyAnimation, QRectF, QSize, QTimer, QUrl, Qt
from PyQt6.QtGui import QDesktopServices, QGuiApplication, QIcon, QImage, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

from constants import (
    AGENT_TERMINAL_PROMPT,
    CONFIG_PATH,
    DEFAULT_SERVER_BASE_URL,
    DEFAULT_PERMISSIONS_ICON_PATH,
    FULL_ACCESS_ICON_PATH,
    LEGACY_CONFIG_PATH,
    MAX_ATTACHMENT_TEXT_CHARS,
    MAX_URL_DOWNLOAD_BYTES,
    MAX_URLS_PER_MESSAGE,
    MAX_URL_TEXT_CHARS,
    TEXT_PREVIEW_SUFFIXES,
    TRAILING_URL_PUNCTUATION,
    URL_FETCH_TIMEOUT,
    URL_RE,
)
from html_utils import HtmlTextExtractor
from markdown_utils import normalize_terminal_fences, replace_terminal_command_tags
from styles import APP_STYLE
from widgets import (
    AttachmentChip,
    AutoResizingTextEdit,
    DeletableHistoryComboBox,
    FilePreviewDialog,
    ImageGalleryDialog,
    MessageCard,
    PinIconButton,
    AssistantCodeBlock,
    StickyCodeHeader,
    SvgActionButton,
)
from constants import ARROW_UP_ICON_PATH, STOP_ICON_PATH
from worker import ChatCompletionWorker

TERMINAL_PERMISSION_DEFAULT = "default"
TERMINAL_PERMISSION_FULL_ACCESS = "full_access"
DEFAULT_TERMINAL_PERMISSIONS = ["pwd", "ls", "date", "whoami", "uname"]
DEFAULT_ASSISTANT_DEBOUNCE_ENABLED = True
DEFAULT_ASSISTANT_DEBOUNCE_INTERVAL_MS = 45
TERMINAL_PERMISSION_COLORS = {
    TERMINAL_PERMISSION_DEFAULT: "#f2f3f5",
    TERMINAL_PERMISSION_FULL_ACCESS: "#d5c537",
}
SIDEBAR_DROPDOWN_TEXT_INSET = "  "

class AgentChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.current_assistant_card = None
        self.history = []
        self.last_submitted_user_text = ""
        self.pending_user_text = None
        self.pending_user_message = None
        self.session_system_prompt = ""
        self.session_prompt_locked = False
        self.pending_attachments = []
        self.message_queue = []
        self.available_models = []
        self.base_url = DEFAULT_SERVER_BASE_URL
        self.config = self.load_config()
        server_config = self.config.get("server", {})
        session_prompt_config = self.config.get("session_prompt", {})
        terminal_config = self.config.get("agent_terminal", {})
        rendering_config = self.config.get("assistant_rendering", {})
        sampling_config = self.config.get("sampling", {})
        ui_config = self.config.get("ui", {})

        self.server_enabled = bool(server_config.get("enabled", True))
        configured_base_url = self.normalize_base_url(server_config.get("base_url", ""))
        if configured_base_url:
            self.base_url = configured_base_url
        self.base_url_history = self.clean_history(
            server_config.get("base_urls", []),
            normalizer=self.normalize_base_url,
        )
        self.base_url_history = self.add_history_value(self.base_url_history, self.base_url)
        self.session_prompt_enabled = bool(session_prompt_config.get("enabled", True))
        self.session_prompt_history = self.clean_history(session_prompt_config.get("history", []))
        self.initial_session_prompt = str(session_prompt_config.get("value", "")).strip()
        if self.initial_session_prompt:
            self.session_prompt_history = self.add_history_value(
                self.session_prompt_history,
                self.initial_session_prompt,
            )
        self.agent_terminal_enabled = bool(terminal_config.get("enabled", False))
        self.agent_terminal_permission = self.normalize_agent_terminal_permission(
            terminal_config.get("permission", TERMINAL_PERMISSION_DEFAULT)
        )
        self.default_permissions = self.clean_default_permissions(
            terminal_config.get("default_permissions", DEFAULT_TERMINAL_PERMISSIONS)
        )
        self.sampling_enabled = bool(sampling_config.get("enabled", True))
        self.assistant_rendering_enabled = bool(rendering_config.get("enabled", True))
        self.assistant_debounce_enabled = self.assistant_rendering_enabled and bool(
            rendering_config.get("debounce_enabled", DEFAULT_ASSISTANT_DEBOUNCE_ENABLED)
        )
        self.assistant_debounce_interval_ms = self.normalize_debounce_interval(
            rendering_config.get("debounce_interval_ms", DEFAULT_ASSISTANT_DEBOUNCE_INTERVAL_MS)
        )
        self.show_thinking = bool(ui_config.get("show_thinking", False))
        self.pin_panel = bool(ui_config.get("pin_panel", False))
        self.pending_terminal_permission = None
        self.assistant_reply_focus_active = False
        self.assistant_reply_focus_card = None
        self.selected_model_name = ""
        self.advanced_expanded = False
        self.sidebar_pinned = self.pin_panel
        self.sidebar_open = False
        self.sidebar_collapsed_width = 68
        self.sidebar_scrollbar_allowance = 60
        self.sidebar_expanded_max_width = 380
        self.default_window_width = 1180
        self.default_window_height = 820
        self.sticky_code_header = None
        self.toast_label = None
        self.toast_timer = None

        self.configure_responsive_metrics()

        self.setWindowTitle("Agent Chat")
        self.setStyleSheet(APP_STYLE)
        self.resize(self.default_window_width, self.default_window_height)
        self.setMinimumSize(520, 420)

        self.build_ui()
        QApplication.instance().focusChanged.connect(self.on_focus_changed)
        QTimer.singleShot(0, self.refresh_server_state)

    def load_config(self):
        default_config = {
            "server": {
                "enabled": True,
                "base_url": DEFAULT_SERVER_BASE_URL,
                "base_urls": [DEFAULT_SERVER_BASE_URL],
            },
            "session_prompt": {
                "enabled": True,
                "value": "",
                "history": [],
            },
            "agent_terminal": {
                "enabled": True,
                "permission": TERMINAL_PERMISSION_DEFAULT,
                "default_permissions": list(DEFAULT_TERMINAL_PERMISSIONS),
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
            "ui": {
                "enabled": True,
                "show_thinking": False,
                "pin_panel": False,
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
            "agent_terminal": {
                "enabled": self.agent_terminal_enabled,
                "permission": self.agent_terminal_permission,
                "default_permissions": self.default_permissions,
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
            "ui": {
                "enabled": True,
                "show_thinking": (
                    self.show_thinking_checkbox.isChecked()
                    if hasattr(self, "show_thinking_checkbox")
                    else self.show_thinking
                ),
                "pin_panel": self.sidebar_pinned,
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
        terminal_payload = payload.get("agent_terminal") if isinstance(payload.get("agent_terminal"), dict) else {}
        sampling_payload = payload.get("sampling") if isinstance(payload.get("sampling"), dict) else {}
        rendering_payload = (
            payload.get("assistant_rendering")
            if isinstance(payload.get("assistant_rendering"), dict)
            else {}
        )
        ui_payload = payload.get("ui") if isinstance(payload.get("ui"), dict) else {}

        return {
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
            "agent_terminal": {
                **default_config["agent_terminal"],
                **terminal_payload,
                "enabled": terminal_payload.get("enabled", payload.get("agent_terminal_enabled", default_config["agent_terminal"]["enabled"])),
                "permission": terminal_payload.get("permission", payload.get("agent_terminal_permission", default_config["agent_terminal"]["permission"])),
                "default_permissions": terminal_payload.get("default_permissions", payload.get("default_permissions", default_config["agent_terminal"]["default_permissions"])),
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
            "ui": {
                **default_config["ui"],
                **ui_payload,
            },
        }

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

    def normalize_debounce_interval(self, value):
        try:
            interval = int(value)
        except (TypeError, ValueError):
            interval = DEFAULT_ASSISTANT_DEBOUNCE_INTERVAL_MS
        return max(0, min(1000, interval))

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

    def add_history_value(self, values, value):
        value = value.strip()
        if not value:
            return values
        return [value] + [item for item in values if item != value]

    def current_session_prompt_value(self):
        if self.session_prompt_locked:
            return self.session_system_prompt
        if hasattr(self, "system_prompt_input"):
            return self.system_prompt_input.toPlainText().strip()
        return self.initial_session_prompt

    def configure_responsive_metrics(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        self.default_window_width = max(520, min(1180, available.width() - 40))
        self.default_window_height = max(420, min(820, available.height() - 40))
        self.sidebar_expanded_max_width = max(320, min(420, int(available.width() * 0.4)))

    def target_sidebar_width(self):
        available_width = self.width() or self.default_window_width
        responsive_width = int(available_width * 0.34)
        content_width = max(300, min(self.sidebar_expanded_max_width, responsive_width))
        return content_width + self.sidebar_scrollbar_allowance

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        self.sidebar = self.build_sidebar()
        root.addWidget(self.sidebar)

        self.content_frame = QFrame()
        self.content_frame.setObjectName("surface")
        self.content_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.content_frame.setMinimumWidth(0)
        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setMinimumWidth(0)
        self.scroll_area.viewport().installEventFilter(self)
        self.scroll_area.verticalScrollBar().installEventFilter(self)
        content_layout.addWidget(self.scroll_area)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.update_sticky_code_header)

        self.chat_surface = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_surface)
        self.chat_layout.setContentsMargins(26, 26, 26, 26)
        self.chat_layout.setSpacing(16)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.empty_state = self.build_empty_state()
        self.chat_layout.addWidget(self.empty_state)
        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(0, 0, 0, 0)
        self.messages_layout.setSpacing(16)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.addWidget(self.messages_container)
        self.chat_layout.addStretch()

        self.scroll_area.setWidget(self.chat_surface)
        self.sticky_code_header = StickyCodeHeader(self.scroll_area.viewport())

        self.composer_frame = self.build_composer()
        self.composer_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.composer_frame.setMinimumWidth(0)
        content_stack = QVBoxLayout()
        content_stack.setContentsMargins(0, 0, 0, 0)
        content_stack.setSpacing(12)
        content_stack.addWidget(self.content_frame, 1)
        content_stack.addWidget(self.composer_frame)
        root.addLayout(content_stack, 1)

        self.build_toast()
        self.refresh_session_prompt_ui()
        self.refresh_rendering_ui()
        self.refresh_terminal_permission_ui()
        self.update_empty_state()
        self.update_send_availability()
        if self.sidebar_pinned:
            QTimer.singleShot(0, self.expand_sidebar)

    def build_toast(self):
        self.toast_label = QLabel("", self)
        self.toast_label.setObjectName("toastLabel")
        self.toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_label.hide()

        self.toast_timer = QTimer(self)
        self.toast_timer.setSingleShot(True)
        self.toast_timer.setInterval(1800)
        self.toast_timer.timeout.connect(self.hide_toast)

    def show_toast(self, text):
        if self.toast_label is None:
            return
        self.toast_label.setText(text)
        self.toast_label.adjustSize()
        self.position_toast()
        self.toast_label.raise_()
        self.toast_label.show()
        if self.toast_timer is not None:
            self.toast_timer.start()

    def hide_toast(self):
        if self.toast_label is not None:
            self.toast_label.hide()

    def position_toast(self):
        if self.toast_label is None:
            return
        margin = 18
        x = max(margin, (self.width() - self.toast_label.width()) // 2)
        y = max(margin, self.height() - self.toast_label.height() - margin)
        self.toast_label.move(x, y)

    def build_sidebar(self):
        frame = QFrame()
        frame.setObjectName("sidebar")
        frame.setMinimumWidth(self.sidebar_collapsed_width)
        frame.setMaximumWidth(self.sidebar_collapsed_width)
        frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        frame.enterEvent = self.sidebar_enter_event
        frame.leaveEvent = self.sidebar_leave_event

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        self.sidebar_menu_button = QPushButton("☰")
        self.sidebar_menu_button.setObjectName("sidebarMenuButton")
        self.sidebar_menu_button.setToolTip("Menu")
        self.sidebar_menu_button.clicked.connect(self.toggle_sidebar)
        header_row.addWidget(self.sidebar_menu_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.pin_button = PinIconButton()
        self.pin_button.setObjectName("pinButton")
        self.pin_button.setToolTip("Pin panel")
        self.pin_button.toggled.connect(self.toggle_sidebar_pin)
        self.pin_button.blockSignals(True)
        self.pin_button.setChecked(self.sidebar_pinned)
        self.pin_button.blockSignals(False)
        self.pin_button.setProperty("pinned", self.sidebar_pinned)
        self.pin_button.hide()
        header_row.addWidget(self.pin_button, 0, Qt.AlignmentFlag.AlignLeft)
        header_row.addStretch()
        layout.addLayout(header_row)

        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setObjectName("sidebarScroll")
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.sidebar_content = QWidget()
        self.sidebar_content.setObjectName("sidebarScrollBody")
        self.sidebar_content.setMinimumWidth(0)
        content_layout = QVBoxLayout(self.sidebar_content)
        content_layout.setContentsMargins(0, 0, 28, 0)
        content_layout.setSpacing(16)

        title = QLabel("Agent Chat")
        title.setObjectName("titleLabel")
        content_layout.addWidget(title)

        subtitle = QLabel("Model, sampling, and session controls.")
        subtitle.setObjectName("subtleLabel")
        subtitle.setWordWrap(True)
        content_layout.addWidget(subtitle)

        self.status_badge = QLabel("Checking server…")
        self.status_badge.setObjectName("statusBadge")
        content_layout.addWidget(self.status_badge)

        self.status_detail = QLabel("")
        self.status_detail.setObjectName("subtleLabel")
        self.status_detail.setWordWrap(True)
        content_layout.addWidget(self.status_detail)

        self.model_selector = QPushButton("Select model")
        self.model_selector.setObjectName("modelSelectorButton")
        self.model_menu = QMenu(self)
        self.model_menu.setObjectName("modelMenu")
        self.model_menu.aboutToShow.connect(self.refresh_model_menu)
        self.model_selector.setMenu(self.model_menu)
        content_layout.addWidget(self.model_selector)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("ghostButton")
        self.refresh_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.refresh_button.clicked.connect(self.refresh_server_state)
        buttons_row.addWidget(self.refresh_button)

        self.clear_button = QPushButton("New session")
        self.clear_button.setObjectName("ghostButton")
        self.clear_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.clear_button.clicked.connect(self.clear_chat)
        buttons_row.addWidget(self.clear_button)
        content_layout.addLayout(buttons_row)

        self.advanced_panel = self.build_advanced_panel()
        content_layout.addWidget(self.advanced_panel)
        content_layout.addStretch()

        self.sidebar_scroll.setWidget(self.sidebar_content)
        layout.addWidget(self.sidebar_scroll, 1)
        self.sidebar_scroll.hide()

        self.sidebar_hover_timer = QTimer(self)
        self.sidebar_hover_timer.setSingleShot(True)
        self.sidebar_hover_timer.setInterval(250)
        self.sidebar_hover_timer.timeout.connect(self.expand_sidebar)

        self.sidebar_animation = QPropertyAnimation(frame, b"minimumWidth", self)
        self.sidebar_animation.setDuration(460)
        self.sidebar_animation.setEasingCurve(QEasingCurve.Type.InOutQuart)
        self.sidebar_animation.valueChanged.connect(self.sync_sidebar_width)
        return frame

    def build_advanced_panel(self):
        frame = QFrame()
        frame.setObjectName("panel")
        frame.setMinimumWidth(0)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(16)

        heading = QLabel("Advanced controls")
        heading.setObjectName("sectionLabel")
        layout.addWidget(heading)

        self.server_section = QWidget()
        server_section_layout = QVBoxLayout(self.server_section)
        server_section_layout.setContentsMargins(0, 0, 0, 0)
        server_section_layout.setSpacing(10)

        server_heading = QLabel("Server URL")
        server_heading.setObjectName("sectionLabel")
        server_header_row = QHBoxLayout()
        server_header_row.setContentsMargins(0, 0, 0, 0)
        server_header_row.setSpacing(8)
        server_header_row.addWidget(server_heading)
        server_header_row.addStretch()

        self.base_url_history_button = QPushButton("▾")
        self.base_url_history_button.setObjectName("fieldIconButton")
        self.base_url_history_button.setToolTip("Select saved server URL")
        self.base_url_history_button.clicked.connect(self.show_base_url_history_menu)
        server_header_row.addWidget(self.base_url_history_button)

        self.apply_url_button = QPushButton("✓")
        self.apply_url_button.setObjectName("fieldIconButton")
        self.apply_url_button.setToolTip("Apply server URL")
        self.apply_url_button.setProperty("applied", True)
        self.apply_url_button.clicked.connect(self.apply_base_url)
        server_header_row.addWidget(self.apply_url_button)
        server_section_layout.addLayout(server_header_row)

        self.base_url_input = DeletableHistoryComboBox()
        self.base_url_input.setEditable(True)
        self.base_url_input.set_history_available(False)
        self.base_url_input.setCurrentText(self.base_url)
        self.base_url_input.setPlaceholderText("http://localhost:8080")
        self.base_url_input.lineEdit().returnPressed.connect(self.apply_base_url)
        self.base_url_input.currentTextChanged.connect(self.on_base_url_text_changed)
        server_section_layout.addWidget(self.base_url_input)

        self.base_url_detail = QLabel(f"Base URL for OpenAI-compatible server: {self.base_url}")
        self.base_url_detail.setObjectName("subtleLabel")
        self.base_url_detail.setWordWrap(True)
        server_section_layout.addWidget(self.base_url_detail)
        self.server_section.setVisible(self.server_enabled)
        layout.addWidget(self.server_section)

        self.session_prompt_section = QWidget()
        session_section_layout = QVBoxLayout(self.session_prompt_section)
        session_section_layout.setContentsMargins(0, 0, 0, 0)
        session_section_layout.setSpacing(10)

        session_heading = QLabel("Session prompt")
        session_heading.setObjectName("sectionLabel")
        session_header_row = QHBoxLayout()
        session_header_row.setContentsMargins(0, 0, 0, 0)
        session_header_row.setSpacing(8)
        session_header_row.addWidget(session_heading)
        session_header_row.addStretch()

        self.session_prompt_history_button = QPushButton("▾")
        self.session_prompt_history_button.setObjectName("fieldIconButton")
        self.session_prompt_history_button.setToolTip("Select saved session prompt")
        self.session_prompt_history_button.clicked.connect(self.show_session_prompt_history_menu)
        session_header_row.addWidget(self.session_prompt_history_button)

        self.apply_prompt_button = QPushButton("✓")
        self.apply_prompt_button.setObjectName("fieldIconButton")
        self.apply_prompt_button.setToolTip("Apply current session prompt")
        self.apply_prompt_button.clicked.connect(self.apply_session_prompt)
        session_header_row.addWidget(self.apply_prompt_button)
        session_section_layout.addLayout(session_header_row)

        self.system_prompt_input = QPlainTextEdit()
        self.system_prompt_input.setPlaceholderText("Optional instruction to lock in for this session.")
        self.system_prompt_input.setFixedHeight(92)
        if self.initial_session_prompt:
            self.system_prompt_input.setPlainText(self.initial_session_prompt)
        self.system_prompt_input.textChanged.connect(self.refresh_session_prompt_ui)
        session_section_layout.addWidget(self.system_prompt_input)

        self.session_prompt_badge = QLabel("")
        self.session_prompt_badge.setObjectName("sessionPromptBadge")
        self.session_prompt_badge.setWordWrap(True)
        session_section_layout.addWidget(self.session_prompt_badge)

        self.session_prompt_detail = QLabel("")
        self.session_prompt_detail.setObjectName("subtleLabel")
        self.session_prompt_detail.setWordWrap(True)
        session_section_layout.addWidget(self.session_prompt_detail)

        prompt_actions = QHBoxLayout()
        prompt_actions.setSpacing(10)

        self.unlock_prompt_button = QPushButton("Edit draft")
        self.unlock_prompt_button.setObjectName("secondaryButton")
        self.unlock_prompt_button.clicked.connect(self.unlock_session_prompt)
        prompt_actions.addWidget(self.unlock_prompt_button)

        self.clear_prompt_button = QPushButton("Clear prompt")
        self.clear_prompt_button.setObjectName("ghostButton")
        self.clear_prompt_button.clicked.connect(self.clear_session_prompt_text)
        prompt_actions.addWidget(self.clear_prompt_button)
        prompt_actions.addStretch()
        session_section_layout.addLayout(prompt_actions)
        self.session_prompt_section.setVisible(self.session_prompt_enabled)
        layout.addWidget(self.session_prompt_section)

        thinking_row = QHBoxLayout()
        thinking_row.setSpacing(10)

        thinking_label = QLabel("Reasoning")
        thinking_label.setObjectName("sectionLabel")
        thinking_row.addWidget(thinking_label)

        self.show_thinking_checkbox = QCheckBox("Show thinking")
        self.show_thinking_checkbox.setChecked(self.show_thinking)
        self.show_thinking_checkbox.toggled.connect(self.update_thinking_visibility)
        thinking_row.addWidget(self.show_thinking_checkbox)
        thinking_row.addStretch()
        layout.addLayout(thinking_row)

        self.assistant_rendering_section = QWidget()
        rendering_section_layout = QVBoxLayout(self.assistant_rendering_section)
        rendering_section_layout.setContentsMargins(0, 0, 0, 0)
        rendering_section_layout.setSpacing(10)

        rendering_heading = QLabel("Assistant rendering")
        rendering_heading.setObjectName("sectionLabel")
        rendering_section_layout.addWidget(rendering_heading)

        debounce_row = QHBoxLayout()
        debounce_row.setSpacing(10)

        self.debounce_checkbox = QCheckBox("Debounce streaming")
        self.debounce_checkbox.setChecked(self.assistant_debounce_enabled)
        self.debounce_checkbox.toggled.connect(self.set_assistant_debounce_enabled)
        debounce_row.addWidget(self.debounce_checkbox)

        self.debounce_interval_spin = QSpinBox()
        self.debounce_interval_spin.setRange(0, 1000)
        self.debounce_interval_spin.setSuffix(" ms")
        self.debounce_interval_spin.setValue(self.assistant_debounce_interval_ms)
        self.debounce_interval_spin.valueChanged.connect(self.set_assistant_debounce_interval)
        debounce_row.addWidget(self.debounce_interval_spin)
        debounce_row.addStretch()
        rendering_section_layout.addLayout(debounce_row)
        self.assistant_rendering_section.setVisible(self.assistant_rendering_enabled)
        layout.addWidget(self.assistant_rendering_section)

        self.agent_terminal_section = QWidget()
        terminal_section_layout = QVBoxLayout(self.agent_terminal_section)
        terminal_section_layout.setContentsMargins(0, 0, 0, 0)
        terminal_section_layout.setSpacing(10)

        terminal_row = QHBoxLayout()
        terminal_row.setSpacing(10)

        terminal_label = QLabel("Agent")
        terminal_label.setObjectName("sectionLabel")
        terminal_row.addWidget(terminal_label)

        self.agent_terminal_checkbox = QCheckBox("Terminal access")
        self.agent_terminal_checkbox.setChecked(self.agent_terminal_enabled)
        self.agent_terminal_checkbox.toggled.connect(self.set_agent_terminal_enabled)
        terminal_row.addWidget(self.agent_terminal_checkbox)
        terminal_row.addStretch()
        terminal_section_layout.addLayout(terminal_row)

        self.side_terminal_permission_button = QPushButton("")
        self.side_terminal_permission_button.setObjectName("terminalPermissionSideButton")
        self.side_terminal_permission_button.setIconSize(QSize(24, 24))
        self.side_terminal_permission_menu = QMenu(self)
        self.side_terminal_permission_menu.setObjectName("terminalPermissionMenu")
        self.side_terminal_permission_menu.aboutToShow.connect(self.refresh_side_terminal_permission_menu)
        self.side_terminal_permission_button.setMenu(self.side_terminal_permission_menu)
        terminal_section_layout.addWidget(self.side_terminal_permission_button)

        self.default_permissions_detail = QLabel("")
        self.default_permissions_detail.setObjectName("subtleLabel")
        self.default_permissions_detail.setWordWrap(True)
        terminal_section_layout.addWidget(self.default_permissions_detail)
        self.agent_terminal_section.setVisible(self.agent_terminal_enabled)
        layout.addWidget(self.agent_terminal_section)

        self.sampling_section = QWidget()
        sampling_section_layout = QVBoxLayout(self.sampling_section)
        sampling_section_layout.setContentsMargins(0, 0, 0, 0)
        sampling_section_layout.setSpacing(10)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(10)
        preset_label = QLabel("Presets")
        preset_label.setObjectName("sectionLabel")
        preset_row.addWidget(preset_label)

        self.precise_button = QPushButton("Precise")
        self.precise_button.clicked.connect(lambda: self.apply_preset("precise"))
        preset_row.addWidget(self.precise_button)

        self.balanced_button = QPushButton("Balanced")
        self.balanced_button.clicked.connect(lambda: self.apply_preset("balanced"))
        preset_row.addWidget(self.balanced_button)

        self.creative_button = QPushButton("Creative")
        self.creative_button.clicked.connect(lambda: self.apply_preset("creative"))
        preset_row.addWidget(self.creative_button)
        preset_row.addStretch()
        sampling_section_layout.addLayout(preset_row)

        sampling_header_row = QHBoxLayout()
        sampling_header_row.setContentsMargins(0, 0, 0, 0)
        sampling_header_row.setSpacing(10)
        sampling_label = QLabel("Sampling")
        sampling_label.setObjectName("sectionLabel")
        sampling_header_row.addWidget(sampling_label)
        sampling_header_row.addStretch()
        sampling_section_layout.addLayout(sampling_header_row)

        sampling_layout = QFormLayout()
        sampling_layout.setSpacing(12)
        sampling_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setDecimals(2)
        self.temperature_spin.setSingleStep(0.05)
        self.temperature_spin.setValue(float(self.config.get("sampling", {}).get("temperature", 0.7)))
        self.temperature_spin.valueChanged.connect(lambda _value: self.save_config())
        sampling_layout.addRow("Temperature", self.temperature_spin)

        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setRange(0.0, 1.0)
        self.top_p_spin.setDecimals(2)
        self.top_p_spin.setSingleStep(0.05)
        self.top_p_spin.setValue(float(self.config.get("sampling", {}).get("top_p", 0.9)))
        self.top_p_spin.valueChanged.connect(lambda _value: self.save_config())
        sampling_layout.addRow("Top P", self.top_p_spin)

        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(1, 200)
        self.top_k_spin.setValue(int(self.config.get("sampling", {}).get("top_k", 40)))
        self.top_k_spin.valueChanged.connect(lambda _value: self.save_config())
        sampling_layout.addRow("Top K", self.top_k_spin)
        sampling_section_layout.addLayout(sampling_layout)
        self.sampling_section.setVisible(self.sampling_enabled)
        layout.addWidget(self.sampling_section)

        return frame

    def build_empty_state(self):
        frame = QFrame()
        frame.setObjectName("panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        title = QLabel("Ready for a better local chat loop")
        title.setObjectName("emptyTitle")
        layout.addWidget(title)

        body = QLabel(
            "Pick a model, set an optional session prompt, then start chatting."
        )
        body.setObjectName("emptyBody")
        body.setWordWrap(True)
        layout.addWidget(body)

        actions = QHBoxLayout()
        actions.setSpacing(10)

        refresh = QPushButton("Refresh models")
        refresh.clicked.connect(self.refresh_server_state)
        actions.addWidget(refresh)

        clear = QPushButton("New session")
        clear.setObjectName("ghostButton")
        clear.clicked.connect(self.clear_chat)
        actions.addWidget(clear)
        actions.addStretch()
        layout.addLayout(actions)
        return frame

    def build_composer(self):
        frame = QFrame()
        frame.setObjectName("composerFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 0, 10, 10)
        layout.setSpacing(0)

        canvas = QFrame()
        canvas.setObjectName("composerCanvas")
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(14, 12, 10, 8)
        canvas_layout.setSpacing(8)

        self.attachment_scroll = QScrollArea()
        self.attachment_scroll.setObjectName("attachmentScroll")
        self.attachment_scroll.setWidgetResizable(True)
        self.attachment_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.attachment_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.attachment_scroll.setFixedHeight(58)

        self.attachments_wrap = QWidget()
        self.attachments_layout = QHBoxLayout(self.attachments_wrap)
        self.attachments_layout.setContentsMargins(0, 0, 0, 0)
        self.attachments_layout.setSpacing(10)
        self.attachments_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.attachment_scroll.setWidget(self.attachments_wrap)
        self.attachment_scroll.hide()
        canvas_layout.addWidget(self.attachment_scroll)

        self.queue_banner = QFrame()
        self.queue_banner.setObjectName("queueBanner")
        queue_layout = QHBoxLayout(self.queue_banner)
        queue_layout.setContentsMargins(12, 10, 12, 10)
        queue_layout.setSpacing(10)

        self.queue_badge = QLabel("0")
        self.queue_badge.setObjectName("queueBadge")
        queue_layout.addWidget(self.queue_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.queue_banner_text = QLabel("Queue empty")
        self.queue_banner_text.setObjectName("queueBannerText")
        self.queue_banner_text.setWordWrap(True)
        queue_layout.addWidget(self.queue_banner_text, 1)

        self.queue_banner.hide()
        canvas_layout.addWidget(self.queue_banner)

        self.terminal_approval_banner = QFrame()
        self.terminal_approval_banner.setObjectName("terminalApprovalBanner")
        approval_layout = QVBoxLayout(self.terminal_approval_banner)
        approval_layout.setContentsMargins(12, 10, 12, 10)
        approval_layout.setSpacing(8)

        self.terminal_approval_label = QLabel("")
        self.terminal_approval_label.setObjectName("terminalApprovalText")
        self.terminal_approval_label.setWordWrap(True)
        approval_layout.addWidget(self.terminal_approval_label)

        approval_actions = QHBoxLayout()
        approval_actions.setSpacing(8)

        self.terminal_approval_yes_button = QPushButton("Yes")
        self.terminal_approval_yes_button.setObjectName("tinyButton")
        self.terminal_approval_yes_button.clicked.connect(lambda: self.resolve_terminal_permission("allow_once"))
        approval_actions.addWidget(self.terminal_approval_yes_button)

        self.terminal_approval_always_button = QPushButton("")
        self.terminal_approval_always_button.setObjectName("tinyButton")
        self.terminal_approval_always_button.clicked.connect(lambda: self.resolve_terminal_permission("allow_always"))
        approval_actions.addWidget(self.terminal_approval_always_button)

        self.terminal_approval_no_button = QPushButton("Dismiss")
        self.terminal_approval_no_button.setObjectName("ghostButton")
        self.terminal_approval_no_button.clicked.connect(lambda: self.resolve_terminal_permission("reject"))
        approval_actions.addWidget(self.terminal_approval_no_button)
        approval_actions.addStretch()
        approval_layout.addLayout(approval_actions)

        self.terminal_approval_banner.hide()
        canvas_layout.addWidget(self.terminal_approval_banner)

        self.composer = AutoResizingTextEdit()
        self.composer.send_requested.connect(self.send_message)
        self.composer.attachment_paths_pasted.connect(self.add_attachment_paths)
        self.composer.textChanged.connect(self.update_send_availability)
        canvas_layout.addWidget(self.composer)

        footer_row = QHBoxLayout()
        footer_row.setSpacing(12)

        self.attach_button = QPushButton("+")
        self.attach_button.setObjectName("composerPlusButton")
        self.attach_button.setToolTip("Add files")
        self.attach_button.clicked.connect(self.add_attachments)
        footer_row.addWidget(self.attach_button)

        self.terminal_permission_button = QPushButton("")
        self.terminal_permission_button.setObjectName("terminalPermissionButton")
        self.terminal_permission_menu = QMenu(self)
        self.terminal_permission_menu.setObjectName("terminalPermissionMenu")
        self.terminal_permission_menu.aboutToShow.connect(self.refresh_terminal_permission_menu)
        self.terminal_permission_button.setMenu(self.terminal_permission_menu)
        footer_row.addWidget(self.terminal_permission_button)

        self.composer_hint = QLabel("Shift+Enter for newline")
        self.composer_hint.setObjectName("subtleLabel")
        self.composer_hint.hide()

        self.queue_label = QLabel("Queue empty")
        self.queue_label.setObjectName("subtleLabel")
        self.queue_label.hide()

        footer_row.addStretch()

        self.clear_attachments_button = QPushButton("Clear files")
        self.clear_attachments_button.setObjectName("ghostButton")
        self.clear_attachments_button.clicked.connect(self.clear_attachments)
        self.clear_attachments_button.hide()
        footer_row.addWidget(self.clear_attachments_button)

        self.send_button = SvgActionButton(ARROW_UP_ICON_PATH)
        self.send_button.setObjectName("iconActionButton")
        self.send_button.setProperty("variant", "send")
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setToolTip("Send")
        self.send_button.clicked.connect(self.handle_send_action_button)
        footer_row.addWidget(self.send_button)

        canvas_layout.addLayout(footer_row)
        layout.addWidget(canvas)
        return frame

    def apply_preset(self, preset):
        if preset == "precise":
            self.temperature_spin.setValue(0.2)
            self.top_p_spin.setValue(0.85)
            self.top_k_spin.setValue(30)
        elif preset == "creative":
            self.temperature_spin.setValue(1.0)
            self.top_p_spin.setValue(0.97)
            self.top_k_spin.setValue(80)
        else:
            self.temperature_spin.setValue(0.7)
            self.top_p_spin.setValue(0.9)
            self.top_k_spin.setValue(40)
        self.show_toast(f"{preset.title()} preset applied")

    def set_session_prompt_enabled(self, enabled):
        self.session_prompt_enabled = bool(enabled)
        self.save_config()
        self.refresh_session_prompt_ui()
        self.set_status_message(
            "Session prompt enabled."
            if self.session_prompt_enabled
            else "Session prompt disabled."
        )

    def set_assistant_debounce_enabled(self, enabled):
        self.assistant_debounce_enabled = bool(enabled)
        self.save_config()
        self.refresh_rendering_ui()
        self.set_status_message(
            "Assistant render debounce enabled."
            if self.assistant_debounce_enabled
            else "Assistant render debounce disabled."
        )

    def set_assistant_debounce_interval(self, value):
        self.assistant_debounce_interval_ms = self.normalize_debounce_interval(value)
        self.save_config()
        self.refresh_rendering_ui()

    def refresh_rendering_ui(self):
        if hasattr(self, "debounce_checkbox"):
            self.debounce_checkbox.blockSignals(True)
            self.debounce_checkbox.setChecked(self.assistant_debounce_enabled)
            self.debounce_checkbox.blockSignals(False)
        if hasattr(self, "debounce_interval_spin"):
            self.debounce_interval_spin.blockSignals(True)
            self.debounce_interval_spin.setValue(self.assistant_debounce_interval_ms)
            self.debounce_interval_spin.setEnabled(self.assistant_debounce_enabled)
            self.debounce_interval_spin.blockSignals(False)
        if hasattr(self, "assistant_rendering_section"):
            self.assistant_rendering_section.setVisible(self.assistant_rendering_enabled)

    def set_agent_terminal_enabled(self, enabled):
        self.agent_terminal_enabled = bool(enabled)
        if not self.agent_terminal_enabled and self.pending_terminal_permission and self.worker is not None:
            self.worker.resolve_terminal_permission("reject")
            self.pending_terminal_permission = None
            if hasattr(self, "terminal_approval_banner"):
                self.terminal_approval_banner.hide()
        self.save_config()
        self.refresh_terminal_permission_ui()
        self.set_status_message(
            "Terminal agent enabled. Commands run in the app workspace."
            if self.agent_terminal_enabled
            else "Terminal agent disabled."
        )

    def set_agent_terminal_permission(self, value):
        value = self.normalize_agent_terminal_permission(value)
        if self.agent_terminal_permission == value:
            self.refresh_terminal_permission_ui()
            return
        self.agent_terminal_permission = value
        self.save_config()
        self.refresh_terminal_permission_ui()
        self.set_status_message(f"Terminal permission set to {self.agent_terminal_permission_label()}.")

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
        if hasattr(self, "terminal_permission_button"):
            suffix = " enabled" if self.agent_terminal_enabled else " disabled"
            self.terminal_permission_button.setText(label)
            self.terminal_permission_button.setIcon(self.terminal_permission_icon(self.agent_terminal_permission))
            self.terminal_permission_button.setToolTip(f"Terminal access is{suffix}.")
            self.terminal_permission_button.setProperty(
                "fullAccess",
                self.agent_terminal_permission == TERMINAL_PERMISSION_FULL_ACCESS,
            )
            self.terminal_permission_button.style().unpolish(self.terminal_permission_button)
            self.terminal_permission_button.style().polish(self.terminal_permission_button)
            self.terminal_permission_button.setEnabled(self.agent_terminal_enabled)
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
            self.side_terminal_permission_button.setEnabled(self.agent_terminal_enabled)
        if hasattr(self, "default_permissions_detail"):
            allowed = ", ".join(self.default_permissions)
            self.default_permissions_detail.setText(f"Default commands: {allowed}")
        if hasattr(self, "agent_terminal_section"):
            self.agent_terminal_section.setVisible(self.agent_terminal_enabled)

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
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Attach files",
            "",
            "Supported Files (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.pdf *.txt *.md *.doc *.docx *.csv *.json *.wav *.mp3 *.mp4 *.mov *.mkv);;All Files (*)",
        )
        self.add_attachment_paths(paths)

    def add_attachment_paths(self, paths):
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.sidebar_open:
            self.sync_sidebar_width(self.target_sidebar_width())
        self.update_sticky_code_header()
        self.position_toast()

    def refresh_server_state(self):
        self.status_badge.setText("Checking OpenAI-compatible server…")
        self.status_detail.setText(f"Refreshing server state from {self.base_url}.")
        self.model_selector.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.apply_url_button.setEnabled(False)

        try:
            health_url = self.build_server_url("/health")
            models_url = self.build_server_url("/v1/models")
            health_response = requests.get(health_url, timeout=2)
            if health_response.status_code != 200:
                self.set_disconnected_state(f"OpenAI-compatible server health returned HTTP {health_response.status_code}.")
                return

            response = requests.get(models_url, timeout=2)
            if response.status_code != 200:
                self.set_disconnected_state(f"OpenAI-compatible server returned HTTP {response.status_code}.")
                return

            payload = response.json()
            models = [item.get("id", "") for item in payload.get("data", []) if item.get("id")]
            self.available_models = models
            self.populate_models(models)

            if models:
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
            self.update_send_availability()

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
        self.available_models = []
        self.set_selected_model_name("")
        self.model_selector.setEnabled(False)
        self.status_badge.setText("Disconnected")
        self.status_detail.setText(detail)

    def current_model_name(self):
        return self.selected_model_name.strip()

    def set_selected_model_name(self, model_name):
        self.selected_model_name = model_name.strip()
        if self.selected_model_name:
            self.model_selector.setText(f"{SIDEBAR_DROPDOWN_TEXT_INSET}{self.selected_model_name}")
            self.model_selector.setToolTip(self.selected_model_name)
        else:
            self.model_selector.setText(f"{SIDEBAR_DROPDOWN_TEXT_INSET}Select model")
            self.model_selector.setToolTip("Select model")
        self.update_send_availability()

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

    def update_send_availability(self):
        has_text = bool(self.composer.toPlainText().strip()) or bool(self.pending_attachments)
        has_model = bool(self.available_models) and bool(self.current_model_name())
        busy = self.worker is not None and self.worker.isRunning()
        if has_text:
            self.configure_send_action_button("send", enabled=has_model)
        elif busy:
            self.configure_send_action_button("stop", enabled=True)
        else:
            self.configure_send_action_button("send", enabled=False)
        self.model_selector.setEnabled(bool(self.available_models) and not busy)
        self.attach_button.setEnabled(True)
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
        prompt_text = user_text.strip()
        self.set_status_message("Reading links..." if self.detect_urls(prompt_text) else "Preparing message...")
        url_inputs = self.fetch_urls_for_prompt(prompt_text) if prompt_text else []
        user_message = self.build_user_message(prompt_text, attachments, url_inputs)
        if prompt_text:
            user_display = prompt_text
        elif attachments:
            user_display = (
                "Refer to this:" if self.has_existing_conversation_content() else "Sent attachments."
            )
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

        self.worker = ChatCompletionWorker(self)
        self.worker.configure(
            base_url=self.base_url,
            model_name=submission["model_name"],
            messages=self.build_messages_payload(submission["user_message"]),
            temperature=self.temperature_spin.value(),
            top_p=self.top_p_spin.value(),
            top_k=self.top_k_spin.value(),
            agent_terminal_enabled=self.agent_terminal_enabled,
            agent_terminal_permission=self.agent_terminal_permission,
            default_permissions=self.default_permissions,
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
            self.session_prompt_section.setVisible(self.session_prompt_enabled)
        self.refresh_session_prompt_history_ui()

    def build_user_message(self, user_text, attachments, url_inputs=None):
        url_inputs = url_inputs or []
        if not attachments and not url_inputs:
            return {"role": "user", "content": user_text}

        prompt = user_text or "Describe the attached inputs."
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
        messages = []
        system_sections = []
        if self.agent_terminal_enabled:
            system_sections.append(AGENT_TERMINAL_PROMPT)
        if self.session_prompt_enabled and self.session_system_prompt:
            system_sections.append(self.session_system_prompt)
        if system_sections:
            messages.append({"role": "system", "content": "\n\n".join(system_sections)})
        messages.extend(self.history)
        messages.append(user_message)
        return messages

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

    def on_generation_finished(self, success, stopped, full_response, _full_thinking):
        if self.current_assistant_card is not None:
            self.current_assistant_card.flush_pending_render()
            self.current_assistant_card.stop_loading()
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
        if watched == self.scroll_area.viewport() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
        ):
            QTimer.singleShot(0, self.update_sticky_code_header)
        if (
            self.assistant_reply_focus_active
            and watched in (self.scroll_area.viewport(), self.scroll_area.verticalScrollBar())
            and event.type() in (
                QEvent.Type.Wheel,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonDblClick,
                QEvent.Type.KeyPress,
            )
        ):
            self.stop_assistant_reply_focus()
        return super().eventFilter(watched, event)

    def start_assistant_reply_focus(self, card):
        self.assistant_reply_focus_card = card
        self.assistant_reply_focus_active = True
        self.scroll_to_assistant_reply()

    def stop_assistant_reply_focus(self):
        self.assistant_reply_focus_active = False
        self.assistant_reply_focus_card = None

    def scroll_to_assistant_reply(self):
        card = self.assistant_reply_focus_card
        if card is None:
            return

        def apply_scroll():
            if not self.assistant_reply_focus_active or self.assistant_reply_focus_card is not card:
                return
            scrollbar = self.scroll_area.verticalScrollBar()
            top = card.mapTo(self.chat_surface, QPoint(0, 0)).y()
            target = max(0, top - self.chat_layout.contentsMargins().top())
            scrollbar.setValue(min(target, scrollbar.maximum()))

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
