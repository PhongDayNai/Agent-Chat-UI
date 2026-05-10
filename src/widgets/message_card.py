"""Message card widget and content phase header."""

import re
import time
from datetime import datetime

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from constants import CODE_STICKY_CONTENT_PADDING, COPY_ICON_PATH, RETRY_ICON_PATH
from markdown_utils import (
    html_text_with_links,
    normalize_terminal_fences,
    prepare_assistant_html,
    render_inert_thinking_terminal_tags,
    render_latexish_text,
    replace_terminal_command_tags,
    split_markdown_code_segments,
)
from styles import MARKDOWN_STYLESHEET, THINKING_MARKDOWN_STYLESHEET
from viewmodels.phase_utils import format_elapsed_time_text
from viewmodels.message_card_state import MessageCardState

from .button_widgets import SvgActionButton, ThinkingPhaseHeader
from .input_widgets import AutoHeightTextBrowser, show_widget_toast
from .code_widgets import AssistantCodeBlock


def link_hover_tooltip(anchor):
    from html import escape
    if anchor.startswith("copy-code:"):
        title = "Copy code"
        lines = ("Click to copy this code snippet.",)
    else:
        title = "Link"
        lines = ("Click to copy.", "Ctrl+click to open in browser.")
    body = "<br>".join(escape(line, quote=False) for line in lines)
    return (
        '<html><body style="margin:0;">'
        '<div style="width:210px; white-space:normal;">'
        f'<div style="font-weight:600; color:#f4f5f6; margin-bottom:4px;">{title}</div>'
        f'<div style="color:#c7cacf; line-height:1.35;">{body}</div>'
        "</div></body></html>"
    )


class ContentPhaseHeader(QWidget):
    pass


