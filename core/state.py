from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from .paths import STATE_PATH, default_mount_kind, ensure_dirs, is_windows

_lock = threading.Lock()


def _default() -> dict[str, Any]:
    kind = default_mount_kind()
    return {
        "version": 1,
        "prefs": {
            "enable_fuse": True,
            # NFS helper is macOS/Linux-oriented; off by default on Windows
            "enable_nfs": not is_windows(),
            "default_mount_kind": kind,
            "auto_migrate_done": False,
        },
        "hosts": [],
        "mounts": [],
    }


def load() -> dict[str, Any]:
    ensure_dirs()
    if not STATE_PATH.exists():
        st = _default()
        save(st)
        return st
    with _lock:
        data = json.loads(STATE_PATH.read_text() or "{}")
    # merge defaults
    base = _default()
    base.update({k: v for k, v in data.items() if k in base or k in ("hosts", "mounts", "prefs", "version")})
    if "prefs" in data:
        base["prefs"] = {**_default()["prefs"], **data["prefs"]}
    base["hosts"] = data.get("hosts") or []
    base["mounts"] = data.get("mounts") or []
    return base


def save(state: dict[str, Any]) -> None:
    ensure_dirs()
    with _lock:
        tmp = STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2) + "\n")
        tmp.replace(STATE_PATH)


def new_id(prefix: str = "") -> str:
    u = uuid.uuid4().hex[:10]
    return f"{prefix}{u}" if prefix else u
