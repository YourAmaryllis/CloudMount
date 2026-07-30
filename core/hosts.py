from __future__ import annotations

import configparser
import io
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Optional

from . import aws_auth, keychain, session_store
from .backends import backend_schema
from .paths import RCLONE_CONF, RCLONE_RUNTIME_CONF
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


# Fields stored in Keychain only — never state options or rclone.conf plaintext
_SECRET_OPTION_NAMES = {
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
    "service_account_credentials",
    "access_key_id",
    "access_key",
    # 2FA / OTP — never plain text on disk
    "2fa",
    "otp_secret_key",
    "mailbox_password",
    "client_uid",
    "client_access_token",
    "client_refresh_token",
    "client_salted_key_pass",
}


def _is_secret_field(name: str) -> bool:
    n = (name or "").lower()
    if n in _SECRET_OPTION_NAMES:
        return True
    if "secret" in n or n.endswith("_password") or n.endswith("_token"):
        return True
    if n in ("2fa", "otp", "otp_secret_key"):
        return True
    return False


def write_rclone_conf() -> None:
    """Write managed rclone.conf. Secrets use env_auth or are omitted (Keychain at runtime)."""
    st = load()
    cp = configparser.ConfigParser()
    cp.optionxform = str  # type: ignore
    for h in st.get("hosts") or []:
        name = h.get("name") or ""
        if not name:
            continue
        section = name
        cp[section] = {}
        t = h.get("type") or "s3"
        cp[section]["type"] = t
        opts = dict(h.get("options") or {})

        # Legacy s3 convenience fields
        if t == "s3":
            if h.get("provider") and "provider" not in opts:
                opts["provider"] = h["provider"]
            if h.get("endpoint") and "endpoint" not in opts:
                opts["endpoint"] = h["endpoint"]
            if h.get("region") and "region" not in opts:
                opts["region"] = h["region"]
            mode = s3_auth_mode(h)
            if mode == "profile":
                opts["env_auth"] = "true"
                # Never leave static keys in conf for profile hosts
                opts.pop("access_key_id", None)
                opts.pop("secret_access_key", None)
            elif keychain.get_host_secret(h["id"], "access_key") or keychain.get_host_secret(
                h["id"], "access_key_id"
            ):
                # Static keys → env_auth + AWS_* at runtime (not written into conf)
                opts.setdefault("env_auth", "true")

        for k, v in opts.items():
            if v is None or str(v) == "":
                continue
            if _is_secret_field(str(k)):
                continue  # never write secrets to disk (password, 2fa, otp, tokens, …)
            # auth_mode is CloudMount-only (not an rclone option)
            if str(k) == "auth_mode":
                continue
            cp[section][str(k)] = str(v)

    RCLONE_CONF.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    cp.write(buf)
    lines = []
    for line in buf.getvalue().splitlines():
        if "=" in line and not line.strip().startswith(";") and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            lines.append(f"{k.strip()} = {v.strip()}")
        else:
            lines.append(line)
    RCLONE_CONF.write_text("\n".join(lines) + ("\n" if lines else ""))


def _obscure_password(plain: str) -> str:
    """rclone password-type config values must be obscured (e.g. protondrive).

    Never fall back to plain text — rclone then fails with
    "couldn't decrypt password: input too short when revealing password".
    """
    plain = (plain or "").strip()
    if not plain:
        return plain
    r = run_rclone(["obscure", plain])
    out = (r.stdout or "").strip().splitlines()
    if r.returncode == 0 and out and out[0].strip():
        return out[0].strip()
    err = ((r.stderr or "") + (r.stdout or "")).strip() or f"exit {r.returncode}"
    raise RuntimeError(f"rclone obscure failed: {err}")


# Fields that rclone treats as Password type (must be obscured in config/env)
_OBSCURE_FIELDS = {
    "password",
    "pass",
    "mailbox_password",
    "otp_secret_key",
    "key_file_pass",
    "client_salted_key_pass",
}

