# Agent Chat UI

Version: 1.2

Agent Chat UI is a PyQt6 desktop chat client for OpenAI-compatible chat
completion APIs. The v1.2 release is a normal desktop chat app: choose a server
URL, load models from the API, send messages, attach context, and stream
responses in the UI. v1.2 stores named API key secrets in the operating
system keychain when available.

The default target is still `http://localhost:8080`, so unauthenticated local
servers such as `llama-server` keep working without an API key. For hosted or
private endpoints, add a named API key from the sidebar, select it, then apply
it before refreshing models or sending messages.

Releases are available here:
https://github.com/PhongDayNai/Agent-Chat-UI/releases

If Agent Chat UI is useful for your workflow, please consider giving the
repository a star.

## Why this exists

Small local models and simple OpenAI-compatible servers often work best when
the client stays straightforward. This app keeps the beginning of a session
lightweight while still exposing the tools that make desktop chat useful:

- a desktop chat interface for public OpenAI-compatible API endpoints
- localhost-first defaults for unauthenticated local model servers
- named API keys for authenticated OpenAI-compatible endpoints
- model selection from the server's `/v1/models` endpoint
- session prompts that lock in only when the first message is sent
- optional terminal execution for local agent workflows
- file and URL context helpers
- simple queueing when messages are submitted while a response is still running
- UI controls for sampling and streaming/rendering behavior

## Features

- **OpenAI-compatible API support**  
  Connects to OpenAI-compatible chat completion servers. v1.2 can call public
  endpoints directly or send a bearer token when a named API key is applied.

- **Named API keys**  
  Save API keys with required display names from the sidebar. The key menu only
  shows saved names, and requests include `Authorization: Bearer <key>` only
  after the selected key has been applied. New key secrets are stored in the
  OS keychain by default; the user config keeps only key metadata.

- **Localhost-first defaults**  
  Uses `http://localhost:8080` by default, which matches common local servers
  such as `llama-server`.

- **Model picker**  
  Loads available models from `/v1/models` and lets you switch models from the
  sidebar.

- **Low-startup-context sessions**  
  A session prompt can be drafted and saved, then locked into the conversation
  only when the first message is sent.

- **Terminal agent mode**  
  When enabled, the assistant can request a shell command with a
  `<terminal_command>...</terminal_command>` block. The app runs the command in
  the configured workspace and feeds the output back to the model.

- **Terminal permission modes**  
  Default permissions allow only configured command names. Full access allows
  all requested commands. Permission state is visible in both the sidebar and
  composer.

- **Attachments**  
  Attach images and files. Text-like files and PDFs can be extracted into the
  prompt; images are sent as image inputs when the server/model supports them.

- **URL fetching**  
  HTTP/HTTPS links in a prompt can be fetched and converted to text context,
  with size and count limits.

- **Streaming UI**  
  Responses stream into the chat, with optional debounce controls to reduce UI
  render churn on slower machines.

- **Message queue**  
  If a response is running, new submissions can be queued and sent
  automatically when the current response finishes.

- **Local configuration**  
  Server URL history, session prompt history, terminal settings, sampling
  settings, and UI state are stored in the current user's app config directory.

## Requirements

- Python 3.10+
- `pip`
- `venv`
- An OpenAI-compatible chat completion server, with or without API key auth
- OS keychain support for saving API keys:
  - Windows: Windows Credential Manager through `keyring`
  - Linux desktop: Secret Service/GNOME Keyring or KWallet, depending on the
    desktop session and distro packages

The server is expected to expose:

- `GET /v1/models`
- `POST /v1/chat/completions`

`GET /health` is optional. If it returns `404`, the app falls back to
`/v1/models` to verify the server.

The default base URL is:

```text
http://localhost:8080
```

## Download

Prebuilt packages are available from the GitHub release page:

https://github.com/PhongDayNai/Agent-Chat-UI/releases

Available artifacts:

- Windows installer or executable
- Linux AppImage
- Linux Debian package
- Linux tarball

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Run

Start your OpenAI-compatible server first, then run:

```bash
python agent_chat_ui.py
```

The app checks `/health` when available, falls back to `/v1/models` when
`/health` returns `404`, and enables sending once a model is available. If your
endpoint requires authentication, open the sidebar, save an API key with a name,
select that name, apply it, then refresh models.

## Terminal Agent Usage

