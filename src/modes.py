"""Chat mode constants and helpers."""

MODE_CHAT = "chat"
MODE_CHARACTER = "character"
MODE_AGENT = "agent"

VALID_MODES = {MODE_CHAT, MODE_CHARACTER, MODE_AGENT}

MODE_LABELS = {
    MODE_CHAT: "Chat",
    MODE_CHARACTER: "Character",
    MODE_AGENT: "Agent",
}


def normalize_mode(value):
    value = str(value or "").strip().lower()
    if value in VALID_MODES:
        return value
    return MODE_CHAT
