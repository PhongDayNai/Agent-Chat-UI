"""Main application window."""

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSize, QTimer, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QButtonGroup,
    QDoubleSpinBox,
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
)

from constants import (
    APP_LOGO_PATH,
    APP_VERSION,
    APP_WORKSPACE,
    ARROW_UP_ICON_PATH,
    DEFAULT_SERVER_BASE_URL,
    PENCIL_ICON_PATH,
)
from characters import (
    normalize_character_profiles,
)
from character_image_cache import CharacterImageCache
from character_theme import CHARACTER_MODE_STYLE_PATCH
from character_widgets import CharacterAccessPanel, CharacterSectionFrame, CharacterSidebarHeroCard, SwitchPill, render_svg_pixmap
from modes import MODE_AGENT, MODE_CHARACTER, MODE_CHAT, MODE_LABELS, normalize_mode
from styles import APP_STYLE
from widgets import (
    AutoResizingTextEdit,
    DeletableHistoryComboBox,
    PinIconButton,
    StickyCodeHeader,
    SvgActionButton,
)
from window_attachments import AttachmentUrlMixin
from window_character import CharacterMixin
from window_chat import ChatFlowMixin
from window_config import ConfigMixin
from window_server import ServerSettingsMixin
from window_shared import (
    ClippedSidebarFrame,
    DEFAULT_ASSISTANT_DEBOUNCE_ENABLED,
    DEFAULT_ASSISTANT_DEBOUNCE_INTERVAL_MS,
    DEFAULT_CHARACTER_CARD_RATIO,
    DEFAULT_COMPOSER_MAX_LINES,
    DEFAULT_TERMINAL_PERMISSIONS,
    MAX_COMPOSER_MAX_LINES,
    MIN_COMPOSER_MAX_LINES,
    StatusBadge,
    TERMINAL_PERMISSION_DEFAULT,
)
from window_sidebar import SidebarMixin
from window_terminal import TerminalPermissionMixin
from window_workspace import WorkspaceLayoutMixin


