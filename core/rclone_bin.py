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

from .paths import ROOT, VENDOR_RCLONE, app_resources, ensure_dirs, LOG_DIR


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


def rclone_path() -> Path:
    key = platform_key()
    name = "rclone.exe" if key.startswith("windows") else "rclone"
    # App bundle Resources first
    res = app_resources()
    if res:
        p = res / "vendor" / "rclone" / key / name
        if p.is_file():
            return p
    p = VENDOR_RCLONE / key / name
    return p


def ensure_rclone(force: bool = False, version: str = "current") -> Path:
    ensure_dirs()
    dest = rclone_path()
    if dest.is_file() and os.access(dest, os.X_OK) and not force:
        return dest

    pkg_os, arch = _pkg_os_arch()
    url = f"https://downloads.rclone.org/rclone-{version}-{pkg_os}-{arch}.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / "ensure-rclone.log"
    with tempfile.TemporaryDirectory() as td:
        zpath = Path(td) / "rclone.zip"
        with open(log, "a") as lf:
            lf.write(f"Downloading {url}\n")
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
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check,
        env=full_env,
        timeout=timeout,
    )


def rclone_version() -> str:
    try:
        r = run_rclone(["version"])
        return (r.stdout or "").splitlines()[0] if r.stdout else "unknown"
    except Exception as e:
        return f"error: {e}"
