# CloudMount on Windows

Same app as macOS: hosts, mounts, local web UI, plus a **system tray** icon (notification area) like SwiftBar on Mac.

## Requirements

1. **Python 3.10+** — [python.org](https://www.python.org/downloads/) (check “Add python.exe to PATH”)  
2. **WinFsp** — [winfsp.dev](https://winfsp.dev/rel/) (required for `rclone mount`)  
3. Tray deps: `pip install -r requirements-windows.txt`

rclone is **downloaded automatically** on first `setup` into  
`%LOCALAPPDATA%\YourAmaryllis\CloudMount\bin\`.

## Quick start

```bat
cd path\to\CloudMount
python -m pip install -r requirements-windows.txt
python bin\cloudmount setup
python bin\cloudmount tray
```

Or double-click **`bin\cloudmount-tray.bat`**.

- **Tray icon** — open UI, mount/unmount, mount all, setup, quit  
- **Web UI** — http://127.0.0.1:8765/ (full host/mount editor)

### Start at login

```bat
python bin\cloudmount install-tray
```

## Mount mode

On Windows CloudMount uses **`rclone mount` + WinFsp** (shown as kind **fuse** in the UI).  
NFS mode is disabled; rclone’s `nfsmount` is not used.

Default local folder: `~\CloudMount\…` under your user profile.

## Secrets

Stored in **Windows Credential Manager** (target names under `com.youramaryllis.cloudmount/…`), not plain files.

## Data locations

| What | Where |
|------|--------|
| State | `%LOCALAPPDATA%\YourAmaryllis\CloudMount\state.json` |
| rclone conf | `…\CloudMount\rclone.conf` |
| Logs | `…\CloudMount\logs\` |
| rclone binary | `…\CloudMount\bin\windows-amd64\rclone.exe` (or arm64) |

## CLI

```bat
python bin\cloudmount status
python bin\cloudmount host-list
python bin\cloudmount mount <id>
python bin\cloudmount unmount <id>
python bin\cloudmount gui
python bin\cloudmount tray
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Mount fails / “not ready” | Install WinFsp; re-run Setup → Re-detect |
| No tray icon | `pip install pystray Pillow`; run `cloudmount tray` |
| Python not found | Reinstall Python with PATH enabled, or use `py -3` |
| Gatekeeper N/A | Windows SmartScreen may warn on unsigned builds later |

## Installer (releases)

GitHub Actions builds:

| Asset | Use |
|-------|-----|
| `CloudMount-*-windows-setup.exe` | **Installer** (Start Menu, optional startup, first-run setup) |
| `CloudMount-*-windows.zip` | Portable folder (same files, no installer) |

```text
# From a release:
# 1. Run setup.exe  → install to %LOCALAPPDATA%\Programs\CloudMount
# 2. First-Run Setup installs pip deps + rclone download + starts tray
# 3. Install WinFsp from https://winfsp.dev/rel/ if mounts fail
```

Local package (on a Windows machine with [Inno Setup](https://jrsoftware.org/isinfo.php)):

```powershell
powershell -File scripts/build-windows.ps1
# → dist/CloudMount-<ver>-windows-setup.exe
# → dist/CloudMount-<ver>-windows.zip
```

CI: `.github/workflows/release.yml` (tag `v*` or workflow_dispatch).
