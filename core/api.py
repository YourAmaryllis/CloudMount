"""JSON-serializable service API used by CLI and GUI."""

from __future__ import annotations

from typing import Any, Optional

from . import __version__, capabilities, hosts, keychain, migrate, mounts, state
from .paths import APP_SUPPORT, RCLONE_CONF, STATE_PATH, LOG_DIR
from .rclone_bin import ensure_rclone, rclone_version


def status(light: bool = False) -> dict[str, Any]:
    """Full status snapshot.

    `light=True` skips per-host Keychain probes (auth_mode/aws_profile/
    has_secrets) — meant for hot polling paths, like the SwiftBar menu-bar
    plugin, that only read mounts/summary and never look at `hosts`.
    """
    migrate.migrate_if_needed()
    caps = capabilities.report()
    mlist = mounts.list_mounts()
    up = sum(1 for m in mlist if m.get("mounted"))
    if light:
        hosts_out: list[dict[str, Any]] = []
        hosts_count = len(hosts.list_hosts())
    else:
        hlist = hosts.list_hosts()
        hosts_count = len(hlist)
        hosts_out = [
            {
                "id": h["id"],
                "name": h.get("name"),
                "type": h.get("type"),
                "provider": h.get("provider") or (h.get("options") or {}).get("provider"),
                "endpoint": h.get("endpoint") or (h.get("options") or {}).get("endpoint"),
                "region": h.get("region") or (h.get("options") or {}).get("region"),
                "options": h.get("options") or {},
                "auth_mode": (
                    hosts.s3_auth_mode(h)
                    if (h.get("type") or "") == "s3"
                    else None
                ),
                "aws_profile": (
                    hosts.s3_profile_name(h)
                    if (h.get("type") or "") == "s3"
                    else None
                ),
                # One Keychain probe per host (cached in-process) — avoid a
                # storm of security(1) calls on every status refresh.
                "has_secrets": bool(
                    keychain.get_host_secret(h["id"], "password")
                    or keychain.get_host_secret(h["id"], "access_key")
                    or keychain.get_host_secret(h["id"], "access_key_id")
                    or keychain.get_host_secret(h["id"], "token")
                    or (
                        (h.get("type") or "") == "s3"
                        and hosts.s3_auth_mode(h) == "profile"
                        and hosts.s3_profile_name(h)
                    )
                ),
            }
            for h in hlist
        ]
    return {
        "version": __version__,
        "capabilities": caps,
        "prefs": state.load().get("prefs"),
        "hosts": hosts_out,
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
        "summary": {"mounts_total": len(mlist), "mounts_up": up, "hosts": hosts_count},
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
    """First-run: rclone binary + migrate + capabilities + menu-bar host."""
    try:
        ensure_rclone()
    except Exception as e:
        return {"ok": False, "error": f"rclone download failed: {e}"}
    mig = migrate.migrate_if_needed()
    scrub = {}
    try:
        from .hosts import scrub_s3_host_options, scrub_secrets_from_state

        scrub = scrub_secrets_from_state()
        scrub_s3 = scrub_s3_host_options()
        scrub = {**scrub, "s3_options": scrub_s3}
    except Exception as e:
        scrub = {"ok": False, "error": str(e)}
    caps = capabilities.report(fresh=True)
    menubar = _install_menubar_if_needed()
    return {
        "ok": True,
        "migrate": mig,
        "scrub": scrub,
        "capabilities": caps,
        "menubar": menubar,
        "rclone_version": rclone_version(),
        "note": (
            "Keychain is only written when you save host credentials. "
            "Mount/Test no longer update Keychain (session tokens use a local file)."
        ),
    }


def _install_menubar_if_needed() -> dict[str, Any]:
    """Best-effort, one-time SwiftBar wiring on macOS (macOS only, non-fatal)."""
    import platform

    if platform.system() != "Darwin":
        return {"ok": True, "skipped": True, "reason": "not macOS"}

    try:
        from scripts.install_menubar import cleanup_legacy_plugin

        cleanup = cleanup_legacy_plugin()
    except Exception as e:
        cleanup = {"error": str(e)}

    st = state.load()
    if st.get("prefs", {}).get("menubar_install_done"):
        return {"ok": True, "skipped": True, "cleanup": cleanup}

    result: dict[str, Any]
    try:
        from scripts.install_menubar import install as install_menubar

        result = install_menubar()
    except Exception as e:
        result = {"ok": False, "error": str(e)}
    result["cleanup"] = cleanup

    st = state.load()
    st.setdefault("prefs", {})["menubar_install_done"] = True
    state.save(st)
    return result


def fix_keychain() -> dict[str, Any]:
    """Optional: open ACL on existing Keychain items. Prefer not needed after session-store fix.

    Warning: each rewrite can prompt for the login password once. Avoid unless
    reads are still prompting after restart.
    """
    result = keychain.reacl_all_host_secrets()
    return result
