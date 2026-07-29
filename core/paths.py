from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

# Repo root when running from source
ROOT = Path(__file__).resolve().parent.parent

BUNDLE_ID = "com.youramaryllis.cloudmount"
APP_VENDOR = "YourAmaryllis"
APP_NAME = "CloudMount"


def _app_support_dir() -> Path:
    """Per-user app data directory (platform-specific)."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / APP_VENDOR / APP_NAME
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_VENDOR / APP_NAME
    # Linux / other
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / APP_VENDOR / APP_NAME
    return Path.home() / ".config" / APP_VENDOR / APP_NAME


APP_SUPPORT = _app_support_dir()
STATE_PATH = APP_SUPPORT / "state.json"
RCLONE_CONF = APP_SUPPORT / "rclone.conf"
# Ephemeral conf with secrets (obscured); rewritten before each rclone use
RCLONE_RUNTIME_CONF = APP_SUPPORT / "rclone.runtime.conf"
# Session tokens (e.g. Proton) — mode 0600 on Unix; ACLs on Windows
SESSION_STORE = APP_SUPPORT / "session_tokens.json"
LOG_DIR = APP_SUPPORT / "logs"
BIN_DIR = APP_SUPPORT / "bin"
VENDOR_RCLONE = ROOT / "vendor" / "rclone"


def app_resources() -> Path | None:
    """Optional Resources dir (macOS .app or Windows install layout)."""
    p = Path(os.environ.get("CLOUDMOUNT_RESOURCES", ""))
    if p.is_dir():
        return p
    exe = Path(os.environ.get("CLOUDMOUNT_APP_EXE", "")).resolve()
    if not exe.parts:
        # When frozen / next to installed tree
        if getattr(sys, "frozen", False):
            cand = Path(sys.executable).resolve().parent / "Resources"
            if cand.is_dir():
                return cand
        return None
    # …/Contents/MacOS/CloudMount → Resources
    if exe.parent.name == "MacOS" and exe.parent.parent.name == "Contents":
        res = exe.parent.parent / "Resources"
        if res.is_dir():
            return res
    # Windows: same folder as launcher / Resources sibling
    for cand in (exe.parent / "Resources", exe.parent.parent / "Resources"):
        if cand.is_dir():
            return cand
    return None


def ensure_dirs() -> None:
    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)


def expand_user(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def prefer_tilde(path: str | Path) -> str:
    """Store paths relative to home when possible (~/… on all platforms)."""
    p = Path(path).expanduser().resolve()
    home = Path.home().resolve()
    try:
        rel = p.relative_to(home)
        return f"~/{rel.as_posix()}" if str(rel) != "." else "~"
    except ValueError:
        return str(p)


def default_mount_kind() -> str:
    """Prefer NFS on macOS when available; WinFsp mount on Windows."""
    if platform.system() == "Windows":
        return "fuse"
    return "nfs"


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_darwin() -> bool:
    return platform.system() == "Darwin"