Terminal access is optional and can be enabled from the sidebar.

When terminal access is enabled, the app adds a compact instruction to the
conversation explaining how the assistant can request one command:

```xml
<terminal_command>
pwd
</terminal_command>
```

The command runs in the configured workspace using the platform shell:
PowerShell on Windows and `bash` on Linux/macOS. If no workspace has been
selected, the app asks whether to choose one at startup and otherwise uses the
current user's home folder for that session. Output is streamed into the UI and
then passed back to the model so it can continue the answer.

Permission modes:

- **Default permissions**: only commands listed in the user config file are
  allowed automatically; other commands require approval.
- **Full access**: requested commands are allowed without per-command approval.

Terminal execution is local and powerful. Use full access only when you trust
the model and the current task.

## Configuration

The app reads and writes `acu_config.json` in the current user's app config
directory:

- Linux: `$XDG_CONFIG_HOME/acu/acu_config.json`, or
  `~/.config/acu/acu_config.json` when `XDG_CONFIG_HOME` is unset
- macOS: `~/Library/Application Support/AgentChatUI/acu_config.json`
- Windows: `%APPDATA%\AgentChatUI\acu_config.json`

For compatibility, if the user config file does not exist yet, the app can read
the old repository-root `config.json`. Future saves are written to the user
config path.

Set `ACU_CONFIG_PATH` to override the config file location for testing or
custom packaging.

Important sections:

- `server`: base URL and saved server URL history
- `api_keys`: saved API key names, storage metadata, and selected key ID
- `session_prompt`: current prompt and prompt history
- `agent_terminal`: terminal enabled state, permission mode, and default command
  allowlist
- `workspace`: optional terminal command workspace path
- `sampling`: temperature, top-p, and top-k values
- `assistant_rendering`: streaming debounce settings
- `ui`: panel pinning, composer sizing, and display preferences

Most settings can be changed from the app UI and are saved automatically. API
key secrets are stored in the OS keychain through `keyring` when available:
Windows uses Windows Credential Manager, macOS uses Keychain, and Linux uses a
Secret Service or KWallet compatible backend. On Linux, some desktop or
minimal/headless environments may need packages such as `gnome-keyring`,
`libsecret`, KWallet, and a working DBus session. Package names vary by distro.

If no keychain backend is available, the app still starts and `No API key`
continues to work for unauthenticated local servers. Saving a new API key fails
clearly instead of writing a plaintext secret to config by default. Legacy v1.1
configs that already contain plaintext API keys are loaded in degraded
compatibility mode and the UI warns that those keys remain in local config.

To verify API keys are really stored in the OS keychain on Linux or Windows,
run this after saving a key in the app:

```bash
python tests/check_keyring_api_keys.py
```

The script checks the current user config, confirms it has no plaintext API key
values, and verifies each `storage: "keyring"` item has a readable keychain
secret without printing the secret.

## File Context

The composer supports file attachments. Text-like files are read directly, PDFs
are extracted when `pypdf` is available, and images are encoded for multimodal
models. Large extracted text is truncated to keep local prompts manageable.

Supported text-like suffixes include common source, config, log, markdown,
JSON, YAML, CSV, HTML, CSS, XML, SQL, shell, and TOML files.

## Project Structure

```text
agent_chat_ui.py      # launcher
src/main.py           # Qt application entrypoint
src/window.py         # main window, UI state, config, message flow
src/worker.py         # streaming chat worker and terminal execution
src/key_storage.py    # OS keychain wrapper for API key secrets
src/widgets.py        # custom widgets for chat cards, previews, terminal logs
src/styles.py         # Qt stylesheet
src/constants.py      # paths, limits, prompt snippets, regexes
src/markdown_utils.py # markdown and terminal tag normalization
src/html_utils.py     # URL HTML-to-text extraction
tests/                # manual verification scripts
assets/               # SVG icons
config.json           # optional legacy local configuration
```

## Notes

- This app is optimized for local workflows and small-to-medium models, not for
  cloud account management.
- Select `No API key` for localhost or another unauthenticated
  OpenAI-compatible endpoint.
- Keep session prompts short when using small context models.
- Terminal output and fetched URL content are truncated by design to avoid
  overwhelming the model context.
- User config is local state. It should only contain API key metadata after a
  successful v1.2 migration, but review legacy `config.json` before sharing the
  repository.
