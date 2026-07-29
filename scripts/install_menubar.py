from __future__ import annotations

import os
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_SRC = ROOT / "plugins" / "cloudmount.5s.sh"


def install() -> dict:
    candidates = [
        Path.home() / "Library/Application Support/SwiftBar/Plugins",
        Path.home() / "Library/Application Support/xbar/plugins",
    ]
    target_dir = None
    for d in candidates:
        if d.is_dir():
            target_dir = d
            break
    if target_dir is None:
        target_dir = candidates[0]
        target_dir.mkdir(parents=True, exist_ok=True)

    PLUGIN_SRC.parent.mkdir(parents=True, exist_ok=True)
    # ensure plugin executable
    if PLUGIN_SRC.is_file():
        mode = PLUGIN_SRC.stat().st_mode
        PLUGIN_SRC.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    link = target_dir / "cloudmount.5s.sh"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(PLUGIN_SRC)

    # chmod cloudmount
    cm = ROOT / "bin" / "cloudmount"
    if cm.is_file():
        cm.chmod(cm.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return {
        "ok": True,
        "plugin_link": str(link),
        "plugin_src": str(PLUGIN_SRC),
        "swiftbar_dir": str(target_dir),
        "hint": "Open SwiftBar if the ☁ icon does not appear",
    }


if __name__ == "__main__":
    import json

    print(json.dumps(install(), indent=2))
