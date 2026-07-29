"""Persist rclone session tokens without touching macOS Keychain.

Proton Drive writes client_uid / access_token / refresh_token / salted_key_pass
into the config after login. Re-saving those into Keychain on every Test/Mount
makes macOS ask for the login password repeatedly (Keychain *writes* always
authenticate; "Always Allow" only helps *reads*).

Store them in Application Support with mode 0600 instead.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from .paths import APP_SUPPORT, SESSION_STORE, ensure_dirs

_SESSION_FIELDS = (
    "client_uid",
    "client_access_token",
    "client_refresh_token",
    "client_salted_key_pass",
)


def _load() -> dict[str, Any]:
    if not SESSION_STORE.exists():
        return {}
    try:
        data = json.loads(SESSION_STORE.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: dict[str, Any]) -> None:
    ensure_dirs()
    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(
        prefix="session_tokens.",
        suffix=".json",
        dir=str(APP_SUPPORT),
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(payload)
        os.chmod(tmp, 0o600)
        os.replace(tmp, SESSION_STORE)
        try:
            SESSION_STORE.chmod(0o600)
        except OSError:
            pass
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def get_session(host_id: str) -> dict[str, str]:
    block = _load().get(host_id) or {}
    if not isinstance(block, dict):
        return {}
    return {k: str(v) for k, v in block.items() if v and k in _SESSION_FIELDS}


def get_session_field(host_id: str, field: str) -> Optional[str]:
    if field not in _SESSION_FIELDS:
        return None
    val = get_session(host_id).get(field)
    return val or None


def set_session(host_id: str, fields: dict[str, str]) -> int:
    """Merge session fields for host. Returns number of fields changed."""
    clean = {
        k: str(v).strip()
        for k, v in fields.items()
        if k in _SESSION_FIELDS and v and str(v).strip()
    }
    if not clean:
        return 0
    data = _load()
    prev = dict(data.get(host_id) or {})
    merged = dict(prev)
    changed = 0
    for k, v in clean.items():
        if prev.get(k) != v:
            merged[k] = v
            changed += 1
    if changed == 0:
        return 0
    data[host_id] = merged
    _save(data)
    return changed


def clear_session(host_id: str) -> None:
    data = _load()
    if host_id in data:
        del data[host_id]
        _save(data)


SESSION_FIELDS = _SESSION_FIELDS
