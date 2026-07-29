from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import keychain
from .hosts import upsert_host, write_rclone_conf
from .mounts import upsert_mount
from .paths import ROOT, prefer_tilde
from .state import load, save


def migrate_if_needed() -> dict[str, Any]:
    st = load()
    if st.get("prefs", {}).get("auto_migrate_done"):
        return {"ok": True, "skipped": True}

    report: dict[str, Any] = {"hosts": 0, "mounts": 0, "keychain": False, "notes": []}

    # 1) ~/.wasabi.json credentials → default wasabi host
    wasabi_json = Path.home() / ".wasabi.json"
    access = secret = None
    if wasabi_json.is_file():
        try:
            d = json.loads(wasabi_json.read_text())
            access = d.get("access-key") or d.get("accessKeyId")
            secret = d.get("secret-key") or d.get("secretAccessKey")
        except Exception as e:
            report["notes"].append(f"wasabi.json read error: {e}")

    host_id = None
    if access and secret:
        h = upsert_host(
            name="wasabi",
            type_="s3",
            provider="Wasabi",
            endpoint="https://s3.us-east-1.wasabisys.com",
            region="us-east-1",
            access_key=access,
            secret_key=secret,
        )
        host_id = h["id"]
        report["hosts"] = 1
        report["keychain"] = True
        report["notes"].append("Imported credentials from ~/.wasabi.json into Keychain")
    elif not load().get("hosts"):
        report["notes"].append("No ~/.wasabi.json — add a host in the UI")

    # 2) legacy mounts.json
    legacy = ROOT / "config" / "mounts.json"
    if legacy.is_file() and host_id:
        try:
            data = json.loads(legacy.read_text())
            for m in data.get("mounts") or []:
                remote = m.get("remote") or ""
                # wasabi:nas-tsang2
                remote_path = ""
                if ":" in remote:
                    _, _, remote_path = remote.partition(":")
                else:
                    remote_path = remote
                kind = (m.get("mount_kind") or "nfs").lower()
                if kind not in ("fuse", "nfs"):
                    kind = "nfs"
                # Keep configured path; invent a generic default only if missing.
                # Never hardcode a product path — that belongs in user config only.
                raw_path = m.get("path") or f"~/CloudMount/{m.get('id') or 'mount'}"
                upsert_mount(
                    label=m.get("label") or m.get("id") or "mount",
                    host_id=host_id,
                    remote_path=remote_path,
                    path=prefer_tilde(raw_path),
                    mount_kind=kind,
                    vfs_cache_mode=m.get("vfs_cache_mode") or "full",
                )
                report["mounts"] += 1
            report["notes"].append(f"Imported {report['mounts']} mounts from config/mounts.json")
        except Exception as e:
            report["notes"].append(f"mounts.json import error: {e}")

    st = load()
    st.setdefault("prefs", {})["auto_migrate_done"] = True
    # Prefer NFS as default when available
    st["prefs"]["default_mount_kind"] = "nfs"
    save(st)
    write_rclone_conf()
    report["ok"] = True
    return report
