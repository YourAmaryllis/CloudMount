# Mount modes: FUSE and NFS

The app supports **both** ways to expose an rclone remote on macOS. Users can enable either or both (when setting up), and pick a mode **per mount**.

## Two backends

| Mode | Command | Needs | How it feels in Finder |
|------|---------|--------|-------------------------|
| **fuse** | `rclone mount …` | Official rclone **with cmount** + **macFUSE** (or FSKit-capable macFUSE 5.x) | Often a path under home (e.g. `~/nas`) that feels like a normal folder |
| **nfs** | `rclone nfsmount …` | rclone that includes `nfsmount` + macOS NFS client (built-in) | More like a **network / volume share** (often under `/Volumes/…`, eject-style) |

Same remote types (S3, Wasabi, Drive, …) work with either. Only the **local plumbing** differs.

## Capability detection

At setup and in UI:

| Capability | How we detect |
|------------|----------------|
| Official-style `mount` (FUSE) | Vendor rclone: `rclone mount -h` succeeds **and** not the brew “mount disabled” message; plus macFUSE present |
| macFUSE installed | `/Library/Filesystems/macfuse.fs` and/or `pkgutil --pkgs` matching macfuse |
| `nfsmount` available | Vendor rclone: `rclone nfsmount -h` exits 0 |

Brew’s macOS rclone often has **nfsmount** but **not** FUSE `mount`. Our **vendored official binary** usually has **both**.

## Enabling during binary / first-run setup

```
[x] Enable FUSE mounts   → requires macFUSE; if missing → Install help
[x] Enable NFS mounts    → usually just works with our rclone
```

User can leave one unchecked → that mode is hidden when adding mounts.

### Help install macFUSE

If possible (Homebrew present):

```bash
brew install --cask macfuse
```

Else open https://macfuse.github.io/ and show:

1. Download latest macFUSE 5.x  
2. Install DMG  
3. Allow system extension in System Settings  
4. Reboot if prompted  
5. Re-run “Detect capabilities”

We **cannot** silently install kernel extensions without user approval; helper = script + UI copy + optional brew.

NFS: no extra package; if `nfsmount` missing, the binary is wrong → re-run ensure-rclone (official).

## Per-mount config

```json
{
  "id": "nas",
  "label": "NAS",
  "remote": "wasabi:nas-tsang2",
  "path": "~/nas",
  "mount_kind": "nfs",
  "vfs_cache_mode": "full"
}
```

`mount_kind`: `fuse` | `nfs` (default: prefer `nfs` if only NFS enabled; else `fuse` if only FUSE; else user choice).

## Unmount

| Kind | Unmount |
|------|---------|
| fuse | `umount` / `diskutil unmount` + kill rclone if needed |
| nfs | same path unmount + kill `rclone nfsmount` process |

## Why both

- You prefer **NFS** (share-like, less macFUSE drama).  
- Others want **FUSE** path under `~/…`.  
- Detection + install help avoids “nothing works” after install.

## Relation to DMG install

DMG installs the app + vendor rclone + optional “first-run wizard” that:

1. Downloads rclone if needed  
2. Runs capability detection  
3. Offers enable FUSE / enable NFS  
4. Opens macFUSE install instructions if FUSE enabled but missing  

See [PACKAGING.md](./PACKAGING.md).
