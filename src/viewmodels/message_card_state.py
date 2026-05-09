from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal
import time as time_module

from .phase_utils import format_elapsed_time_text


class WorkPhase(Enum):
    INACTIVE = "inactive"
    PROGRESS = "progress"
    COMPLETE = "complete"


class MessageCardState(QObject):
    """ViewModel for managing work progress phase state in MessageCard.

    Signals:
        progress_updated(float): Emitted with elapsed seconds when timer updates.
        phase_transition(str, str): Emitted when phase changes (old_phase, new_phase).
        phase_completed(float): Emitted when work completes with total elapsed seconds.
    """

    progress_updated = pyqtSignal(float)
    phase_transition = pyqtSignal(str, str)
    phase_completed = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self._phase = WorkPhase.INACTIVE
        self._start_time = None
        self._elapsed = 0.0

    def start_progress(self):
        """Start the work progress phase. Transitions INACTIVE -> PROGRESS."""
        if self._phase != WorkPhase.INACTIVE:
            return
        self._phase = WorkPhase.PROGRESS
        self._start_time = time_module.monotonic()
        self._elapsed = 0.0
        self.phase_transition.emit("inactive", "progress")

    def update_progress(self):
        """Update progress. Should be called by timer. Emits progress_updated with elapsed seconds."""
        if self._phase != WorkPhase.PROGRESS:
            return
        self._elapsed = time_module.monotonic() - self._start_time
        self.progress_updated.emit(self._elapsed)

    def complete_progress(self):
        """Complete the work progress phase. Transitions PROGRESS -> COMPLETE."""
        if self._phase != WorkPhase.PROGRESS:
            return
        self._phase = WorkPhase.COMPLETE
        self._elapsed = time_module.monotonic() - self._start_time
        self.phase_transition.emit("progress", "complete")
        self.phase_completed.emit(self._elapsed)

    def reset(self):
        """Reset to INACTIVE state."""
        was_phase = self._phase.value if self._phase else "inactive"
        self._phase = WorkPhase.INACTIVE
        self._start_time = None
        self._elapsed = 0.0
        if was_phase != "inactive":
            self.phase_transition.emit(was_phase, "inactive")

    @property
    def phase(self) -> WorkPhase:
        """Current phase."""
        return self._phase

    @property
    def elapsed(self) -> float:
        """Elapsed time in seconds."""
        return self._elapsed

    @property
    def title_text(self) -> str:
        """Get the title text based on current phase.

        Returns 'Working for Xs' when in PROGRESS, 'Worked for Xs' when COMPLETE.
        """
        elapsed_formatted = format_elapsed_time_text(self._elapsed)
        if self._phase == WorkPhase.PROGRESS:
            return f"Working for {elapsed_formatted}"
        elif self._phase == WorkPhase.COMPLETE:
            return f"Worked for {elapsed_formatted}"
        return ""

    @property
    def is_active(self) -> bool:
        """True if work is in progress (PROGRESS phase)."""
        return self._phase == WorkPhase.PROGRESS

    @property
    def is_complete(self) -> bool:
        """True if work is complete (COMPLETE phase)."""
        return self._phase == WorkPhase.COMPLETE

    @property
    def is_inactive(self) -> bool:
        """True if work is inactive."""
        return self._phase == WorkPhase.INACTIVE