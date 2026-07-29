from __future__ import annotations

import os
from pathlib import Path

# Repo root when running from source (…/wasabi)
ROOT = Path(__file__).resolve().parent.parent

BUNDLE_ID = "com.youramaryllis.cloudmount"
APP_SUPPORT = Path.home() / "Library" / "Application Support" / "YourAmaryllis" / "CloudMount"
STATE_PATH = APP_SUPPORT / "state.json"
RCLONE_CONF = APP_SUPPORT / "rclone.conf"
# Ephemeral conf with Keychain secrets (obscured); rewritten before each rclone use
RCLONE_RUNTIME_CONF = APP_SUPPORT / "rclone.runtime.conf"
# Proton (etc.) session tokens after login — mode 0600 file, NOT Keychain.
# Writing Keychain on every mount forces macOS password prompts; disk is fine here.
SESSION_STORE = APP_SUPPORT / "session_tokens.json"
LOG_DIR = APP_SUPPORT / "logs"
# Downloaded official rclone lives here (DMG install — no source tree required)
BIN_DIR = APP_SUPPORT / "bin"
# Optional local/dev seed only (gitignored); never the primary install location
VENDOR_RCLONE = ROOT / "vendor" / "rclone"

# Prefer bundled Resources when running from .app
def app_resources() -> Path | None:
    # CloudMount.app/Contents/Resources
    p = Path(os.environ.get("CLOUDMOUNT_RESOURCES", ""))
    if p.is_dir():
        return p
    # Detect macOS app bundle
    exe = Path(os.environ.get("CLOUDMOUNT_APP_EXE", "")).resolve()
    if not exe.parts:
        return None
    # …/Contents/MacOS/CloudMount → Resources
    if exe.parent.name == "MacOS" and exe.parent.parent.name == "Contents":
        res = exe.parent.parent / "Resources"
        if res.is_dir():
            return res
    return None


def ensure_dirs() -> None:
    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)


def expand_user(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def prefer_tilde(path: str | Path) -> str:
    p = Path(path).expanduser().resolve()
    home = Path.home().resolve()
    try:
        rel = p.relative_to(home)
        return f"~/{rel.as_posix()}" if str(rel) != "." else "~"
    except ValueError:
        return str(p)
