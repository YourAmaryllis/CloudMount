"""JSON-serializable service API used by CLI and GUI."""

from __future__ import annotations

from typing import Any, Optional

from . import __version__, capabilities, hosts, keychain, migrate, mounts, state
from .paths import APP_SUPPORT, RCLONE_CONF, STATE_PATH, LOG_DIR
from .rclone_bin import ensure_rclone, rclone_version


def status() -> dict[str, Any]:
    migrate.migrate_if_needed()
    caps = capabilities.report()
    mlist = mounts.list_mounts()
    hlist = hosts.list_hosts()
    up = sum(1 for m in mlist if m.get("mounted"))
    return {
        "version": __version__,
        "capabilities": caps,
        "prefs": state.load().get("prefs"),
        "hosts": [
            {
                "id": h["id"],
                "name": h.get("name"),
                "type": h.get("type"),
                "provider": h.get("provider"),
                "endpoint": h.get("endpoint"),
                "region": h.get("region"),
                "has_secrets": bool(keychain.get_host_secret(h["id"], "access_key")),
            }
            for h in hlist
        ],
        "mounts": [
            {
                "id": m["id"],
                "label": m.get("label"),
                "host_id": m.get("host_id"),
                "host_name": (m.get("host") or {}).get("name"),
                "remote_path": m.get("remote_path"),
                "path": m.get("path"),
                "mount_kind": m.get("mount_kind"),
                "vfs_cache_mode": m.get("vfs_cache_mode"),
                "mounted": m.get("mounted"),
            }
            for m in mlist
        ],
        "summary": {"mounts_total": len(mlist), "mounts_up": up, "hosts": len(hlist)},
        "paths": {
            "app_support": str(APP_SUPPORT),
            "state": str(STATE_PATH),
            "rclone_conf": str(RCLONE_CONF),
            "logs": str(LOG_DIR),
        },
        "rclone_version": rclone_version(),
    }


def set_prefs(**kwargs: Any) -> dict[str, Any]:
    st = state.load()
    prefs = st.setdefault("prefs", {})
    for k, v in kwargs.items():
        if k in (
            "enable_fuse",
            "enable_nfs",
            "default_mount_kind",
            "auto_migrate_done",
        ):
            prefs[k] = v
    state.save(st)
    return prefs


def setup() -> dict[str, Any]:
    """First-run: rclone binary + migrate + capabilities."""
    try:
        ensure_rclone()
    except Exception as e:
        return {"ok": False, "error": f"rclone download failed: {e}"}
    mig = migrate.migrate_if_needed()
    caps = capabilities.report()
    return {"ok": True, "migrate": mig, "capabilities": caps, "rclone_version": rclone_version()}
