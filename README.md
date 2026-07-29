# CloudMount

macOS app to mount cloud storage with **rclone** — add hosts, pick folders, mount as FUSE or NFS, keep credentials in the Keychain.

**License:** [MIT](LICENSE)

Any rclone backend can be configured in the UI. **Tested so far: Wasabi (S3) and Proton Drive.** Other types are untested.

## Features

- **FUSE** (`rclone mount`) and **NFS** (`rclone nfsmount`) — choose per mount  
- Hosts and mounts managed in a local web UI (`http://127.0.0.1:8765/`)  
- Secrets in **macOS Keychain** (saved when you edit a host)  
- App data under Application Support  
- Official rclone binary downloaded on first setup  
- DMG install (currently unsigned; one build works on Apple Silicon and Intel)

## Install (DMG)

Download `CloudMount-x.y.z.dmg` from [Releases](https://github.com/arthurtsang/CloudMount/releases).

1. Open the DMG → drag **CloudMount** to Applications  
2. First launch: **right-click → Open** if Gatekeeper warns (unsigned build)  
3. On first run the app downloads official rclone for your Mac into Application Support  
4. Browser UI opens → **Hosts** → add a remote → **Mounts** → mount  

## Quick start (from source)

```bash
chmod +x bin/cloudmount scripts/*.sh
python3 bin/cloudmount setup
python3 bin/cloudmount gui
```

Or build the app bundle / DMG:

```bash
./scripts/build-app.sh && open dist/CloudMount.app
./scripts/build-dmg.sh   # → dist/CloudMount-<version>.dmg
```

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

| What | Where |
|------|--------|
| State (hosts, mounts, prefs) | `~/Library/Application Support/YourAmaryllis/CloudMount/state.json` |
| rclone config (no secrets) | `…/CloudMount/rclone.conf` |
| Session tokens (e.g. Proton) | `…/CloudMount/session_tokens.json` (mode 0600) |
| Credentials | Keychain service `com.youramaryllis.cloudmount` |
| Logs | `…/CloudMount/logs/` |
| rclone binary | `…/CloudMount/bin/<platform>/rclone` |

## Mount kinds

| Kind | Command | Needs |
|------|---------|--------|
| **nfs** | `rclone nfsmount` | Official rclone |
| **fuse** | `rclone mount` | Official rclone + [macFUSE](https://osxfuse.github.io/) |

See [docs/MOUNT_MODES.md](docs/MOUNT_MODES.md).

## Releases (CI)

Push a version tag to build both architectures and publish a GitHub Release:

```bash
# bump VERSION, commit, then:
git tag v0.0.1
git push origin v0.0.1
```

Or **Actions → Release DMG → Run workflow**.  
Workflow: [`.github/workflows/release-dmg.yml`](.github/workflows/release-dmg.yml)

Version source: [`VERSION`](VERSION).

## Docs

- [Mount modes (FUSE vs NFS)](docs/MOUNT_MODES.md)  
- [Packaging & install notes](docs/PACKAGING.md)  
