from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from . import capabilities
from .hosts import (
    capture_session_tokens,
    ensure_host_runtime_secrets,
    get_host,
    host_env,
    write_rclone_conf,
    write_runtime_conf,
)
from .paths import (
    APP_SUPPORT,
    LOG_DIR,
    RCLONE_CONF,
    RCLONE_RUNTIME_CONF,
    default_mount_kind,
    expand_user,
    prefer_tilde,
    ensure_dirs,
    is_windows,
)
from .rclone_bin import ensure_rclone, rclone_path, run_rclone
from .state import load, new_id, save


def list_mounts() -> list[dict[str, Any]]:
    st = load()
    out = []
    for m in st.get("mounts") or []:
        item = dict(m)
        item["mounted"] = is_mounted(m.get("path") or "")
        item["host"] = get_host(m.get("host_id") or "")
        out.append(item)
    return out


def get_mount(mount_id: str) -> Optional[dict[str, Any]]:
    for m in load().get("mounts") or []:
        if m.get("id") == mount_id:
            return m
    return None


def is_mounted(path: str) -> bool:
    if not path:
        return False
    p = str(expand_user(path))
    if is_windows():
        return _win_is_mounted(p)
    try:
        r = subprocess.run(["mount"], capture_output=True, text=True, check=False)
        text = r.stdout or ""
        return f" on {p} " in text or f" on {p}/ " in text
    except Exception:
        return False


def _win_is_mounted(path: str) -> bool:
    """True if path looks like an active WinFsp/rclone mount."""
    try:
        if os.path.ismount(path):
            return True
    except Exception:
        pass
    # Folder mount: rclone process still holding it
    try:
        return _pid_for_any_path(path) is not None
    except Exception:
        return False


def _pid_for_any_path(path: str) -> Optional[int]:
    """Find any rclone mount PID that references this local path."""
    return _pid_for("", path, only_cloudmount=True) or _pid_for(
        "", path, only_cloudmount=False
    )


def upsert_mount(
    *,
    mount_id: Optional[str] = None,
    label: str,
    host_id: str,
    remote_path: str,
    path: str,
    mount_kind: str = "",
    vfs_cache_mode: str = "full",
) -> dict[str, Any]:
    st = load()
    prefs = st.get("prefs") or {}
    mount_kind = (mount_kind or prefs.get("default_mount_kind") or default_mount_kind()).lower()
    if mount_kind not in ("fuse", "nfs"):
        raise ValueError("mount_kind must be fuse or nfs")
    if is_windows() and mount_kind == "nfs":
        # Windows uses WinFsp via rclone mount only
        mount_kind = "fuse"
    if mount_kind == "fuse" and not prefs.get("enable_fuse", True):
        raise ValueError("FUSE/WinFsp mounts are disabled in prefs")
    if mount_kind == "nfs" and not prefs.get("enable_nfs", True):
        raise ValueError("NFS mounts are disabled in prefs")
    if not get_host(host_id):
        raise ValueError("Host does not exist — create a host first")

    # Empty remote_path = root of the remote (Drive, Proton, SFTP, …).
    # S3 users typically put "bucket" or "bucket/prefix" here.
    remote_path = (remote_path or "").strip().strip("/")
    path = prefer_tilde(path)

    existing = None
    if mount_id:
        existing = next((m for m in st["mounts"] if m["id"] == mount_id), None)
    if not existing:
        mount_id = mount_id or new_id("m")
        existing = {"id": mount_id}
        st["mounts"].append(existing)

    existing.update(
        {
            "id": mount_id,
            "label": label.strip() or mount_id,
            "host_id": host_id,
            "remote_path": remote_path,
            "path": path,
            "mount_kind": mount_kind,
            "vfs_cache_mode": vfs_cache_mode or "full",
        }
    )
    save(st)
    return existing