class MessageCard(QFrame):
    retry_requested = pyqtSignal(str)
    image_preview_requested = pyqtSignal(list, int)
    file_preview_requested = pyqtSignal(str)

    def __init__(
        self,
        role,
        text="",
        timestamp=None,
        retry_text=None,
        attachments=None,
        render_debounce_enabled=True,
        render_debounce_interval_ms=45,
        code_sticky_content_padding=CODE_STICKY_CONTENT_PADDING,
        parent=None,
    ):
        super().__init__(parent)
        self.role = role
        self.raw_text = text
        self.thinking_text = ""
        self.retry_text = retry_text
        self.loading_step = 0
        self.attachments = attachments or []
        self.body_layout = None
        self.terminal_blocks_layout = None
        self.terminal_blocks = []
        self.current_terminal_block = None
        self.pending_render_text = None
        self.render_timer = None
        self.loading_active = False
        self.timeline_phases = []
        self.active_stream_phase = None
        self.final_answer_pending = False
        self.final_answer_phase = None
        self.work_summary_phase = None
        self.work_progress_phase = None
        self.loading_placeholder = None

        self.code_sticky_content_padding = max(0, int(code_sticky_content_padding))
        self.render_debounce_enabled = bool(render_debounce_enabled)
        self.render_debounce_interval_ms = max(0, int(render_debounce_interval_ms))

        self.setObjectName("messageCard")
        self.setProperty("user", role == "user")
        self.setProperty("system", role == "system")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMaximumHeight(16777215)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(18, 16, 18, 16)
        outer_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        self.role_label = QLabel(self.role_title())
        self.role_label.setObjectName("roleLabel")
        header_layout.addWidget(self.role_label)

        self.time_label = QLabel(timestamp or self.now_text())
        self.time_label.setObjectName("timeLabel")
        header_layout.addWidget(self.time_label)
        header_layout.addStretch()

        self.copy_button = None
        self.retry_button = None
        if role in {"assistant", "user"}:
            self.copy_button = SvgActionButton(COPY_ICON_PATH)
            self.copy_button.setObjectName("messageIconButton")
            self.copy_button.setToolTip("Copy")
            self.copy_button.clicked.connect(self.copy_text)
            header_layout.addWidget(self.copy_button)

        if role == "assistant":
            self.retry_button = SvgActionButton(RETRY_ICON_PATH)
            self.retry_button.setObjectName("messageIconButton")
            self.retry_button.setToolTip("Retry")
            self.retry_button.clicked.connect(self.emit_retry)
            header_layout.addWidget(self.retry_button)

        outer_layout.addLayout(header_layout)

        if role == "assistant":
            self.body = QWidget()
            self.body_layout = QVBoxLayout(self.body)
            self.body_layout.setContentsMargins(0, 0, 0, 0)
            self.body_layout.setSpacing(10)
            outer_layout.addWidget(self.body)
            self.terminal_blocks_layout = self.body_layout

            self.loading_timer = QTimer(self)
            self.loading_timer.setInterval(320)
            self.loading_timer.timeout.connect(self.advance_loading_frame)
            self.work_progress_timer = QTimer(self)
            self.work_progress_timer.setInterval(250)
            self.work_progress_timer.timeout.connect(self.update_work_progress_phase)
            self.render_timer = QTimer(self)
            self.render_timer.setSingleShot(True)
            self.render_timer.setInterval(self.render_debounce_interval_ms)
            self.render_timer.timeout.connect(self.flush_pending_render)

            self._work_state = MessageCardState()
            self._work_state.progress_updated.connect(self._on_work_progress_updated)
            self._work_state.phase_completed.connect(self._on_work_phase_completed)
        else:
            self.body = AutoHeightTextBrowser()
            self.body.document().setDefaultStyleSheet(MARKDOWN_STYLESHEET)
            self.body.setMaximumHeight(16777215)
            outer_layout.addWidget(self.body)

        self.attachments_widget = None
        self.attachments_layout = None
        if role == "user":
            self.attachments_widget = QWidget()
            self.attachments_layout = QHBoxLayout(self.attachments_widget)
            self.attachments_layout.setContentsMargins(0, 2, 0, 0)
            self.attachments_layout.setSpacing(10)
            self.attachments_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.attachments_widget.hide()
            outer_layout.addWidget(self.attachments_widget)
        self.update_text(text)
        self.refresh_attachments()

    def now_text(self):
        return datetime.now().strftime("%H:%M")

    def role_title(self):
        return {
            "user": "You",
            "assistant": "Assistant",
            "system": "Status",
        }.get(self.role, self.role.title())

    def update_text(self, text):
        self.raw_text = text
        if self.role == "assistant":
            self.pending_render_text = None
            if self.render_timer is not None and self.render_timer.isActive():
                self.render_timer.stop()
            self.render_assistant_message_text(text)
        else:
            self.body.setHtml(html_text_with_links(text))
            self.body.update_height()

    def render_assistant_message_text(self, text):
        self.reset_timeline_from_text(text)
        self.notify_assistant_content_changed()

    def notify_assistant_content_changed(self):
        window = self.window()
        if hasattr(window, "handle_assistant_reply_content_changed"):
            QTimer.singleShot(0, lambda: window.handle_assistant_reply_content_changed(self))

    def flush_pending_render(self):
        if self.role != "assistant" or self.pending_render_text is None:
            return
        text = self.pending_render_text
        self.pending_render_text = None
        phase = self.active_stream_phase
        if phase is not None and phase.get("type") == "content":
            self.render_content_phase(phase)
            self.refresh_loading_placeholder()
            self.notify_assistant_content_changed()
            return
        self.render_assistant_message_text(text)

    def reset_timeline_from_text(self, text):
        if self.body_layout is None:
            return
        self.cleanup_timeline_phases()
        self.clear_layout(self.body_layout)
        self.timeline_phases = []
        self.terminal_blocks = []
        self.current_terminal_block = None
        self.active_stream_phase = None
        self.final_answer_pending = False
        self.final_answer_phase = None
        self.work_summary_phase = None
        self.loading_placeholder = None

        text = text or ""
        if text:
            phase = self.create_content_phase()
            phase["text"] = text
            self.render_content_phase(phase)
            if not self.phase_has_visible_content(phase):
                self.remove_phase(phase)
            else:
                self.active_stream_phase = phase
        self.refresh_loading_placeholder()
        self.body.setVisible(self.body_layout.count() > 0)

    def create_content_phase(self, final=False):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        widget.setVisible(False)
        phase = {"type": "content", "text": "", "widget": widget, "layout": layout, "final": bool(final), "started_at": time.monotonic()}
        self.timeline_phases.append(phase)
        self.body_layout.addWidget(widget)
        return phase

    def create_thinking_phase(self, expanded=False):
        from .input_widgets import AutoHeightTextBrowser
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = ThinkingPhaseHeader()
        layout.addWidget(header)

        body = AutoHeightTextBrowser()
        body.document().setDefaultStyleSheet(THINKING_MARKDOWN_STYLESHEET)
        body.setMaximumHeight(16777215)

        body_container = QWidget()
        body_container_layout = QVBoxLayout(body_container)
        body_container_layout.setContentsMargins(0, 0, 0, 0)
        body_container_layout.setSpacing(0)
        body_container_layout.addWidget(body)
        body_container.hide()
        body_container.setMaximumHeight(0)
        layout.addWidget(body_container)

        phase = {
            "type": "thinking",
            "text": "",
            "widget": widget,
            "header": header,
            "body": body,
            "body_container": body_container,
            "expanded": bool(expanded),
            "active": True,
            "started_at": time.monotonic(),
            "ended_at": None,
            "body_animation": None,
            "timer": None,
        }
        timer = QTimer(self)
        timer.setInterval(250)
        timer.timeout.connect(lambda phase=phase: self.update_thinking_phase_timer(phase))
        phase["timer"] = timer
        timer.start()
        header.toggled.connect(lambda phase=phase: self.toggle_thinking_phase(phase))
        header.set_expanded(False)
        header.set_active(True)
        self.update_thinking_phase_timer(phase)
        self.timeline_phases.append(phase)
        self.body_layout.addWidget(widget)
        return phase

    def create_terminal_phase(self, block):
        phase = {"type": "terminal", "widget": block}
        self.timeline_phases.append(phase)
        self.body_layout.addWidget(block)
        block.show()
        return phase

    def remove_phase(self, phase):
        self.cleanup_timeline_phase(phase)
        widget = phase.get("widget")
        if widget is not None:
            self.remove_widget_from_layout(self.body_layout, widget)
            widget.deleteLater()
        if phase in self.timeline_phases:
            self.timeline_phases.remove(phase)
        if self.active_stream_phase is phase:
            self.active_stream_phase = None

    def phase_has_visible_content(self, phase):
        if phase.get("type") == "terminal":
            return True
        if phase.get("type") == "work_summary":
            return bool(phase.get("children"))
        if phase.get("type") == "content":
            return bool(self.assistant_segments(phase.get("text", "")))
        return False

    def has_answer_or_tool_phase(self):
        return any(self.phase_has_visible_content(phase) for phase in self.timeline_phases)

    def render_content_phase(self, phase):
        layout = phase.get("layout")
        if layout is None:
            return
        self.render_assistant_content(layout, phase.get("text", ""))
        phase["widget"].setVisible(layout.count() > 0)

    def render_thinking_phase(self, phase):
        has_text = bool(phase.get("text", "").strip())
        widget = phase.get("widget")
        body = phase.get("body")
        body_container = phase.get("body_container")
        header = phase.get("header")
        if widget is None or body is None or body_container is None or header is None:
            return
        widget.setVisible(has_text)
        if not has_text:
            return

        body.setHtml(prepare_assistant_html(
            render_inert_thinking_terminal_tags(phase["text"])
        ))
        body.update_height()
        header.set_title(self.thinking_phase_title(phase.get("text", "")))
        header.set_active(bool(phase.get("active")))
        self.update_thinking_phase_timer(phase)
        if phase.get("expanded"):
            body_container.show()
            body_container.setMaximumHeight(16777215)
        else:
            body_container.hide()
            body_container.setMaximumHeight(0)
        header.set_expanded(bool(phase.get("expanded")))

    def toggle_thinking_phase(self, phase):
        if phase.get("type") != "thinking":
            return
        self.set_thinking_phase_expanded(phase, not bool(phase.get("expanded")))

    def set_thinking_phase_expanded(self, phase, expanded):
        self.set_collapsible_phase_expanded(phase, expanded)

    def set_collapsible_phase_expanded(self, phase, expanded):
        from PyQt6.QtCore import QEasingCurve, QPropertyAnimation
        body = phase.get("body_container")
        header = phase.get("header")
        if body is None or header is None:
            return
        expanded = bool(expanded)
        if phase.get("expanded") == expanded:
            return

        if phase.get("body_animation") is not None:
            phase["body_animation"].stop()
            phase["body_animation"] = None

        phase["expanded"] = expanded
        header.set_expanded(expanded)
        if expanded:
            body.show()
            body.setMaximumHeight(0)
            start_height = 0
            end_height = max(1, body.sizeHint().height())
        else:
            start_height = max(1, body.height())
            end_height = 0

        animation = QPropertyAnimation(body, b"maximumHeight", self)
        animation.setDuration(180)
        animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        animation.setStartValue(start_height)
        animation.setEndValue(end_height)
        animation.finished.connect(
            lambda phase=phase, expanded=expanded: self.finish_thinking_body_animation(phase, expanded)
        )
        phase["body_animation"] = animation
        animation.start()

    def finish_thinking_body_animation(self, phase, expanded):
        body = phase.get("body_container")
        if body is None:
            return
        phase["body_animation"] = None
        if expanded:
            body.setMaximumHeight(16777215)
            body.show()
        else:
            body.hide()
            body.setMaximumHeight(0)
        self.body.setVisible(self.body_layout.count() > 0)

    def thinking_phase_title(self, text):
        cleaned = re.sub(r"</?terminal_command[^>]*>", " ", text or "", flags=re.IGNORECASE)
        cleaned = re.sub(r"`{1,3}", " ", cleaned)
        for line in cleaned.splitlines():
            line = re.sub(r"^[\s#>*-]+", "", line).strip()
            line = re.sub(r"\s+", " ", line)
            if len(line) >= 3:
                title = re.split(r"(?<=[.!?])\s+", line, maxsplit=1)[0].strip()
                return title or "Analyzing request"
        return "Analyzing request"

    def update_thinking_phase_timer(self, phase):
        header = phase.get("header")
        started_at = phase.get("started_at")
        if header is None or started_at is None:
            return
        ended_at = phase.get("ended_at") or time.monotonic()
        header.set_elapsed_text(self.format_elapsed_time(ended_at - started_at))

    def format_elapsed_time(self, elapsed):
        return format_elapsed_time_text(elapsed)

    def finish_thinking_phase(self, phase):
        if phase.get("type") != "thinking" or not phase.get("active"):
            return
        phase["active"] = False
        phase["ended_at"] = time.monotonic()
        timer = phase.get("timer")
        if timer is not None:
            timer.stop()
        header = phase.get("header")
        if header is not None:
            header.set_active(False)
        self.update_thinking_phase_timer(phase)

    def finish_active_thinking_phase(self):
        phase = self.active_stream_phase
        if phase is not None and phase.get("type") == "thinking":
            self.finish_thinking_phase(phase)

    def finish_streaming(self):
        self.finish_active_thinking_phase()
        if self.work_progress_phase is not None:
            self.work_progress_timer.stop()
            self._work_state.complete_progress()
            self.work_progress_phase["header"].set_title(self._work_state.title_text)
            self.work_progress_phase["header"].set_active(False)
            self.remove_phase_widget(self.work_progress_phase)
            self.work_progress_phase = None
        if self.work_summary_phase is None and self.timeline_phases:
            final_phase = self.timeline_phases[-1]
            if final_phase.get("type") == "content" and self.phase_has_work_content(final_phase):
                self.ensure_work_summary_for_final(final_phase)

    def mark_final_answer_started(self):
        if self.role != "assistant":
            return
        if self.render_timer is not None and self.render_timer.isActive():
            self.flush_pending_render()
        self.finish_active_thinking_phase()
        self.final_answer_pending = True
        self.active_stream_phase = None
        self.refresh_loading_placeholder()
        self.notify_assistant_content_changed()

    def cancel_pending_final_answer(self):
        self.final_answer_pending = False
        if self.final_answer_phase is not None:
            self.final_answer_phase["final"] = False
        self.unwrap_work_summary_phase()
        self.final_answer_phase = None

    def confirm_final_answer(self):
        if self.role != "assistant":
            return
        if self.render_timer is not None and self.render_timer.isActive():
            self.flush_pending_render()
        final_phase = self.final_answer_phase
        if final_phase is None or final_phase not in self.timeline_phases:
            self.final_answer_pending = False
            return
        self.ensure_work_summary_for_final(final_phase)
        self.final_answer_pending = False
        self.refresh_loading_placeholder()
        self.notify_assistant_content_changed()

    def ensure_work_progress_phase(self):
        if self.work_progress_phase is not None:
            return
        if self.work_summary_phase is not None:
            return
        self._work_state.start_progress()
        header = ThinkingPhaseHeader()
        header.set_title(self._work_state.title_text)
        header.set_active(True)
        header.set_elapsed_text("")
        header.set_expanded(False)

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        widget.setMinimumHeight(60)
        widget.setVisible(True)
        widget.show()

        phase = {
            "type": "work_progress",
            "widget": widget,
            "header": header,
            "children": [],
            "expanded": False,
        }

        self.body_layout.addWidget(widget)
        self.timeline_phases.insert(0, phase)
        self.work_progress_phase = phase
        self.work_progress_timer.start()
        self.body.setVisible(True)
        self.notify_assistant_content_changed()
        return phase

    def update_work_progress_phase(self):
        self._work_state.update_progress()

    def _on_work_progress_updated(self, elapsed):
        """Slot for work_state.progress_updated signal."""
        if self.work_progress_phase is not None:
            self.work_progress_phase["header"].set_title(
                self._work_state.title_text
            )

    def _on_work_phase_completed(self, elapsed):
        """Slot for work_state.phase_completed signal."""
        if self.work_progress_phase is not None:
            self.work_progress_phase["header"].set_title(
                self._work_state.title_text
            )

    def confirm_work_progress_done(self):
        if self.work_progress_phase is None:
            return
        self.work_progress_timer.stop()
        self._work_state.complete_progress()
        self.work_progress_phase["header"].set_title(self._work_state.title_text)
        self.work_progress_phase["header"].set_active(False)
        self.work_progress_phase = None

    def ensure_work_summary_for_final(self, final_phase):
        if self.work_summary_phase is not None:
            return
        if final_phase is None or final_phase not in self.timeline_phases:
            return

        final_index = self.timeline_phases.index(final_phase)
        previous_phases = [
            phase for phase in self.timeline_phases[:final_index]
            if phase.get("type") in {"content", "thinking", "terminal"}
        ]
        work_phases = [phase for phase in previous_phases if self.phase_has_work_content(phase)]
        for phase in previous_phases:
            if phase not in work_phases:
                self.remove_phase_widget(phase)
                if phase in self.timeline_phases:
                    self.timeline_phases.remove(phase)
        if self.work_progress_phase is not None:
            self.work_progress_timer.stop()
            self._work_state.complete_progress()
            self.remove_phase_widget(self.work_progress_phase)
            self.work_progress_phase = None
        if work_phases:
            summary_phase = self.create_work_summary_phase(work_phases)
            tail_phases = [phase for phase in self.timeline_phases if phase not in previous_phases]
            self.timeline_phases = [summary_phase, *tail_phases]
            self.work_summary_phase = summary_phase

    def unwrap_work_summary_phase(self):
        summary_phase = self.work_summary_phase
        if summary_phase is None:
            return
        summary_widget = summary_phase.get("widget")
        body_container = summary_phase.get("body_container")
        body_layout = body_container.layout() if body_container is not None else None
        children = list(summary_phase.get("children", []))
        insert_index = self.layout_widget_index(self.body_layout, summary_widget)
        if insert_index < 0:
            insert_index = 0

        animation = summary_phase.get("body_animation")
        if animation is not None:
            animation.stop()
        header = summary_phase.get("header")
        if header is not None:
            header.set_active(False)

        for child_phase in children:
            current_widget = child_phase.get("widget")
            if body_layout is not None and current_widget is not None:
                self.remove_widget_from_layout(body_layout, current_widget)
            child_widget = self.restore_work_child_phase(child_phase)
            if child_widget is not None:
                self.body_layout.insertWidget(insert_index, child_widget)
                child_widget.show()
                insert_index += 1

        if summary_widget is not None and self.remove_widget_from_layout(self.body_layout, summary_widget):
            summary_widget.deleteLater()
        if summary_phase in self.timeline_phases:
            summary_index = self.timeline_phases.index(summary_phase)
            self.timeline_phases[summary_index:summary_index + 1] = children
        self.work_summary_phase = None
        self.refresh_loading_placeholder()
        self.notify_assistant_content_changed()

    def restore_work_child_phase(self, phase):
        if not phase.get("wrapped_for_work"):
            return phase.get("widget")

        wrapper = phase.get("widget")
        content_widget = phase.get("content_widget")
        body_container = phase.get("body_container")
        body_layout = body_container.layout() if body_container is not None else None
        if body_layout is not None and content_widget is not None:
            self.remove_widget_from_layout(body_layout, content_widget)
        if wrapper is not None:
            wrapper.deleteLater()

        phase["widget"] = content_widget
        for key in ("content_widget", "header", "body_container", "expanded", "body_animation", "wrapped_for_work"):
            phase.pop(key, None)
        if content_widget is not None:
            content_widget.show()
        return content_widget

    def remove_phase_widget(self, phase):
        self.cleanup_timeline_phase(phase)
        widget = phase.get("widget")
        if widget is not None and self.remove_widget_from_layout(self.body_layout, widget):
            widget.deleteLater()

    def create_work_summary_phase(self, child_phases):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        total_elapsed = sum(self.phase_elapsed_seconds(phase) for phase in child_phases)
        elapsed_formatted = format_elapsed_time_text(total_elapsed)
        header = ThinkingPhaseHeader()
        header.set_title(f"Worked for {elapsed_formatted}")
        header.set_active(False)
        header.set_elapsed_text("")
        layout.addWidget(header)

        body_container = QWidget()
        body_layout = QVBoxLayout(body_container)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        body_container.hide()
        body_container.setMaximumHeight(0)
        layout.addWidget(body_container)

        phase = {
            "type": "work_summary",
            "widget": widget,
            "header": header,
            "body_container": body_container,
            "children": child_phases,
            "expanded": False,
            "body_animation": None,
        }
        header.set_expanded(False)
        header.toggled.connect(lambda phase=phase: self.toggle_collapsible_phase(phase))

        insert_index = self.layout_widget_index(self.body_layout, child_phases[0].get("widget"))
        if insert_index < 0:
            self.body_layout.addWidget(widget)
        else:
            self.body_layout.insertWidget(insert_index, widget)

        for child_phase in child_phases:
            child_widget = self.prepare_work_child_phase(child_phase)
            if child_widget is None:
                continue
            self.remove_widget_from_layout(self.body_layout, child_widget)
            body_layout.addWidget(child_widget)
            child_widget.show()

        return phase

    def prepare_work_child_phase(self, phase):
        phase_type = phase.get("type")
        if phase_type == "thinking":
            self.set_thinking_phase_expanded(phase, False)
            return phase.get("widget")
        if phase_type == "terminal":
            block = phase.get("widget")
            if hasattr(block, "set_expanded"):
                block.set_expanded(False)
            return block
        if phase_type == "content":
            return self.wrap_content_phase_for_work(phase)
        return phase.get("widget")

    def wrap_content_phase_for_work(self, phase):
        content_widget = phase.get("widget")
        if content_widget is None:
            return None

        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(8)

        header = ThinkingPhaseHeader()
        header.set_title(self.content_phase_title(phase.get("text", "")))
        header.set_active(False)
        header.set_elapsed_text("")
        wrapper_layout.addWidget(header)

        body_container = QWidget()
        body_layout = QVBoxLayout(body_container)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        self.remove_widget_from_layout(self.body_layout, content_widget)
        body_layout.addWidget(content_widget)
        body_container.hide()
        body_container.setMaximumHeight(0)
        wrapper_layout.addWidget(body_container)

        phase.update({
            "widget": wrapper,
            "content_widget": content_widget,
            "header": header,
            "body_container": body_container,
            "expanded": False,
            "body_animation": None,
            "wrapped_for_work": True,
        })
        header.set_expanded(False)
        header.toggled.connect(lambda phase=phase: self.toggle_collapsible_phase(phase))
        return wrapper

    def toggle_collapsible_phase(self, phase):
        self.set_collapsible_phase_expanded(phase, not bool(phase.get("expanded")))

    def content_phase_title(self, text):
        text = normalize_terminal_fences(replace_terminal_command_tags(text or ""))
        for line in text.splitlines():
            title = re.sub(r"^[\s#>*-]+", "", line).strip()
            title = re.sub(r"\s+", " ", title)
            if title:
                return title[:96] + ("..." if len(title) > 96 else "")
        return "Progress note"

    def phase_has_work_content(self, phase):
        phase_type = phase.get("type")
        if phase_type == "terminal":
            return True
        if phase_type == "thinking":
            return bool(phase.get("text", "").strip())
        if phase_type == "content":
            return self.phase_has_visible_content(phase)
        return False

    def phase_elapsed_seconds(self, phase):
        phase_type = phase.get("type")
        if phase_type == "thinking":
            started_at = phase.get("started_at")
            if started_at is None:
                return 0.0
            return max(0.0, (phase.get("ended_at") or time.monotonic()) - started_at)
        if phase_type == "terminal":
            block = phase.get("widget")
            if hasattr(block, "elapsed_seconds"):
                return block.elapsed_seconds()
        if phase_type == "content":
            started_at = phase.get("started_at")
            if started_at is None:
                return 0.0
            return max(0.0, time.monotonic() - started_at)
        return 0.0

    def layout_widget_index(self, layout, target):
        if layout is None or target is None:
            return -1
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is not None and item.widget() is target:
                return index
        return -1

    def set_active_thinking_auto_expanded(self, expanded):
        if self.role != "assistant":
            return
        for phase in self.timeline_phases:
            if phase.get("type") == "thinking" and phase.get("active"):
                self.set_thinking_phase_expanded(phase, expanded)

    def cleanup_timeline_phase(self, phase):
        if phase.get("type") == "work_summary":
            for child_phase in phase.get("children", []):
                self.cleanup_timeline_phase(child_phase)
        if phase.get("type") not in {"thinking", "content", "work_summary"}:
            return
        timer = phase.get("timer")
        if timer is not None:
            timer.stop()
        animation = phase.get("body_animation")
        if animation is not None:
            animation.stop()
        header = phase.get("header")
        if header is not None:
            header.set_active(False)

    def cleanup_timeline_phases(self):
        for phase in self.timeline_phases:
            self.cleanup_timeline_phase(phase)

    def ensure_loading_placeholder(self):
        if self.loading_placeholder is None:
            self.loading_placeholder = AutoHeightTextBrowser()
            self.loading_placeholder.document().setDefaultStyleSheet(MARKDOWN_STYLESHEET)
            self.loading_placeholder.setMaximumHeight(16777215)
            self.loading_placeholder.setProperty("segmentContent", None)
            self.loading_placeholder.setProperty("segmentLanguage", None)
            self.body_layout.addWidget(self.loading_placeholder)
        return self.loading_placeholder

    def refresh_loading_placeholder(self):
        if self.has_answer_or_tool_phase():
            self.loading_active = False
            if self.loading_timer.isActive():
                self.loading_timer.stop()
        show_placeholder = self.loading_active and not self.has_answer_or_tool_phase() and self.work_progress_phase is None
        if show_placeholder:
            placeholder = self.ensure_loading_placeholder()
            segment = {
                "type": "placeholder",
                "content": self.loading_placeholder_text(),
                "language": "",
            }
            self.update_segment_widget(placeholder, segment)
            placeholder.show()
        elif self.loading_placeholder is not None:
            self.remove_widget_from_layout(self.body_layout, self.loading_placeholder)
            self.loading_placeholder.deleteLater()
            self.loading_placeholder = None
        self.body.setVisible(self.body_layout.count() > 0)

    def render_assistant_content(self, layout, text):
        if layout is None:
            return
        segments = self.assistant_segments(text)
        for index, segment in enumerate(segments):
            widget = layout.itemAt(index).widget() if index < layout.count() else None
            if not self.can_reuse_segment_widget(widget, segment):
                if widget is not None:
                    item = layout.takeAt(index)
                    old_widget = item.widget()
                    if old_widget is not None:
                        old_widget.deleteLater()
                widget = self.create_segment_widget(segment)
                layout.insertWidget(index, widget)
            else:
                self.update_segment_widget(widget, segment)

        while layout.count() > len(segments):
            item = layout.takeAt(layout.count() - 1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        parent_widget = layout.parentWidget()
        if parent_widget is not None:
            parent_widget.updateGeometry()
        window = self.window()
        if hasattr(window, "update_sticky_code_header"):
            QTimer.singleShot(0, window.update_sticky_code_header)

    def assistant_segments(self, text):
        normalized_text = replace_terminal_command_tags(text or "")
        normalized_text = normalize_terminal_fences(normalized_text)
        segments = []
        for segment_type, content, language in split_markdown_code_segments(normalized_text):
            if segment_type == "code":
                segments.append({"type": "code", "content": content, "language": language})
            elif content.strip():
                segments.append({"type": "text", "content": render_latexish_text(content), "language": ""})
        return segments

    def remove_widget_from_layout(self, layout, target):
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is not None and item.widget() is target:
                layout.takeAt(index)
                return True
        return False

    def loading_placeholder_text(self):
        return "." * (self.loading_step + 1)

    def can_reuse_segment_widget(self, widget, segment):
        if segment["type"] == "code":
            return isinstance(widget, AssistantCodeBlock)
        return isinstance(widget, AutoHeightTextBrowser)

    def create_segment_widget(self, segment):
        if segment["type"] == "code":
            widget = AssistantCodeBlock(
                segment["content"],
                segment["language"],
                content_padding=self.code_sticky_content_padding,
            )
        else:
            widget = AutoHeightTextBrowser()
            widget.document().setDefaultStyleSheet(MARKDOWN_STYLESHEET)
            widget.setMaximumHeight(16777215)
        widget.setProperty("segmentContent", None)
        widget.setProperty("segmentLanguage", None)
        return widget

    def update_segment_widget(self, widget, segment):
        previous_content = widget.property("segmentContent")
        previous_language = widget.property("segmentLanguage")
        if segment["type"] == "code":
            if previous_content != segment["content"] or previous_language != segment["language"]:
                widget.update_code(segment["content"], segment["language"])
        else:
            if previous_content != segment["content"]:
                widget.setHtml(prepare_assistant_html(segment["content"]))
                widget.update_height()
        widget.setProperty("segmentContent", segment["content"])
        widget.setProperty("segmentLanguage", segment["language"])

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self.clear_layout(child_layout)

    def refresh_attachments(self):
        from .attachment_widgets import AttachmentChip, ImagePreviewButton
        if self.role != "user" or self.attachments_layout is None:
            return

        while self.attachments_layout.count():
            item = self.attachments_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self.attachments:
            self.attachments_widget.hide()
            return

        image_attachments = [item for item in self.attachments if item.get("type") == "image"]
        image_paths = [item["path"] for item in image_attachments]
        image_index = 0
        for attachment in self.attachments:
            if attachment.get("type") == "image":
                preview = ImagePreviewButton(attachment["path"])
                preview.clicked_preview.connect(
                    lambda image_paths=image_paths, index=image_index: self.image_preview_requested.emit(image_paths, index)
                )
                self.attachments_layout.addWidget(preview)
                image_index += 1
            else:
                chip = AttachmentChip(attachment, removable=False)
                chip.preview_requested.connect(self.file_preview_requested.emit)
                self.attachments_layout.addWidget(chip)

        self.attachments_layout.addStretch()
        self.attachments_widget.show()

    def append_text(self, token):
        if self.role == "assistant":
            self.ensure_work_progress_phase()
            self.raw_text += token
            if self.active_stream_phase is None or self.active_stream_phase.get("type") != "content":
                self.finish_active_thinking_phase()
                self.active_stream_phase = self.create_content_phase(final=self.final_answer_pending)
                if self.final_answer_pending:
                    self.final_answer_phase = self.active_stream_phase
                    self.final_answer_pending = False
            self.active_stream_phase["text"] += token
            if (
                self.active_stream_phase is self.final_answer_phase
                and self.work_summary_phase is None
                and self.phase_has_visible_content(self.final_answer_phase)
            ):
                self.ensure_work_summary_for_final(self.final_answer_phase)
            if self.render_debounce_enabled and self.render_timer is not None:
                self.pending_render_text = self.active_stream_phase["text"]
                if self.render_debounce_interval_ms <= 0:
                    self.flush_pending_render()
                elif not self.render_timer.isActive():
                    self.render_timer.start()
            else:
                self.render_content_phase(self.active_stream_phase)
                self.refresh_loading_placeholder()
                self.notify_assistant_content_changed()
            return
        self.update_text(self.raw_text + token)

    def start_terminal_command(self, command, shell_name):
        from .terminal_widgets import TerminalCommandBlock
        if self.role != "assistant" or self.terminal_blocks_layout is None:
            return
        self.cancel_pending_final_answer()
        if self.render_timer is not None and self.render_timer.isActive():
            self.flush_pending_render()
        self.finish_active_thinking_phase()
        block = TerminalCommandBlock(command, shell_name)
        self.terminal_blocks.append(block)
        self.current_terminal_block = block
        self.active_stream_phase = self.create_terminal_phase(block)
        self.refresh_loading_placeholder()
        self.notify_assistant_content_changed()

    def append_terminal_log(self, text):
        if self.role != "assistant":
            return
        if self.current_terminal_block is None:
            self.start_terminal_command("command", "Bash")
        if self.current_terminal_block is not None:
            self.current_terminal_block.append_log(text)

    def finish_terminal_command(self, status):
        if self.role != "assistant" or self.current_terminal_block is None:
            return
        self.current_terminal_block.finish(status)
        self.current_terminal_block = None
        self.active_stream_phase = None

    def append_thinking(self, token, visible):
        if self.role != "assistant":
            return
        self.ensure_work_progress_phase()
        self.thinking_text += token
        if self.render_timer is not None and self.render_timer.isActive():
            self.flush_pending_render()
        if self.active_stream_phase is None or self.active_stream_phase.get("type") != "thinking":
            self.active_stream_phase = self.create_thinking_phase(expanded=visible)
        self.active_stream_phase["text"] += token
        self.render_thinking_phase(self.active_stream_phase)
        self.refresh_loading_placeholder()
        self.notify_assistant_content_changed()

    def start_loading(self):
        if self.role != "assistant":
            return
        self.loading_step = 0
        self.loading_active = True
        self.update_loading_text()
        self.loading_timer.start()

    def stop_loading(self):
        if self.role != "assistant":
            return
        if self.loading_active and not self.has_answer_or_tool_phase():
            return
        self.loading_timer.stop()
        self.loading_active = False
        self.refresh_loading_placeholder()

    def advance_loading_frame(self):
        self.loading_step = (self.loading_step + 1) % 4
        if self.loading_active:
            self.update_loading_text()

    def update_loading_text(self):
        self.refresh_loading_placeholder()
        self.notify_assistant_content_changed()

    def copy_text(self):
        QGuiApplication.clipboard().setText(self.raw_text)
        show_widget_toast(self, "Message copied")

    def emit_retry(self):
        if self.retry_text:
            self.retry_requested.emit(self.retry_text)