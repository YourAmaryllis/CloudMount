"""Discover rclone backend types and config fields from the live binary."""

from __future__ import annotations

import re
import time
from typing import Any, Optional

from .rclone_bin import ensure_rclone, run_rclone

_cache: dict[str, Any] = {"ts": 0.0, "backends": None, "schemas": {}}
_CACHE_TTL = 3600.0


def _parse_backends_list(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for line in text.splitlines():
        m = re.match(r"^\s{2}(\S+)\s{2,}(.+)$", line)
        if not m:
            continue
        name, desc = m.group(1), m.group(2).strip()
        if name in ("To", "All") or name.startswith("-"):
            continue
        out.append({"type": name, "description": desc})
    # stable sort by type name
    out.sort(key=lambda x: x["type"].lower())
    return out


def list_backends(force: bool = False) -> list[dict[str, str]]:
    now = time.time()
    if (
        not force
        and _cache["backends"] is not None
        and now - _cache["ts"] < _CACHE_TTL
    ):
        return _cache["backends"]  # type: ignore
    ensure_rclone()
    r = run_rclone(["help", "backends"])
    text = (r.stdout or "") + (r.stderr or "")
    backends = _parse_backends_list(text)
    if not backends:
        # fallback minimal set
        backends = [
            {"type": "s3", "description": "S3-compatible (AWS, Wasabi, …)"},
            {"type": "drive", "description": "Google Drive"},
            {"type": "sftp", "description": "SSH/SFTP"},
            {"type": "b2", "description": "Backblaze B2"},
            {"type": "webdav", "description": "WebDAV"},
            {"type": "local", "description": "Local Disk"},
        ]
    _cache["backends"] = backends
    _cache["ts"] = now
    return backends


def _parse_backend_help(text: str) -> dict[str, Any]:
    """Parse `rclone help backend <type>` into fields + provider examples."""
    fields: list[dict[str, Any]] = []
    current: Optional[dict[str, Any]] = None
    examples: list[dict[str, str]] = []
    in_examples = False
    pending_example_value: Optional[str] = None

    def flush() -> None:
        nonlocal current, examples, in_examples, pending_example_value
        if current:
            if examples:
                current["examples"] = examples
            fields.append(current)
        current = None
        examples = []
        in_examples = False
        pending_example_value = None

    for line in text.splitlines():
        # New option header: #### --s3-provider
        m = re.match(r"^####\s+--[\w-]+-([\w-]+)\s*$", line)
        if m:
            flush()
            current = {
                "name": m.group(1).replace("-", "_"),
                "flag": line.strip().lstrip("#").strip(),
                "help": "",
                "type": "string",
                "required": False,
                "is_password": False,
                "examples": [],
            }
            continue
        if current is None:
            continue
        if line.startswith("Properties:"):
            continue
        m = re.match(r"^- Config:\s+(\S+)", line)
        if m:
            current["name"] = m.group(1)
            continue
        m = re.match(r"^- Type:\s+(\S+)", line)
        if m:
            current["type"] = m.group(1)
            if m.group(1).lower() == "password" or "Password" in m.group(1):
                current["is_password"] = True
            continue
        m = re.match(r"^- Required:\s+(\S+)", line)
        if m:
            current["required"] = m.group(1).lower() == "true"
            continue
        if line.strip() == "- Examples:":
            in_examples = True
            continue
        if in_examples:
            #   - "Wasabi"
            m = re.match(r'^\s{2}-\s+"([^"]*)"', line)
            if m:
                pending_example_value = m.group(1)
                continue
            #     - Description
            m = re.match(r"^\s{4}-\s+(.+)$", line)
            if m and pending_example_value is not None:
                examples.append(
                    {"value": pending_example_value, "help": m.group(1).strip()}
                )
                pending_example_value = None
                continue
            if line.startswith("####") or line.startswith("###"):
                in_examples = False
            continue
        # prose help lines before Properties
        if line.startswith("- ") or line.startswith("####") or line.startswith("###"):
            continue
        if line.strip() and not current.get("help"):
            current["help"] = line.strip()
            if "internal use only" in line.lower():
                current["internal"] = True
        elif line.strip() and current.get("help") and len(current["help"]) < 200:
            current["help"] += " " + line.strip()
            if "internal use only" in line.lower():
                current["internal"] = True

    flush()

    # Capture help text while parsing already done — mark internal / runtime fields
    # These are generated by rclone at login, or one-shot codes, not user setup.
    always_internal = {
        "2fa",  # one-time 6-digit code (runtime), not the authenticator secret
        "client_uid",
        "client_access_token",
        "client_refresh_token",
        "client_salted_key_pass",
        "token",  # often OAuth token blob written by rclone after auth
        "auth_url",
        "token_url",
    }
    # Mark secret-ish fields (Keychain only — never plain in UI persistence / conf)
    always_secret = {
        "secret_access_key",
        "secret_key",
        "password",
        "pass",
        "key",
        "token",
        "client_secret",
        "auth_token",
        "access_token",
        "key_file_pass",
        "access_key_id",
        "access_key",
        "2fa",
        "otp_secret_key",
        "mailbox_password",
        "client_uid",
        "client_access_token",
        "client_refresh_token",
        "client_salted_key_pass",
        "service_account_credentials",
    }
    never_secret = {
        "user",
        "username",
        "endpoint",
        "region",
        "provider",
        "acl",
        "host",
        "port",
        "encoding",
        "description",
        "app_version",
    }
    # Friendly labels for setup UI
    friendly_labels = {
        "username": "Username / email",
        "password": "Password",
        "otp_secret_key": "Authenticator secret (TOTP key from 2FA setup)",
        "mailbox_password": "Mailbox password (two-password Proton accounts only)",
        "access_key_id": "Access key ID",
        "secret_access_key": "Secret access key",
        "provider": "Provider",
        "endpoint": "Endpoint",
        "region": "Region",
        "client_id": "OAuth client ID",
        "client_secret": "OAuth client secret",
        "service_account_file": "Service account JSON file path",
        "host": "Host",
        "user": "User",
        "pass": "Password",
        "port": "Port",
        "env_auth": "Use environment / runtime credentials",
        "profile": "AWS shared config profile name",
        "shared_credentials_file": "Path to AWS credentials file",
        "session_token": "AWS session token (temporary keys)",
        "role_arn": "IAM role ARN to assume",
    }
    for f in fields:
        n = (f.get("name") or "").lower()
        help_l = (f.get("help") or "").lower()
        f["internal"] = (
            n in always_internal
            or "internal use only" in help_l
            or "internal use" in help_l
        )
        if n in never_secret:
            f["is_secret"] = False
        elif f.get("is_password") or n in always_secret or "secret" in n or n.endswith("_password"):
            f["is_secret"] = True
        elif n.endswith("_key") and n not in ("public_key",):
            f["is_secret"] = True
        else:
            f["is_secret"] = False
        f["label"] = friendly_labels.get(n) or n.replace("_", " ")
        # Setup-relevant: required, or common auth/config (not internal, not obscure flags)
        f["show_in_setup"] = (not f["internal"]) and (
            f.get("required")
            or n
            in (
                "username",
                "password",
                "otp_secret_key",
                "mailbox_password",
                "provider",
                "endpoint",
                "region",
                "env_auth",
                "access_key_id",
                "secret_access_key",
                "profile",
                "shared_credentials_file",
                "user",
                "pass",
                "host",
                "port",
                "client_id",
                "client_secret",
                "service_account_file",
                "scope",
                "acl",
                "location_constraint",
                "account",
                "key",
            )
            or bool(f.get("examples"))
        )

    # provider field examples for dropdowns
    provider_field = next((f for f in fields if f.get("name") == "provider"), None)
    providers = (provider_field or {}).get("examples") or []

    setup_fields = [f for f in fields if f.get("show_in_setup")]
    advanced_fields = [
        f
        for f in fields
        if not f.get("internal") and not f.get("show_in_setup")
    ]

    return {
        "fields": fields,
        "setup_fields": setup_fields,
        "advanced_fields": advanced_fields,
        "providers": providers,
        # common credentials we always support in UI for keychain
        "credential_fields": [
            f["name"]
            for f in fields
            if f.get("is_secret")
            or f["name"]
            in (
                "access_key_id",
                "secret_access_key",
                "user",
                "pass",
                "password",
                "key",
                "token",
                "client_id",
                "client_secret",
                "otp_secret_key",
                "mailbox_password",
            )
        ],
    }


# S3: only these matter for day-to-day host setup (SSE/KMS/etc. work automatically).
_S3_SETUP_NAMES = (
    "provider",
    "region",
    "endpoint",
    "access_key_id",
    "secret_access_key",
)
# Optional rare knobs — collapsed under Advanced, not required for AWS profile mounts.
_S3_ADVANCED_ALLOW = {
    "acl",
    "location_constraint",
    "force_path_style",
    "storage_class",
    "server_side_encryption",
    "sse_kms_key_id",
    "shared_credentials_file",
}


def backend_schema(type_name: str, force: bool = False) -> dict[str, Any]:
    type_name = (type_name or "").strip()
    if not type_name:
        return {"ok": False, "error": "type required", "fields": [], "providers": []}
    if not force and type_name in _cache["schemas"]:
        return _cache["schemas"][type_name]
    ensure_rclone()
    r = run_rclone(["help", "backend", type_name])
    text = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0 and "didn't find" in text.lower():
        return {"ok": False, "error": f"Unknown backend: {type_name}", "fields": [], "providers": []}
    parsed = _parse_backend_help(text)
    fields = parsed["fields"]
    setup_fields = parsed.get("setup_fields") or [
        f for f in fields if f.get("show_in_setup") and not f.get("internal")
    ]
    advanced_fields = parsed.get("advanced_fields") or [
        f for f in fields if not f.get("internal") and not f.get("show_in_setup")
    ]

    if type_name == "s3":
        by_name = {f.get("name"): f for f in fields if f.get("name")}
        setup_fields = [by_name[n] for n in _S3_SETUP_NAMES if n in by_name]
        # Drop env_auth / profile from rclone list — CloudMount owns auth UI
        advanced_fields = [
            f
            for f in fields
            if f.get("name") in _S3_ADVANCED_ALLOW and not f.get("internal")
        ]

    out = {
        "ok": True,
        "type": type_name,
        "fields": fields,
        "setup_fields": setup_fields,
        "advanced_fields": advanced_fields,
        "providers": parsed["providers"],
        "credential_fields": parsed["credential_fields"],
    }
    _cache["schemas"][type_name] = out
    return out


def backends_catalog() -> dict[str, Any]:
    return {"ok": True, "backends": list_backends()}
