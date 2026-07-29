from __future__ import annotations

import configparser
import io
import re
from typing import Any, Optional

from . import keychain
from .paths import RCLONE_CONF, prefer_tilde
from .rclone_bin import run_rclone
from .state import load, new_id, save


def list_hosts() -> list[dict[str, Any]]:
    st = load()
    return list(st.get("hosts") or [])


def get_host(host_id: str) -> Optional[dict[str, Any]]:
    for h in list_hosts():
        if h.get("id") == host_id:
            return h
    return None


def get_host_by_name(name: str) -> Optional[dict[str, Any]]:
    for h in list_hosts():
        if h.get("name") == name:
            return h
    return None


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
    return s or new_id("host-")


def write_rclone_conf() -> None:
    """Write managed rclone.conf (no secrets — env_auth / runtime env)."""
    st = load()
    cp = configparser.ConfigParser()
    for h in st.get("hosts") or []:
        name = h.get("name") or ""
        if not name:
            continue
        section = name
        # configparser needs lower-case? rclone uses any case; ConfigParser lowercases by default
        cp.optionxform = str  # type: ignore
        cp[section] = {}
        t = h.get("type") or "s3"
        cp[section]["type"] = t
        if t == "s3":
            cp[section]["provider"] = h.get("provider") or "Wasabi"
            cp[section]["env_auth"] = "true"
            if h.get("endpoint"):
                cp[section]["endpoint"] = h["endpoint"]
            if h.get("region"):
                cp[section]["region"] = h["region"]
            if h.get("acl"):
                cp[section]["acl"] = h["acl"]
        else:
            # generic passthrough of non-secret fields
            for k, v in (h.get("options") or {}).items():
                if v is not None and str(v) != "":
                    cp[section][str(k)] = str(v)
    RCLONE_CONF.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    cp.write(buf)
    # ConfigParser writes [section]\nkey = value — rclone accepts spaces around =
    text = buf.getvalue()
    # Prefer no spaces around = for classic rclone style
    lines = []
    for line in text.splitlines():
        if "=" in line and not line.strip().startswith(";") and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            lines.append(f"{k.strip()} = {v.strip()}")
        else:
            lines.append(line)
    RCLONE_CONF.write_text("\n".join(lines) + ("\n" if lines else ""))


def host_env(host_id: str) -> dict[str, str]:
    """Env vars for rclone when using env_auth (S3)."""
    env: dict[str, str] = {}
    ak = keychain.get_host_secret(host_id, "access_key")
    sk = keychain.get_host_secret(host_id, "secret_key")
    if ak:
        env["AWS_ACCESS_KEY_ID"] = ak
    if sk:
        env["AWS_SECRET_ACCESS_KEY"] = sk
    return env


def upsert_host(
    *,
    host_id: Optional[str] = None,
    name: str,
    type_: str = "s3",
    provider: str = "Wasabi",
    endpoint: str = "https://s3.us-east-1.wasabisys.com",
    region: str = "us-east-1",
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    options: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    st = load()
    name = _slug(name)
    existing = None
    if host_id:
        existing = next((h for h in st["hosts"] if h["id"] == host_id), None)
    if not existing:
        # name uniqueness
        if any(h.get("name") == name and h.get("id") != host_id for h in st["hosts"]):
            raise ValueError(f"Host name already exists: {name}")
        host_id = host_id or new_id("h")
        existing = {"id": host_id}
        st["hosts"].append(existing)

    existing.update(
        {
            "id": host_id,
            "name": name,
            "type": type_,
            "provider": provider,
            "endpoint": endpoint,
            "region": region,
            "options": options or existing.get("options") or {},
        }
    )
    if access_key:
        keychain.set_host_secret(host_id, "access_key", access_key)
    if secret_key:
        keychain.set_host_secret(host_id, "secret_key", secret_key)

    save(st)
    write_rclone_conf()
    return existing


def delete_host(host_id: str) -> None:
    st = load()
    # block if mounts reference it
    for m in st.get("mounts") or []:
        if m.get("host_id") == host_id:
            raise ValueError(
                f"Host is used by mount “{m.get('label') or m.get('id')}”. Remove mounts first."
            )
    st["hosts"] = [h for h in st["hosts"] if h.get("id") != host_id]
    save(st)
    keychain.delete_host_secrets(host_id)
    write_rclone_conf()


def test_host(host_id: str) -> dict[str, Any]:
    h = get_host(host_id)
    if not h:
        return {"ok": False, "error": "Host not found"}
    write_rclone_conf()
    env = host_env(host_id)
    if h.get("type") == "s3" and (not env.get("AWS_ACCESS_KEY_ID") or not env.get("AWS_SECRET_ACCESS_KEY")):
        return {"ok": False, "error": "Missing access_key/secret_key in Keychain for this host"}
    r = run_rclone(
        ["lsd", f"{h['name']}:", "--max-depth", "1"],
        env=env,
        config=RCLONE_CONF,
    )
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        return {"ok": False, "error": out[-1500:] or f"exit {r.returncode}"}
    # parse bucket names from lsd
    buckets = []
    for line in (r.stdout or "").splitlines():
        parts = line.split()
        if parts:
            buckets.append(parts[-1])
    return {"ok": True, "buckets": buckets, "raw": (r.stdout or "")[:2000]}


def list_remote_paths(host_id: str, prefix: str = "") -> dict[str, Any]:
    """List directories under host:prefix.

    prefix examples: "" (buckets), "my-bucket", "my-bucket/subfolder"
    Each entry includes name and full remote_path (prefix/name) for mounting.
    """
    h = get_host(host_id)
    if not h:
        return {"ok": False, "error": "Host not found"}
    write_rclone_conf()
    prefix = (prefix or "").strip().strip("/")
    path = f"{h['name']}:{prefix}" if prefix else f"{h['name']}:"
    r = run_rclone(["lsd", path], env=host_env(host_id), config=RCLONE_CONF)
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or r.stdout or "")[-1500:]}
    entries = []
    for line in (r.stdout or "").splitlines():
        parts = line.split()
        if not parts:
            continue
        name = parts[-1]
        full = f"{prefix}/{name}" if prefix else name
        entries.append({"name": name, "remote_path": full})
    # parent for UI navigation
    parent = ""
    if prefix and "/" in prefix:
        parent = prefix.rsplit("/", 1)[0]
    elif prefix:
        parent = ""  # up to root (buckets)
    return {
        "ok": True,
        "prefix": prefix,
        "parent": parent if prefix else None,
        "entries": entries,
        # backwards compat for older UI
        "names": [e["name"] for e in entries],
    }
