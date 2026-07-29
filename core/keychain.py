from __future__ import annotations

import subprocess
import threading
from typing import Optional

from . import SERVICE

# In-process cache: each `security find-generic-password -w` can pop a Keychain
# dialog when the item ACL does not trust the caller. Cache cuts repeat prompts
# during one mount/test/status refresh.
_lock = threading.Lock()
_cache: dict[str, Optional[str]] = {}
_CACHE_MISS = object()  # not used; None means missing, key absent means uncached


def _run(args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=check,
    )


def _cache_get(account: str) -> tuple[bool, Optional[str]]:
    with _lock:
        if account in _cache:
            return True, _cache[account]
    return False, None


def _cache_set(account: str, value: Optional[str]) -> None:
    with _lock:
        _cache[account] = value


def _cache_invalidate(account: Optional[str] = None) -> None:
    with _lock:
        if account is None:
            _cache.clear()
        else:
            _cache.pop(account, None)


def get_password(account: str) -> Optional[str]:
    hit, val = _cache_get(account)
    if hit:
        return val
    r = _run(
        [
            "security",
            "find-generic-password",
            "-s",
            SERVICE,
            "-a",
            account,
            "-w",
        ]
    )
    if r.returncode != 0:
        _cache_set(account, None)
        return None
    # security prints the password; strip only trailing newline from CLI
    value = r.stdout.rstrip("\n")
    _cache_set(account, value)
    return value


def set_password(account: str, password: str) -> None:
    """Store secret in macOS Keychain without resetting ACL / re-prompting.

    Important:
    - Do **not** delete+recreate (that wipes "Always Allow").
    - Use ``-A`` so any app may read (Python CLI, GUI, menu bar all differ).
    - Use ``-U`` to update in place when the item already exists.
    - Skip the write entirely when the value is unchanged.
    """
    if password is None:
        return
    existing = get_password(account)
    if existing is not None and existing == password:
        return  # no ACL churn, no prompt

    # Prefer update-in-place with open ACL (no delete).
    r = _run(
        [
            "security",
            "add-generic-password",
            "-s",
            SERVICE,
            "-a",
            account,
            "-w",
            password,
            "-A",  # allow any application (Always Allow equivalent)
            "-U",  # update if exists — keeps item identity better than delete
            "-l",
            f"CloudMount {account}",
        ]
    )
    if r.returncode == 0:
        _cache_set(account, password)
        return

    # Item may exist with conflicting flags; last resort: delete then add with -A
    _run(
        [
            "security",
            "delete-generic-password",
            "-s",
            SERVICE,
            "-a",
            account,
        ]
    )
    r2 = _run(
        [
            "security",
            "add-generic-password",
            "-s",
            SERVICE,
            "-a",
            account,
            "-w",
            password,
            "-A",
            "-l",
            f"CloudMount {account}",
        ]
    )
    if r2.returncode != 0:
        raise RuntimeError(
            f"Keychain store failed for {account}: "
            f"{(r2.stderr or r.stderr or r.stdout or '').strip()}"
        )
    _cache_set(account, password)


def delete_password(account: str) -> None:
    _run(
        [
            "security",
            "delete-generic-password",
            "-s",
            SERVICE,
            "-a",
            account,
        ]
    )
    _cache_invalidate(account)


def host_account(host_id: str, field: str) -> str:
    return f"host/{host_id}/{field}"


def set_host_secret(host_id: str, field: str, value: str) -> None:
    set_password(host_account(host_id, field), value)


def get_host_secret(host_id: str, field: str) -> Optional[str]:
    return get_password(host_account(host_id, field))


def delete_host_secrets(host_id: str) -> None:
    for field in (
        "access_key",
        "access_key_id",
        "secret_key",
        "secret_access_key",
        "password",
        "token",
        "otp_secret_key",
        "2fa",
        "mailbox_password",
        "client_uid",
        "client_access_token",
        "client_refresh_token",
        "client_salted_key_pass",
        "client_secret",
        "key",
    ):
        delete_password(host_account(host_id, field))


def reacl_all_host_secrets() -> dict:
    """Re-save every CloudMount secret with ``-A`` so Keychain stops re-prompting.

    Call once after upgrading. Reads each item (may prompt once), then writes
    it back with open ACL without changing the value when possible.
    """
    from .state import load

    fixed = 0
    missing = 0
    errors: list[str] = []
    fields = (
        "access_key",
        "access_key_id",
        "secret_key",
        "secret_access_key",
        "password",
        "token",
        "otp_secret_key",
        "2fa",
        "mailbox_password",
        "client_uid",
        "client_access_token",
        "client_refresh_token",
        "client_salted_key_pass",
        "client_secret",
        "key",
    )
    # Force fresh reads (bypass stale None cache for reacl)
    _cache_invalidate()
    for h in load().get("hosts") or []:
        hid = h.get("id")
        if not hid:
            continue
        for field in fields:
            acc = host_account(hid, field)
            # bust cache for this account
            _cache_invalidate(acc)
            val = get_password(acc)
            if val is None:
                missing += 1
                continue
            try:
                # Force rewrite with -A even if value same: temporarily differ
                # by using delete+add only when ACL is wrong is hard to detect;
                # instead always run add -A -U which refreshes access control.
                _force_set_with_open_acl(acc, val)
                fixed += 1
            except Exception as e:
                errors.append(f"{acc}: {e}")
    return {"ok": not errors, "rewritten": fixed, "empty_slots": missing, "errors": errors}


def _force_set_with_open_acl(account: str, password: str) -> None:
    """Rewrite item with -A even when value is unchanged (ACL repair)."""
    # delete+add is the reliable way to reset ACL to -A on macOS
    _run(
        [
            "security",
            "delete-generic-password",
            "-s",
            SERVICE,
            "-a",
            account,
        ]
    )
    r = _run(
        [
            "security",
            "add-generic-password",
            "-s",
            SERVICE,
            "-a",
            account,
            "-w",
            password,
            "-A",
            "-l",
            f"CloudMount {account}",
        ]
    )
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or f"exit {r.returncode}").strip())
    _cache_set(account, password)
