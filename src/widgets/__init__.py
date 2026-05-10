"""Re-export all widgets for backward compatibility."""

from .button_widgets import (
    ThinkingPhaseHeader,
    ThinkingTitleLabel,
    RotatingSvgButton,
    SvgActionButton,
    PinIconButton,
    elided_text_lines,
)
from .input_widgets import (
    AutoHeightTextBrowser,
    AutoResizingTextEdit,
    DeletableHistoryComboBox,
    DeletableHistoryDelegate,
    NoWheelDoubleSpinBox,
    NoWheelSpinBox,
    link_hover_tooltip,
    show_widget_toast,
)
from .attachment_widgets import (
    AttachmentChip,
    ImagePreviewButton,
)
from .code_widgets import (
    AssistantCodeBlock,
    AssistantCodeTextEdit,
    StickyCodeHeader,
)
from .terminal_widgets import (
    AssistantCodeHighlighter,
    TerminalCommandBlock,
)
from .dialog_widgets import (
    FilePreviewDialog,
    ImageGalleryDialog,
)
from .message_card import (
    ContentPhaseHeader,
    MessageCard,
)

__all__ = [
    "elided_text_lines",
    "ThinkingPhaseHeader",
    "ThinkingTitleLabel",
    "RotatingSvgButton",
    "SvgActionButton",
    "PinIconButton",
    "AutoHeightTextBrowser",
    "AutoResizingTextEdit",
    "DeletableHistoryComboBox",
    "DeletableHistoryDelegate",
    "NoWheelDoubleSpinBox",
    "NoWheelSpinBox",
    "link_hover_tooltip",
    "show_widget_toast",
    "AttachmentChip",
    "ImagePreviewButton",
    "AssistantCodeBlock",
    "AssistantCodeTextEdit",
    "StickyCodeHeader",
    "AssistantCodeHighlighter",
    "TerminalCommandBlock",
    "FilePreviewDialog",
    "ImageGalleryDialog",
    "ContentPhaseHeader",
    "MessageCard",
]