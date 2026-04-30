"""Character profile normalization and local-state helpers for Agent Chat UI v2.0."""

DEFAULT_CHARACTER_CAPABILITIES = {
    "file_context": True,
    "url_context": True,
    "terminal": False,
    "mcp": False,
}

LEGACY_DEFAULT_CHARACTER_CAPABILITIES = {
    "file_context": True,
    "url_context": False,
    "terminal": False,
    "mcp": False,
}

DEFAULT_CHARACTER_PROFILES = {
    "source_url": "",
    "last_sync": None,
    "active_character_id": None,
    "items": [],
    "local_state": {},
}


def normalize_capabilities(value):
    caps = dict(DEFAULT_CHARACTER_CAPABILITIES)
    if isinstance(value, dict):
        if all(value.get(key) == legacy_value for key, legacy_value in LEGACY_DEFAULT_CHARACTER_CAPABILITIES.items()):
            return caps
        for key in DEFAULT_CHARACTER_CAPABILITIES:
            if key in value:
                caps[key] = bool(value.get(key))
    return caps


def _clean_text(value, default=""):
    return str(value if value is not None else default).strip()


def _clean_tags(value):
    if not isinstance(value, list):
        return []
    cleaned = []
    for tag in value:
        text = _clean_text(tag)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def normalize_character(raw):
    if not isinstance(raw, dict):
        return None

    style = _clean_text(raw.get("style"))
    role = _clean_text(raw.get("role") or style or "AI Character")

    item = {
        "id": _clean_text(raw.get("id")),
        "name": _clean_text(raw.get("name")),
        "role": role,
        "style": style or role,
        "avatar_url": _clean_text(raw.get("avatar_url") or raw.get("image_url")),
        "poster_url": _clean_text(raw.get("poster_url") or raw.get("cover_url")),
        "description": _clean_text(raw.get("description")),
        "system_prompt": _clean_text(raw.get("system_prompt")),
        "greeting": _clean_text(raw.get("greeting")),
        "tags": _clean_tags(raw.get("tags", [])),
        "version": raw.get("version") or 1,
        "default_capabilities": normalize_capabilities(raw.get("default_capabilities")),
    }
    return item if validate_character(item) else None


def validate_character(item):
    return bool(
        isinstance(item, dict)
        and item.get("id")
        and item.get("name")
        and item.get("system_prompt")
    )


def normalize_local_state(value, valid_ids=None):
    valid_ids = set(valid_ids or [])
    local_state = {}
    if not isinstance(value, dict):
        return local_state

    for character_id, raw_state in value.items():
        character_id = _clean_text(character_id)
        if not character_id or (valid_ids and character_id not in valid_ids):
            continue

        raw_state = raw_state if isinstance(raw_state, dict) else {}
        normalized = {"favorite": bool(raw_state.get("favorite", False))}

        overrides = raw_state.get("capabilities_override")
        if isinstance(overrides, dict):
            normalized["capabilities_override"] = {
                key: bool(overrides[key])
                for key in DEFAULT_CHARACTER_CAPABILITIES
                if key in overrides
            }

        local_state[character_id] = normalized

    return local_state


def normalize_character_profiles(raw):
    raw = raw if isinstance(raw, dict) else {}
    items = []
    seen_ids = set()

    for raw_item in raw.get("items", []):
        item = normalize_character(raw_item)
        if not item or item["id"] in seen_ids:
            continue
        seen_ids.add(item["id"])
        items.append(item)

    active_id = _clean_text(raw.get("active_character_id")) or None
    if active_id and active_id not in seen_ids:
        active_id = None
    if not active_id and items:
        active_id = items[0]["id"]

    return {
        "source_url": _clean_text(raw.get("source_url")),
        "last_sync": raw.get("last_sync"),
        "active_character_id": active_id,
        "items": items,
        "local_state": normalize_local_state(raw.get("local_state"), seen_ids),
    }


def get_active_character(character_profiles):
    if not isinstance(character_profiles, dict):
        return None
    active_id = character_profiles.get("active_character_id")
    items = character_profiles.get("items", [])
    for item in items:
        if item.get("id") == active_id:
            return item
    return items[0] if items else None


def get_character_local_state(character_profiles, character_id):
    if not isinstance(character_profiles, dict) or not character_id:
        return {}
    state = character_profiles.get("local_state", {}).get(character_id, {})
    return state if isinstance(state, dict) else {}


def is_character_favorite(character_profiles, character_id):
    return bool(get_character_local_state(character_profiles, character_id).get("favorite", False))


def get_effective_character_capabilities(character, local_state):
    caps = dict(DEFAULT_CHARACTER_CAPABILITIES)
    character_id = None

    if isinstance(character, dict):
        caps.update(normalize_capabilities(character.get("default_capabilities")))
        character_id = character.get("id")

    if isinstance(local_state, dict) and character_id:
        state = local_state.get(character_id, {})
        overrides = state.get("capabilities_override", {}) if isinstance(state, dict) else {}
        if isinstance(overrides, dict):
            for key in DEFAULT_CHARACTER_CAPABILITIES:
                if key in overrides:
                    caps[key] = bool(overrides[key])

    return caps


def sort_characters(items, local_state):
    local_state = local_state if isinstance(local_state, dict) else {}
    return sorted(
        items or [],
        key=lambda item: (
            not local_state.get(item.get("id"), {}).get("favorite", False),
            item.get("name", "").lower(),
        ),
    )


def filter_characters(items, local_state=None, query="", favorites_only=False):
    local_state = local_state if isinstance(local_state, dict) else {}
    query = _clean_text(query).lower()
    result = []

    for item in items or []:
        character_id = item.get("id", "")
        state = local_state.get(character_id, {})

        if favorites_only and not state.get("favorite", False):
            continue

        haystack = " ".join(
            [
                item.get("name", ""),
                item.get("role", ""),
                item.get("style", ""),
                item.get("description", ""),
                " ".join(item.get("tags", [])),
            ]
        ).lower()

        if query and query not in haystack:
            continue

        result.append(item)

    return sort_characters(result, local_state)


def set_character_favorite(character_profiles, character_id, favorite):
    if not character_id:
        return
    state = character_profiles.setdefault("local_state", {}).setdefault(character_id, {})
    state["favorite"] = bool(favorite)


def set_character_capability(character_profiles, character_id, key, value):
    if key not in DEFAULT_CHARACTER_CAPABILITIES or not character_id:
        return
    state = character_profiles.setdefault("local_state", {}).setdefault(character_id, {})
    overrides = state.setdefault("capabilities_override", {})
    overrides[key] = bool(value)


def character_role(character):
    if not isinstance(character, dict):
        return "AI Character"
    return _clean_text(character.get("role") or character.get("style") or "AI Character")


def character_poster_url(character):
    if not isinstance(character, dict):
        return ""
    return _clean_text(character.get("poster_url") or character.get("cover_url"))


def character_avatar_url(character):
    if not isinstance(character, dict):
        return ""
    return _clean_text(character.get("avatar_url") or character.get("image_url"))


def should_render_full_poster(character):
    return bool(character_poster_url(character))


def character_accent(character):
    if not isinstance(character, dict):
        return "#7c6cff"

    tags = [str(tag).lower() for tag in character.get("tags", [])]
    role = character_role(character).lower()
    text = " ".join(tags + [role])

    if "motivation" in text or "coach" in text or "growth" in text:
        return "#22d3ee"
    if "technical" in text or "mentor" in text or "teaching" in text:
        return "#60a5fa"
    if "strategic" in text or "planner" in text or "productivity" in text:
        return "#8b5cf6"
    return "#7c6cff"