class AgentChatWindow(
    AttachmentUrlMixin,
    CharacterMixin,
    ChatFlowMixin,
    ConfigMixin,
    ServerSettingsMixin,
    SidebarMixin,
    TerminalPermissionMixin,
    WorkspaceLayoutMixin,
    QMainWindow,
):
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
        self.config_needs_save = False
        self.api_key_storage_warnings = []
        self.config = self.load_config()
        self.active_mode = normalize_mode(self.config.get("active_mode", MODE_CHAT))
        server_config = self.config.get("server", {})
        session_prompt_config = self.config.get("session_prompt", {})
        terminal_config = self.config.get("agent_terminal", {})
        character_profiles_config = self.config.get("character_profiles", {})
        rendering_config = self.config.get("assistant_rendering", {})
        sampling_config = self.config.get("sampling", {})
        ui_config = self.config.get("ui", {})
        workspace_config = self.config.get("workspace", {})
        api_keys_config = self.config.get("api_keys", {})
        self.character_card_ratio = self.normalize_character_card_ratio(
            ui_config.get("character_card_ratio", DEFAULT_CHARACTER_CARD_RATIO)
        )

        self.server_enabled = bool(server_config.get("enabled", True))
        configured_base_url = self.normalize_base_url(server_config.get("base_url", ""))
        if configured_base_url:
            self.base_url = configured_base_url
        self.base_url_history = self.clean_history(
            server_config.get("base_urls", []),
            normalizer=self.normalize_base_url,
        )
        self.base_url_history = self.add_history_value(self.base_url_history, self.base_url)
        self.api_keys_enabled = bool(api_keys_config.get("enabled", True))
        self.api_keys = list(api_keys_config.get("items", []))
        self.selected_api_key_id = str(api_keys_config.get("selected_id", "")).strip()
        self.pending_api_key_id = self.selected_api_key_id
        self.character_profiles = normalize_character_profiles(character_profiles_config)
        self.session_prompt_enabled = bool(session_prompt_config.get("enabled", True))
        self.session_prompt_history = self.clean_history(session_prompt_config.get("history", []))
        self.initial_session_prompt = str(session_prompt_config.get("value", "")).strip()
        if self.initial_session_prompt:
            self.session_prompt_history = self.add_history_value(
                self.session_prompt_history,
                self.initial_session_prompt,
            )
        self.agent_terminal_enabled = True
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
        self.composer_max_lines = self.normalize_composer_max_lines(
            ui_config.get("composer_max_lines", DEFAULT_COMPOSER_MAX_LINES)
        )
        self.workspace_path_config = str(workspace_config.get("path", "")).strip()
        self.workspace_path = self.resolve_workspace_path(self.workspace_path_config)
        self.workspace_prompt_checked = False
        self.pending_terminal_permission = None
        self.assistant_reply_focus_active = False
        self.assistant_reply_focus_card = None
        self.assistant_reply_last_scroll_max = 0
        self.assistant_reply_scroll_interaction_active = False
        self.assistant_reply_scroll_away_requested = False
        self.selected_model_name = ""
        self.server_connected = False
        self.server_url_editing = False
        self.api_key_editing = False
        self.advanced_controls_config_expanded = bool(ui_config.get("advanced_controls_expanded", True))
        self.advanced_expanded = self.advanced_controls_config_expanded
        self.advanced_body_animation = None
        self.composer_expanded = bool(ui_config.get("chat_controls_expanded", True))
        self.composer_body_animation = None
        self.auto_scrollbar_timers = {}
        self.sidebar_pinned = self.pin_panel
        self.sidebar_open = False
        self.sidebar_collapsed_width = 68
        self.sidebar_expanded_max_width = 320
        self.compact_layout_active = False
        self.default_window_width = 1180
        self.default_window_height = 820
        self.sticky_code_header = None
        self.toast_label = None
        self.toast_timer = None
        self.character_search_query = ""
        self.character_show_favorites_only = False
        self.character_image_cache = CharacterImageCache(self)
        self.character_image_cache.pixmap_loaded.connect(self.on_character_pixmap_loaded)

        self.configure_responsive_metrics()

        self.setWindowTitle(f"Agent Chat v{APP_VERSION}")
        self.setWindowIcon(QIcon(str(APP_LOGO_PATH)))
        self.setStyleSheet(APP_STYLE + CHARACTER_MODE_STYLE_PATCH)
        self.resize(self.default_window_width, self.default_window_height)
        self.setMinimumSize(520, 420)

        self.build_ui()
        QApplication.instance().focusChanged.connect(self.on_focus_changed)
        if self.config_needs_save:
            QTimer.singleShot(0, self.save_config)
        if self.api_key_storage_warnings:
            QTimer.singleShot(0, self.show_api_key_storage_warning)
        QTimer.singleShot(0, self.prompt_for_workspace_if_needed)
        QTimer.singleShot(0, self.refresh_server_state)





























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
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setMinimumWidth(0)
        self.scroll_area.viewport().installEventFilter(self)
        self.scroll_area.verticalScrollBar().installEventFilter(self)
        self.setup_auto_hide_scrollbar(self.scroll_area)
        content_layout.addWidget(self.scroll_area)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.update_sticky_code_header)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.update_assistant_reply_follow_state)
        self.scroll_area.verticalScrollBar().rangeChanged.connect(self.update_assistant_reply_follow_range)

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
        self.build_character_overlay()

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
        self.refresh_api_key_ui()
        self.refresh_workspace_ui()
        self.refresh_session_prompt_ui()
        self.refresh_rendering_ui()
        self.refresh_terminal_permission_ui()
        self.refresh_character_ui()
        self.refresh_mode_ui()
        self.update_empty_state()
        self.update_send_availability()
        self.apply_responsive_layout()
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
        frame = ClippedSidebarFrame()
        frame.setObjectName("sidebar")
        frame.setMinimumWidth(self.sidebar_collapsed_width)
        frame.setMaximumWidth(self.sidebar_collapsed_width)
        frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        frame.enterEvent = self.sidebar_enter_event
        frame.leaveEvent = self.sidebar_leave_event

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 16, 12, 0)
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

        self.status_badge = StatusBadge("Checking")
        self.status_badge.setObjectName("statusBadge")
        header_row.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(header_row)

        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setObjectName("sidebarScroll")
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.sidebar_scroll.viewport().installEventFilter(self)
        self.sidebar_scroll.verticalScrollBar().installEventFilter(self)
        self.setup_auto_hide_scrollbar(self.sidebar_scroll)

        self.sidebar_content = QWidget()
        self.sidebar_content.setObjectName("sidebarScrollBody")
        self.sidebar_content.setMinimumWidth(0)
        content_layout = QVBoxLayout(self.sidebar_content)
        content_layout.setContentsMargins(0, 0, 4, 0)
        content_layout.setSpacing(16)

        title = QLabel("Agent Chat")
        title.setObjectName("titleLabel")
        content_layout.addWidget(title)

        self.status_detail = QLabel("", frame)
        self.status_detail.hide()

        mode_heading = QLabel("Mode")
        mode_heading.setObjectName("sectionLabel")
        content_layout.addWidget(mode_heading)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.setExclusive(True)
        self.mode_buttons = {}
        for mode in (MODE_CHAT, MODE_CHARACTER, MODE_AGENT):
            button = QPushButton(MODE_LABELS[mode])
            button.setObjectName("modeButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, value=mode: self.set_active_mode(value))
            self.mode_button_group.addButton(button)
            self.mode_buttons[mode] = button
            mode_row.addWidget(button)
        content_layout.addLayout(mode_row)

        model_heading = QLabel("Model")
        model_heading.setObjectName("sectionLabel")
        content_layout.addWidget(model_heading)

        self.model_selector = QPushButton("Select model")
        self.model_selector.setObjectName("modelSelectorButton")
        self.model_menu = QMenu(self)
        self.model_menu.setObjectName("modelMenu")
        self.model_menu.aboutToShow.connect(self.refresh_model_menu)
        self.model_selector.setMenu(self.model_menu)
        content_layout.addWidget(self.model_selector)

        self.sidebar_actions_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.sidebar_actions_layout.setSpacing(10)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("ghostButton")
        self.refresh_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.refresh_button.clicked.connect(self.refresh_server_state)
        self.sidebar_actions_layout.addWidget(self.refresh_button)

        self.clear_button = QPushButton("New session")
        self.clear_button.setObjectName("ghostButton")
        self.clear_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.clear_button.clicked.connect(self.clear_chat)
        self.sidebar_actions_layout.addWidget(self.clear_button)
        content_layout.addLayout(self.sidebar_actions_layout)

        self.advanced_panel = self.build_advanced_panel()
        content_layout.addWidget(self.advanced_panel)
        content_layout.addSpacing(16)

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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        advanced_header_row = QHBoxLayout()
        advanced_header_row.setContentsMargins(16, 18, 16, 0)
        advanced_header_row.setSpacing(8)
        self.advanced_heading = QLabel("Advanced controls")
        self.advanced_heading.setObjectName("sidebarGroupLabel")
        advanced_header_row.addWidget(self.advanced_heading)
        advanced_header_row.addStretch()
        self.advanced_collapse_button = QPushButton("")
        self.advanced_collapse_button.setObjectName("advancedCollapseButton")
        self.advanced_collapse_button.setIconSize(QSize(16, 16))
        self.advanced_collapse_button.setToolTip("Collapse advanced controls")
        self.advanced_collapse_button.clicked.connect(self.toggle_advanced_panel)
        advanced_header_row.addWidget(self.advanced_collapse_button)
        layout.addLayout(advanced_header_row)

        self.advanced_body = QWidget()
        advanced_body_layout = QVBoxLayout(self.advanced_body)
        advanced_body_layout.setContentsMargins(16, 0, 16, 0)
        advanced_body_layout.setSpacing(16)

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

        self.base_url_detail = QLabel("")
        self.base_url_detail.setObjectName("subtleLabel")
        self.base_url_detail.setWordWrap(True)
        server_section_layout.addWidget(self.base_url_detail)
        self.base_url_detail.setText(f"Base URL for OpenAI-compatible server: {self.base_url}")
        self.server_section.setVisible(self.server_enabled)
        advanced_body_layout.addWidget(self.server_section)

        self.api_keys_section = QWidget()
        api_keys_section_layout = QVBoxLayout(self.api_keys_section)
        api_keys_section_layout.setContentsMargins(0, 0, 0, 0)
        api_keys_section_layout.setSpacing(10)

        api_keys_heading = QLabel("API keys")
        api_keys_heading.setObjectName("sectionLabel")
        api_keys_header_row = QHBoxLayout()
        api_keys_header_row.setContentsMargins(0, 0, 0, 0)
        api_keys_header_row.setSpacing(8)
        api_keys_header_row.addWidget(api_keys_heading)
        api_keys_header_row.addStretch()

        self.api_key_history_button = QPushButton("▾")
        self.api_key_history_button.setObjectName("fieldIconButton")
        self.api_key_history_button.setToolTip("Select saved API key")
        self.api_key_history_button.clicked.connect(self.show_api_key_menu)
        api_keys_header_row.addWidget(self.api_key_history_button)

        self.apply_api_key_button = QPushButton("✓")
        self.apply_api_key_button.setObjectName("fieldIconButton")
        self.apply_api_key_button.setToolTip("Apply selected API key")
        self.apply_api_key_button.clicked.connect(self.apply_selected_api_key)
        api_keys_header_row.addWidget(self.apply_api_key_button)
        api_keys_section_layout.addLayout(api_keys_header_row)

        self.api_key_active_badge = QLabel("")
        self.api_key_active_badge.setObjectName("sessionPromptBadge")
        self.api_key_active_badge.setWordWrap(False)
        self.api_key_active_badge.setMinimumWidth(0)
        self.api_key_active_badge.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        api_keys_section_layout.addWidget(self.api_key_active_badge)

        self.new_api_key_button = QPushButton("New key")
        self.new_api_key_button.setObjectName("ghostButton")
        self.new_api_key_button.clicked.connect(self.toggle_new_api_key_panel)
        api_keys_section_layout.addWidget(self.new_api_key_button)

        self.new_api_key_panel = QFrame()
        self.new_api_key_panel.setObjectName("terminalPanel")
        new_api_key_panel_layout = QVBoxLayout(self.new_api_key_panel)
        new_api_key_panel_layout.setContentsMargins(12, 12, 12, 12)
        new_api_key_panel_layout.setSpacing(10)

        new_api_key_header_row = QHBoxLayout()
        new_api_key_header_row.setContentsMargins(0, 0, 0, 0)
        new_api_key_header_row.setSpacing(8)
        new_api_key_title = QLabel("New API key")
        new_api_key_title.setObjectName("sectionLabel")
        new_api_key_header_row.addWidget(new_api_key_title)
        new_api_key_header_row.addStretch()

        self.save_new_api_key_button = QPushButton("✓")
        self.save_new_api_key_button.setObjectName("fieldIconButton")
        self.save_new_api_key_button.setToolTip("Save and apply new API key")
        self.save_new_api_key_button.clicked.connect(self.save_new_api_key)
        new_api_key_header_row.addWidget(self.save_new_api_key_button)
        new_api_key_panel_layout.addLayout(new_api_key_header_row)

        api_key_form = QFormLayout()
        api_key_form.setSpacing(10)
        api_key_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.api_key_name_input = QLineEdit()
        self.api_key_name_input.setPlaceholderText("Display name")
        self.api_key_name_input.returnPressed.connect(self.save_new_api_key)
        api_key_form.addRow("Name", self.api_key_name_input)

        self.api_key_value_input = QLineEdit()
        self.api_key_value_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_value_input.setPlaceholderText("Paste API key")
        self.api_key_value_input.returnPressed.connect(self.save_new_api_key)
        api_key_form.addRow("Key", self.api_key_value_input)
        new_api_key_panel_layout.addLayout(api_key_form)
        api_keys_section_layout.addWidget(self.new_api_key_panel)
        self.new_api_key_panel.hide()
        self.new_api_key_panel.setMaximumHeight(16777215)
        self.new_api_key_panel_expanded = False
        self.new_api_key_panel_animation = None

        self.api_key_detail = QLabel("")
        self.api_key_detail.setObjectName("subtleLabel")
        self.api_key_detail.setWordWrap(False)
        api_keys_section_layout.addWidget(self.api_key_detail)
        self.api_keys_section.setVisible(self.api_keys_enabled)
        advanced_body_layout.addWidget(self.api_keys_section)
        layout.addWidget(self.advanced_body)
        self.set_advanced_panel_expanded(self.advanced_expanded, animate=False, persist=False)

        self.character_section = CharacterSectionFrame()
        self.character_section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        character_section_layout = QVBoxLayout(self.character_section)
        character_section_layout.setContentsMargins(16, 8, 16, 10)
        character_section_layout.setSpacing(10)

        character_heading = QLabel("Character")
        character_heading.setObjectName("sidebarGroupLabel")
        character_section_layout.addWidget(character_heading)

        self.character_source_panel = QWidget()
        character_source_panel_layout = QVBoxLayout(self.character_source_panel)
        character_source_panel_layout.setContentsMargins(0, 0, 0, 0)
        character_source_panel_layout.setSpacing(8)
        self.character_source_top_label = QLabel("Source")
        self.character_source_top_label.setObjectName("sectionLabel")
        character_source_panel_layout.addWidget(self.character_source_top_label)

        character_source_row = QHBoxLayout()
        character_source_row.setSpacing(8)
        self.character_source_label = QLabel("")
        self.character_source_label.setObjectName("characterMeta")
        character_source_row.addWidget(self.character_source_label, 1)

        self.character_source_input = QLineEdit(self.character_source_panel)
        self.character_source_input.setPlaceholderText("https://server.example/api/characters")
        self.character_source_input.setText(self.character_profiles.get("source_url", ""))
        self.character_source_input.returnPressed.connect(self.sync_characters)
        self.character_source_input.hide()

        self.sync_characters_button = QPushButton("Sync")
        self.sync_characters_button.setObjectName("ghostButton")
        self.sync_characters_button.clicked.connect(self.sync_characters)
        character_source_row.addWidget(self.sync_characters_button)
        character_source_panel_layout.addLayout(character_source_row)
        self.character_sync_label = QLabel("")
        self.character_sync_label.setObjectName("characterMeta")
        character_source_panel_layout.addWidget(self.character_sync_label)

        self.character_hero_card = CharacterSidebarHeroCard()
        self.character_hero_card.setFixedHeight(237)
        self.character_hero_card.clicked.connect(self.show_character_overlay)
        self.character_hero_card.favorite_toggled.connect(
            lambda _character_id: self.toggle_active_character_favorite()
        )
        character_section_layout.addWidget(self.character_hero_card)

        self.character_picker_button = QPushButton("")
        self.character_picker_button.setObjectName("characterChangeButton")
        self.character_picker_button.clicked.connect(self.show_character_overlay)
        character_picker_layout = QHBoxLayout(self.character_picker_button)
        character_picker_layout.setContentsMargins(14, 0, 14, 0)
        character_picker_layout.setSpacing(8)
        self.character_picker_label = QLabel("Change character")
        self.character_picker_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        character_picker_layout.addStretch(1)
        character_picker_layout.addWidget(self.character_picker_label)
        character_picker_layout.addStretch(1)
        self.character_picker_icon = QLabel("")
        self.character_picker_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.character_picker_icon.setPixmap(render_svg_pixmap(PENCIL_ICON_PATH, QSize(16, 16), "#f8fafc"))
        character_picker_layout.addWidget(self.character_picker_icon, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        character_section_layout.addWidget(self.character_picker_button)

        self.character_access_section = QWidget()
        access_layout = QVBoxLayout(self.character_access_section)
        access_layout.setContentsMargins(0, 0, 0, 0)
        access_layout.setSpacing(8)
        access_heading = QLabel("Access")
        access_heading.setObjectName("sectionLabel")
        access_layout.addWidget(access_heading)
        self.character_access_panel = CharacterAccessPanel(show_mcp=False)
        self.character_access_panel.capability_toggled.connect(
            self.set_active_character_capability
        )
        access_layout.addWidget(self.character_access_panel)
        character_section_layout.addWidget(self.character_access_section)

        personality_row = QHBoxLayout()
        personality_row.setSpacing(8)
        self.character_personality_label = QLabel("")
        self.character_personality_label.setObjectName("characterPersonality")
        self.character_personality_label.setWordWrap(True)
        personality_row.addWidget(self.character_personality_label, 1)
        self.character_personality_view_button = QPushButton("View")
        self.character_personality_view_button.setObjectName("inlineLinkButton")
        self.character_personality_view_button.clicked.connect(self.show_character_personality)
        personality_row.addWidget(self.character_personality_view_button, 0, Qt.AlignmentFlag.AlignBottom)

        self.character_personality_section = QWidget()
        personality_layout = QVBoxLayout(self.character_personality_section)
        personality_layout.setContentsMargins(0, 0, 0, 0)
        personality_layout.setSpacing(6)
        personality_heading = QLabel("Personality")
        personality_heading.setObjectName("sectionLabel")
        personality_layout.addWidget(personality_heading)
        personality_layout.addLayout(personality_row)
        character_section_layout.addWidget(self.character_personality_section)

        character_section_layout.addWidget(self.character_source_panel)
        layout.addWidget(self.character_section, 0, Qt.AlignmentFlag.AlignTop)

        self.workspace_section = QWidget()
        workspace_section_layout = QVBoxLayout(self.workspace_section)
        workspace_section_layout.setContentsMargins(16, 0, 16, 0)
        workspace_section_layout.setSpacing(10)

        workspace_heading = QLabel("Workspace")
        workspace_heading.setObjectName("sectionLabel")
        workspace_header_row = QHBoxLayout()
        workspace_header_row.setContentsMargins(0, 0, 0, 0)
        workspace_header_row.setSpacing(8)
        workspace_header_row.addWidget(workspace_heading)
        workspace_header_row.addStretch()

        self.choose_workspace_button = QPushButton("…")
        self.choose_workspace_button.setObjectName("fieldIconButton")
        self.choose_workspace_button.setToolTip("Choose workspace folder")
        self.choose_workspace_button.clicked.connect(self.choose_workspace)
        workspace_header_row.addWidget(self.choose_workspace_button)

        self.apply_workspace_button = QPushButton("✓")
        self.apply_workspace_button.setObjectName("fieldIconButton")
        self.apply_workspace_button.setToolTip("Apply workspace path")
        self.apply_workspace_button.clicked.connect(self.apply_workspace_path)
        workspace_header_row.addWidget(self.apply_workspace_button)
        workspace_section_layout.addLayout(workspace_header_row)

        self.workspace_input = QLineEdit()
        self.workspace_input.setPlaceholderText(str(APP_WORKSPACE))
        self.workspace_input.setText(self.workspace_path_config)
        self.workspace_input.returnPressed.connect(self.apply_workspace_path)
        workspace_section_layout.addWidget(self.workspace_input)

        self.workspace_detail = QLabel("")
        self.workspace_detail.setObjectName("subtleLabel")
        self.workspace_detail.setWordWrap(True)
        workspace_section_layout.addWidget(self.workspace_detail)
        layout.addWidget(self.workspace_section)

        self.session_prompt_section = QWidget()
        session_section_layout = QVBoxLayout(self.session_prompt_section)
        session_section_layout.setContentsMargins(16, 0, 16, 0)
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

        self.composer_section = QWidget()
        composer_section_layout = QVBoxLayout(self.composer_section)
        composer_section_layout.setContentsMargins(16, 4, 16, 16)
        composer_section_layout.setSpacing(12)

        composer_header_row = QHBoxLayout()
        composer_header_row.setContentsMargins(0, 0, 0, 0)
        composer_header_row.setSpacing(8)
        composer_heading = QLabel("Chat controls")
        composer_heading.setObjectName("sidebarGroupLabel")
        composer_header_row.addWidget(composer_heading)
        composer_header_row.addStretch()
        self.composer_collapse_button = QPushButton("")
        self.composer_collapse_button.setObjectName("advancedCollapseButton")
        self.composer_collapse_button.setIconSize(QSize(16, 16))
        self.composer_collapse_button.setToolTip("Collapse chat controls")
        self.composer_collapse_button.clicked.connect(self.toggle_composer_panel)
        composer_header_row.addWidget(self.composer_collapse_button)
        composer_section_layout.addLayout(composer_header_row)

        self.composer_body = QWidget()
        composer_body_layout = QVBoxLayout(self.composer_body)
        composer_body_layout.setContentsMargins(0, 0, 0, 0)
        composer_body_layout.setSpacing(14)

        composer_settings_section = QWidget()
        composer_settings_layout = QVBoxLayout(composer_settings_section)
        composer_settings_layout.setContentsMargins(0, 0, 0, 0)
        composer_settings_layout.setSpacing(8)
        composer_settings_heading = QLabel("Composer")
        composer_settings_heading.setObjectName("sectionLabel")
        composer_settings_layout.addWidget(composer_settings_heading)

        composer_layout = QFormLayout()
        composer_layout.setContentsMargins(0, 0, 0, 0)
        composer_layout.setHorizontalSpacing(14)
        composer_layout.setVerticalSpacing(8)
        composer_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        composer_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        composer_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)

        self.composer_max_lines_spin = QSpinBox()
        self.composer_max_lines_spin.setRange(MIN_COMPOSER_MAX_LINES, MAX_COMPOSER_MAX_LINES)
        self.composer_max_lines_spin.setSuffix(" lines")
        self.composer_max_lines_spin.setValue(self.composer_max_lines)
        self.composer_max_lines_spin.setFixedWidth(132)
        self.composer_max_lines_spin.valueChanged.connect(self.set_composer_max_lines)
        composer_layout.addRow("Max height", self.composer_max_lines_spin)
        composer_settings_layout.addLayout(composer_layout)
        composer_body_layout.addWidget(composer_settings_section)

        self.reasoning_section = QWidget()
        reasoning_section_layout = QVBoxLayout(self.reasoning_section)
        reasoning_section_layout.setContentsMargins(0, 0, 0, 0)
        reasoning_section_layout.setSpacing(8)

        thinking_label = QLabel("Reasoning")
        thinking_label.setObjectName("sectionLabel")
        reasoning_section_layout.addWidget(thinking_label)
        thinking_row = QHBoxLayout()
        thinking_row.setContentsMargins(0, 0, 0, 0)
        thinking_row.setSpacing(10)
        thinking_row.addWidget(QLabel("Show thinking"), 0, Qt.AlignmentFlag.AlignVCenter)
        thinking_row.addStretch()
        self.show_thinking_checkbox = SwitchPill(self.show_thinking)
        self.show_thinking_checkbox.setChecked(self.show_thinking)
        self.show_thinking_checkbox.toggled.connect(self.update_thinking_visibility)
        thinking_row.addWidget(self.show_thinking_checkbox, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        reasoning_section_layout.addLayout(thinking_row)
        composer_body_layout.addWidget(self.reasoning_section)

        self.assistant_rendering_section = QWidget()
        rendering_section_layout = QVBoxLayout(self.assistant_rendering_section)
        rendering_section_layout.setContentsMargins(0, 0, 0, 0)
        rendering_section_layout.setSpacing(8)

        rendering_heading = QLabel("Assistant rendering")
        rendering_heading.setObjectName("sectionLabel")
        rendering_section_layout.addWidget(rendering_heading)

        debounce_row = QHBoxLayout()
        debounce_row.setContentsMargins(0, 0, 0, 0)
        debounce_row.setSpacing(10)

        debounce_row.addWidget(QLabel("Debounce streaming"), 1, Qt.AlignmentFlag.AlignVCenter)

        self.debounce_interval_spin = QSpinBox()
        self.debounce_interval_spin.setRange(0, 1000)
        self.debounce_interval_spin.setSuffix(" ms")
        self.debounce_interval_spin.setValue(self.assistant_debounce_interval_ms)
        self.debounce_interval_spin.setFixedWidth(116)
        self.debounce_interval_spin.valueChanged.connect(self.set_assistant_debounce_interval)
        debounce_row.addWidget(self.debounce_interval_spin)

        self.debounce_checkbox = SwitchPill(self.assistant_debounce_enabled)
        self.debounce_checkbox.setChecked(self.assistant_debounce_enabled)
        self.debounce_checkbox.toggled.connect(self.set_assistant_debounce_enabled)
        debounce_row.addWidget(self.debounce_checkbox, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        rendering_section_layout.addLayout(debounce_row)
        self.assistant_rendering_section.setVisible(self.assistant_rendering_enabled)
        composer_body_layout.addWidget(self.assistant_rendering_section)
        composer_section_layout.addWidget(self.composer_body)
        self.set_composer_panel_expanded(self.composer_expanded, animate=False, persist=False)
        layout.addWidget(self.composer_section)

        self.agent_terminal_section = QWidget()
        terminal_section_layout = QVBoxLayout(self.agent_terminal_section)
        terminal_section_layout.setContentsMargins(16, 0, 16, 0)
        terminal_section_layout.setSpacing(10)

        terminal_row = QHBoxLayout()
        terminal_row.setSpacing(10)

        terminal_label = QLabel("Agent")
        terminal_label.setObjectName("sectionLabel")
        terminal_row.addWidget(terminal_label)

        self.agent_terminal_toggle_label = QLabel("Terminal access")
        terminal_row.addWidget(self.agent_terminal_toggle_label, 1, Qt.AlignmentFlag.AlignVCenter)
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

        self.empty_title = QLabel("Ready for a better local chat loop")
        self.empty_title.setObjectName("emptyTitle")
        layout.addWidget(self.empty_title)

        self.empty_body = QLabel(
            "Pick a model, set an optional session prompt, then start chatting."
        )
        self.empty_body.setObjectName("emptyBody")
        self.empty_body.setWordWrap(True)
        layout.addWidget(self.empty_body)

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

        self.composer = AutoResizingTextEdit(max_lines=self.composer_max_lines)
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

    def set_composer_max_lines(self, value):
        self.composer_max_lines = self.normalize_composer_max_lines(value)
        if hasattr(self, "composer_max_lines_spin"):
            self.composer_max_lines_spin.blockSignals(True)
            self.composer_max_lines_spin.setValue(self.composer_max_lines)
            self.composer_max_lines_spin.blockSignals(False)
        if hasattr(self, "composer"):
            self.composer.set_max_lines(self.composer_max_lines)
        self.save_config()

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

    def set_active_mode(self, mode):
        mode = normalize_mode(mode)
        if self.active_mode == mode:
            self.refresh_mode_ui()
            self.refresh_terminal_permission_ui()
            return
        if self.worker is not None and self.worker.isRunning():
            self.set_status_message("Wait for the current response before changing mode.")
            self.refresh_mode_ui()
            self.refresh_terminal_permission_ui()
            return
        if self.has_existing_conversation_content():
            self.clear_chat()
        self.active_mode = mode
        self.save_config()
        self.refresh_mode_ui()
        self.refresh_terminal_permission_ui()
        self.refresh_character_ui()
        self.update_empty_state()
        self.update_send_availability()
        if mode == MODE_AGENT:
            self.prompt_for_workspace_if_needed()
        self.set_status_message(f"{MODE_LABELS[mode]} mode active.")

    def refresh_mode_ui(self):
        if hasattr(self, "mode_buttons"):
            for mode, button in self.mode_buttons.items():
                button.blockSignals(True)
                button.setChecked(mode == self.active_mode)
                button.blockSignals(False)
                button.style().unpolish(button)
                button.style().polish(button)
        for attr in ("sidebar", "content_frame", "composer_frame"):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.setProperty("mode", self.active_mode)
                widget.style().unpolish(widget)
                widget.style().polish(widget)
        is_character = self.active_mode == MODE_CHARACTER
        is_agent = self.active_mode == MODE_AGENT
        character_terminal = is_character and bool(self.active_character_capabilities().get("terminal"))
        tools_visible = is_agent or character_terminal
        effective_terminal_enabled = self.is_terminal_enabled_for_request()
        if hasattr(self, "session_prompt_section"):
            self.session_prompt_section.setVisible(self.session_prompt_enabled and not is_character)
        if hasattr(self, "character_section"):
            self.character_section.setVisible(is_character)
        if hasattr(self, "character_capabilities_section"):
            self.character_capabilities_section.setVisible(is_character)
        if hasattr(self, "workspace_section"):
            self.workspace_section.setVisible(tools_visible)
        if hasattr(self, "agent_terminal_section"):
            self.agent_terminal_section.setVisible(tools_visible)
        if hasattr(self, "agent_terminal_checkbox"):
            self.agent_terminal_checkbox.setVisible(is_agent)
        if hasattr(self, "agent_terminal_toggle_label"):
            self.agent_terminal_toggle_label.setVisible(is_agent)
        if hasattr(self, "side_terminal_permission_button"):
            self.side_terminal_permission_button.setEnabled(effective_terminal_enabled)
        if hasattr(self, "terminal_permission_button"):
            self.terminal_permission_button.setVisible(tools_visible)
            self.terminal_permission_button.setEnabled(effective_terminal_enabled)
        if hasattr(self, "composer"):
            self.composer.setPlaceholderText(self.composer_placeholder())

    def composer_placeholder(self):
        if self.active_mode == MODE_AGENT:
            return "Ask for changes..."
        if self.active_mode == MODE_CHARACTER:
            character = self.active_character()
            if character:
                return f"Message {character.get('name', 'character')}..."
            return "Select a character to start..."
        return "Type your message..."

    def build_access_row(self, title, description, checkbox):
        row = QFrame()
        row.setObjectName("accessRow")

        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("accessLabel")

        desc_label = QLabel(description)
        desc_label.setObjectName("accessDescription")

        text_col.addWidget(title_label)
        text_col.addWidget(desc_label)

        checkbox.setObjectName("switchCheckBox")

        layout.addLayout(text_col, 1)
        layout.addWidget(checkbox)

        return row































































    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.apply_responsive_layout()
        if self.sidebar_open:
            self.sync_sidebar_width(self.target_sidebar_width())
        self.update_model_selector_text()
        self.update_sticky_code_header()
        self.position_toast()
        self.position_character_overlay()
        self.position_character_hero_elements()
        self.refresh_connection_settings_ui()
