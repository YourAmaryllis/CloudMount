from __future__ import annotations

import subprocess
from typing import Optional

from . import SERVICE


def _run(args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=check,
    )


def set_password(account: str, password: str) -> None:
    """Store secret in macOS Keychain (updates if exists)."""
    # Delete existing then add (add -U sometimes flaky with empty)
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
            "-T",
            "",  # allow all apps to read later? empty means current only; use -A for any
            "-U",
        ]
    )
    if r.returncode != 0:
        # retry without -U
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
            ]
        )
        if r2.returncode != 0:
            raise RuntimeError(
                f"Keychain store failed for {account}: {r2.stderr or r.stderr}"
            )


def get_password(account: str) -> Optional[str]:
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


def host_account(host_id: str, field: str) -> str:
    return f"host/{host_id}/{field}"


def set_host_secret(host_id: str, field: str, value: str) -> None:
    set_password(host_account(host_id, field), value)


def get_host_secret(host_id: str, field: str) -> Optional[str]:
    return get_password(host_account(host_id, field))


def delete_host_secrets(host_id: str) -> None:
    for field in ("access_key", "secret_key", "password", "token"):
        delete_password(host_account(host_id, field))
