"""Terminal and code display widgets."""

import time
from math import ceil

from PyQt6.QtCore import QRegularExpression, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from constants import ARROW_RIGHT_ICON_PATH, COPY_ICON_PATH

from widget_components.button_widgets import RotatingSvgButton, SvgActionButton, elided_text_lines, format_elapsed_time_text


def show_widget_toast(widget, text):
    """Show a toast notification on a widget."""
    from PyQt6.QtWidgets import QLabel, QGraphicsOpacityEffect
    label = QLabel(text, widget)
    label.setObjectName("toastLabel")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet("""
        QLabel {
            background: #32383f;
            color: #e0e0e0;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 13px;
        }
    """)
    opacity = QGraphicsOpacityEffect(label)
    label.setGraphicsEffect(opacity)
    label.setAutoFillBackground(True)

    from PyQt6.QtCore import QPropertyAnimation, Property
    current_opacity = [1.0]

    def animate():
        current_opacity[0] -= 0.02
        opacity.setOpacity(current_opacity[0])
        if current_opacity[0] <= 0:
            animation.stop()
            label.deleteLater()

    label.move(
        (widget.width() - label.sizeHint().width()) // 2,
        widget.height() - 60,
    )
    label.show()
    animation = QTimer()
    animation.timeout.connect(animate)
    animation.start(30)
    QTimer.singleShot(2500, lambda: (animation.stop(), label.deleteLater()))


