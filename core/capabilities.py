from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Any, Optional

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


def winfsp_installed() -> bool:
    """WinFsp is required for rclone mount on Windows."""
    if platform.system() != "Windows":
        return False
    candidates = [
        Path(r"C:\Program Files (x86)\WinFsp\bin\winfsp-x64.dll"),
        Path(r"C:\Program Files\WinFsp\bin\winfsp-x64.dll"),
        Path(r"C:\Program Files (x86)\WinFsp\bin\winfsp-x86.dll"),
        Path(r"C:\Program Files\WinFsp\bin\winfsp-x86.dll"),
    ]
    for p in candidates:
        if p.is_file():
            return True
    # Registry / service name
    try:
        r = subprocess.run(
            ["sc", "query", "WinFsp.Launcher"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if r.returncode == 0 and "RUNNING" in (r.stdout or "").upper():
            return True
        if r.returncode == 0:
            return True  # service exists even if stopped
    except Exception:
        pass
    return False


def rclone_has_fuse_mount() -> bool:
    try:
        ensure_rclone()
    except Exception:
        return False
    r = run_rclone(["version"])
    text = (r.stdout or "") + (r.stderr or "")
    if "cmount" in text:
        return True
    h = run_rclone(["mount", "-h"])
    text = (h.stdout or "") + (h.stderr or "")
    if "unknown command" in text.lower() and "mount" in text.lower():
        return False
    return "Rclone mount allows" in text or "mount any of Rclone" in text or "Usage:" in text


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
    """FUSE-style local mount ready (macFUSE on macOS, WinFsp on Windows)."""
    if not rclone_has_fuse_mount():
        return False
    system = platform.system()
    if system == "Darwin":
        return macfuse_installed()
    if system == "Windows":
        return winfsp_installed()
    # Linux: typically FUSE userspace
    return True


def nfs_ready() -> bool:
    # NFS mount helper is primarily a macOS/Linux story; rare on Windows
    if platform.system() == "Windows":
        return False
    return rclone_has_nfsmount()


_CACHE_TTL_SECONDS = 120  # rclone/macFUSE/WinFsp support essentially never
# changes mid-session, but each caller (e.g. the SwiftBar menu-bar plugin)
# runs in a fresh short-lived process every few seconds, so an in-memory
# cache wouldn't survive between calls — hence a small disk cache instead.


def _cache_path() -> Path:
    from .paths import APP_SUPPORT

    return APP_SUPPORT / "capabilities.cache.json"


def _read_cache() -> Optional[dict[str, Any]]:
    import json
    import time

    try:
        data = json.loads(_cache_path().read_text())
        if time.time() - float(data.get("ts", 0)) < _CACHE_TTL_SECONDS:
            return data.get("report")
    except Exception:
        pass
    return None


def _write_cache(data: dict[str, Any]) -> None:
    import json
    import time

    try:
        p = _cache_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"ts": time.time(), "report": data}))
    except Exception:
        pass


def report(*, fresh: bool = False) -> dict[str, Any]:
    """Mount-backend capability report.

    Cached to disk for `_CACHE_TTL_SECONDS` — computing it spawns the rclone
    binary a couple of times, which is wasteful on a hot polling path (e.g.
    the SwiftBar plugin calling `cloudmount status` every few seconds).
    Pass `fresh=True` right after installing/removing macFUSE etc.
    """
    if not fresh:
        cached = _read_cache()
        if cached is not None:
            return cached

    path = rclone_path()
    present = path.is_file()
    try:
        if not present:
            ensure_rclone()
            present = rclone_path().is_file()
    except Exception:
        pass
    system = platform.system()
    has_fuse = rclone_has_fuse_mount() if present else False
    has_nfs = rclone_has_nfsmount() if present else False
    mf = macfuse_installed()
    wf = winfsp_installed()
    if system == "Darwin":
        fuse_ok = has_fuse and mf
    elif system == "Windows":
        fuse_ok = has_fuse and wf
    else:
        fuse_ok = has_fuse  # Linux: typically FUSE userspace
    nfs_ok = has_nfs if system != "Windows" else False

    data = {
        "rclone_path": str(rclone_path()),
        "rclone_present": present,
        "platform_system": system,
        "macfuse_installed": mf,
        "winfsp_installed": wf,
        "rclone_has_fuse_mount": has_fuse,
        "rclone_has_nfsmount": has_nfs,
        "fuse_ready": fuse_ok,
        "nfs_ready": nfs_ok,
        "platform": platform.platform(),
        "default_mount_kind": "fuse" if system == "Windows" else "nfs",
        "mount_backend_label": (
            "WinFsp" if system == "Windows" else ("macFUSE" if system == "Darwin" else "FUSE")
        ),
    }
    _write_cache(data)
    return data


def help_install_macfuse(open_browser: bool = True) -> dict[str, Any]:
    """Install help for FUSE-class drivers (macFUSE or WinFsp)."""
    import shutil
    import webbrowser

    if platform.system() == "Windows":
        url = "https://winfsp.dev/rel/"
        steps = [
            "Install WinFsp (required for rclone mount on Windows).",
            f"Download from {url}",
            "Run the installer, then re-check capabilities in CloudMount Setup.",
            "Optional: reboot if the WinFsp service does not start.",
        ]
        if open_browser:
            webbrowser.open(url)
        return {"ok": True, "brew_command": None, "url": url, "steps": steps}

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

    if platform.system() == "Windows":
        return {
            "ok": False,
            "error": "Use the WinFsp installer from https://winfsp.dev/rel/",
            **help_install_macfuse(False),
        }
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
