# CloudMount (wasabi project)

Menu-bar + single-window manager for **rclone mounts** (Wasabi/S3 and any rclone remote).

- **FUSE** (`rclone mount`) and **NFS** (`rclone nfsmount`) — pick per mount  
- Credentials in **macOS Keychain**  
- App-owned state under Application Support (not hand-edited `~/.wasabi.json`)  
- Managed `rclone.conf`  
- SwiftBar status icon + full UI at `http://127.0.0.1:8765/`  
- DMG: `dist/CloudMount-0.2.0.dmg`

> Design notes: [docs/REDESIGN.md](docs/REDESIGN.md) · [docs/MOUNT_MODES.md](docs/MOUNT_MODES.md) · [docs/PACKAGING.md](docs/PACKAGING.md)

## Quick start (dev)

```bash
cd ~/YourAmaryllis/wasabi
chmod +x bin/cloudmount scripts/*.sh plugins/*.sh
python3 bin/cloudmount setup          # rclone binary, migrate, Keychain import
python3 bin/cloudmount install-menubar
python3 bin/cloudmount gui            # opens browser UI
```

Or open the app:

```bash
./scripts/build-app.sh
open dist/CloudMount.app
```

DMG:

```bash
./scripts/build-dmg.sh
open dist/CloudMount-0.2.0.dmg
```

(Unsigned — first launch may need right-click → Open.)

## UI

| Tab | What |
|-----|------|
| **Mounts** | List, Mount / Unmount, Add / Edit / Remove; kind **nfs** or **fuse** |
| **Hosts** | rclone remotes; access/secret keys → Keychain; Test connection |
| **Setup** | Capabilities (macFUSE / nfsmount), enable modes, install help |

## CLI

```bash
python3 bin/cloudmount status
python3 bin/cloudmount capabilities
python3 bin/cloudmount host-list
python3 bin/cloudmount host-test <id>
python3 bin/cloudmount mount <id>
python3 bin/cloudmount unmount <id>
python3 bin/cloudmount prefs --default-kind nfs --enable-fuse true --enable-nfs true
```

## Where data lives

| What | Where |
|------|--------|
| Mounts / hosts / prefs | `~/Library/Application Support/YourAmaryllis/CloudMount/state.json` |
| rclone config (no secrets) | `…/CloudMount/rclone.conf` |
| Access keys | Keychain service `com.youramaryllis.cloudmount` |
| Logs | `…/CloudMount/logs/` |
| Official rclone binary | `vendor/rclone/<platform>/` (also bundled in .app) |

First `setup` migrates `~/.wasabi.json` + `config/mounts.json` once if present.

## Mount kinds

| Kind | Command | Needs | Feel |
|------|---------|--------|------|
| **nfs** | `rclone nfsmount` | official rclone | Network/share-like volume |
| **fuse** | `rclone mount` | official rclone + **macFUSE** | Local path you choose |

```bash
python3 bin/cloudmount install-macfuse-help
python3 bin/cloudmount install-macfuse-help --brew
```

## Menu bar (SwiftBar)

After `install-menubar`, SwiftBar shows **☁**.  
**Open CloudMount…** launches the UI. Quick mount/unmount per entry.

Plugin: `plugins/cloudmount.5s.sh`  
(params after `|` are **space**-separated for SwiftBar 2.x.)

## YeungAD media bucket

Wasabi bucket for the architecture site: **`yeungad`**.

## vs RClone Manager

We stay **mount + hosts + Keychain + menu bar**, not a full remote file manager.  
See [docs/REDESIGN.md](docs/REDESIGN.md) for the comparison and brew-vs-official rclone notes.
