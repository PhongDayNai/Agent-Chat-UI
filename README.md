# Agent Chat UI

Agent Chat UI is a PyQt6 desktop client for local OpenAI-compatible chat
completion servers. It is designed for running smaller local models with a
comfortable desktop workflow, a low-friction first prompt, and optional local
agent features such as terminal command execution.

The goal is not to be a hosted chat product. The goal is to make local model
usage feel practical: pick a model, optionally set a short session prompt, send
messages, attach files, and let the assistant request terminal commands when
that is useful for local coding or inspection tasks.

## Why this exists

Small local models often work best when the starting context is compact. This
app keeps the beginning of a session lightweight while still exposing the tools
that make local work useful:

- a desktop chat interface for local OpenAI-compatible servers
- model selection from the server's `/v1/models` endpoint
- session prompts that lock in only when the first message is sent
- optional terminal execution for local agent workflows
- file and URL context helpers
- simple queueing when messages are submitted while a response is still running
- UI controls for sampling and streaming/rendering behavior

## Features

- **OpenAI-compatible local server support**  
  Connects to a local server such as `llama-server` at
  `http://localhost:8080` by default.

- **Model picker**  
  Loads available models from `/v1/models` and lets you switch models from the
  sidebar.

- **Low-startup-context sessions**  
  A session prompt can be drafted and saved, then locked into the conversation
  only when the first message is sent.

- **Terminal agent mode**  
  When enabled, the assistant can request a shell command with a
  `<terminal_command>...</terminal_command>` block. The app runs the command in
  the repository workspace and feeds the output back to the model.

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
  settings, and UI state are stored in `config.json`.

## Requirements

- Python 3.10+
- `pip`
- `venv`
- A local OpenAI-compatible chat completion server

The server is expected to expose:

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`

The default base URL is:

```text
http://localhost:8080
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Run

Start your local OpenAI-compatible server first, then run:

```bash
python agent_chat_ui.py
```

The app will check `/health`, load models from `/v1/models`, and enable sending
once a model is available.

## Terminal Agent Usage

Terminal access is optional and can be enabled from the sidebar.

When terminal access is enabled, the app adds a compact instruction to the
conversation explaining how the assistant can request one command:

```xml
<terminal_command>
pwd
</terminal_command>
```

The command runs with `bash` in this repository workspace. Output is streamed
into the UI and then passed back to the model so it can continue the answer.

Permission modes:

- **Default permissions**: only commands listed in `config.json` are allowed
  automatically; other commands require approval.
- **Full access**: requested commands are allowed without per-command approval.

Terminal execution is local and powerful. Use full access only when you trust
the model and the current task.

## Configuration

The app reads and writes `config.json` in the repository root.

Important sections:

- `server`: base URL and saved server URL history
- `session_prompt`: current prompt and prompt history
- `agent_terminal`: terminal enabled state, permission mode, and default command
  allowlist
- `sampling`: temperature, top-p, and top-k values
- `assistant_rendering`: streaming debounce settings
- `ui`: panel pinning and display preferences

Most settings can be changed from the app UI and are saved automatically.

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
src/widgets.py        # custom widgets for chat cards, previews, terminal logs
src/styles.py         # Qt stylesheet
src/constants.py      # paths, limits, prompt snippets, regexes
src/markdown_utils.py # markdown and terminal tag normalization
src/html_utils.py     # URL HTML-to-text extraction
assets/               # SVG icons
config.json           # local user/app configuration
```

## Notes

- This app is optimized for local workflows and small-to-medium models, not for
  cloud account management.
- Keep session prompts short when using small context models.
- Terminal output and fetched URL content are truncated by design to avoid
  overwhelming the model context.
- `config.json` is local state; review it before sharing the repository.
