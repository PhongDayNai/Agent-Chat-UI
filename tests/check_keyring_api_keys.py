#!/usr/bin/env python3
"""Check that configured API keys are backed by the OS keychain.

This script is intended for manual verification on Linux and Windows after
running Agent Chat UI v1.2 at least once.

Usage:
    python tests/check_keyring_api_keys.py

Optional:
    ACU_CONFIG_PATH=/path/to/acu_config.json python tests/check_keyring_api_keys.py
"""

import json
import platform
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from constants import CONFIG_PATH, KEYRING_SERVICE_NAME  # noqa: E402
import key_storage  # noqa: E402


def fail(message):
    print(f"FAIL: {message}")
    return 1


def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Config root must be a JSON object.")
    return payload


def check_keyring_api_keys():
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Config: {CONFIG_PATH}")
    print(f"Keyring service: {KEYRING_SERVICE_NAME}")

    ok, message = key_storage.available()
    print(f"Keyring available: {ok} ({message})")
    if not ok:
        return fail("OS keychain backend is unavailable.")

    config = load_config()
    api_keys = config.get("api_keys", {})
    if not isinstance(api_keys, dict):
        return fail("Missing api_keys object in config.")

    items = api_keys.get("items", [])
    if not isinstance(items, list):
        return fail("api_keys.items must be a list.")
    if not items:
        print("PASS: No API keys configured.")
        return 0

    failures = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            failures.append(f"Item {index} is not an object.")
            continue

        name = str(item.get("name", "")).strip() or f"item-{index}"
        key_id = str(item.get("id", "")).strip()
        storage = str(item.get("storage", "")).strip()
        has_plaintext_value = bool(str(item.get("value", "")).strip())

        print(f"- {name}: id={key_id or '<missing>'} storage={storage or '<missing>'}")

        if has_plaintext_value:
            failures.append(f"{name}: config still contains plaintext value.")
        if not key_id:
            failures.append(f"{name}: missing id.")
            continue
        if storage != "keyring":
            failures.append(f"{name}: storage is {storage!r}, expected 'keyring'.")
            continue

        try:
            secret = key_storage.get_api_key_secret(key_id)
        except key_storage.KeyStorageError as exc:
            failures.append(f"{name}: could not read keyring secret: {exc}")
            continue

        if not secret:
            failures.append(f"{name}: keyring secret is missing or empty.")
        else:
            print(f"  secret: present, length={len(secret)}")

    if failures:
        print("")
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print("")
    print("PASS: All configured API keys are stored in OS keychain and config has no plaintext values.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(check_keyring_api_keys())
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(fail(str(exc)))
