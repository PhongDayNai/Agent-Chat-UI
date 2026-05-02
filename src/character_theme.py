"""Character Mode QSS patch.

Append this to APP_STYLE in window.py:
    from character_theme import CHARACTER_MODE_STYLE_PATCH
    self.setStyleSheet(APP_STYLE + CHARACTER_MODE_STYLE_PATCH)
"""

CHARACTER_MODE_STYLE_PATCH = """
QMainWindow {
    background: #070807;
}

QFrame#surface[mode="character"] {
    background: rgb(15, 20, 17);
    border-color: #25332b;
}

QFrame#sidebar[mode="character"] {
    background: rgb(15, 20, 17);
    border-color: #25332b;
}

QFrame#sidebar[mode="character"] QWidget#sidebarScrollBody {
    background: transparent;
}

QFrame#sidebar[mode="character"] QPushButton#modeButton:checked {
    background: #7c6cff;
    color: #ffffff;
    border-color: #7c6cff;
    font-weight: 700;
}

QFrame#composerCanvas[mode="character"] {
    background: rgb(15, 20, 17);
    border: 1px solid #25332b;
    border-radius: 24px;
}

QPushButton#iconActionButton[variant="send"][mode="character"] {
    background: #7c6cff;
    border-color: #7c6cff;
    color: #ffffff;
}

QPushButton#iconActionButton[variant="send"][mode="character"]:hover {
    background: #8b7cff;
    border-color: #8b7cff;
    color: #ffffff;
}

QFrame#characterOverlay {
    background: rgba(15, 20, 17, 248);
    border: 1px solid #25332b;
    border-radius: 24px;
}

QLabel#overlayTitle {
    color: #f8fafc;
    font-size: 22pt;
    font-weight: 850;
    letter-spacing: -0.04em;
}

QLabel#overlaySubtitle {
    color: #94a3b8;
    font-size: 11pt;
    font-weight: 500;
}

QPushButton#overlayCloseButton {
    min-width: 40px;
    max-width: 40px;
    min-height: 40px;
    max-height: 40px;
    padding: 0;
    border-radius: 12px;
    background: transparent;
    border: 1px solid #25332b;
    color: #e5e7eb;
    font-size: 13pt;
    font-weight: 900;
}

QPushButton#overlayCloseButton:hover {
    background: rgba(255, 255, 255, 18);
    border-color: #25332b;
}

QPushButton#overlayRatioButton,
QPushButton#characterSortButton,
QPushButton#characterViewButton {
    min-height: 40px;
    padding: 0 12px;
    border-radius: 12px;
    background: transparent;
    border: 1px solid #25332b;
    color: #f8fafc;
    font-size: 10pt;
    font-weight: 800;
}

QPushButton#overlayRatioButton:hover,
QPushButton#characterSortButton:hover,
QPushButton#characterViewButton:hover {
    background: rgba(255, 255, 255, 18);
    border-color: #25332b;
}

QPushButton#characterViewButton[active="true"] {
    background: transparent;
    border-color: #25332b;
    color: #ffffff;
}

QPushButton#characterSortButton {
    min-width: 112px;
    max-width: 112px;
    min-height: 40px;
    max-height: 40px;
    padding: 0;
}

QFrame#characterLayoutToggle {
    min-width: 76px;
    max-width: 76px;
    min-height: 40px;
    max-height: 40px;
    background: transparent;
    border: 1px solid #25332b;
    border-radius: 12px;
}

QPushButton#characterLayoutButton {
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
    background: transparent;
    border: none;
    border-radius: 8px;
}

QPushButton#characterLayoutButton:hover {
    background: rgba(255, 255, 255, 18);
    border: none;
}

QPushButton#characterLayoutButton:checked {
    background: rgba(255, 255, 255, 51);
    border: none;
}

QPushButton#characterLayoutButton:disabled {
    background: transparent;
    border: none;
}

QScrollArea#characterOverlayScroll {
    background: transparent;
    border: none;
}

QPushButton#characterChangeButton {
    background: rgba(24, 30, 27, 190);
    border: 1px solid #35423a;
    border-radius: 14px;
    color: #f8fafc;
    padding: 10px 14px;
    font-size: 10.5pt;
    font-weight: 750;
}

QPushButton#characterChangeButton:hover {
    background: rgba(31, 40, 35, 230);
    border-color: #586a5f;
    color: #ffffff;
}

QFrame#accessPanel {
    background: transparent;
    border: none;
    border-radius: 0;
}

QFrame#accessRow {
    background: transparent;
    border: none;
    border-radius: 13px;
}

QFrame#accessRow:hover {
    background: rgba(255, 255, 255, 10);
}

QLabel#accessIcon {
    color: #8c9298;
    font-size: 13pt;
    font-weight: 800;
}

QLabel#accessLabel {
    color: #f1f5f9;
    font-size: 8pt;
    font-weight: 800;
}

QFrame#personalityCard,
QFrame#sourceCard {
    background: #101827;
    border: 1px solid #273244;
    border-radius: 16px;
}

QPushButton#personalityViewButton {
    background: transparent;
    border: none;
    color: #c4b5fd;
    font-weight: 800;
}

QLabel#privacyFooter {
    color: #667085;
    font-size: 9.5pt;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 4px 0 4px 0;
}

QScrollBar::handle:vertical {
    background: #2f3a4f;
    border-radius: 5px;
    min-height: 42px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}

/* === Character switch-style checkbox override begin === */
QCheckBox#switchCheckBox::indicator {
    width: 44px;
    height: 24px;
    border-radius: 12px;
    border: 1px solid #3b4658;
    background: #111827;
}

QCheckBox#switchCheckBox::indicator:hover {
    border-color: #64748b;
    background: #172033;
}

QCheckBox#switchCheckBox::indicator:checked {
    border-color: #7c6cff;
    background: #7c6cff;
}

QCheckBox#switchCheckBox::indicator:unchecked {
    border-color: #3b4658;
    background: #111827;
}
/* === Character switch-style checkbox override end === */
"""