def delete_mount(mount_id: str, unmount_first: bool = True) -> None:
    if unmount_first:
        try:
            unmount(mount_id)
        except Exception:
            pass
    st = load()
    st["mounts"] = [m for m in st["mounts"] if m.get("id") != mount_id]
    save(st)


def bulk_add_from_paths(
    *,
    host_id: str,
    remote_paths: list[str],
    local_root: str = "~/CloudMount",
    mount_kind: str = "",
    vfs_cache_mode: str = "full",
    label_from: str = "basename",
) -> dict[str, Any]:
    """Create one mount per remote path (e.g. bucket/subfolder).

    Default local_root is ~/CloudMount so basename mounts do not collide with
    macOS case-insensitive home folders (Pictures, Music, Movies).
    """
    if not get_host(host_id):
        raise ValueError("Host does not exist")
    if not mount_kind:
        mount_kind = default_mount_kind()
    created = []
    skipped = []
    st = load()
    existing_remotes = {
        (m.get("host_id"), (m.get("remote_path") or "").strip("/"))
        for m in st.get("mounts") or []
    }
    root = prefer_tilde(local_root or "~/CloudMount")
    # Never use bare ~ as parent for basenames (collides with ~/Pictures etc.)
    if root in ("~", "~/"):
        root = "~/CloudMount"

    for rp in remote_paths:
        rp = (rp or "").strip().strip("/")
        if not rp:
            continue
        if (host_id, rp) in existing_remotes:
            skipped.append({"remote_path": rp, "reason": "already configured"})
            continue
        base = rp.rsplit("/", 1)[-1]
        if label_from == "full":
            label = rp.replace("/", " · ")
            local = f"{root.rstrip('/')}/{rp}"
        else:
            label = base
            local = f"{root.rstrip('/')}/{base}"
        m = upsert_mount(
            label=label,
            host_id=host_id,
            remote_path=rp,
            path=local,
            mount_kind=mount_kind,
            vfs_cache_mode=vfs_cache_mode,
        )
        created.append(m)
        existing_remotes.add((host_id, rp))
    return {"ok": True, "created": created, "skipped": skipped}


def _remote_spec(m: dict[str, Any]) -> str:
    h = get_host(m["host_id"])
    if not h:
        raise ValueError("Host missing for mount")
    rp = (m.get("remote_path") or "").strip()
    return f"{h['name']}:{rp}"


