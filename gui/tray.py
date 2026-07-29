"""System tray / notification-area host for CloudMount (Windows + optional others).

SwiftBar equivalent: status icon + menu for open UI, mount/unmount, setup, quit.

Requires: pip install pystray Pillow
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import api, mounts  # noqa: E402
from core.paths import LOG_DIR, ensure_dirs  # noqa: E402

DEFAULT_PORT = 8765


def _log(msg: str) -> None:
    ensure_dirs()
    log = LOG_DIR / "tray.log"
    try:
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass


def _ensure_server(port: int = DEFAULT_PORT) -> None:
    """Start the web UI server if it is not already listening."""
    import urllib.request

    url = f"http://127.0.0.1:{port}/api/status"
    try:
        urllib.request.urlopen(url, timeout=0.5)
        return
    except Exception:
        pass

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    cmd = [
        sys.executable,
        str(ROOT / "bin" / "cloudmount"),
        "serve",
        "--port",
        str(port),
        "--no-open",
    ]
    kw: dict[str, Any] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "env": env,
        "cwd": str(ROOT),
    }
    if sys.platform == "win32":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0x00000008
        )
        kw["close_fds"] = False
    else:
        kw["start_new_session"] = True
    try:
        subprocess.Popen(cmd, **kw)
        _log(f"started serve on {port}")
    except Exception as e:
        _log(f"failed to start serve: {e}")
        return

    for _ in range(40):
        try:
            urllib.request.urlopen(url, timeout=0.4)
            return
        except Exception:
            time.sleep(0.15)


def _open_ui(port: int = DEFAULT_PORT) -> None:
    _ensure_server(port)
    webbrowser.open(f"http://127.0.0.1:{port}/")


def _run_action(fn: Callable[[], Any], label: str) -> None:
    def worker() -> None:
        try:
            result = fn()
            _log(f"{label}: {result!r}"[:500])
        except Exception as e:
            _log(f"{label} error: {e}")

    threading.Thread(target=worker, daemon=True).start()


def _make_icon():
    """Simple cloud-ish icon (no external asset required)."""
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # soft blue circle + white cloud blobs
    d.ellipse((4, 4, size - 4, size - 4), fill=(56, 132, 255, 255))
    d.ellipse((14, 28, 34, 48), fill=(255, 255, 255, 255))
    d.ellipse((24, 20, 48, 44), fill=(255, 255, 255, 255))
    d.ellipse((36, 28, 54, 48), fill=(255, 255, 255, 255))
    d.rectangle((16, 34, 50, 48), fill=(255, 255, 255, 255))
    return img


def _status_title() -> str:
    try:
        st = api.status()
        up = st.get("summary", {}).get("mounts_up", 0)
        total = st.get("summary", {}).get("mounts_total", 0)
        if total == 0:
            return "CloudMount"
        if up == total:
            return f"CloudMount · {up}"
        return f"CloudMount · {up}/{total}"
    except Exception:
        return "CloudMount"


def run_tray(port: int = DEFAULT_PORT) -> None:
    try:
        import pystray
        from pystray import MenuItem as Item
    except ImportError:
        print(
            "CloudMount tray needs: pip install pystray Pillow\n"
            "Then: python bin/cloudmount tray",
            file=sys.stderr,
        )
        sys.exit(1)

    ensure_dirs()
    _ensure_server(port)
    icon_holder: dict[str, Any] = {}

    def refresh_menu(icon: Any, _item: Any = None) -> None:
        icon.menu = pystray.Menu(*_build_items(icon, port, pystray, Item))
        try:
            icon.title = _status_title()
            icon.update_menu()
        except Exception:
            pass

    def _build_items(icon: Any, port: int, pystray_mod: Any, Item: Any) -> list:
        items: list = [
            Item("Open CloudMount…", lambda: _open_ui(port), default=True),
            Item("Refresh menu", lambda i, it: refresh_menu(i, it)),
            pystray_mod.Menu.SEPARATOR,
        ]
        try:
            mlist = mounts.list_mounts()
        except Exception as e:
            _log(f"list_mounts: {e}")
            mlist = []

        if not mlist:
            items.append(Item("(no mounts configured)", None, enabled=False))
        else:
            for m in mlist:
                mid = m.get("id") or ""
                label = m.get("label") or mid
                kind = m.get("mount_kind") or "fuse"
                mounted = bool(m.get("mounted"))
                mark = "✓" if mounted else "○"
                title = f"{mark} {label} ({kind})"

                def make_mount(i: str = mid) -> Callable:
                    return lambda: _run_action(lambda: mounts.mount(i), f"mount {i}")

                def make_unmount(i: str = mid) -> Callable:
                    return lambda: _run_action(lambda: mounts.unmount(i), f"unmount {i}")

                if mounted:
                    items.append(
                        Item(
                            title,
                            pystray_mod.Menu(
                                Item("Unmount", make_unmount()),
                                Item(
                                    "Reveal path",
                                    lambda p=m.get("path") or "": _reveal_path(p),
                                ),
                            ),
                        )
                    )
                else:
                    items.append(
                        Item(
                            title,
                            pystray_mod.Menu(Item("Mount", make_mount())),
                        )
                    )

        items.extend(
            [
                pystray_mod.Menu.SEPARATOR,
                Item(
                    "Mount all",
                    lambda: _run_action(lambda: mounts.mount_all(), "mount-all"),
                ),
                Item(
                    "Unmount all",
                    lambda: _run_action(lambda: mounts.unmount_all(), "unmount-all"),
                ),
                Item(
                    "Run setup",
                    lambda: _run_action(lambda: api.setup(), "setup"),
                ),
                pystray_mod.Menu.SEPARATOR,
                Item("Quit CloudMount tray", lambda i, _it: _quit(i)),
            ]
        )
        return items

    def _quit(icon: Any) -> None:
        _log("tray quit")
        icon.stop()

    icon = pystray.Icon(
        "CloudMount",
        _make_icon(),
        _status_title(),
        menu=pystray.Menu(
            lambda: pystray.Menu(
                *_build_items(icon_holder.get("icon"), port, pystray, Item)
            )
        ),
    )
    icon_holder["icon"] = icon
    # Static menu first (lambda dynamic menu can be flaky on some backends)
    icon.menu = pystray.Menu(*_build_items(icon, port, pystray, Item))

    # Periodic menu title refresh
    def ticker() -> None:
        while True:
            time.sleep(15)
            try:
                icon.title = _status_title()
            except Exception:
                break

    threading.Thread(target=ticker, daemon=True).start()
    _log("tray started")
    icon.run()


def _reveal_path(path: str) -> None:
    if not path:
        return
    from core.paths import expand_user

    p = str(expand_user(path))
    if sys.platform == "win32":
        os.startfile(p)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


if __name__ == "__main__":
    run_tray()
