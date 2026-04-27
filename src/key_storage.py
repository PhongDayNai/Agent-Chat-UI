"""OS keychain storage helpers for API keys."""

import os

from constants import API_KEY_KEYRING_PREFIX, KEYRING_SERVICE_NAME


class KeyStorageError(Exception):
    """Raised when the OS keychain cannot be accessed."""


def _disabled_message():
    if os.environ.get("ACU_DISABLE_KEYRING") == "1":
        return "Keyring disabled by ACU_DISABLE_KEYRING"
    return ""


def _load_keyring():
    disabled = _disabled_message()
    if disabled:
        raise KeyStorageError(disabled)
    try:
        import keyring
        from keyring.errors import KeyringError
    except ImportError as exc:
        raise KeyStorageError("Keyring library is not installed.") from exc
    return keyring, KeyringError


def _account_name(key_id):
    key_id = str(key_id or "").strip()
    if not key_id:
        raise KeyStorageError("API key id is missing.")
    return f"{API_KEY_KEYRING_PREFIX}{key_id}"


def _backend_unavailable(backend):
    backend_module = backend.__class__.__module__.lower()
    backend_name = backend.__class__.__name__.lower()
    priority = getattr(backend, "priority", 1)
    return "keyring.backends.fail" in backend_module or "fail" in backend_name or priority <= 0


def available():
    """Return whether the configured keyring backend is accessible."""
    try:
        keyring, keyring_error = _load_keyring()
        backend = keyring.get_keyring()
        if _backend_unavailable(backend):
            return False, "No supported OS keychain backend is available."
    except KeyStorageError as exc:
        return False, str(exc)
    except keyring_error as exc:
        return False, f"Keychain unavailable: {exc}"
    except Exception as exc:
        return False, f"Keychain unavailable: {exc}"
    return True, "OS keychain available."


def set_api_key_secret(key_id, value):
    value = str(value or "")
    if not value:
        raise KeyStorageError("API key value is empty.")
    account = _account_name(key_id)
    try:
        keyring, keyring_error = _load_keyring()
        keyring.set_password(KEYRING_SERVICE_NAME, account, value)
    except KeyStorageError:
        raise
    except keyring_error as exc:
        raise KeyStorageError(f"Could not save API key to OS keychain: {exc}") from exc
    except Exception as exc:
        raise KeyStorageError(f"Could not save API key to OS keychain: {exc}") from exc


def get_api_key_secret(key_id):
    account = _account_name(key_id)
    try:
        keyring, keyring_error = _load_keyring()
        return keyring.get_password(KEYRING_SERVICE_NAME, account) or ""
    except KeyStorageError:
        raise
    except keyring_error as exc:
        raise KeyStorageError(f"Could not read API key from OS keychain: {exc}") from exc
    except Exception as exc:
        raise KeyStorageError(f"Could not read API key from OS keychain: {exc}") from exc


def delete_api_key_secret(key_id):
    account = _account_name(key_id)
    try:
        keyring, keyring_error = _load_keyring()
        keyring.delete_password(KEYRING_SERVICE_NAME, account)
    except KeyStorageError:
        raise
    except keyring_error as exc:
        message = str(exc).lower()
        if "not found" in message or "not available" in message:
            return
        raise KeyStorageError(f"Could not delete API key from OS keychain: {exc}") from exc
    except Exception as exc:
        message = str(exc).lower()
        if "not found" in message or "not available" in message:
            return
        raise KeyStorageError(f"Could not delete API key from OS keychain: {exc}") from exc