# Proton Drive session tokens written back by rclone after successful login
_SESSION_TOKEN_FIELDS = (
    "client_uid",
    "client_access_token",
    "client_refresh_token",
    "client_salted_key_pass",
)


def _remote_env_prefix(remote_name: str) -> str:
    # rclone: RCLONE_CONFIG_MYREMOTE_OPTION — name uppercased, - → _
    return remote_name.upper().replace("-", "_")


def s3_auth_mode(host: dict[str, Any]) -> str:
    """Return ``profile`` or ``static`` for an S3 host."""
    opts = host.get("options") or {}
    mode = (opts.get("auth_mode") or "").strip().lower()
    if mode in ("profile", "static"):
        return mode
    # Infer: profile option set without keys → profile
    if opts.get("profile") and not (
        keychain.get_host_secret(host["id"], "access_key")
        or keychain.get_host_secret(host["id"], "access_key_id")
    ):
        return "profile"
    # env_auth true and no keys
    if str(opts.get("env_auth") or "").lower() in ("true", "1") and not (
        keychain.get_host_secret(host["id"], "access_key")
        or keychain.get_host_secret(host["id"], "access_key_id")
    ):
        return "profile"
    return "static"


def s3_profile_name(host: dict[str, Any]) -> str:
    opts = host.get("options") or {}
    return (opts.get("profile") or opts.get("aws_profile") or "").strip()


def host_env(host_id: str) -> dict[str, str]:
    """Env for rclone — AWS keys for static S3, or AWS_PROFILE for profile mode.

    Password-type backends (protondrive, etc.) get secrets via
    write_runtime_conf() (obscured into a temp conf file).
    """
    env: dict[str, str] = {}
    h = get_host(host_id)
    if not h:
        return env
    t = (h.get("type") or "").lower()
    if t == "s3" and s3_auth_mode(h) == "profile":
        profile = s3_profile_name(h)
        if profile:
            env["AWS_PROFILE"] = profile
            env["AWS_DEFAULT_PROFILE"] = profile
        # Do not inject static keys over a profile session
        return env
    for field, env_name in (
        ("access_key", "AWS_ACCESS_KEY_ID"),
        ("access_key_id", "AWS_ACCESS_KEY_ID"),
        ("secret_key", "AWS_SECRET_ACCESS_KEY"),
        ("secret_access_key", "AWS_SECRET_ACCESS_KEY"),
    ):
        val = keychain.get_host_secret(host_id, field)
        if val and env_name not in env:
            env[env_name] = val
    return env


def _keychain_secret_names(host_id: str, type_: str) -> list[str]:
    """Fields that exist in Keychain for this host (minimal probes per type)."""
    schema = backend_schema(type_ or "s3")
    # Prefer schema credential list + a small type-specific set so we do not
    # call `security` dozens of times for fields that never exist.
    t = (type_ or "s3").lower()
    if t == "s3":
        candidates = [
            "access_key",
            "access_key_id",
            "secret_key",
            "secret_access_key",
        ]
    elif t == "protondrive":
        # Session tokens live in session_store (disk), not Keychain probes.
        candidates = [
            "password",
            "otp_secret_key",
            "2fa",
            "mailbox_password",
        ]
    else:
        candidates = list(schema.get("credential_fields") or [])
        candidates += [
            "password",
            "token",
            "client_secret",
            "otp_secret_key",
            "mailbox_password",
            "key",
            *_SESSION_TOKEN_FIELDS,
        ]
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for n in candidates:
        if n in seen:
            continue
        seen.add(n)
        if keychain.get_host_secret(host_id, n):
            out.append(n)
    return out


def _parse_conf_sections(text: str) -> tuple[dict[str, list[str]], list[str]]:
    sections: dict[str, list[str]] = {}
    order: list[str] = []
    cur = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            cur = s[1:-1]
            if cur not in sections:
                sections[cur] = []
                order.append(cur)
            continue
        if cur is not None:
            sections[cur].append(line)
    return sections, order


