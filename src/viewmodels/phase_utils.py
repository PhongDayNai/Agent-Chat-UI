import time


def format_elapsed_time_text(elapsed):
    """Format elapsed seconds into human-readable string like '1h 30m 45s' or '45s'."""
    total_seconds = max(0, int(elapsed))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return "".join(parts)


def calculate_elapsed(started_at, ended_at=None):
    """Calculate elapsed time between started_at and ended_at (or now if ended_at is None)."""
    if ended_at is None:
        ended_at = time.monotonic()
    return ended_at - started_at