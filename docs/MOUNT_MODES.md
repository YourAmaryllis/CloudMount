# Mount modes: FUSE and NFS

CloudMount supports **both** ways to expose an rclone remote on macOS. You can enable either or both in **Setup**, and pick a mode **per mount**.

## Two backends

| Mode | Command | Needs | How it feels in Finder |
|------|---------|--------|-------------------------|
| **fuse** | `rclone mount …` | Official rclone with FUSE support + **macFUSE** | A folder path you choose (e.g. under `~/CloudMount/…`) |
| **nfs** | `rclone nfsmount …` | rclone with `nfsmount` + macOS NFS client (built-in) | More like a **network / volume share** (eject-style) |

The same cloud remotes work with either mode. Only the **local plumbing** differs.

## Capability detection

| Capability | How it is detected |
|------------|--------------------|
| FUSE mount | `rclone mount` available and macFUSE present |
| macFUSE installed | macFUSE filesystem package present |
| NFS mount | `rclone nfsmount` available |

Homebrew’s rclone build on macOS often includes **nfsmount** but **not** FUSE `mount`. CloudMount downloads the **official** rclone binary on first setup so both modes can be available.

## Enabling modes (Setup tab)

- **Enable FUSE mounts** — requires macFUSE; if missing, use install help  
- **Enable NFS mounts** — usually works once official rclone is installed  

Unchecked modes are hidden when adding mounts.

### Install macFUSE

If Homebrew is available:

```bash
brew install --cask macfuse
```

Or install from [macfuse.github.io](https://macfuse.github.io/):

1. Download latest macFUSE  
2. Install the package  
3. Allow the system extension in System Settings  
4. Reboot if prompted  
5. Re-run capability detection in CloudMount  

Kernel extensions cannot be installed silently; user approval is required.

If `nfsmount` is missing, re-run **Setup** so the app re-downloads official rclone.

## Per-mount config

Each mount stores roughly:

```json
{
  "label": "Photos",
  "remote_path": "my-bucket/photos",
  "path": "~/CloudMount/photos",
  "mount_kind": "nfs",
  "vfs_cache_mode": "full"
}
```

`mount_kind` is `fuse` or `nfs`. Default prefers **nfs** when both are enabled (less dependence on macFUSE).

## Unmount

| Kind | Unmount |
|------|---------|
| fuse | Unmount the path + stop the rclone process |
| nfs | Same for the NFS mount path + stop `rclone nfsmount` |

## Why both

- **NFS** — share-like volumes, fewer macFUSE issues  
- **FUSE** — mount at an arbitrary path under your home folder  
- Detection + install help avoid “nothing mounts after install”

## Relation to DMG install

First launch of the app:

1. Downloads rclone if needed  
2. Detects FUSE / NFS capabilities  
3. Lets you enable modes and open macFUSE help if needed  

See [PACKAGING.md](./PACKAGING.md).
