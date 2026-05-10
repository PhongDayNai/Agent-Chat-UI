"""Code widgets: code block, sticky header."""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QSizePolicy, QVBoxLayout

from constants import COPY_ICON_PATH, CODE_STICKY_CONTENT_PADDING, CODE_STICKY_HEADER_HEIGHT
from .button_widgets import SvgActionButton
from .input_widgets import show_widget_toast
from .terminal_widgets import AssistantCodeHighlighter


class AssistantCodeTextEdit(QPlainTextEdit):
    def wheelEvent(self, event):
        event.ignore()


class AssistantCodeBlock(QFrame):
    def __init__(self, code, language="", content_padding=CODE_STICKY_CONTENT_PADDING, parent=None):
        super().__init__(parent)
        self.code = code.rstrip("\n")
        self.language = self.display_language(language)
        self.content_padding = max(0, int(content_padding))
        self.setObjectName("assistantCodeBlock")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        icon = QLabel("</>")
        icon.setObjectName("assistantCodeIcon")
        header.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)

        self.language_label = QLabel(self.language)
        self.language_label.setObjectName("assistantCodeLanguage")
        header.addWidget(self.language_label, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addStretch()

        copy_button = SvgActionButton(COPY_ICON_PATH)
        copy_button.setObjectName("assistantCodeCopyButton")
        copy_button.setToolTip("Copy code")
        copy_button.clicked.connect(self.copy_code)
        header.addWidget(copy_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)
        layout.addSpacing(self.content_padding)

        self.editor = AssistantCodeTextEdit()
        self.editor.setObjectName("assistantCodeText")
        self.editor.setReadOnly(True)
        self.editor.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.editor.setPlainText(self.code)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editor.document().documentLayout().documentSizeChanged.connect(self.update_editor_height)
        self.highlighter = AssistantCodeHighlighter(self.editor.document(), language)
        layout.addWidget(self.editor)
        self.update_editor_height()

    def update_editor_height(self, *_args):
        self.editor.document().setTextWidth(max(0, self.editor.viewport().width()))
        doc_layout = self.editor.document().documentLayout()
        doc_height = 0
        block = self.editor.document().firstBlock()
        while block.isValid():
            rect = doc_layout.blockBoundingRect(block)
            doc_height += max(self.editor.fontMetrics().lineSpacing(), int(rect.height()))
            block = block.next()
        frame = self.editor.frameWidth() * 2
        target = max(24, doc_height + frame + 12)
        self.editor.setMinimumHeight(target)
        self.editor.setMaximumHeight(target)
        self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.reset_editor_scroll()
        QTimer.singleShot(0, self.reset_editor_scroll)
        self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_editor_height()

    def reset_editor_scroll(self):
        self.editor.verticalScrollBar().setValue(0)
        self.editor.horizontalScrollBar().setValue(0)

    def copy_code(self):
        QGuiApplication.clipboard().setText(self.code)
        show_widget_toast(self, "Code copied")

    def update_code(self, code, language=""):
        code = code.rstrip("\n")
        display_language = self.display_language(language)
        if self.language != display_language:
            self.language = display_language
            self.language_label.setText(self.language)
            self.highlighter.language = (language or "").lower()
            self.highlighter.rehighlight()
        if self.code == code:
            return
        self.code = code
        self.editor.setPlainText(self.code)
        self.update_editor_height()

    def display_language(self, language):
        normalized = (language or "").strip()
        if not normalized:
            return "Code"
        aliases = {
            "bash": "Bash",
            "sh": "Bash",
            "shell": "Bash",
            "python": "Python",
            "py": "Python",
            "javascript": "JavaScript",
            "js": "JavaScript",
            "typescript": "TypeScript",
            "ts": "TypeScript",
            "json": "JSON",
            "html": "HTML",
            "css": "CSS",
            "sql": "SQL",
        }
        return aliases.get(normalized.lower(), normalized[:1].upper() + normalized[1:])


class StickyCodeHeader(QFrame):
    def __init__(self, parent=None, header_height=CODE_STICKY_HEADER_HEIGHT):
        super().__init__(parent)
        self.code_block = None
        self.setObjectName("stickyCodeHeader")
        self.set_header_height(header_height)
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(8)

        icon = QLabel("</>")
        icon.setObjectName("assistantCodeIcon")
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)

        self.language_label = QLabel("Code")
        self.language_label.setObjectName("assistantCodeLanguage")
        layout.addWidget(self.language_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch()

        self.copy_button = SvgActionButton(COPY_ICON_PATH)
        self.copy_button.setObjectName("assistantCodeCopyButton")
        self.copy_button.setToolTip("Copy code")
        self.copy_button.clicked.connect(self.copy_code)
        layout.addWidget(self.copy_button, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_code_block(self, code_block):
        self.code_block = code_block
        self.language_label.setText(code_block.language if code_block is not None else "Code")

    def set_header_height(self, header_height):
        self.setFixedHeight(max(28, int(header_height)))

    def copy_code(self):
        if self.code_block is not None:
            QGuiApplication.clipboard().setText(self.code_block.code)
            show_widget_toast(self, "Code copied")

    def wheelEvent(self, event):
        event.ignore()