def _list_rclone_processes() -> list[tuple[int, str]]:
    """Return [(pid, command_line), ...] for rclone processes."""
    out: list[tuple[int, str]] = []
    if is_windows():
        # WMIC is deprecated but still widely available; PowerShell as fallback
        try:
            r = subprocess.run(
                [
                    "wmic",
                    "process",
                    "where",
                    "name='rclone.exe'",
                    "get",
                    "ProcessId,CommandLine",
                    "/FORMAT:LIST",
                ],
                capture_output=True,
                text=True,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            pid = None
            cmd = ""
            for line in (r.stdout or "").splitlines():
                line = line.strip()
                if line.startswith("CommandLine="):
                    cmd = line[len("CommandLine=") :]
                elif line.startswith("ProcessId="):
                    try:
                        pid = int(line[len("ProcessId=") :])
                    except ValueError:
                        pid = None
                elif not line and pid is not None:
                    out.append((pid, cmd))
                    pid, cmd = None, ""
            if pid is not None:
                out.append((pid, cmd))
            if out:
                return out
        except Exception:
            pass
        try:
            ps = (
                "Get-CimInstance Win32_Process -Filter \"Name='rclone.exe'\" | "
                "ForEach-Object { $_.ProcessId.ToString() + '|' + $_.CommandLine }"
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True,
                text=True,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            for line in (r.stdout or "").splitlines():
                if "|" not in line:
                    continue
                spid, _, cmd = line.partition("|")
                try:
                    out.append((int(spid.strip()), cmd.strip()))
                except ValueError:
                    continue
        except Exception:
            pass
        return out

    r = subprocess.run(["pgrep", "-fl", "rclone"], capture_output=True, text=True)
    for line in (r.stdout or "").splitlines():
        try:
            pid = int(line.split()[0])
        except ValueError:
            continue
        out.append((pid, line))
    return out


def _pid_for(remote: str, path: str, *, only_cloudmount: bool = True) -> Optional[int]:
    """Find rclone mount PID for this remote+path.

    When only_cloudmount=True (default), only match processes that use our
    managed rclone.conf — never kill a hand-started ~/rclone-mount or other
    unrelated rclone mount on the same path.
    """
    p = str(expand_user(path))
    # Normalize Windows path separators for cmdline match
    p_variants = {p, p.replace("\\", "/"), p.replace("/", "\\")}
    conf_markers = (
        str(RCLONE_CONF),
        str(RCLONE_RUNTIME_CONF),
        "CloudMount",
        str(APP_SUPPORT),
    )
    for pid, line in _list_rclone_processes():
        # empty remote = path-only match (used by Windows is_mounted helper)
        if remote and remote not in line:
            continue
        if not any(v and v in line for v in p_variants):
            continue
        low = line.lower()
        if "mount" not in low and "nfsmount" not in low:
            continue
        if only_cloudmount:
            if not any(m in line for m in conf_markers) and "--config" not in line:
                continue
            if not any(m in line for m in conf_markers):
                if "YourAmaryllis" not in line and "CloudMount" not in line:
                    continue
        return pid
    return None


def mount(mount_id: str) -> dict[str, Any]:
    ensure_dirs()
    m = get_mount(mount_id)
    if not m:
        return {"ok": False, "error": "Mount not found"}
    path = expand_user(m["path"])
    kind = (m.get("mount_kind") or default_mount_kind()).lower()
    if is_windows() and kind == "nfs":
        kind = "fuse"
    if is_mounted(str(path)):
        return {"ok": True, "already": True, "path": str(path), "kind": kind}

    if kind == "fuse":
        if not capabilities.fuse_ready():
            help_ = capabilities.help_install_macfuse(open_browser=False)
            need = "WinFsp" if is_windows() else "macFUSE"
            return {
                "ok": False,
                "error": f"Mount not ready (need {need} + rclone with mount)",
                "help": help_,
            }
        cmd_name = "mount"
    else:
        if not capabilities.nfs_ready():
            return {"ok": False, "error": "NFS mount not available on this rclone binary"}
        cmd_name = "nfsmount"

    ensure_rclone()

    missing = ensure_host_runtime_secrets(m["host_id"])
    if missing:
        return {"ok": False, "error": missing}

    write_rclone_conf()
    # Runtime conf injects Keychain secrets as obscured values (needed for Proton Drive)
    try:
        runtime_conf = write_runtime_conf([m["host_id"]])
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}
    path.mkdir(parents=True, exist_ok=True)
    remote = _remote_spec(m)
    env = host_env(m["host_id"])
    bin_path = rclone_path()
    log = LOG_DIR / f"{mount_id}.log"
    mode = m.get("vfs_cache_mode") or "full"

    cmd = [
        str(bin_path),
        "--config",
        str(runtime_conf),
        cmd_name,
        remote,
        str(path),
        "--vfs-cache-mode",
        mode,
        "--dir-cache-time",
        "5m",
        "--poll-interval",
        "1m",
    ]
    full_env = os.environ.copy()
    full_env.update(env)

    log.parent.mkdir(parents=True, exist_ok=True)
    logf = open(log, "a", buffering=1)
    logf.write(f"\n--- starting {cmd_name} {remote} -> {path}\n")
    logf.write(f"config={runtime_conf}\n")
    popen_kw: dict[str, Any] = {
        "stdout": logf,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
        "env": full_env,
    }
    if is_windows():
        # Hide console window; new process group for clean kill
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        popen_kw["creationflags"] = flags
        popen_kw["close_fds"] = False
    else:
        popen_kw["start_new_session"] = True
        popen_kw["close_fds"] = True
    proc = subprocess.Popen(cmd, **popen_kw)

    def _ok_payload() -> dict[str, Any]:
        # rclone may have written client_* session tokens into the conf
        try:
            capture_session_tokens(m["host_id"], runtime_conf)
        except Exception:
            pass
        return {
            "ok": True,
            "path": str(path),
            "kind": kind,
            "pid": proc.pid,
            "remote": remote,
        }

    for _ in range(40):
        if is_mounted(str(path)):
            return _ok_payload()
        if proc.poll() is not None:
            tail = log.read_text()[-2000:] if log.exists() else ""
            hint = ""
            low = tail.lower()
            if "2fa" in low or "incorrect login" in low or "8002" in tail:
                hint = (
                    "\n\nProton 2FA/login failed. Click Test on the host first. "
                    "Use the Authenticator secret key (base32), not a 6-digit code. "
                    "Re-enter password if needed."
                )
            if "input too short" in low or "obscured" in low:
                hint = (
                    "\n\nPassword was not rclone-obscured. Re-save the host, "
                    "then Test, then Mount."
                )
            return {
                "ok": False,
                "error": f"rclone exited early\n{tail}{hint}",
                "log": str(log),
            }
        time.sleep(0.5)

    if is_mounted(str(path)):
        return _ok_payload()
    tail = log.read_text()[-2000:] if log.exists() else ""
    return {
        "ok": False,
        "error": f"Mount did not appear in time\n{tail}",
        "log": str(log),
        "pid": proc.pid,
    }


def unmount(mount_id: str) -> dict[str, Any]:
    """Unmount only this CloudMount entry.

    Never kills rclone processes that were not started with our managed
    --config (e.g. the legacy ~/rclone-mount script).
    """
    m = get_mount(mount_id)
    if not m:
        return {"ok": False, "error": "Mount not found"}
    path = expand_user(m["path"])
    remote = ""
    try:
        remote = _remote_spec(m)
    except Exception:
        pass

    our_pid = _pid_for(remote, str(path), only_cloudmount=True) if remote else None

    if not is_mounted(str(path)):
        if our_pid:
            _kill_pid(our_pid)
            return {"ok": True, "message": "killed leftover CloudMount process"}
        return {"ok": True, "already": True}

    # If this path is mounted but not by CloudMount, refuse to tear it down.
    if our_pid is None:
        foreign = _pid_for(remote, str(path), only_cloudmount=False) if remote else None
        return {
            "ok": False,
            "error": (
                f"{path} is mounted but not by CloudMount "
                f"(pid={foreign}). Leaving it alone — stop the other rclone "
                f"yourself if you intend to replace it."
            ),
            "foreign": True,
            "path": str(path),
        }

    if not is_windows():
        for args in (
            ["umount", str(path)],
            ["diskutil", "unmount", str(path)],
            ["umount", "-f", str(path)],
        ):
            subprocess.run(args, capture_output=True)
            if not is_mounted(str(path)):
                return {"ok": True, "path": str(path)}

    _kill_pid(our_pid)
    time.sleep(0.5)
    if not is_windows():
        subprocess.run(["umount", "-f", str(path)], capture_output=True)

    if is_mounted(str(path)):
        return {"ok": False, "error": f"Failed to unmount {path}"}
    return {"ok": True, "path": str(path)}


def _kill_pid(pid: int) -> None:
    if is_windows():
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def mount_all() -> list[dict[str, Any]]:
    results = []
    for m in list_mounts():
        if not m.get("mounted"):
            results.append({"id": m["id"], **mount(m["id"])})
        else:
            results.append({"id": m["id"], "ok": True, "already": True})
    return results


def unmount_all() -> list[dict[str, Any]]:
    return [{"id": m["id"], **unmount(m["id"])} for m in list_mounts()]
