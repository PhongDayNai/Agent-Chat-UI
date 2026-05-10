"""Terminal widgets: command block, code highlighter."""

import re
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSizePolicy, QVBoxLayout

from constants import ARROW_RIGHT_ICON_PATH, COPY_ICON_PATH
from viewmodels.phase_utils import format_elapsed_time_text
from .button_widgets import RotatingSvgButton
from .input_widgets import show_widget_toast


class TerminalCommandBlock(QFrame):
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

        self.copy_command_button = RotatingSvgButton(COPY_ICON_PATH)
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
        if self.panel_animation is not None:
            self.panel_animation.stop()

        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
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
        from .button_widgets import elided_text_lines
        command = " ".join(self.command.split())
        label = f"{self.run_label} {command}"
        available_width = max(120, self.width() - 120)
        lines = elided_text_lines(label, self.toggle_button.font(), available_width, max_lines=2)
        line_height = self.toggle_button.fontMetrics().lineSpacing()
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
        self.function_format = QTextCharFormat()
        self.function_format.setForeground(QColor("#82aaff"))
        self.type_format = QTextCharFormat()
        self.type_format.setForeground(QColor("#7fdbca"))
        self.property_format = QTextCharFormat()
        self.property_format.setForeground(QColor("#f7b267"))
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#8c9298"))
        self.tag_format = QTextCharFormat()
        self.tag_format.setForeground(QColor("#ff7b72"))
        self.attr_format = QTextCharFormat()
        self.attr_format.setForeground(QColor("#d2a8ff"))

    def highlightBlock(self, text):
        stripped_language = self.language.strip()
        if stripped_language in {"bash", "sh", "shell"}:
            self.highlight_strings(text)
            match = re.match(r"^(\s*)([A-Za-z_][\w-]*)", text)
            if match:
                self.setFormat(match.start(2), match.end(2) - match.start(2), self.command_format)
            for match in re.finditer(r"(?<!\w)(--?[\w-]+)", text):
                self.setFormat(match.start(1), match.end(1) - match.start(1), self.type_format)
            for match in re.finditer(r"(\$[\w_]+|\$\{[^}]+\})", text):
                self.setFormat(match.start(1), match.end(1) - match.start(1), self.property_format)
            comment_index = text.find("#")
            if comment_index >= 0:
                self.setFormat(comment_index, len(text) - comment_index, self.comment_format)
        elif stripped_language in {"python", "py"}:
            self.highlight_python(text)
        elif stripped_language in {"javascript", "js", "typescript", "ts", "tsx", "jsx"}:
            self.highlight_regex(
                text,
                r"\b(const|let|var|function|return|if|else|for|while|class|import|from|export|async|await|new|try|catch|finally|throw|true|false|null|undefined)\b",
                self.keyword_format,
            )
            self.highlight_regex(text, r"\b([A-Za-z_$][\w$]*)\b(?=\s*\()", self.function_format)
            self.highlight_regex(text, r"\b\d+(?:\.\d+)?\b", self.number_format)
            self.highlight_strings(text)
            self.highlight_line_comment(text, "//")
        elif stripped_language == "json":
            self.highlight_regex(text, r'"([^"\\]|\\.)*"\s*(?=:)', self.property_format)
            self.highlight_regex(text, r":\s*(\"([^\"\\]|\\.)*\")", self.string_format, group=1)
            self.highlight_regex(text, r"\b(true|false|null)\b", self.keyword_format)
            self.highlight_regex(text, r"\b-?\d+(?:\.\d+)?\b", self.number_format)
        elif stripped_language in {"html", "xml"}:
            self.highlight_regex(text, r"</?[\w:-]+", self.tag_format)
            self.highlight_regex(text, r"\b[\w:-]+(?=\=)", self.attr_format)
            self.highlight_strings(text)
        elif stripped_language == "css":
            self.highlight_regex(text, r"[.#]?[-_a-zA-Z][\w-]*(?=\s*\{)", self.tag_format)
            self.highlight_regex(text, r"[-_a-zA-Z][\w-]*(?=\s*:)", self.property_format)
            self.highlight_regex(
                text,
                r"#[0-9a-fA-F]{3,8}\b|\b\d+(?:\.\d+)?(?:px|rem|em|%|vh|vw)?\b",
                self.number_format,
            )
            self.highlight_strings(text)
        else:
            self.highlight_strings(text)
            self.highlight_regex(text, r"\b\d+(?:\.\d+)?\b", self.number_format)

    def highlight_regex(self, text, pattern, fmt, group=0):
        for match in re.finditer(pattern, text):
            start = match.start(group)
            end = match.end(group)
            self.setFormat(start, end - start, fmt)

    def highlight_python(self, text):
        self.setCurrentBlockState(0)
        protected_ranges = self.highlight_python_strings_and_comments(text)
        self.highlight_python_regex(
            text,
            r"\b(def|class|for|while|if|elif|else|return|import|from|in|try|except|with|as|pass|break|continue|and|or|not|True|False|None|lambda|yield)\b",
            self.keyword_format,
            protected_ranges,
        )
        self.highlight_python_regex(
            text,
            r"\b(print|range|len|str|int|float|list|dict|set|tuple|enumerate|zip|open|sum|min|max)\b(?=\s*\()",
            self.function_format,
            protected_ranges,
        )
        self.highlight_python_regex(text, r"\b\d+(?:\.\d+)?\b", self.number_format, protected_ranges)

    def highlight_python_strings_and_comments(self, text):
        ranges = []
        index = 0
        previous_state = self.previousBlockState()
        if previous_state == self.PYTHON_TRIPLE_SINGLE_STATE:
            index = self.highlight_python_triple_continuation(text, "'''", previous_state, ranges)
        elif previous_state == self.PYTHON_TRIPLE_DOUBLE_STATE:
            index = self.highlight_python_triple_continuation(text, '"""', previous_state, ranges)

        while index < len(text):
            character = text[index]
            if character == "#":
                self.setFormat(index, len(text) - index, self.comment_format)
                ranges.append((index, len(text)))
                break
            if character in {"'", '"'}:
                quote = character
                if text.startswith(quote * 3, index):
                    end = self.highlight_python_triple_start(text, index, quote, ranges)
                    if self.currentBlockState() != 0:
                        break
                    index = end
                    continue
                end = self.find_python_string_end(text, index, quote)
                self.setFormat(index, end - index, self.string_format)
                ranges.append((index, end))
                index = end
                continue
            index += 1
        return ranges

    def highlight_python_triple_start(self, text, index, quote, ranges):
        delimiter = quote * 3
        state = self.PYTHON_TRIPLE_SINGLE_STATE if quote == "'" else self.PYTHON_TRIPLE_DOUBLE_STATE
        end_index = text.find(delimiter, index + 3)
        if end_index < 0:
            self.setFormat(index, len(text) - index, self.string_format)
            ranges.append((index, len(text)))
            self.setCurrentBlockState(state)
            return len(text)
        end = end_index + 3
        self.setFormat(index, end - index, self.string_format)
        ranges.append((index, end))
        return end

    def highlight_python_triple_continuation(self, text, quote, state, ranges):
        end_index = text.find(quote)
        if end_index < 0:
            self.setFormat(0, len(text), self.string_format)
            ranges.append((0, len(text)))
            self.setCurrentBlockState(state)
            return len(text)
        end = end_index + 3
        self.setFormat(0, end, self.string_format)
        ranges.append((0, end))
        self.setCurrentBlockState(0)
        return end

    def find_python_string_end(self, text, start, quote):
        index = start + 1
        escaped = False
        while index < len(text):
            character = text[index]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                return index + 1
            index += 1
        return len(text)

    def highlight_python_regex(self, text, pattern, fmt, protected_ranges):
        for match in re.finditer(pattern, text):
            if self.range_overlaps(match.start(), match.end(), protected_ranges):
                continue
            self.setFormat(match.start(), match.end() - match.start(), fmt)

    def range_overlaps(self, start, end, ranges):
        return any(start < range_end and end > range_start for range_start, range_end in ranges)

    def highlight_strings(self, text):
        self.highlight_regex(text, r'"([^"\\]|\\.)*"', self.string_format)
        self.highlight_regex(text, r"'([^'\\]|\\.)*'", self.string_format)

    def highlight_line_comment(self, text, marker):
        comment_index = text.find(marker)
        if comment_index >= 0:
            self.setFormat(comment_index, len(text) - comment_index, self.comment_format)