"""Application constants and filesystem paths."""

import os
import re
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
APP_VERSION = "2.1"
APP_WORKSPACE = Path.home()
IS_WINDOWS = sys.platform == "win32"
KEYRING_SERVICE_NAME = "AgentChatUI"
API_KEY_KEYRING_PREFIX = "api-key:"


def resource_path(relative_path):
    for root in (RESOURCE_ROOT, RESOURCE_ROOT / "_internal", PROJECT_ROOT):
        candidate = root / relative_path
        if candidate.exists():
            return candidate
    return RESOURCE_ROOT / relative_path


def user_config_path():
    """Return the per-user config path for the current OS."""
    override_path = os.environ.get("ACU_CONFIG_PATH")
    if override_path:
        return Path(override_path).expanduser()
    if sys.platform == "win32":
        config_root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return config_root / "AgentChatUI" / "acu_config.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AgentChatUI" / "acu_config.json"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "acu" / "acu_config.json"


DEFAULT_SERVER_BASE_URL = "http://localhost:8080"
CONFIG_PATH = user_config_path()
LEGACY_CONFIG_PATH = resource_path("config.json")
ASSETS_DIR = resource_path("assets")
APP_LOGO_PATH = ASSETS_DIR / "app_logo.png"
ANIM_LOADING_SMALL_PATH = ASSETS_DIR / "anim_loading_small.gif"
PIN_ICON_PATH = ASSETS_DIR / "ic_pin.svg"
ARROW_UP_ICON_PATH = ASSETS_DIR / "ic_arrow_up.svg"
ARROW_DOWN_ICON_PATH = ASSETS_DIR / "ic_arrow_down.svg"
STOP_ICON_PATH = ASSETS_DIR / "ic_stop.svg"
COPY_ICON_PATH = ASSETS_DIR / "ic_copy.svg"
RETRY_ICON_PATH = ASSETS_DIR / "ic_retry.svg"
ARROW_RIGHT_ICON_PATH = ASSETS_DIR / "ic_arrow_right.svg"
LAYOUT_GRID_ICON_PATH = ASSETS_DIR / "ic_layout_grid.svg"
LAYOUT_LIST_ICON_PATH = ASSETS_DIR / "ic_layout_list.svg"
CLOSE_ICON_PATH = ASSETS_DIR / "ic_close.svg"
TICK_ICON_PATH = ASSETS_DIR / "ic_tick.svg"
STAR_ICON_PATH = ASSETS_DIR / "ic_star.svg"
FILE_ICON_PATH = ASSETS_DIR / "ic_file.svg"
LINK_ICON_PATH = ASSETS_DIR / "ic_link.svg"
TERMINAL_ICON_PATH = ASSETS_DIR / "ic_terrminal.svg"
PENCIL_ICON_PATH = ASSETS_DIR / "ic_pencil.svg"
DEFAULT_PERMISSIONS_ICON_PATH = ASSETS_DIR / "ic_default_permissions.svg"
FULL_ACCESS_ICON_PATH = ASSETS_DIR / "ic_full_access.svg"
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
MAX_OUTPUT_TOKENS = 2048
URL_RE = re.compile(r"https?://[^\s<>\]\)\"']+", re.IGNORECASE)
TRAILING_URL_PUNCTUATION = ".,;:!?)]}\"'"
TERMINAL_COMMAND_RE = re.compile(
    r"<terminal_command>\s*([\s\S]*?)\s*</terminal_command>|```terminal\s*\n([\s\S]*?)```",
    re.IGNORECASE,
)
TERMINAL_OUTPUT_LIMIT = 20000
TERMINAL_TIMEOUT_SECONDS = 60
MAX_AGENT_TERMINAL_STEPS = 6
TERMINAL_SHELL_NAME = "PowerShell" if IS_WINDOWS else "Bash"
TERMINAL_SHELL_DESCRIPTION = "PowerShell" if IS_WINDOWS else "bash"
FINAL_ANSWER_MARKER = "[[final_answer]]"
FINAL_ANSWER_PROTOCOL_PROMPT = """
## AGENT WORKFLOW & UI PROTOCOL:
1. **WORK PHASE (Mandatory for Tools)**:
   - All reasoning, terminal commands, and tool calls MUST happen here.
   - Use brief progress notes.
   - **Constraint**: This phase remains "open" as long as you are performing actions.

2. **THE FINAL MARKER**:
   - You must output exactly `[[final_answer]]` on its own line ONLY when all technical work is 100% complete.
   - This marker is a **HARD BARRIER**. It is not a label; it is a system command to switch modes.

3. **FINAL ANSWER PHASE (Post-Marker)**:
   - This phase starts IMMEDIATELY after `[[final_answer]]`.
   - **STRICT PROHIBITION**: Do not request terminal commands, do not use XML tags, and do not perform any further reasoning.
   - Content must be 100% human-readable text only.
   - If you need to run one more command, you ARE NOT ready to write the marker.
"""


AGENT_TERMINAL_PROMPT = """
## TERMINAL EXECUTION COMMANDS:
- **Usage**: Request exactly one command using `<terminal_command>command</terminal_command>`.
- **Placement**: Terminal commands are strictly forbidden after the `[[final_answer]]` marker.
- **Verification Loop**:
    1. Run command -> Observe output -> Repeat if necessary.
    2. Once the result is achieved, verify it.
    3. ONLY THEN, write `[[final_answer]]` and provide the final text summary.
- **Zero-Tolerance**: If you write `[[final_answer]]`, your ability to execute code is terminated for that turn. Do not attempt to "summarize and then run one last check". Finish the check FIRST, then end with the marker.
"""


def agent_terminal_prompt(workspace_path):
    return AGENT_TERMINAL_PROMPT
