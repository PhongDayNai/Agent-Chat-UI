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
FINAL_ANSWER_PROTOCOL_PROMPT = f"""
## Agent/tool workflow UI protocol:
- **Phase 1: Execution & Reasoning**: Use normal assistant text for progress notes and tool requests.
- **Phase 2: Transition**: When all reasoning and tool work is complete, write the marker `[[final_answer]]` on its own line.
- **Phase 3: Final Delivery**:
    - This phase is for pure text communication with the user only.
    - **STRICT PROHIBITION**: Do NOT include `<terminal_command>`, tool calls, or any functional tags after the `[[final_answer]]` marker.
    - The marker is an absolute "Point of No Return": once written, all system interactions must cease.
- The UI will collapse Phase 1 and 2, showing only what follows the marker.
""".strip()


def agent_terminal_prompt(workspace_path):
    return f"""
## Terminal Execution Rules:
- Request exactly one command at a time using: `<terminal_command>command here</terminal_command>`.
- **Pre-condition**: Terminal commands are only allowed BEFORE the `[[final_answer]]` marker.
- **Completion Criteria**:
    - If the user asks to "run", "inspect", or "execute", you must perform these tasks and observe the output first.
    - Only after the task is finished, provide a summary starting with `[[final_answer]]`.
- **Integrity Check**: Never include terminal commands before or after the `[[final_answer]]` marker. The final answer must be a clean, non-executable summary for the user.
- The command runs with {TERMINAL_SHELL_DESCRIPTION} in this workspace: {workspace_path}
- After terminal output is returned, continue from the result.
- Do not invent terminal output.
""".strip()


AGENT_TERMINAL_PROMPT = agent_terminal_prompt(APP_WORKSPACE)
