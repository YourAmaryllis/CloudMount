"""Install CloudMount tray to Windows Startup (optional auto-start)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def install() -> dict[str, Any]:
    if sys.platform != "win32":
        return {
            "ok": False,
            "error": "install-tray is for Windows. On macOS, build mac-app/ instead.",
        }

    startup = Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
    if not startup.is_dir():
        return {"ok": False, "error": f"Startup folder not found: {startup}"}

    bat = ROOT / "bin" / "cloudmount-tray.bat"
    if not bat.is_file():
        return {"ok": False, "error": f"Missing {bat}"}

    # Shortcut via a small .cmd that lives in Startup (no win32com required)
    launcher = startup / "CloudMount-tray.cmd"
    content = f'@echo off\r\nstart "" /B "{bat}"\r\n'
    launcher.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "startup_script": str(launcher),
        "hint": "CloudMount tray will start at login. Run: pip install -r requirements-windows.txt",
    }
