"""Widget components extracted from widgets.py for better organization."""

from widget_components.button_widgets import (
    PinIconButton,
    RotatingSvgButton,
    SvgActionButton,
    ThinkingTitleLabel,
    ThinkingPhaseHeader,
    elided_text_lines,
    format_elapsed_time_text,
)
from widget_components.input_widgets import (
    DeletableHistoryDelegate,
    DeletableHistoryComboBox,
    NoWheelSpinBox,
    NoWheelDoubleSpinBox,
    AutoResizingTextEdit,
    AutoHeightTextBrowser,
)
from widget_components.attachment_widgets import (
    ImagePreviewButton,
    AttachmentChip,
)
from widget_components.dialog_widgets import (
    ImageGalleryDialog,
    FilePreviewDialog,
)
from widget_components.terminal_widgets import (
    TerminalCommandBlock,
    AssistantCodeHighlighter,
    AssistantCodeTextEdit,
    AssistantCodeBlock,
    StickyCodeHeader,
    show_widget_toast,
)

__all__ = [
    # Button/icon widgets
    "PinIconButton",
    "RotatingSvgButton",
    "SvgActionButton",
    "ThinkingTitleLabel",
    "ThinkingPhaseHeader",
    # Input widgets
    "DeletableHistoryDelegate",
    "DeletableHistoryComboBox",
    "NoWheelSpinBox",
    "NoWheelDoubleSpinBox",
    "AutoResizingTextEdit",
    "AutoHeightTextBrowser",
    # Attachment widgets
    "ImagePreviewButton",
    "AttachmentChip",
    "ImageGalleryDialog",
    "FilePreviewDialog",
    # Terminal/code widgets
    "TerminalCommandBlock",
    "AssistantCodeHighlighter",
    "AssistantCodeTextEdit",
    "AssistantCodeBlock",
    "StickyCodeHeader",
    # Utility functions
    "elided_text_lines",
    "format_elapsed_time_text",
    "show_widget_toast",
]