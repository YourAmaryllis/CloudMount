from __future__ import annotations

import plistlib
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_SOURCES = [
    ROOT / "plugins" / "cloudmount.5s.sh",
    ROOT / "plugins" / "rclone-mounts.10s.sh",
]

HOST_APPS = {
    "SwiftBar": Path("/Applications/SwiftBar.app"),
    "xbar": Path("/Applications/xbar.app"),
}
SWIFTBAR_PREF_DOMAIN = "com.ameba.SwiftBar"


def _find_host() -> str | None:
    for name, app in HOST_APPS.items():
        if app.is_dir():
            return name
    return None


def _plugin_dir_for(host: str) -> Path:
    if host == "xbar":
        return Path.home() / "Library/Application Support/xbar/plugins"
    return Path.home() / "Library/Application Support/SwiftBar/Plugins"


def _read_disabled_plugins() -> list[str]:
    try:
        r = subprocess.run(
            ["defaults", "export", SWIFTBAR_PREF_DOMAIN, "-"],
            capture_output=True,
            check=False,
        )
        if r.returncode != 0 or not r.stdout:
            return []
        data = plistlib.loads(r.stdout)
        return [str(x) for x in (data.get("DisabledPlugins") or [])]
    except Exception:
        return []


def _enable_plugins(names: list[str]) -> None:
    """Remove our plugins from SwiftBar's DisabledPlugins list, if present."""
    current = _read_disabled_plugins()
    if not any(n in current for n in names):
        return
    remaining = [n for n in current if n not in names]
    try:
        subprocess.run(
            ["defaults", "write", SWIFTBAR_PREF_DOMAIN, "DisabledPlugins", "-array", *remaining],
            check=False,
        )
    except Exception:
        pass


def install() -> dict[str, Any]:
    if sys.platform != "darwin":
        return {
            "ok": False,
            "error": "install-menubar is for macOS. On Windows use install-tray.",
        }

    host = _find_host()
    target_dir = _plugin_dir_for(host or "SwiftBar")
    target_dir.mkdir(parents=True, exist_ok=True)

    links: list[str] = []
    names: list[str] = []
    for src in PLUGIN_SOURCES:
        if not src.is_file():
            continue
        src.chmod(src.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        link = target_dir / src.name
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(src)
        links.append(str(link))
        names.append(src.name)

    cm = ROOT / "bin" / "cloudmount"
    if cm.is_file():
        cm.chmod(cm.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    if not host:
        return {
            "ok": True,
            "host": None,
            "plugin_links": links,
            "plugin_dir": str(target_dir),
            "hint": "No SwiftBar/xbar found. Install with: brew install --cask swiftbar",
        }

    if host == "SwiftBar":
        _enable_plugins(names)
    try:
        subprocess.run(["open", "-a", host], check=False)
    except Exception:
        pass

    return {
        "ok": True,
        "host": host,
        "plugin_links": links,
        "plugin_dir": str(target_dir),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(install(), indent=2))
