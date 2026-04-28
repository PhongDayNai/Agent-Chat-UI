"""Qt stylesheets for agent-chat-ui."""

from constants import ASSETS_DIR


CHEVRON_DOWN_ICON = ASSETS_DIR / "ic_chevron_down.svg"
CHEVRON_RIGHT_ICON = ASSETS_DIR / "ic_chevron_right.svg"
CHECK_ICON = ASSETS_DIR / "ic_menu_check.svg"
ARROW_DOWN_ICON = ASSETS_DIR / "ic_arrow_down.svg"
ARROW_DOWN_FULL_ACCESS_ICON = ASSETS_DIR / "ic_arrow_down_full_access.svg"


APP_STYLE = """
QMainWindow {
    background: #0f1011;
}
QWidget {
    color: #e8eaed;
    background: transparent;
    font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 6px 0;
}
QScrollBar::handle:vertical {
    background: #2a2d30;
    min-height: 28px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #3c4044;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
    border: none;
}
QPushButton {
    border: 1px solid #2b2f33;
    border-radius: 12px;
    background: #17191b;
    color: #e8eaed;
    padding: 9px 14px;
    font-size: 11pt;
}
QPushButton:hover {
    background: #202326;
    border-color: #3a3f44;
}
QPushButton:pressed {
    background: #121416;
}
QPushButton:disabled {
    background: #141618;
    color: #5f6368;
    border-color: #24272a;
}
QPushButton#primaryButton {
    background: #f2f3f5;
    color: #111315;
    border-color: #f2f3f5;
    font-weight: 600;
}
QPushButton#primaryButton:hover {
    background: #ffffff;
    border-color: #ffffff;
}
QPushButton#dangerButton {
    background: #321c20;
    color: #ffd7dc;
    border-color: #60313a;
}
QPushButton#dangerButton:hover {
    background: #46262d;
}
QPushButton#ghostButton {
    background: transparent;
    border-color: #2a2d30;
}
QPushButton#ghostButton:hover {
    background: #181a1c;
}
QPushButton#modeButton {
    background: transparent;
    border-color: #2a2d30;
    min-height: 22px;
    padding: 9px 12px;
}
QPushButton#modeButton:hover {
    background: #181a1c;
    border-color: #3a3f44;
}
QPushButton#modeButton:checked {
    background: #f2f3f5;
    color: #111315;
    border-color: #f2f3f5;
    font-weight: 600;
}
QPushButton#modeButton:checked:hover {
    background: #ffffff;
    border-color: #ffffff;
}
QPushButton#tinyButton {
    padding: 6px 10px;
    border-radius: 10px;
    font-size: 10pt;
}
QPushButton#messageIconButton {
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
    padding: 0;
    border-radius: 9px;
    font-size: 12pt;
    font-weight: 700;
    background: #17191b;
    border: 1px solid #2a2d30;
    color: #cbd0d5;
}
QPushButton#messageIconButton:hover {
    background: #202326;
    border-color: #3a3f44;
    color: #ffffff;
}
QPushButton#secondaryButton {
    background: #17191b;
    border-color: #2b2f33;
}
QPushButton#secondaryButton:hover {
    background: #202326;
    border-color: #3a3f44;
}
QLabel#titleLabel {
    font-size: 21pt;
    font-weight: 700;
    color: #f4f5f6;
}
QLabel#subtleLabel {
    color: #8c9298;
    font-size: 10pt;
}
QLabel#sectionLabel {
    font-size: 10pt;
    font-weight: 600;
    color: #8c9298;
    letter-spacing: 0.03em;
}
QFrame#panel QCheckBox {
    spacing: 10px;
    color: #e8eaed;
    font-size: 10.5pt;
    font-weight: 500;
}
QFrame#panel QCheckBox:hover {
    color: #ffffff;
}
QFrame#panel QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 1px solid #3a3f44;
    background: #101214;
}
QFrame#panel QCheckBox::indicator:hover {
    border-color: #7d858d;
    background: #171a1d;
}
QFrame#panel QCheckBox::indicator:checked {
    border-color: #f2f3f5;
    background: #202326;
    image: url("__CHECK_ICON__");
}
QFrame#panel QCheckBox::indicator:checked:hover {
    border-color: #ffffff;
    background: #282c30;
}
QFrame#panel QCheckBox::indicator:disabled {
    border-color: #24272a;
    background: #141618;
}
QFrame#panel QCheckBox:disabled {
    color: #5f6368;
}
QPushButton#fieldIconButton {
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    padding: 0;
    border-radius: 10px;
    font-size: 12pt;
    font-weight: 700;
    background: #17191b;
    border: 1px solid #2a2d30;
    color: #8c9298;
}
QPushButton#fieldIconButton:hover {
    background: #202326;
    border-color: #3a3f44;
    color: #e8eaed;
}
QPushButton#fieldIconButton[applied="true"] {
    color: #f2f3f5;
    border-color: #f2f3f5;
}
QPushButton#inlineLinkButton {
    background: transparent;
    border: none;
    color: #f2f3f5;
    padding: 2px 0;
    font-size: 10pt;
    font-weight: 600;
}
QPushButton#inlineLinkButton:hover {
    color: #ffffff;
    text-decoration: underline;
}
QLabel#statusBadge {
    background: #17191b;
    border: 1px solid #2a2d30;
    border-radius: 999px;
    padding: 6px 10px;
    font-size: 10pt;
    font-weight: 600;
}
QLabel#sessionPromptBadge {
    background: #141618;
    border: 1px solid #2a2d30;
    border-radius: 14px;
    padding: 8px 10px;
    color: #d7d9dc;
    font-size: 9.5pt;
    font-weight: 600;
}
QFrame#characterHeroCard {
    background: #111315;
    border: 1px solid #2a2d30;
    border-radius: 6px;
}
QPushButton#heroIconButton {
    min-width: 28px;
    max-width: 28px;
    min-height: 26px;
    max-height: 26px;
    padding: 0;
    border: none;
    background: rgba(15, 16, 17, 120);
    color: #f2f3f5;
    font-size: 11pt;
    font-weight: 700;
}
QPushButton#heroIconButton:hover {
    background: rgba(242, 243, 245, 35);
}
QPushButton#heroIconButton[favorite="true"] {
    color: #f5c84c;
}
QPushButton#heroIconButton[favorite="true"]:hover {
    background: rgba(245, 200, 76, 45);
}
QLabel#characterHeroAvatar {
    background: #101214;
    color: #8c9298;
    font-size: 16pt;
    font-weight: 700;
}
QFrame#characterHeroInfo {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(8, 10, 12, 0),
        stop:0.36 rgba(8, 10, 12, 158),
        stop:1 rgba(8, 10, 12, 232)
    );
    border: none;
    border-radius: 0px;
    min-width: 0px;
}
QLabel#characterName {
    color: #ffffff;
    font-size: 15pt;
    font-weight: 700;
}
QLabel#characterStyle {
    color: #dfe5ea;
    font-size: 9.5pt;
    font-weight: 600;
}
QLabel#characterHeroTags {
    color: #bfc6ce;
    font-size: 9.5pt;
    font-weight: 600;
}
QLabel#characterPersonality {
    color: #c5c9ce;
    font-size: 10pt;
}
QLabel#characterMeta {
    color: #c5c9ce;
    font-size: 10pt;
}
QLabel#accessLabel {
    color: #e8eaed;
    font-size: 10.5pt;
    font-weight: 600;
}
QCheckBox#switchCheckBox {
    spacing: 0;
}
QCheckBox#switchCheckBox::indicator {
    width: 38px;
    height: 20px;
    border-radius: 10px;
    border: 1px solid #3a3f44;
    background: #141618;
}
QCheckBox#switchCheckBox::indicator:checked {
    border-color: #f2f3f5;
    background: #f2f3f5;
}
QCheckBox#switchCheckBox::indicator:hover {
    border-color: #7d858d;
}
QFrame#characterOverlay {
    background: rgba(8, 9, 10, 236);
    border: 1px solid #25292e;
    border-radius: 18px;
}
QLabel#overlayTitle {
    color: #f4f5f6;
    font-size: 18pt;
    font-weight: 700;
}
QPushButton#overlayCloseButton {
    min-width: 34px;
    max-width: 34px;
    min-height: 34px;
    max-height: 34px;
    padding: 0;
    border-radius: 10px;
    background: #17191b;
    border: 1px solid #2a2d30;
}
QPushButton#overlayRatioButton {
    min-width: 58px;
    max-width: 58px;
    min-height: 34px;
    max-height: 34px;
    padding: 0 8px;
    border-radius: 10px;
    background: #17191b;
    border: 1px solid #2a2d30;
    color: #f4f5f6;
    font-size: 10pt;
    font-weight: 700;
}
QPushButton#overlayRatioButton:hover {
    background: #202326;
    border-color: #3a3f44;
}
QScrollArea#characterOverlayScroll {
    background: transparent;
    border: none;
}
QFrame#characterChoiceCard {
    background: #101214;
    border: none;
    border-radius: 16px;
}
QFrame#characterChoiceCard:hover,
QFrame#characterChoiceCard[expanded="true"] {
    background: #121518;
}
QLabel#characterChoiceCover {
    background: #101214;
    color: #8c9298;
    font-size: 18pt;
    font-weight: 700;
}
QFrame#characterChoiceInfo {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(8, 10, 12, 0),
        stop:0.34 rgba(8, 10, 12, 162),
        stop:1 rgba(8, 10, 12, 236)
    );
    border: none;
}
QLabel#characterChoiceName {
    color: #ffffff;
    font-size: 13pt;
    font-weight: 700;
}
QLabel#characterChoiceMeta {
    color: #dfe5ea;
    font-size: 9.5pt;
    font-weight: 600;
}
QLabel#characterChoiceDescription {
    color: #f0f3f6;
    font-size: 10pt;
    font-weight: 500;
}
QFrame#queueBanner {
    background: #181a1c;
    border: 1px solid #2d3135;
    border-radius: 16px;
}
QLabel#queueBadge {
    background: #f2f3f5;
    color: #111315;
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 9.5pt;
    font-weight: 700;
}
QLabel#queueBannerText {
    color: #d8dadd;
    font-size: 10pt;
    font-weight: 600;
}
QLabel#emptyTitle {
    font-size: 20pt;
    font-weight: 700;
    color: #f4f5f6;
}
QLabel#emptyBody {
    color: #9aa0a6;
    font-size: 11pt;
}
QFrame#sidebar {
    background: #111315;
    border: 1px solid #1d2023;
    border-radius: 24px;
}
QScrollArea#sidebarScroll {
    border: none;
    background: transparent;
}
QWidget#sidebarScrollBody {
    background: transparent;
}
QPushButton#sidebarMenuButton {
    background: #17191b;
    border: 1px solid #2a2d30;
    border-radius: 14px;
    min-width: 44px;
    max-width: 44px;
    min-height: 44px;
    max-height: 44px;
    padding: 0;
    font-size: 18pt;
    font-weight: 700;
    color: #d8dadd;
}
QPushButton#sidebarMenuButton:hover {
    background: #202326;
    border-color: #3a3f44;
}
QPushButton#pinButton {
    background: #17191b;
    border: 1px solid #2a2d30;
    border-radius: 14px;
    color: #8c9298;
    min-width: 44px;
    max-width: 44px;
    min-height: 44px;
    max-height: 44px;
    padding: 0;
    font-size: 15pt;
    font-weight: 700;
}
QPushButton#pinButton:hover {
    background: #202326;
    border-color: #3a3f44;
    color: #e8eaed;
}
QPushButton#pinButton[pinned="true"] {
    background: #202326;
    border-color: #f2f3f5;
    color: #f2f3f5;
}
QFrame#surface {
    background: #111315;
    border: 1px solid #1d2023;
    border-radius: 24px;
}
QFrame#panel {
    background: #151719;
    border: 1px solid #24272a;
    border-radius: 18px;
}
QFrame#composerFrame {
    background: transparent;
    border: none;
}
QFrame#composerCanvas {
    background: #111315;
    border: 1px solid #171a1d;
    border-radius: 24px;
}
QScrollArea#attachmentScroll {
    border: none;
    background: transparent;
}
QFrame#attachmentChip {
    background: #181a1c;
    border: 1px solid #2d3135;
    border-radius: 16px;
}
QFrame#imageChip {
    background: #181a1c;
    border: 1px solid #2d3135;
    border-radius: 18px;
}
QLabel#attachmentName {
    color: #e8eaed;
    font-size: 10pt;
}
QLabel#fileGlyph {
    color: #d8dadd;
    font-size: 14pt;
    font-weight: 700;
}
QPushButton#attachmentRemoveButton {
    background: rgba(10, 14, 18, 0.62);
    border: 1px solid rgba(255, 255, 255, 0.06);
    color: #eff5fb;
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
    padding: 0;
    font-size: 12pt;
    border-radius: 12px;
}
QPushButton#attachmentRemoveButton:hover {
    background: rgba(10, 14, 18, 0.9);
}
QPushButton#composerPlusButton {
    background: transparent;
    border: none;
    color: #8a8f94;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    padding: 0;
    font-size: 18pt;
    font-weight: 300;
}
QPushButton#composerPlusButton:hover {
    background: #1a1d20;
    border-radius: 16px;
    color: #d8dde2;
}
QPushButton#terminalPermissionButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 14px;
    color: #f2f3f5;
    padding: 5px 30px 5px 9px;
    font-size: 10pt;
    font-weight: 400;
}
QPushButton#terminalPermissionButton[fullAccess="true"] {
    color: #d5c537;
}
QPushButton#terminalPermissionButton:hover {
    background: #1a1d20;
    border-color: #2a2d30;
}
QPushButton#terminalPermissionButton:disabled {
    color: #5f6368;
    background: transparent;
    border-color: transparent;
}
QPushButton#terminalPermissionButton::menu-indicator {
    image: url("__ARROW_DOWN_ICON__");
    subcontrol-origin: padding;
    subcontrol-position: center right;
    right: 9px;
    width: 12px;
    height: 12px;
}
QPushButton#terminalPermissionButton[fullAccess="true"]::menu-indicator {
    image: url("__ARROW_DOWN_FULL_ACCESS_ICON__");
}
QPushButton#terminalPermissionButton::menu-indicator:disabled {
    image: none;
}
QMenu#terminalPermissionMenu {
    min-width: 196px;
    padding: 7px;
}
QPushButton#terminalPermissionMenuItem {
    min-width: 172px;
    background: transparent;
    border: none;
    border-radius: 8px;
    color: #f2f3f5;
    padding: 8px 16px 8px 10px;
    text-align: left;
    font-size: 10pt;
    font-weight: 500;
}
QPushButton#terminalPermissionMenuItem:hover,
QPushButton#terminalPermissionMenuItem[selected="true"] {
    background: #23272b;
    color: #ffffff;
}
QPushButton#terminalPermissionMenuItem[fullAccess="true"] {
    color: #d5c537;
}
QPushButton#terminalPermissionMenuItem[fullAccess="true"]:hover,
QPushButton#terminalPermissionMenuItem[fullAccess="true"][selected="true"] {
    background: #29291c;
    color: #d5c537;
}
QPushButton#modelSelectorButton,
QPushButton#terminalPermissionSideButton {
    background: #151719;
    border: 1px solid #2a2d30;
    border-radius: 14px;
    color: #e8eaed;
    padding: 8px 38px 8px 12px;
    font-size: 11pt;
    text-align: left;
}
QPushButton#modelSelectorButton:hover,
QPushButton#terminalPermissionSideButton:hover {
    background: #151719;
    border-color: #3a3f44;
}
QPushButton#modelSelectorButton:pressed,
QPushButton#terminalPermissionSideButton:pressed {
    background: #151719;
    border-color: #f2f3f5;
}
QPushButton#modelSelectorButton:disabled,
QPushButton#terminalPermissionSideButton:disabled {
    background: #141618;
    color: #5f6368;
    border-color: #24272a;
}
QPushButton#modelSelectorButton::menu-indicator,
QPushButton#terminalPermissionSideButton::menu-indicator {
    image: url("__CHEVRON_DOWN_ICON__");
    subcontrol-origin: padding;
    subcontrol-position: center right;
    right: 13px;
    width: 12px;
    height: 12px;
}
QPushButton#modelSelectorButton::menu-indicator:disabled,
QPushButton#terminalPermissionSideButton::menu-indicator:disabled {
    image: none;
}
QPushButton#terminalPermissionSideButton::menu-indicator {
    image: url("__ARROW_DOWN_ICON__");
}
QPushButton#terminalPermissionSideButton[fullAccess="true"] {
    color: #d5c537;
}
QPushButton#terminalPermissionSideButton[fullAccess="true"]::menu-indicator {
    image: url("__ARROW_DOWN_FULL_ACCESS_ICON__");
}
QMenu#modelMenu,
QMenu#terminalPermissionMenu {
    min-width: 196px;
}
QFrame#terminalApprovalBanner {
    background: #181a1c;
    border: 1px solid #3e3520;
    border-radius: 14px;
}
QLabel#terminalApprovalText {
    color: #f0e6b2;
    font-size: 10pt;
    font-weight: 600;
}
QPushButton#iconActionButton {
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    padding: 0;
    border-radius: 16px;
    font-size: 15pt;
    font-weight: 800;
}
QPushButton#iconActionButton[variant="send"] {
    background: #6f7378;
    color: #151719;
    border: 1px solid #6f7378;
}
QPushButton#iconActionButton[variant="send"]:hover {
    background: #f2f3f5;
    border-color: #f2f3f5;
}
QPushButton#iconActionButton[variant="send"]:disabled {
    background: #5f6368;
    color: #26292c;
    border-color: #5f6368;
}
QPushButton#iconActionButton[variant="send"]:enabled {
    background: #f2f3f5;
    color: #111315;
    border-color: #f2f3f5;
}
QPushButton#iconActionButton[variant="stop"] {
    background: #321c20;
    color: #ffc9d2;
    border: 1px solid #6f3342;
}
QPushButton#iconActionButton[variant="stop"]:hover {
    background: #5a2935;
}
QFrame#gallerySurface {
    background: #151719;
    border: 1px solid #2a2d30;
    border-radius: 24px;
}
QFrame#messageCard {
    border-radius: 22px;
    border: 1px solid #2a2d30;
}
QFrame#messageCard[user="true"] {
    background: #1d2023;
    border-color: #34383d;
}
QFrame#messageCard[user="false"] {
    background: #151719;
}
QFrame#messageCard[system="true"] {
    background: #181a1c;
    border-color: #33373b;
}
QFrame#terminalRunBlock {
    background: transparent;
    border: none;
}
QFrame#terminalHeaderLine {
    background: #2a2d30;
    min-height: 1px;
    max-height: 1px;
}
QFrame#terminalPanel {
    background: #090b0d;
    border: 1px solid #2a2f35;
    border-radius: 10px;
}
QPushButton#terminalRunButton {
    background: transparent;
    border: none;
    color: #d8dde3;
    font-size: 10pt;
    font-weight: 700;
    padding: 5px 4px;
    text-align: left;
}
QPushButton#terminalRunButton:hover {
    color: #ffffff;
}
QPushButton#terminalArrowButton {
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    padding: 0;
    border: none;
    background: transparent;
    color: #d8dde3;
}
QPushButton#terminalArrowButton:hover {
    background: #202326;
    color: #ffffff;
}
QLabel#terminalShell {
    color: #d8dde3;
    font-size: 9.5pt;
    font-weight: 800;
}
QLabel#terminalCommand {
    color: #f1f5f9;
    font-family: "IBM Plex Mono", "Consolas", monospace;
    font-size: 10pt;
}
QLabel#terminalStatus {
    color: #8c9298;
    font-size: 9pt;
}
QPlainTextEdit#terminalLog {
    background: #090b0d;
    border: 1px solid #1d2329;
    border-radius: 8px;
    color: #dbe7f3;
    padding: 8px;
    font-family: "IBM Plex Mono", "Consolas", monospace;
    font-size: 10pt;
    selection-background-color: #2b4c6f;
}
QLabel#roleLabel {
    font-size: 10pt;
    font-weight: 600;
    color: #f4f5f6;
}
QLabel#timeLabel {
    font-size: 9pt;
    color: #858b91;
}
QLabel#attachmentLabel {
    color: #d8dadd;
    font-size: 9.5pt;
    padding: 4px 0;
}
QFrame#assistantCodeBlock {
    background: #151617;
    border: 1px solid #2a2d30;
    border-radius: 18px;
}
QFrame#stickyCodeHeader {
    background: #151617;
    border: 1px solid #2a2d30;
    border-bottom-color: #25282c;
    border-top-left-radius: 18px;
    border-top-right-radius: 18px;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
}
QLabel#assistantCodeIcon,
QLabel#assistantCodeLanguage {
    color: #f2f3f5;
    font-size: 10pt;
}
QLabel#assistantCodeIcon {
    font-family: "IBM Plex Mono", "Consolas", monospace;
    font-weight: 800;
}
QPushButton#assistantCodeCopyButton {
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
    padding: 0;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: #d6d9dd;
}
QPushButton#assistantCodeCopyButton:hover {
    background: #202326;
    color: #ffffff;
}
QPlainTextEdit#assistantCodeText {
    background: transparent;
    border: none;
    color: #f2f3f5;
    padding: 0;
    font-family: "IBM Plex Mono", "Consolas", monospace;
    font-size: 11pt;
    selection-background-color: #2b4c6f;
}
QLabel#toastLabel {
    background: #202326;
    border: 1px solid #3a3f44;
    border-radius: 10px;
    color: #f4f5f6;
    font-size: 10.5pt;
    font-weight: 600;
    padding: 9px 14px;
}
QToolTip {
    background: #202326;
    border: 1px solid #3a3f44;
    border-radius: 10px;
    color: #f4f5f6;
    padding: 8px 10px;
    font-size: 10pt;
}
QMenu {
    background: #151719;
    border: 1px solid #2f3338;
    border-radius: 12px;
    padding: 6px;
}
QMenu::item {
    background: transparent;
    color: #d8dadd;
    padding: 8px 30px 8px 12px;
    border-radius: 8px;
}
QMenu::item:selected {
    background: #23272b;
    color: #ffffff;
}
QMenu::item:pressed {
    background: #2b3035;
}
QMenu::item:disabled {
    background: transparent;
    color: #747a80;
}
QMenu::separator {
    height: 1px;
    background: #2a2d30;
    margin: 7px 4px;
}
QMenu::indicator {
    width: 16px;
    height: 16px;
    padding-left: 4px;
}
QMenu::indicator:checked {
    image: url("__CHECK_ICON__");
}
QMenu::right-arrow {
    image: url("__CHEVRON_RIGHT_ICON__");
    width: 12px;
    height: 12px;
}
QPlainTextEdit#composerInput {
    background: transparent;
    border: none;
    border-radius: 0;
    font-size: 12pt;
    color: #e8eaed;
    padding: 0;
}
QPlainTextEdit#composerInput:focus {
    border: none;
}
QComboBox,
QPlainTextEdit,
QDoubleSpinBox,
QSpinBox {
    background: #151719;
    border: 1px solid #2a2d30;
    border-radius: 14px;
    color: #e8eaed;
    padding: 8px 10px;
    selection-background-color: #3a3f44;
}
QComboBox:focus,
QPlainTextEdit:focus,
QDoubleSpinBox:focus,
QSpinBox:focus {
    border-color: #f2f3f5;
}
QComboBox {
    min-height: 20px;
    padding: 8px 38px 8px 12px;
}
QComboBox:hover {
    background: #181b1e;
    border-color: #3a3f44;
}
QComboBox:on {
    background: #1b1f22;
    border-color: #f2f3f5;
    border-bottom-left-radius: 10px;
    border-bottom-right-radius: 10px;
}
QComboBox:disabled {
    background: #141618;
    color: #5f6368;
    border-color: #24272a;
}
QComboBox::drop-down {
    border: none;
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 32px;
    border-top-right-radius: 14px;
    border-bottom-right-radius: 14px;
    background: transparent;
}
QComboBox::drop-down:hover {
    background: #202326;
}
QComboBox::down-arrow {
    image: url("__CHEVRON_DOWN_ICON__");
    width: 12px;
    height: 12px;
}
QComboBox::down-arrow:disabled {
    image: none;
}
QComboBox[historyAvailable="false"]::drop-down {
    width: 0px;
}
QComboBox[historyAvailable="false"] {
    padding-right: 12px;
}
QComboBox[historyAvailable="false"]::down-arrow {
    image: none;
}
QComboBox QLineEdit {
    background: transparent;
    border: none;
    color: #e8eaed;
    padding: 0;
    selection-background-color: #3a3f44;
}
QComboBox QAbstractItemView {
    background: #151719;
    border: 1px solid #2f3338;
    border-radius: 12px;
    padding: 6px;
    color: #d8dadd;
    selection-background-color: #23272b;
    selection-color: #ffffff;
    outline: none;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 7px 10px;
    border-radius: 8px;
}
QComboBox QAbstractItemView::item:hover,
QComboBox QAbstractItemView::item:selected {
    background: #23272b;
    color: #ffffff;
}
QPlainTextEdit {
    padding: 12px 14px;
    font-size: 11pt;
}
QTextBrowser {
    border: none;
    background: transparent;
    color: #e8eaed;
    font-size: 11pt;
}
""".replace("__CHEVRON_DOWN_ICON__", CHEVRON_DOWN_ICON.as_posix()).replace(
    "__CHEVRON_RIGHT_ICON__",
    CHEVRON_RIGHT_ICON.as_posix(),
).replace("__CHECK_ICON__", CHECK_ICON.as_posix()).replace(
    "__ARROW_DOWN_FULL_ACCESS_ICON__",
    ARROW_DOWN_FULL_ACCESS_ICON.as_posix(),
).replace("__ARROW_DOWN_ICON__", ARROW_DOWN_ICON.as_posix())

MARKDOWN_STYLESHEET = """
body {
    color: #e8eaed;
    font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
    font-size: 15px;
    line-height: 1.55;
}
p {
    margin: 0 0 10px 0;
}
h1, h2, h3, h4 {
    color: #f4f5f6;
    margin: 12px 0 8px 0;
}
ul, ol {
    margin-top: 6px;
    margin-bottom: 10px;
}
blockquote {
    color: #c7cacf;
    border-left: 3px solid #3a3f44;
    margin: 10px 0;
    padding-left: 12px;
}
pre {
    background: #0f1011;
    border: 1px solid #2a2d30;
    border-radius: 14px;
    padding: 12px;
    white-space: pre-wrap;
    font-family: "IBM Plex Mono", "Consolas", monospace;
}
code {
    background: #0f1011;
    border: 1px solid #2a2d30;
    border-radius: 8px;
    padding: 2px 5px;
    font-family: "IBM Plex Mono", "Consolas", monospace;
}
a {
    color: #57a6ff;
    text-decoration: underline;
}
a:hover {
    color: #2f7ed8;
    text-decoration: underline;
}
"""
