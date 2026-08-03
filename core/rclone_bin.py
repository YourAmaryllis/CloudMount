from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional
from urllib.request import urlretrieve

from .paths import BIN_DIR, LOG_DIR, VENDOR_RCLONE, app_resources, ensure_dirs


def platform_key() -> str:
    sys = platform.system().lower()
    mach = platform.machine().lower()
    if sys == "darwin":
        os_name = "darwin"
    elif sys == "windows":
        os_name = "windows"
    else:
        os_name = "linux"
    if mach in ("arm64", "aarch64"):
        arch = "arm64"
    elif mach in ("x86_64", "amd64"):
        arch = "amd64"
    else:
        arch = mach
    return f"{os_name}-{arch}"


def _pkg_os_arch() -> tuple[str, str]:
    key = platform_key()
    os_name, arch = key.split("-", 1)
    pkg_os = {"darwin": "osx", "windows": "windows", "linux": "linux"}.get(os_name, os_name)
    return pkg_os, arch


def _binary_name() -> str:
    return "rclone.exe" if platform_key().startswith("windows") else "rclone"


def installed_rclone_path() -> Path:
    """Writable install location (Application Support). Used for downloads."""
    return BIN_DIR / platform_key() / _binary_name()


def bundled_rclone_path() -> Optional[Path]:
    """Optional read-only copy shipped inside the .app (or dev vendor/)."""
    name = _binary_name()
    key = platform_key()
    res = app_resources()
    if res:
        for p in (
            res / "bin" / key / name,
            res / "vendor" / "rclone" / key / name,
            res / "wasabi" / "vendor" / "rclone" / key / name,
        ):
            if p.is_file():
                return p
    # Dev checkout seed only
    p = VENDOR_RCLONE / key / name
    if p.is_file():
        return p
    return None


def _is_runnable(path: Path) -> bool:
    if not path.is_file():
        return False
    # Windows: os.access X_OK is unreliable for .exe
    if platform.system() == "Windows":
        return True
    return os.access(path, os.X_OK)


def rclone_path() -> Path:
    """Path used to run rclone: prefer App Support install, else bundled."""
    installed = installed_rclone_path()
    if _is_runnable(installed):
        return installed
    bundled = bundled_rclone_path()
    if bundled is not None:
        return bundled
    return installed  # default target for ensure_rclone download


def ensure_rclone(force: bool = False, version: str = "current") -> Path:
    """Ensure rclone exists under Application Support (download if needed).

    DMG users: binary is never written into /Applications (may be read-only).
    First run copies from the app bundle if present, otherwise downloads from
    downloads.rclone.org into:
      ~/Library/Application Support/YourAmaryllis/CloudMount/bin/<platform>/rclone
    """
    ensure_dirs()
    dest = installed_rclone_path()
    if _is_runnable(dest) and not force:
        return dest

    # Seed from bundled copy without re-downloading when possible
    bundled = bundled_rclone_path()
    if bundled is not None and bundled.is_file() and not force:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, dest)
        try:
            dest.chmod(0o755)
        except OSError:
            pass
        return dest

    pkg_os, arch = _pkg_os_arch()
    url = f"https://downloads.rclone.org/rclone-{version}-{pkg_os}-{arch}.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / "ensure-rclone.log"
    with tempfile.TemporaryDirectory() as td:
        zpath = Path(td) / "rclone.zip"
        with open(log, "a") as lf:
            lf.write(f"Downloading {url} -> {dest}\n")
        urlretrieve(url, zpath)
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(td)
        found = None
        for root, _dirs, files in os.walk(td):
            for f in files:
                if f in ("rclone", "rclone.exe"):
                    found = Path(root) / f
                    break
            if found:
                break
        if not found:
            raise RuntimeError(f"rclone binary not found in archive from {url}")
        shutil.copy2(found, dest)
        dest.chmod(0o755)
        with open(log, "a") as lf:
            lf.write(f"Installed {dest}\n")
    return dest


def run_rclone(
    args: list[str],
    *,
    env: Optional[dict[str, str]] = None,
    config: Optional[Path] = None,
    check: bool = False,
    capture: bool = True,
    timeout: Optional[float] = None,
) -> subprocess.CompletedProcess[str]:
    bin_path = ensure_rclone()
    cmd = [str(bin_path)]
    if config:
        cmd += ["--config", str(config)]
    cmd += args
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    kw: dict = {
        "capture_output": capture,
        "text": True,
        "check": check,
        "env": full_env,
        "timeout": timeout,
    }
    if platform.system() == "Windows":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(cmd, **kw)


def _version_cache_path() -> Path:
    return LOG_DIR.parent / "rclone-version.cache.json"


def rclone_version() -> str:
    """rclone's own version string, cached to disk keyed by binary mtime.

    Spawning the rclone binary just to print its version is wasteful on a
    hot polling path (e.g. `cloudmount status` called every few seconds by
    the SwiftBar plugin). Each poll runs in a fresh short-lived process, so
    an in-memory cache wouldn't help — hence a small disk cache, keyed on
    the binary's mtime (rather than a time-based TTL) so an rclone upgrade
    invalidates it immediately.
    """
    import json

    try:
        p = rclone_path()
        mtime = p.stat().st_mtime
    except Exception:
        mtime = -1.0

    cache_file = _version_cache_path()
    try:
        data = json.loads(cache_file.read_text())
        if data.get("path") == str(rclone_path()) and data.get("mtime") == mtime:
            return data.get("version", "unknown")
    except Exception:
        pass

    try:
        r = run_rclone(["version"])
        val = (r.stdout or "").splitlines()[0] if r.stdout else "unknown"
    except Exception as e:
        val = f"error: {e}"

    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            json.dumps({"path": str(rclone_path()), "mtime": mtime, "version": val})
        )
    except Exception:
        pass
    return val
