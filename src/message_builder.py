"""Build OpenAI-compatible chat messages for the active app mode."""

from characters import get_active_character, get_effective_character_capabilities
from modes import MODE_AGENT, MODE_CHARACTER


def build_messages(config, history, user_message, terminal_instruction=None, mcp_instruction=None):
    mode = config.get("active_mode", "chat")
    messages = []
    sections = []

    if mode == MODE_CHARACTER:
        profiles = config.get("character_profiles", {})
        character = get_active_character(profiles)
        if not character:
            return None

        sections.append("You are chatting as the selected character. Follow the character profile exactly.")

        system_prompt = character.get("system_prompt", "").strip()
        if system_prompt:
            sections.append(system_prompt)

        caps = get_effective_character_capabilities(character, profiles.get("local_state", {}))

        if caps.get("terminal") and terminal_instruction:
            sections.append(terminal_instruction)

        if caps.get("mcp") and mcp_instruction:
            sections.append(mcp_instruction)

    else:
        if mode == MODE_AGENT and terminal_instruction:
            sections.append(terminal_instruction)

        session_prompt = config.get("session_prompt", {})
        value = str(session_prompt.get("value", "")).strip()
        if session_prompt.get("enabled") and value:
            sections.append(value)

    if sections:
        messages.append({"role": "system", "content": "\n\n".join(sections)})

    messages.extend(history)
    messages.append(user_message)
    return messages