def _section_kv(lines: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in lines:
        if "=" not in line or line.strip().startswith(("#", ";")):
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def capture_session_tokens(host_id: str, conf_path: Optional[Path] = None) -> int:
    """After a successful rclone call, persist Proton client_* tokens from conf.

    rclone writes these into the config on login so later runs can skip 2FA.
    Stored in session_tokens.json (0600) — NOT Keychain — so remounts do not
    trigger macOS Keychain password dialogs on every write.
    """
    h = get_host(host_id)
    if not h or (h.get("type") or "") != "protondrive":
        return 0
    path = conf_path or RCLONE_RUNTIME_CONF
    if not path.exists():
        return 0
    sections, _ = _parse_conf_sections(path.read_text())
    lines = sections.get(h.get("name") or "") or []
    kv = _section_kv(lines)
    fields = {
        fname: (kv.get(fname) or "").strip()
        for fname in _SESSION_TOKEN_FIELDS
        if (kv.get(fname) or "").strip()
    }
    return session_store.set_session(host_id, fields)


def ensure_host_runtime_secrets(host_id: str) -> Optional[str]:
    """Return error string if host lacks secrets needed for a live rclone call."""
    h = get_host(host_id)
    if not h:
        return "Host not found"
    t = (h.get("type") or "").lower()
    if t == "protondrive":
        if not (h.get("options") or {}).get("username"):
            return "Proton Drive host needs a username (email)"
        if not keychain.get_host_secret(host_id, "password"):
            return "Proton Drive password missing in Keychain — edit host and re-enter password"
        # otp optional if session tokens exist, or if account has no 2FA
        has_otp = bool(keychain.get_host_secret(host_id, "otp_secret_key"))
        has_session = bool(
            session_store.get_session_field(host_id, "client_access_token")
            or keychain.get_host_secret(host_id, "client_access_token")
        )
        if not has_otp and not has_session:
            return (
                "Proton Drive 2FA: store Authenticator secret as otp_secret_key "
                "(the base32 key from 2FA setup, not a 6-digit code), then Test again"
            )
    elif t == "s3":
        mode = s3_auth_mode(h)
        if mode == "profile":
            if not s3_profile_name(h):
                return (
                    "S3 profile mode needs an AWS profile name "
                    "(from ~/.aws/config or credentials)."
                )
        else:
            if not (
                keychain.get_host_secret(host_id, "access_key")
                or keychain.get_host_secret(host_id, "access_key_id")
            ):
                return "S3 access key missing in Keychain (or switch host to Profile auth)"
            if not (
                keychain.get_host_secret(host_id, "secret_key")
                or keychain.get_host_secret(host_id, "secret_access_key")
            ):
                return "S3 secret key missing in Keychain"
    return None


def prepare_s3_host(host_id: str, *, try_login: bool = True) -> Optional[dict[str, Any]]:
    """Deprecated name: only used for on-failure SSO refresh (not proactive).

    Prefer :func:`refresh_s3_after_auth_failure`. Returns None if N/A or login OK,
    or ``{ok: False, error: ...}`` if login failed.
    """
    return refresh_s3_after_auth_failure(host_id) if try_login else None


def refresh_s3_after_auth_failure(host_id: str) -> Optional[dict[str, Any]]:
    """Run ``aws sso login`` only after a failed rclone/AWS call (profile hosts).

    We intentionally do **not** proactively refresh on every Test/Browse/Mount —
    that would open a browser while the user is idle or just listing dirs.

    Returns:
      None — not a profile host, or login succeeded (caller should retry)
      dict with ok=False — login failed / not applicable SSO
    """
    h = get_host(host_id)
    if not h or (h.get("type") or "").lower() != "s3":
        return None
    if s3_auth_mode(h) != "profile":
        return None
    profile = s3_profile_name(h)
    if not profile:
        return {"ok": False, "error": "AWS profile name missing", "code": "aws_auth"}

    login = aws_auth.sso_login(profile)
    if login.get("ok"):
        return None  # success → caller retries the operation
    return {
        "ok": False,
        "error": login.get("error") or "AWS SSO login failed",
        "aws_login_ran": True,
        "code": "aws_auth",
        "not_sso": login.get("not_sso"),
    }


def _format_s3_rclone_error(out: str, host: dict[str, Any]) -> str:
    profile = s3_profile_name(host) if s3_auth_mode(host) == "profile" else ""
    msg = aws_auth.friendly_aws_error(out, profile=profile)
    if aws_auth.is_auth_failure(out) and s3_auth_mode(host) == "profile":
        msg += (
            f"\n\nTry: aws sso login --profile {profile or 'YOUR_PROFILE'}"
            if profile
            else "\n\nTry refreshing AWS credentials for this profile."
        )
    return msg


def write_runtime_conf(host_ids: Optional[list[str]] = None) -> Path:
    """Write rclone.runtime.conf = public conf + Keychain secrets (obscured).

    Permanent rclone.conf never holds secrets. Proton Drive and similar need
    password/otp in the config file as obscured values — env vars fail.
    Runtime file mode 0o600 under Application Support.
    """
    write_rclone_conf()
    text = RCLONE_CONF.read_text() if RCLONE_CONF.exists() else ""
    st = load()
    all_hosts = st.get("hosts") or []
    # host_ids currently only used for validation callers; always inject all
    # secrets so concurrent mounts sharing one conf stay valid.
    _ = host_ids

    sections, order = _parse_conf_sections(text)
    host_by_name = {h.get("name"): h for h in all_hosts}
    for name in order:
        h = host_by_name.get(name)
        if not h:
            continue
        # drop any leftover secret keys from section lines
        cleaned = []
        for line in sections[name]:
            if "=" not in line:
                cleaned.append(line)
                continue
            key = line.split("=", 1)[0].strip()
            if _is_secret_field(key):
                continue
            cleaned.append(line)
        for fname in _keychain_secret_names(h["id"], h.get("type") or ""):
            # S3 keys go via env_auth / AWS_*; don't put in conf
            if fname in (
                "access_key",
                "access_key_id",
                "secret_key",
                "secret_access_key",
            ):
                if (h.get("type") or "") == "s3":
                    continue
            plain = keychain.get_host_secret(h["id"], fname)
            if not plain:
                continue
            # skip one-shot 2fa unless user explicitly stored a short code
            if fname == "2fa" and len(plain) > 8:
                continue
            val = plain
            if fname in _OBSCURE_FIELDS:
                val = _obscure_password(plain)
            cleaned.append(f"{fname} = {val}")

        # Proton session tokens from disk store only (never Keychain — writes
        # to Keychain on every mount were the cause of endless password prompts).
        for fname, plain in session_store.get_session(h["id"]).items():
            if fname == "client_salted_key_pass":
                # already rclone-obscured when captured from conf write-back
                cleaned.append(f"{fname} = {plain}")
            else:
                cleaned.append(f"{fname} = {plain}")

        sections[name] = cleaned

    lines_out: list[str] = []
    for name in order:
        lines_out.append(f"[{name}]")
        lines_out.extend(sections.get(name) or [])
        lines_out.append("")
    RCLONE_RUNTIME_CONF.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(lines_out)
    # Atomic replace so a concurrent rclone never sees a half-written conf
    fd, tmp = tempfile.mkstemp(
        prefix="rclone.runtime.",
        suffix=".conf",
        dir=str(RCLONE_RUNTIME_CONF.parent),
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(payload)
        os.chmod(tmp, 0o600)
        os.replace(tmp, RCLONE_RUNTIME_CONF)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return RCLONE_RUNTIME_CONF


def _normalize_host_options(type_: str, options: dict[str, Any], secrets: dict[str, str]) -> None:
    """Move any secret-like values out of options → secrets (Keychain).

    - Never leave 2fa / otp_secret_key / passwords in plain options
    - Long base32 in `2fa` is almost certainly otp_secret_key (TOTP secret), not a 6-digit code
    """
    # Pull every secret-named key out of options into secrets
    for k in list(options.keys()):
        if _is_secret_field(str(k)):
            val = options.pop(k)
            if val is not None and str(val) != "" and not secrets.get(k):
                secrets[str(k)] = str(val)

    twofa = (secrets.get("2fa") or "").strip()
    if twofa and len(twofa) >= 16 and twofa.replace(" ", "").isalnum():
        # TOTP secret, not a one-time code
        if not secrets.get("otp_secret_key"):
            secrets["otp_secret_key"] = twofa.replace(" ", "")
        secrets.pop("2fa", None)


def scrub_secrets_from_state() -> dict[str, Any]:
    """One-shot: move plain-text secrets out of host options into Keychain + rewrite conf."""
    st = load()
    moved = 0
    for h in st.get("hosts") or []:
        opts = dict(h.get("options") or {})
        sec: dict[str, str] = {}
        _normalize_host_options(h.get("type") or "", opts, sec)
        if sec:
            for k, v in sec.items():
                if v:
                    keychain.set_host_secret(h["id"], k, v)
                    moved += 1
        h["options"] = opts
    save(st)
    write_rclone_conf()
    return {"ok": True, "secrets_moved_to_keychain": moved}


def upsert_host(
    *,
    host_id: Optional[str] = None,
    name: str,
    type_: str = "s3",
    provider: Optional[str] = None,
    endpoint: Optional[str] = None,
    region: Optional[str] = None,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    options: Optional[dict[str, Any]] = None,
    secrets: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    st = load()
    name = _slug(name)
    existing = None
    if host_id:
        existing = next((h for h in st["hosts"] if h["id"] == host_id), None)
    if not existing:
        if any(h.get("name") == name and h.get("id") != host_id for h in st["hosts"]):
            raise ValueError(f"Host name already exists: {name}")
        host_id = host_id or new_id("h")
        existing = {"id": host_id, "options": {}}
        st["hosts"].append(existing)

    opts = dict(existing.get("options") or {})
    if options:
        for k, v in options.items():
            if v is None or v == "":
                opts.pop(str(k), None)
            elif not _is_secret_field(str(k)):
                opts[str(k)] = v

    # Legacy convenience → options
    if provider is not None and provider != "":
        opts["provider"] = provider
    if endpoint is not None and endpoint != "":
        opts["endpoint"] = endpoint
    if region is not None and region != "":
        opts["region"] = region

    sec: dict[str, str] = dict(secrets or {})
    if access_key:
        sec["access_key"] = access_key
        sec["access_key_id"] = access_key
    if secret_key:
        sec["secret_key"] = secret_key
        sec["secret_access_key"] = secret_key

    # username is a plain option for protondrive/sftp/etc., not Keychain-only
    for plain_key in ("username", "user", "host", "email"):
        if sec.get(plain_key):
            opts[plain_key] = sec.pop(plain_key)

    _normalize_host_options(type_, opts, sec)

    existing.update(
        {
            "id": host_id,
            "name": name,
            "type": type_,
            "provider": opts.get("provider") or provider or "",
            "endpoint": opts.get("endpoint") or endpoint or "",
            "region": opts.get("region") or region or "",
            "options": opts,
        }
    )

    # Keychain secrets (plain values; obscured only when handed to rclone)
    for k, v in sec.items():
        if v:
            keychain.set_host_secret(host_id, k, v)

    # Normalize S3 auth mode + drop rclone noise options (SSE/bool flags/etc.)
    if type_ == "s3":
        mode = (existing["options"].get("auth_mode") or "").strip().lower()
        if mode not in ("static", "profile"):
            # Infer from what user submitted
            if existing["options"].get("profile") and not (
                keychain.get_host_secret(host_id, "access_key")
                or keychain.get_host_secret(host_id, "access_key_id")
                or sec.get("access_key")
                or sec.get("access_key_id")
            ):
                mode = "profile"
            else:
                mode = "static"
            existing["options"]["auth_mode"] = mode
        if mode == "profile":
            existing["options"]["env_auth"] = "true"
            if not existing["options"].get("provider"):
                existing["options"]["provider"] = "AWS"
            existing["options"].pop("access_key_id", None)
            existing["options"].pop("secret_access_key", None)
        else:
            if keychain.get_host_secret(host_id, "access_key") or keychain.get_host_secret(
                host_id, "access_key_id"
            ):
                existing["options"]["env_auth"] = "true"
        existing["options"] = _slim_s3_options(existing["options"], mode)

    save(st)
    write_rclone_conf()
    return existing


# Options we keep for S3 hosts (everything else is rclone noise).
_S3_OPTION_KEEP = frozenset(
    {
        "auth_mode",
        "profile",
        "provider",
        "region",
        "endpoint",
        "env_auth",
        "acl",
        "location_constraint",
        "force_path_style",
        "storage_class",
        "server_side_encryption",
        "sse_kms_key_id",
        "shared_credentials_file",
    }
)


def _slim_s3_options(opts: dict[str, Any], mode: str) -> dict[str, Any]:
    """Keep only useful S3 host options; drop default-false flags and clutter."""
    out: dict[str, Any] = {}
    for k, v in (opts or {}).items():
        if k not in _S3_OPTION_KEEP:
            continue
        if v is None or str(v) == "":
            continue
        # Skip default false flags (user never meant to set these)
        if str(v).lower() in ("false", "0", "no"):
            continue
        out[k] = v
    out["auth_mode"] = mode
    if mode == "profile":
        out["env_auth"] = "true"
        if not out.get("provider"):
            out["provider"] = "AWS"
    return out


def scrub_s3_host_options() -> dict[str, Any]:
    """One-shot: slim existing S3 host options in state (remove SSE/bool clutter)."""
    st = load()
    n = 0
    for h in st.get("hosts") or []:
        if (h.get("type") or "") != "s3":
            continue
        mode = s3_auth_mode(h)
        before = dict(h.get("options") or {})
        h["options"] = _slim_s3_options(before, mode)
        if h["options"] != before:
            n += 1
    save(st)
    write_rclone_conf()
    return {"ok": True, "hosts_updated": n}


def delete_host(host_id: str) -> None:
    st = load()
    for m in st.get("mounts") or []:
        if m.get("host_id") == host_id:
            raise ValueError(
                f"Host is used by mount “{m.get('label') or m.get('id')}”. Remove mounts first."
            )
    st["hosts"] = [h for h in st["hosts"] if h.get("id") != host_id]
    save(st)
    keychain.delete_host_secrets(host_id)
    session_store.clear_session(host_id)
    write_rclone_conf()


def _run_lsd(host_id: str, remote_path: str) -> tuple[int, str, str, Any]:
    """Return (rc, stdout, stderr, conf_path) for rclone lsd."""
    conf = write_runtime_conf([host_id])
    env = host_env(host_id)
    r = run_rclone(["lsd", remote_path, "--max-depth", "1"], env=env, config=conf)
    return r.returncode, r.stdout or "", r.stderr or "", conf


def test_host(host_id: str) -> dict[str, Any]:
    h = get_host(host_id)
    if not h:
        return {"ok": False, "error": "Host not found"}
    missing = ensure_host_runtime_secrets(host_id)
    if missing:
        return {"ok": False, "error": missing}

    try:
        conf = write_runtime_conf([host_id])
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}

    env = host_env(host_id)
    remote = f"{h['name']}:"
    r = run_rclone(["lsd", remote, "--max-depth", "1"], env=env, config=conf)
    out = (r.stdout or "") + (r.stderr or "")

    # On auth failure only: try SSO login once, then retry (no proactive refresh)
    if r.returncode != 0 and (h.get("type") or "").lower() == "s3" and aws_auth.is_auth_failure(out):
        login = refresh_s3_after_auth_failure(host_id)
        if login is None:
            conf = write_runtime_conf([host_id])
            r = run_rclone(
                ["lsd", remote, "--max-depth", "1"],
                env=host_env(host_id),
                config=conf,
            )
            out = (r.stdout or "") + (r.stderr or "")
        elif login.get("ok") is False and not login.get("not_sso"):
            return login

    if r.returncode != 0:
        if (h.get("type") or "").lower() == "s3":
            return {
                "ok": False,
                "error": _format_s3_rclone_error(out, h),
                "code": "s3_error",
            }
        hint = ""
        low = out.lower()
        if "2fa" in low or "incorrect login" in low or "8002" in out:
            hint = (
                "\n\nHint: Proton 2FA failed. Re-enter login password and the "
                "Authenticator *secret key* (base32 from 2FA setup), not a 6-digit code. "
                "If you use a two-password Proton account, also set mailbox_password."
            )
        if "input too short" in low or "obscured" in low:
            hint = (
                "\n\nHint: password was not rclone-obscured. Re-save the host "
                "(password stays in Keychain; CloudMount obscures it for rclone)."
            )
        return {"ok": False, "error": (out[-1500:] or f"exit {r.returncode}") + hint}
    # Keep session tokens so the next mount does not re-hit /auth/v4/2fa
    tokens = capture_session_tokens(host_id, conf)
    buckets = []
    for line in (r.stdout or "").splitlines():
        parts = line.split()
        if parts:
            buckets.append(parts[-1])
    return {
        "ok": True,
        "buckets": buckets,
        "raw": (r.stdout or "")[:2000],
        "session_tokens_saved": tokens,
        "auth_mode": s3_auth_mode(h) if (h.get("type") or "").lower() == "s3" else None,
    }


def list_remote_paths(host_id: str, prefix: str = "") -> dict[str, Any]:
    """List directories under host:prefix (buckets at root for S3)."""
    h = get_host(host_id)
    if not h:
        return {"ok": False, "error": "Host not found"}
    missing = ensure_host_runtime_secrets(host_id)
    if missing:
        return {"ok": False, "error": missing}

    try:
        conf = write_runtime_conf([host_id])
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}
    prefix = (prefix or "").strip().strip("/")
    path = f"{h['name']}:{prefix}" if prefix else f"{h['name']}:"
    r = run_rclone(["lsd", path], env=host_env(host_id), config=conf)
    out = (r.stderr or "") + (r.stdout or "")
    # On auth failure only: SSO login + one retry
    if r.returncode != 0 and (h.get("type") or "").lower() == "s3" and aws_auth.is_auth_failure(out):
        login = refresh_s3_after_auth_failure(host_id)
        if login is None:
            conf = write_runtime_conf([host_id])
            r = run_rclone(["lsd", path], env=host_env(host_id), config=conf)
            out = (r.stderr or "") + (r.stdout or "")
        elif login.get("ok") is False and not login.get("not_sso"):
            return login
    if r.returncode != 0:
        err = out[-1500:] or f"exit {r.returncode}"
        if (h.get("type") or "").lower() == "s3":
            err = _format_s3_rclone_error(out, h)
        return {"ok": False, "error": err, "code": "list_failed"}
    capture_session_tokens(host_id, conf)
    entries = []
    for line in (r.stdout or "").splitlines():
        parts = line.split()
        if not parts:
            continue
        name = parts[-1]
        full = f"{prefix}/{name}" if prefix else name
        entries.append({"name": name, "remote_path": full})
    parent = None
    if prefix:
        parent = prefix.rsplit("/", 1)[0] if "/" in prefix else ""
    return {
        "ok": True,
        "prefix": prefix,
        "parent": parent,
        "entries": entries,
        "names": [e["name"] for e in entries],
    }
