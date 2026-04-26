"""Application constants and filesystem paths."""

import re
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / "assets"
APP_WORKSPACE = PROJECT_ROOT

DEFAULT_SERVER_BASE_URL = "http://localhost:8080"
CONFIG_PATH = PROJECT_ROOT / "config.json"
PIN_ICON_PATH = ASSETS_DIR / "ic_pin.svg"
ARROW_UP_ICON_PATH = ASSETS_DIR / "ic_arrow_up.svg"
STOP_ICON_PATH = ASSETS_DIR / "ic_stop.svg"
COPY_ICON_PATH = ASSETS_DIR / "ic_copy.svg"
RETRY_ICON_PATH = ASSETS_DIR / "ic_retry.svg"
CLIPBOARD_IMAGE_DIR = Path(tempfile.gettempdir()) / "agent_chat_ui_clipboard"
TEXT_PREVIEW_SUFFIXES = {
    ".txt", ".md", ".json", ".csv", ".py", ".kt", ".js", ".ts", ".tsx", ".jsx",
    ".html", ".css", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".log",
    ".sh", ".bash", ".zsh", ".bat", ".ps1", ".java", ".c", ".cpp", ".h", ".hpp",
    ".sql", ".toml", ".rs",
}
MAX_ATTACHMENT_TEXT_CHARS = 12000
CODE_STICKY_HEADER_HEIGHT = 44
CODE_STICKY_CONTENT_PADDING = 12
MAX_URLS_PER_MESSAGE = 4
MAX_URL_DOWNLOAD_BYTES = 8 * 1024 * 1024
MAX_URL_TEXT_CHARS = 16000
URL_FETCH_TIMEOUT = 12
URL_RE = re.compile(r"https?://[^\s<>\]\)\"']+", re.IGNORECASE)
TRAILING_URL_PUNCTUATION = ".,;:!?)]}\"'"
TERMINAL_COMMAND_RE = re.compile(
    r"<terminal_command>\s*([\s\S]*?)\s*</terminal_command>|```terminal\s*\n([\s\S]*?)```",
    re.IGNORECASE,
)
TERMINAL_OUTPUT_LIMIT = 20000
TERMINAL_TIMEOUT_SECONDS = 60
MAX_AGENT_TERMINAL_STEPS = 6
AGENT_TERMINAL_PROMPT = f"""
You are running inside a local desktop chat app with terminal access enabled.
When you need to inspect files or change the workspace, request exactly one terminal command by writing:

<terminal_command>
command here
</terminal_command>

Rules:
- Run commands only when they are useful for the user's request.
- The command runs with bash in this workspace: {APP_WORKSPACE}
- After terminal output is returned, continue from the result.
- Do not invent terminal output.
- When the task is complete, answer normally without a terminal_command tag.
""".strip()
