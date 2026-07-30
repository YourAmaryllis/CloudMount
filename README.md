# CloudMount

Mount cloud storage with **rclone** — add hosts, pick folders, mount locally, manage from a tray/menu icon and a local web UI.

**License:** [MIT](LICENSE) · **Platforms:** macOS and Windows

Any rclone backend can be configured in the UI. **Tested so far:** Wasabi (S3 static keys), **AWS S3 (profile / SSO)**, and Proton Drive. Other types are untested.

## Features

- **macOS:** FUSE (`rclone mount` + macFUSE) and **NFS** (`rclone nfsmount`)  
- **Windows:** `rclone mount` + **WinFsp**, plus a **system tray** icon (notification area)  
- Hosts and mounts in a local web UI (`http://127.0.0.1:8765/`)  
- **S3:** static access keys **or** AWS shared **profile** (`~/.aws`) for SSO / IAM user keys / Roles Anywhere via `credential_process`  
- Secrets in **Keychain** (macOS) or **Credential Manager** (Windows); profile mode uses the AWS CLI credential chain  
- Official rclone binary downloaded on first setup  
- macOS DMG + Windows installer from [Releases](https://github.com/arthurtsang/CloudMount/releases)

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
| **Hosts** | rclone remotes, credentials / AWS profile, Test connection |
| **Setup** | Capabilities (macFUSE / nfsmount / WinFsp), preferences |

### S3 hosts (short)

1. **Hosts → Add** → type **s3**  
2. Auth: **Static keys** (Wasabi/IAM user) **or** **AWS profile** (name from `~/.aws`)  
3. **Test** or **Browse remote** to list buckets/folders  
4. Add mounts as usual  

If an SSO session has expired, CloudMount runs `aws sso login` **only after** a failed Test/Browse/Mount (not on a timer). Manual **AWS login** is also available on profile hosts.

Full detail: [docs/S3.md](docs/S3.md).

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
| Static secrets | Keychain `com.youramaryllis.cloudmount` | Credential Manager |
| AWS profile mode | `~/.aws/config` + `credentials` (and SSO cache) | Same under `%USERPROFILE%\.aws` |
| rclone binary | `…/bin/<platform>/rclone` | `…\bin\windows-*\rclone.exe` |

## Mount kinds

| Kind | Command | Needs |
|------|---------|--------|
| **nfs** | `rclone nfsmount` | Official rclone (macOS) |
| **fuse** | `rclone mount` | Official rclone + [macFUSE](https://osxfuse.github.io/) or [WinFsp](https://winfsp.dev/rel/) |

See [docs/MOUNT_MODES.md](docs/MOUNT_MODES.md).

## Releases (CI)

Push a version tag to build **macOS DMG + Windows installer** and publish a GitHub Release:

```bash
# bump VERSION, commit, then:
git tag v0.0.3
git push origin v0.0.3
```

Or **Actions → Release → Run workflow**.  
Workflow: [`.github/workflows/release.yml`](.github/workflows/release.yml)

Version source: [`VERSION`](VERSION).

## Docs

- [S3 / AWS profile](docs/S3.md)  
- [Mount modes (FUSE vs NFS)](docs/MOUNT_MODES.md)  
- [Windows](docs/WINDOWS.md)  
- [Packaging & install notes](docs/PACKAGING.md)  
