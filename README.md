# CloudMount

Mount cloud storage with **rclone** — add hosts, pick folders, mount locally, manage from a tray/menu icon and a local web UI.

**License:** [MIT](LICENSE) · **Platforms:** macOS and Windows

Any rclone backend can be configured in the UI. **Tested so far: Wasabi (S3) and Proton Drive.** Other types are untested.

## Features

- **macOS:** FUSE (`rclone mount` + macFUSE) and **NFS** (`rclone nfsmount`)  
- **Windows:** `rclone mount` + **WinFsp**, plus a **system tray** icon (notification area)  
- Hosts and mounts in a local web UI (`http://127.0.0.2:8765/`)  
- Secrets in **Keychain** (macOS) or **Credential Manager** (Windows)  
- Official rclone binary downloaded on first setup  
- macOS DMG (unsigned); Windows: run from source / tray script (see [docs/WINDOWS.md](docs/WINDOWS.md))

## Install

Download from [Releases](https://github.com/arthurtsang/CloudMount/releases):

| Asset | Platform |
|-------|----------|
| `CloudMount-x.y.z.dmg` | macOS |
| `CloudMount-x.y.z-windows-setup.exe` | Windows installer |
| `CloudMount-x.y.z-windows.zip` | Windows portable |

### macOS

1. Open the DMG → drag **CloudMount** to Applications  
2. First launch: **right-click → Open** if Gatekeeper warns (unsigned)  
3. rclone downloads on first setup  

### Windows

1. Run the **setup.exe** (or extract the zip)  
2. Install [Python 3](https://www.python.org/downloads/) (Add to PATH) if needed  
3. Install [WinFsp](https://winfsp.dev/rel/) for mounts  
4. Run **First-Run Setup** from the Start Menu → tray icon appears  

Details: [docs/WINDOWS.md](docs/WINDOWS.md).

## Quick start (from source)

### macOS

```bash
chmod +x bin/cloudmount scripts/*.sh
python3 bin/cloudmount setup
python3 bin/cloudmount gui
```

```bash
./scripts/build-app.sh && open dist/CloudMount.app
./scripts/build-dmg.sh   # → dist/CloudMount-<version>.dmg
```

### Windows

Install [WinFsp](https://winfsp.dev/rel/), then:

```bat
python -m pip install -r requirements-windows.txt
python bin\cloudmount setup
python bin\cloudmount tray
```

Or run `bin\cloudmount-tray.bat`. Full notes: [docs/WINDOWS.md](docs/WINDOWS.md).

## UI

| Tab | Purpose |
|-----|---------|
| **Mounts** | Mount / unmount, add paths, FUSE vs NFS |
| **Hosts** | rclone remotes, credentials, Test connection |
| **Setup** | Capabilities (macFUSE / nfsmount), preferences |

## CLI

```bash
python3 bin/cloudmount status
python3 bin/cloudmount host-list
python3 bin/cloudmount host-test <id>
python3 bin/cloudmount mount <id>
python3 bin/cloudmount unmount <id>
python3 bin/cloudmount capabilities
```

## Data locations

| What | macOS | Windows |
|------|--------|---------|
| State | `~/Library/Application Support/YourAmaryllis/CloudMount/` | `%LOCALAPPDATA%\YourAmaryllis\CloudMount\` |
| Credentials | Keychain `com.youramaryllis.cloudmount` | Credential Manager |
| rclone binary | `…/bin/<platform>/rclone` | `…\bin\windows-*\rclone.exe` |

## Mount kinds

| Kind | Command | Needs |
|------|---------|--------|
| **nfs** | `rclone nfsmount` | Official rclone |
| **fuse** | `rclone mount` | Official rclone + [macFUSE](https://osxfuse.github.io/) |

See [docs/MOUNT_MODES.md](docs/MOUNT_MODES.md).

## Releases (CI)

Push a version tag to build **macOS DMG + Windows installer** and publish a GitHub Release:

```bash
# bump VERSION, commit, then:
git tag v0.0.2
git push origin v0.0.2
```

Or **Actions → Release → Run workflow**.  
Workflow: [`.github/workflows/release.yml`](.github/workflows/release.yml)

Version source: [`VERSION`](VERSION).

## Docs

- [Mount modes (FUSE vs NFS)](docs/MOUNT_MODES.md)  
- [Windows](docs/WINDOWS.md)  
- [Packaging & install notes](docs/PACKAGING.md)  
