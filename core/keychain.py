from __future__ import annotations

import platform
import subprocess
import threading
from typing import Optional

from . import SERVICE

# In-process cache: avoids hammering Keychain / Credential Manager.
_lock = threading.Lock()
_cache: dict[str, Optional[str]] = {}


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


def _target_name(account: str) -> str:
    return f"{SERVICE}/{account}"


# ── Windows Credential Manager ─────────────────────────────────────────────

def _win_get(account: str) -> Optional[str]:
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return None

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_char)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    cred_ptr = ctypes.POINTER(CREDENTIAL)()
    # CRED_TYPE_GENERIC = 1
    ok = advapi32.CredReadW(_target_name(account), 1, 0, ctypes.byref(cred_ptr))
    if not ok:
        return None
    try:
        cred = cred_ptr.contents
        size = cred.CredentialBlobSize
        if size <= 0 or not cred.CredentialBlob:
            return ""
        raw = ctypes.string_at(cred.CredentialBlob, size)
        # Stored as UTF-16-LE by CredWriteW when we write unicode
        try:
            return raw.decode("utf-16-le").rstrip("\x00")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")
    finally:
        advapi32.CredFree(cred_ptr)


def _win_set(account: str, password: str) -> None:
    import ctypes
    from ctypes import wintypes

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.c_void_p),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    blob = password.encode("utf-16-le")
    cred = CREDENTIAL()
    cred.Type = 1  # CRED_TYPE_GENERIC
    cred.TargetName = _target_name(account)
    cred.UserName = account
    cred.CredentialBlobSize = len(blob)
    cred.CredentialBlob = ctypes.cast(
        ctypes.create_string_buffer(blob), ctypes.c_void_p
    )
    cred.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE (or 1 = session, 3 = enterprise)
    # CRED_PERSIST_LOCAL_MACHINE = 2 works for user logon session credentials;
    # CRED_PERSIST_ENTERPRISE = 3 is more portable across sessions.
    cred.Persist = 3
    if not advapi32.CredWriteW(ctypes.byref(cred), 0):
        err = ctypes.get_last_error()
        raise RuntimeError(f"CredWrite failed for {account} (winerr={err})")


def _win_delete(account: str) -> None:
    import ctypes

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.CredDeleteW(_target_name(account), 1, 0)


# ── macOS Keychain ──────────────────────────────────────────────────────────

def _mac_get(account: str) -> Optional[str]:
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
        return None
    return r.stdout.rstrip("\n")


def _mac_set(account: str, password: str) -> None:
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
            "-U",
            "-l",
            f"CloudMount {account}",
        ]
    )
    if r.returncode == 0:
        return
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


def _mac_delete(account: str) -> None:
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


# ── Public API ──────────────────────────────────────────────────────────────

def get_password(account: str) -> Optional[str]:
    hit, val = _cache_get(account)
    if hit:
        return val
    system = platform.system()
    if system == "Darwin":
        value = _mac_get(account)
    elif system == "Windows":
        value = _win_get(account)
    else:
        # Linux: file-backed fallback under app support (mode 0600)
        value = _file_get(account)
    _cache_set(account, value)
    return value


def set_password(account: str, password: str) -> None:
    if password is None:
        return
    existing = get_password(account)
    if existing is not None and existing == password:
        return
    system = platform.system()
    if system == "Darwin":
        _mac_set(account, password)
    elif system == "Windows":
        _win_set(account, password)
    else:
        _file_set(account, password)
    _cache_set(account, password)


def delete_password(account: str) -> None:
    system = platform.system()
    if system == "Darwin":
        _mac_delete(account)
    elif system == "Windows":
        try:
            _win_delete(account)
        except Exception:
            pass
    else:
        _file_delete(account)
    _cache_invalidate(account)


def _secrets_dir():
    from .paths import APP_SUPPORT

    d = APP_SUPPORT / "secrets"
    d.mkdir(parents=True, exist_ok=True)
    try:
        d.chmod(0o700)
    except OSError:
        pass
    return d


def _file_path(account: str):
    # safe filename
    safe = account.replace("/", "__").replace("\\", "__")
    return _secrets_dir() / f"{safe}.txt"


def _file_get(account: str) -> Optional[str]:
    p = _file_path(account)
    if not p.is_file():
        return None
    return p.read_text(encoding="utf-8")


def _file_set(account: str, password: str) -> None:
    p = _file_path(account)
    p.write_text(password, encoding="utf-8")
    try:
        p.chmod(0o600)
    except OSError:
        pass


def _file_delete(account: str) -> None:
    p = _file_path(account)
    try:
        p.unlink(missing_ok=True)  # type: ignore[call-arg]
    except TypeError:
        if p.exists():
            p.unlink()


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
    """macOS-only ACL repair; no-op elsewhere."""
    if platform.system() != "Darwin":
        return {"ok": True, "skipped": True, "reason": "not macOS"}
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
    _cache_invalidate()
    for h in load().get("hosts") or []:
        hid = h.get("id")
        if not hid:
            continue
        for field in fields:
            acc = host_account(hid, field)
            _cache_invalidate(acc)
            val = get_password(acc)
            if val is None:
                missing += 1
                continue
            try:
                _mac_delete(acc)
                _mac_set(acc, val)
                _cache_set(acc, val)
                fixed += 1
            except Exception as e:
                errors.append(f"{acc}: {e}")
    return {"ok": not errors, "rewritten": fixed, "empty_slots": missing, "errors": errors}
