from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Final

SERVICE_NAME: Final = "openbrief"
BACKEND_ENV: Final = "OPENBRIEF_SECRET_BACKEND"
FILE_BACKEND_VALUE: Final = "file"
FALLBACK_FILENAME: Final = ".secrets.json"


class SecretStoreError(RuntimeError):
    pass


def get_secret(home: Path, name: str) -> str | None:
    if use_file_backend():
        return get_file_secret(home, name)

    try:
        import keyring

        value = keyring.get_password(SERVICE_NAME, account_name(home, name))
    except Exception:  # noqa: BLE001
        return get_file_secret(home, name)
    return value or get_file_secret(home, name)


def set_secret(home: Path, name: str, value: str) -> str:
    if not value:
        raise SecretStoreError(f"{name} cannot be empty")
    if use_file_backend():
        set_file_secret(home, name, value)
        return "file"

    try:
        import keyring

        keyring.set_password(SERVICE_NAME, account_name(home, name), value)
    except Exception:  # noqa: BLE001
        set_file_secret(home, name, value)
        return "file"
    return "keyring"


def get_or_create_secret(home: Path, name: str, factory: Callable[[], str]) -> str:
    existing = get_secret(home, name)
    if existing:
        return existing
    value = factory()
    set_secret(home, name, value)
    return value


def migrate_legacy_secret(home: Path, name: str, legacy_value: str | None) -> None:
    if not legacy_value:
        return
    set_secret(home, name, legacy_value)


def use_file_backend() -> bool:
    return os.environ.get(BACKEND_ENV) == FILE_BACKEND_VALUE


def account_name(home: Path, name: str) -> str:
    return f"{home.resolve()}:{name}"


def fallback_path(home: Path) -> Path:
    return home / FALLBACK_FILENAME


def get_file_secret(home: Path, name: str) -> str | None:
    path = fallback_path(home)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    value = data.get(name)
    return str(value) if value else None


def set_file_secret(home: Path, name: str, value: str) -> None:
    home.mkdir(parents=True, exist_ok=True)
    path = fallback_path(home)
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    data[name] = value
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    path.chmod(0o600)
