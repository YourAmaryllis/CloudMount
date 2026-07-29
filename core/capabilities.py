from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Any

from .rclone_bin import ensure_rclone, rclone_path, run_rclone


def macfuse_installed() -> bool:
    if platform.system() != "Darwin":
        return False
    for p in (
        Path("/Library/Filesystems/macfuse.fs"),
        Path("/Library/Filesystems/osxfuse.fs"),
    ):
        if p.exists():
            return True
    try:
        r = subprocess.run(
            ["pkgutil", "--pkgs"],
            capture_output=True,
            text=True,
            check=False,
        )
        if r.stdout and any(
            x in r.stdout.lower() for x in ("macfuse", "osxfuse", "fuse.osxfuse")
        ):
            return True
    except Exception:
        pass
    return False


def rclone_has_fuse_mount() -> bool:
    try:
        ensure_rclone()
    except Exception:
        return False
    r = run_rclone(["version"])
    if "cmount" in (r.stdout or ""):
        return True
    h = run_rclone(["mount", "-h"])
    text = (h.stdout or "") + (h.stderr or "")
    if "unknown command" in text.lower() and "mount" in text.lower():
        return False
    return "Rclone mount allows" in text or "mount any of Rclone" in text


def rclone_has_nfsmount() -> bool:
    try:
        ensure_rclone()
    except Exception:
        return False
    h = run_rclone(["nfsmount", "-h"])
    text = (h.stdout or "") + (h.stderr or "")
    if "unknown command" in text.lower() and "nfsmount" in text.lower():
        return False
    return "Rclone nfsmount" in text or "nfsmount allows" in text.lower()


def fuse_ready() -> bool:
    return rclone_has_fuse_mount() and macfuse_installed()


def nfs_ready() -> bool:
    return rclone_has_nfsmount()


def report() -> dict[str, Any]:
    path = rclone_path()
    present = path.is_file()
    try:
        if not present:
            ensure_rclone()
            present = rclone_path().is_file()
    except Exception:
        pass
    return {
        "rclone_path": str(rclone_path()),
        "rclone_present": present,
        "macfuse_installed": macfuse_installed(),
        "rclone_has_fuse_mount": rclone_has_fuse_mount() if present else False,
        "rclone_has_nfsmount": rclone_has_nfsmount() if present else False,
        "fuse_ready": fuse_ready() if present else False,
        "nfs_ready": nfs_ready() if present else False,
        "platform": platform.platform(),
    }


def help_install_macfuse(open_browser: bool = True) -> dict[str, Any]:
    import shutil
    import webbrowser

    brew = shutil.which("brew")
    steps = [
        "Install macFUSE (required for FUSE path mounts).",
        "Allow the system extension in System Settings → Privacy & Security.",
        "Reboot if macOS asks, then re-check capabilities.",
    ]
    brew_cmd = None
    if brew:
        brew_cmd = "brew install --cask macfuse"
        steps.insert(1, f"Terminal: {brew_cmd}")
    else:
        steps.insert(1, "Download from https://macfuse.github.io/")
    if open_browser:
        webbrowser.open("https://macfuse.github.io/")
    return {
        "ok": True,
        "brew_command": brew_cmd,
        "url": "https://macfuse.github.io/",
        "steps": steps,
    }


def try_brew_install_macfuse() -> dict[str, Any]:
    import shutil

    brew = shutil.which("brew")
    if not brew:
        return {"ok": False, "error": "Homebrew not found", **help_install_macfuse(False)}
    r = subprocess.run(
        [brew, "install", "--cask", "macfuse"],
        capture_output=True,
        text=True,
    )
    return {
        "ok": r.returncode == 0,
        "stdout": r.stdout[-2000:] if r.stdout else "",
        "stderr": r.stderr[-2000:] if r.stderr else "",
        "returncode": r.returncode,
        "macfuse_installed": macfuse_installed(),
    }