class TerminalCommandBlock(QFrame):
    """Block displaying terminal command with expandable output."""

    def __init__(self, command, shell_name="Bash", parent=None):
        super().__init__(parent)
        self.command = command
        self.shell_name = shell_name
        self.expanded = True
        self.panel_animation = None
        self.run_label = "Running"
        self.started_at = time.monotonic()
        self.ended_at = None
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(1000)
        self.elapsed_timer.timeout.connect(self.update_terminal_timer)

        self.setObjectName("terminalRunBlock")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)

        self.toggle_button = QPushButton()
        self.toggle_button.setObjectName("terminalRunButton")
        self.toggle_button.setToolTip(command)
        self.toggle_button.setMinimumWidth(0)
        self.toggle_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.toggle_button.clicked.connect(self.toggle_expanded)
        header.addWidget(self.toggle_button, 0)

        self.arrow_button = RotatingSvgButton(ARROW_RIGHT_ICON_PATH)
        self.arrow_button.setObjectName("terminalArrowButton")
        self.arrow_button.setToolTip(command)
        self.arrow_button.clicked.connect(self.toggle_expanded)
        header.addWidget(self.arrow_button)

        self.timer_label = QLabel("0s")
        self.timer_label.setObjectName("terminalTimerLabel")
        header.addWidget(self.timer_label, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addStretch()
        layout.addLayout(header)

        line = QFrame()
        line.setObjectName("terminalHeaderLine")
        layout.addWidget(line)

        self.panel = QFrame()
        self.panel.setObjectName("terminalPanel")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(10)

        shell_row = QHBoxLayout()
        shell_row.setContentsMargins(0, 0, 0, 0)
        shell_row.setSpacing(8)

        self.shell_label = QLabel(shell_name)
        self.shell_label.setObjectName("terminalShell")
        shell_row.addWidget(self.shell_label)

        self.status_label = QLabel("running")
        self.status_label.setObjectName("terminalStatus")
        shell_row.addWidget(self.status_label)
        shell_row.addStretch()
        panel_layout.addLayout(shell_row)

        command_row = QHBoxLayout()
        command_row.setContentsMargins(0, 0, 0, 0)
        command_row.setSpacing(10)

        self.command_label = QLabel(command)
        self.command_label.setObjectName("terminalCommand")
        self.command_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.command_label.setWordWrap(True)
        self.command_label.setMinimumWidth(0)
        self.command_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        command_row.addWidget(self.command_label, 1)

        self.copy_command_button = SvgActionButton(COPY_ICON_PATH)
        self.copy_command_button.setObjectName("messageIconButton")
        self.copy_command_button.setToolTip("Copy command")
        self.copy_command_button.clicked.connect(self.copy_command)
        command_row.addWidget(self.copy_command_button, 0, Qt.AlignmentFlag.AlignTop)
        panel_layout.addLayout(command_row)

        self.log = QPlainTextEdit()
        self.log.setObjectName("terminalLog")
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.log.setMinimumHeight(150)
        self.log.setMaximumHeight(300)
        panel_layout.addWidget(self.log)
        layout.addWidget(self.panel)
        self.panel.setMaximumHeight(16777215)

        self.update_toggle_text()
        self.update_terminal_timer()
        self.elapsed_timer.start()

    def toggle_expanded(self):
        self.set_expanded(not self.expanded)

    def set_expanded(self, expanded):
        if self.expanded == bool(expanded):
            return
        self.expanded = bool(expanded)
        self.animate_panel_visibility(self.expanded)
        self.update_toggle_text()

    def animate_panel_visibility(self, expanded):
        from PyQt6.QtCore import QEasingCurve, QPropertyAnimation
        if self.panel_animation is not None:
            self.panel_animation.stop()

        if expanded:
            self.panel.show()
            self.panel.setMaximumHeight(0)
            start_height = 0
            end_height = max(1, self.panel.sizeHint().height())
        else:
            start_height = max(1, self.panel.height())
            end_height = 0

        self.panel_animation = QPropertyAnimation(self.panel, b"maximumHeight", self)
        self.panel_animation.setDuration(220)
        self.panel_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.panel_animation.setStartValue(start_height)
        self.panel_animation.setEndValue(end_height)
        self.panel_animation.finished.connect(
            lambda expanded=expanded: self.finish_panel_animation(expanded)
        )
        self.panel_animation.start()

    def finish_panel_animation(self, expanded):
        if expanded:
            self.panel.setMaximumHeight(16777215)
        else:
            self.panel.hide()
            self.panel.setMaximumHeight(16777215)

    def update_toggle_text(self):
        command = " ".join(self.command.split())
        label = f"{self.run_label} {command}"
        available_width = max(120, self.width() - 120)
        lines = elided_text_lines(label, self.toggle_button.font(), available_width, max_lines=2)
        line_height = QFontMetrics(self.toggle_button.font()).lineSpacing()
        self.toggle_button.setMaximumWidth(available_width)
        self.toggle_button.setMinimumHeight(line_height * len(lines) + 12)
        self.toggle_button.setMaximumHeight(line_height * 2 + 14)
        self.toggle_button.setText("\n".join(lines))
        self.arrow_button.set_rotation(90 if self.expanded else 0)

    def update_terminal_timer(self):
        self.timer_label.setText(format_elapsed_time_text(self.elapsed_seconds()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_toggle_text()

    def copy_command(self):
        from PyQt6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(self.command)
        show_widget_toast(self, "Command copied")

    def append_log(self, text):
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.log.setTextCursor(cursor)
        self.log.ensureCursorVisible()

    def finish(self, status):
        self.run_label = "Ran"
        self.ended_at = time.monotonic()
        self.elapsed_timer.stop()
        self.update_terminal_timer()
        self.status_label.setText(status)
        if not self.log.toPlainText().strip():
            self.append_log("(no output)\n")
        self.update_toggle_text()
        self.set_expanded(False)

    def elapsed_seconds(self):
        ended_at = self.ended_at or time.monotonic()
        return max(0.0, ended_at - self.started_at)


class AssistantCodeHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for code blocks."""

    PYTHON_TRIPLE_SINGLE_STATE = 1
    PYTHON_TRIPLE_DOUBLE_STATE = 2

    def __init__(self, document, language=""):
        super().__init__(document)
        self.language = (language or "").lower()
        self.command_format = QTextCharFormat()
        self.command_format.setForeground(QColor("#ff9f43"))
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#ffcf70"))
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#9ad67d"))
        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor("#c792ea"))
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#7a7a7a"))
        self.heading_format = QTextCharFormat()
        self.heading_format.setForeground(QColor("#ff9f43"))
        self.heading_format.setFontWeight(QFont.Weight.Bold)
        self.bold_format = QTextCharFormat()
        self.bold_format.setFontWeight(QFont.Weight.Bold)
        self.italic_format = QTextCharFormat()
        self.italic_format.setFontStyle(QFont.Style.StyleItalic)
        self.bold_italic_format = QTextCharFormat()
        self.bold_italic_format.setFontWeight(QFont.Weight.Bold)
        self.bold_italic_format.setFontStyle(QFont.Style.StyleItalic)
        self.code_format = QTextCharFormat()
        self.code_format.setFontFamily("JetBrains Mono, Consolas, monospace")
        self.link_format = QTextCharFormat()
        self.link_format.setForeground(QColor("#78a4c4"))

    def highlightBlock(self, text):
        if not self.language:
            return

        if self.language in ("python", "py", "python3"):
            self._highlight_python(text)
        elif self.language in ("bash", "sh", "shell", "zsh"):
            self._highlight_bash(text)
        elif self.language in ("json",):
            self._highlight_json(text)
        elif self.language in ("html", "xml"):
            self._highlight_html(text)
        else:
            self._highlight_generic(text)

    def _highlight_python(self, text):
        keywords = {
            "False", "None", "True", "and", "as", "assert", "async", "await",
            "break", "class", "continue", "def", "del", "elif", "else", "except",
            "finally", "for", "from", "global", "if", "import", "in", "is",
            "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
            "while", "with", "yield",
        }
        self._highlight_generic_with_keywords(text, keywords)

    def _highlight_bash(self, text):
        keywords = {
            "if", "then", "else", "elif", "fi", "case", "esac", "for", "while",
            "until", "do", "done", "in", "function", "select", "time", "coproc",
            "local", "declare", "typeset", "readonly", "return", "exit", "break",
            "continue", "shift", "trap", "eval", "exec", "source", "alias", "unalias",
            "set", "unset", "export", "readonly", "declare", "typeset", "local",
        }
        self._highlight_generic_with_keywords(text, keywords)

    def _highlight_json(self, text):
        import re
        patterns = [
            (r'"[^"\\]*(?:\\.[^"\\]*)*"', self.string_format),
            (r'-?\d+\.?\d*(?:[eE][+-]?\d+)?', self.number_format),
            (r'\b(true|false|null)\b', self.keyword_format),
        ]
        for pattern, fmt in patterns:
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)

    def _highlight_html(self, text):
        import re
        tag_pattern = r'</?[\w\-]+'
        attr_pattern = r'\s+[\w\-]+(?:\s*=\s*"[^"]*")?'
        for match in re.finditer(tag_pattern, text):
            self.setFormat(match.start(), match.end() - match.start(), self.keyword_format)
        for match in re.finditer(attr_pattern, text):
            self.setFormat(match.start(), match.end() - match.start(), self.command_format)

    def _highlight_generic_with_keywords(self, text, keywords):
        import re
        patterns = [
            (r'#[^\n]*', self.comment_format),
            (r'"[^"\\]*(?:\\.[^"\\]*)*"', self.string_format),
            (r"'''[^']*(?:''[^']*)*'''", self.string_format),
            (r'"""[^"]*(?:""[^"]*)*"""', self.string_format),
            (r'\b\d+\.?\d*\b', self.number_format),
        ]
        for pattern, fmt in patterns:
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)

        word_pattern = r'\b\w+\b'
        for match in re.finditer(word_pattern, text):
            word = match.group()
            if word in keywords:
                self.setFormat(match.start(), len(word), self.keyword_format)

    def _highlight_generic(self, text):
        import re
        patterns = [
            (r'#[^\n]*', self.comment_format),
            (r'"[^"\\]*(?:\\.[^"\\]*)*"', self.string_format),
            (r"'[^'\\]*(?:\\.[^'\\]*)*'", self.string_format),
            (r'\b\d+\.?\d*\b', self.number_format),
        ]
        for pattern, fmt in patterns:
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class AssistantCodeTextEdit(QPlainTextEdit):
    """Read-only code text edit with syntax highlighting."""

    def __init__(self, code="", language="", parent=None):
        super().__init__(parent)
        self.code = code
        self.language = language
        self.setReadOnly(True)
        self.setFont(QFont("JetBrains Mono, Consolas, monospace"))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.highlighter = AssistantCodeHighlighter(self.document(), language)
        self.setPlainText(code)


class AssistantCodeBlock(QFrame):
    """Block displaying code with header and optional copy button."""

    copy_clicked = pyqtSignal()

    def __init__(self, code, language="", show_copy=True, parent=None):
        super().__init__(parent)
        self.code = code
        self.language = language
        self.setObjectName("assistantCodeBlock")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(0)

        self.header_widget = StickyCodeHeader(language)
        header.addWidget(self.header_widget)

        if show_copy:
            self.copy_button = SvgActionButton(COPY_ICON_PATH)
            self.copy_button.setObjectName("messageIconButton")
            self.copy_button.setToolTip("Copy code")
            self.copy_button.clicked.connect(self.copy_clicked.emit)
            header.addWidget(self.copy_button)

        layout.addLayout(header)

        self.code_edit = AssistantCodeTextEdit(code, language)
        self.code_edit.setObjectName("codeContent")
        layout.addWidget(self.code_edit)

        self.copy_clicked.connect(self._copy_code)

    def _copy_code(self):
        from PyQt6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(self.code)


class StickyCodeHeader(QFrame):
    """Header bar for code blocks with language label and sticky positioning."""

    def __init__(self, language="", parent=None):
        super().__init__(parent)
        self.language = language
        self.setObjectName("stickyCodeHeader")
        self.setMinimumHeight(28)
        self.setMaximumHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        language_label = QLabel(self.language or "Code")
        language_label.setObjectName("codeBlockLanguage")
        layout.addWidget(language_label, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)