"""Character profile normalization and local-state helpers."""

DEFAULT_CHARACTER_CAPABILITIES = {
    "file_context": True,
    "url_context": False,
    "terminal": False,
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
        for key in DEFAULT_CHARACTER_CAPABILITIES:
            if key in value:
                caps[key] = bool(value.get(key))
    return caps


def normalize_character(raw):
    if not isinstance(raw, dict):
        return None
    tags = raw.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    item = {
        "id": str(raw.get("id", "")).strip(),
        "name": str(raw.get("name", "")).strip(),
        "avatar_url": str(raw.get("avatar_url") or "").strip(),
        "description": str(raw.get("description") or "").strip(),
        "system_prompt": str(raw.get("system_prompt") or "").strip(),
        "greeting": str(raw.get("greeting") or "").strip(),
        "style": str(raw.get("style") or "").strip(),
        "tags": [str(tag).strip() for tag in tags if str(tag).strip()],
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
        character_id = str(character_id or "").strip()
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

    active_id = str(raw.get("active_character_id") or "").strip() or None
    if active_id and active_id not in seen_ids:
        active_id = None
    if not active_id and items:
        active_id = items[0]["id"]

    return {
        "source_url": str(raw.get("source_url") or "").strip(),
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


def get_effective_character_capabilities(character, local_state):
    caps = dict(DEFAULT_CHARACTER_CAPABILITIES)
    if isinstance(character, dict):
        caps.update(normalize_capabilities(character.get("default_capabilities")))
        character_id = character.get("id")
    else:
        character_id = None
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


def set_character_favorite(character_profiles, character_id, favorite):
    state = character_profiles.setdefault("local_state", {}).setdefault(character_id, {})
    state["favorite"] = bool(favorite)


def set_character_capability(character_profiles, character_id, key, value):
    if key not in DEFAULT_CHARACTER_CAPABILITIES:
        return
    state = character_profiles.setdefault("local_state", {}).setdefault(character_id, {})
    overrides = state.setdefault("capabilities_override", {})
    overrides[key] = bool(value)
