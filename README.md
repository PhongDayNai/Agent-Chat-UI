# agent-chat-ui

PyQt6 desktop chat client for local OpenAI-compatible chat completion servers.

This repository is being migrated from an older local prototype in small, reviewable phases. See `MIGRATION_PLAN.md` for the migration order and commit boundaries.

## Requirements

- Python 3.10+
- `pip`
- `venv`
- A local OpenAI-compatible server, such as `llama-server`, available at `http://localhost:8080`

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Run

```bash
python agent_chat_ui.py
```

## Structure

```text
agent_chat_ui.py      # thin launcher
src/                 # application modules
assets/               # SVG icons
config.json           # local default config
```
