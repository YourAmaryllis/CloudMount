# Redesign: menu-bar cloud mounts (working name “Wasabi”)

**Date:** 2026-07-29 (updated same day: dual FUSE/NFS + DMG)  
**Status:** Design + partial interim bash support (`mount_kind`, `wasabi-capabilities`)  
**Codebase today:** `~/YourAmaryllis/wasabi` (SwiftBar plugin + bash + rclone vendor binary)

**Also read:** [MOUNT_MODES.md](./MOUNT_MODES.md) · [PACKAGING.md](./PACKAGING.md)

Despite the name “Wasabi,” the product is a **thin, opinionated mount manager on top of rclone**. It should work for **any rclone remote type** (S3/Wasabi, Drive, SFTP, B2, …), not only Wasabi buckets.

---

## 1. Goals (from requirements)

| # | Requirement | Today | Target |
|---|-------------|--------|--------|
| 1 | No external config files the user must edit | `~/.wasabi.json`, `config/mounts.json`, relies on `~/.config/rclone/rclone.conf` | All durable settings owned by the app; no hand-edited sidecar files |
| 2 | Credentials in macOS Keychain | Plain JSON on disk | Keychain (and later Windows Credential Manager / DPAPI) |
| 3 | Don’t assume a pre-existing rclone “wasabi” host | Uses remote name `wasabi:` already in rclone.conf + env_auth | App creates/updates remotes; mounts reference remotes the app knows about |
| 4 | One consolidated mounts window | Many osascript dialogs + YAML/JSON | Single window: list mounts, Mount / Unmount, Add / Edit / Remove |
| 5 | Hosts setup as separate flow (or tab) | Not really managed | Separate **Hosts** UI; mount editor only allows remotes that exist (or offers “create host…”) |
| 6 | FUSE **and** NFS mounts | FUSE-only (`rclone mount`) | Per-mount `fuse` \| `nfs`; detect macFUSE / nfsmount; help install |
| 7 | Good Mac install UX | Manual clone + script | **DMG** → Applications; first-run wizard |
| 8 | Keep menu-bar feel | SwiftBar | SwiftBar short-term; native `MenuBarExtra` long-term |

Non-goals for v1 of the redesign:

- Full remote file browser / sync jobs / bandwidth graphs (that’s RClone Manager territory).
- Replacing rclone itself — we still **run** official rclone binaries.

---

## 2. Product shape

### 2.1 Menu bar (status only + entry points)

```
☁ 1/2                    ← glance: mounted / configured
  ─────────────────
  Open Mounts…           ← opens main window
  Open Hosts…            ← opens hosts window (or same app, Hosts tab)
  ─────────────────
  Quick: Mount all
  Quick: Unmount all
  ─────────────────
  Quit
```

Menu bar stays **OpenUsage-simple**. Real configuration is a **real app window**, not a stack of system dialogs.

### 2.2 Main window — Mounts

| Column / control | Meaning |
|------------------|---------|
| Name | Display label |
| Host | rclone remote name (e.g. `wasabi-prod`) |
| Path on remote | `nas-tsang2` or `bucket/prefix` |
| Local path | `~/nas` or `/Volumes/…` style for NFS |
| Kind | **FUSE** or **NFS** |
| State | Mounted / Unmounted / Error |
| Actions | Mount · Unmount · Edit · Remove |

Toolbar: **Add mount…**, **Refresh**, optional **Open local folder**.

Validation when adding/editing a mount:

1. Selected **host must exist** in the app’s host registry (which is also reflected into rclone config).
2. If no hosts yet → block with “Create a host first” and deep-link to Hosts UI.

### 2.3 Hosts window (or tab)

A **host** = one rclone remote definition (what people often call “rclone config entry”).

| Field | Example |
|-------|---------|
| Name | `wasabi-home` (becomes `wasabi-home:` in rclone) |
| Type | `s3`, `drive`, `sftp`, … |
| Provider-specific | Wasabi: endpoint, region, provider=Wasabi |
| Credentials | Stored in **Keychain**, never in plaintext JSON |
| Test | `rclone lsd name:` with injected config |

For S3/Wasabi:

- Access key + secret → Keychain items namespaced by host id.
- Non-secret settings (endpoint, region, provider) → app store (see below).

App writes (or rewrites) a **managed** rclone config fragment so CLI and mounts stay consistent.

---

## 3. Where configuration lives (no `~/.wasabi.json` / no user-facing `mounts.json`)

### 3.1 Secrets — Keychain (macOS)

Use the Security framework / `security` CLI / SecItem API:

| Item | Example |
|------|---------|
| Service | `com.youramaryllis.cloudmount` (or final bundle id) |
| Account | `host/<hostId>/access_key` |
| Account | `host/<hostId>/secret_key` |
| Optional | OAuth tokens for Google Drive remotes later |

Never write access keys into git, `~/`, or Application Support as plain files.

**Windows later:** Credential Manager / DPAPI with the same logical keys.

### 3.2 Non-secret app state — Application Support

Single SQLite DB or one JSON **owned only by the app** (not a “user edits this file” contract):

```
~/Library/Application Support/YourAmaryllis/CloudMount/
  state.db          # hosts metadata, mounts, prefs
  # OR state.json   # only if we keep it tiny and never document it for hand-editing
```

Suggested tables / documents:

```text
hosts:
  id, name, type, provider, endpoint, region, extra_json, created_at

mounts:
  id, label, host_id, remote_path, local_path, vfs_cache_mode, sort_order

prefs:
  key, value
  # e.g. auto_mount_on_login, rclone_channel (stable/current)
```

**User-facing rule:** configuration is done **only in the UI**. Files under Application Support are an implementation detail (like Safari bookmarks SQLite).

### 3.3 rclone config — managed, not assumed

Two viable strategies (pick one in implementation):

**A. Private rclone config (recommended)**  
```text
Application Support/.../rclone.conf
```
Always invoke:

```bash
rclone --config "$APP_RCLONE_CONF" ...
```

- Zero dependency on the user’s existing `~/.config/rclone/rclone.conf`.
- Hosts UI fully owns remotes.
- Credentials: either rclone.conf with obscure, **or** empty keys + env from Keychain at mount time (`env_auth` / explicit flags). Prefer **Keychain → env or `RCLONE_CONFIG_*` at process start** so secrets never sit on disk.

**B. Merge into user rclone.conf**  
Harder, risk of clobbering user’s other remotes. Avoid for v1.

### 3.4 What we delete / stop using

| Path | Action |
|------|--------|
| `~/.wasabi.json` | Stop reading; migrate keys into Keychain once if present |
| `config/mounts.json` / `mounts.yaml` | Stop using; migrate rows into app state once |
| Hard-coded remote name `wasabi` | Replace with host records |
| Stack of `osascript` config dialogs | Replace with one real window |

---

## 4. Runtime architecture

```
┌─────────────────────────────────────────────┐
│  Menu bar host (SwiftBar thin shim OR       │
│  native NSStatusItem in the same app)       │
└─────────────────┬───────────────────────────┘
                  │ open window / quick mount
┌─────────────────▼───────────────────────────┐
│  CloudMount.app (SwiftUI / AppKit)          │
│  • Mounts window                            │
│  • Hosts window                             │
│  • Keychain + Application Support state     │
└─────────────────┬───────────────────────────┘
                  │ spawn / control
┌─────────────────▼───────────────────────────┐
│  vendor/rclone/<platform>/rclone            │
│  (official build with cmount)               │
│  --config <app rclone.conf>                 │
│  credentials from Keychain at spawn         │
└─────────────────────────────────────────────┘
```

### 4.0 Dual mount modes (FUSE + NFS)

See **[MOUNT_MODES.md](./MOUNT_MODES.md)**.

- **fuse:** `rclone mount` → path often under `~/…` (needs macFUSE + cmount binary).  
- **nfs:** `rclone nfsmount` → share/volume feel (no macFUSE; preferred default for many users).  
- First-run / binary setup: detect both; user enables one or both; install help for macFUSE (`brew install --cask macfuse` or https://macfuse.github.io/).  
- Interim CLI: `wasabi-capabilities`, `mount_kind` in mount records.

### 4.1 Official rclone binary (keep)

Continue vendoring **official** rclone per platform (has both `mount` and `nfsmount`):

| Platform key | Binary |
|--------------|--------|
| `darwin-arm64` | Apple Silicon |
| `darwin-amd64` | Intel Mac |
| `windows-amd64` | Windows later |

`ensure-rclone` (or in-app updater) downloads from `downloads.rclone.org`, never leaves a free-floating tree in `$HOME`.

### 4.2 Why not Homebrew’s rclone? (this is a real, specific difference)

Homebrew’s macOS formula **intentionally builds rclone without FUSE/`cmount` support** (see [rclone#5373](https://github.com/rclone/rclone/issues/5373) and [formulae.brew.sh/formula/rclone](https://formulae.brew.sh/formula/rclone)):

> Homebrew’s installation does not include the `mount` subcommand on macOS which depends on FUSE; use `nfsmount` instead.

Historical reason: Homebrew avoided depending on macFUSE (licensing / closed-source transition of osxfuse). So:

| | Official binary (rclone.org) | `brew install rclone` |
|--|------------------------------|------------------------|
| `rclone copy/sync/ls` | Yes | Yes |
| `rclone mount` (FUSE/macFUSE) | **Yes** (needs macFUSE installed) | **No** — mount disabled at build time |
| `rclone nfsmount` | Yes (where supported) | Suggested alternative on brew |
| Linked with cmount/FUSE tags | Yes | No |

So the difference is **not** “brew is older” or “brew is a little weaker.” It is:

**Brew’s macOS rclone is a different build flavor: core CLI without FUSE mount.**  
Our app needs **mount**, so we must ship or download the **official** (or self-built with FUSE tags) binary. RClone Manager does the same class of thing: it downloads rclone itself rather than trusting a mount-less brew install.

You still need **macFUSE** (or fuse-t / alternative) installed on the system for mount to work; the binary alone isn’t enough.

### 4.3 Process lifecycle

- Mounts started with a **new process session** so the menu bar / UI exit does not kill rclone.
- Track PID + mount path; Unmount uses `umount` / `diskutil unmount` then SIGTERM if needed.

---

## 5. UI flows (consolidated)

### 5.1 First launch

1. Ensure vendor rclone for this arch.
2. Empty hosts → show Hosts: “Add your first cloud host.”
3. Add Wasabi host → keys go to Keychain → write managed remote.
4. Mounts: Add mount → pick host → pick bucket/path → local folder → Mount.

### 5.2 Add host (Wasabi / S3 example)

```
Name:     wasabi-home
Type:     S3
Provider: Wasabi
Endpoint: https://s3.us-east-1.wasabisys.com
Region:   us-east-1
Access key: ********   → Keychain
Secret key: ********   → Keychain
[ Test connection ]
```

### 5.3 Add mount

```
Label:     NAS
Host:      [ wasabi-home ▼ ]   // only existing hosts; + Create host…
Remote:    nas-tsang2          // or browse via rclone lsd
Local:     ~/nas               // folder picker
Cache:     full
[ Save ] [ Save & Mount ]
```

### 5.4 Separate Hosts menu item

Recommended:

- **Menu → Open Mounts…** and **Open Hosts…** as two entries (or one window with two tabs).
- Mounts editor **refuses** unknown hosts and offers jump to Hosts if the selected host was deleted.

---

## 6. Comparison: RClone Manager vs this app

Upstream: [Zarestia-Dev/rclone-manager](https://github.com/Zarestia-Dev/rclone-manager)

### 6.1 What RClone Manager is

- Full **desktop GUI** (Angular + Tauri): Linux, Windows, macOS, Android beta.
- **Nautilus-style remote browser**, previews, copy/move/delete.
- Mount **and** serve (WebDAV, SFTP, HTTP, FTP).
- Job watcher, bandwidth control, headless/server mode.
- Downloads rclone automatically; documents macFUSE / WinFsp.
- General-purpose “rclone control panel.”

### 6.2 What our app is (target)

- **Mount-first** tool: status in menu bar, one clean window for mounts + hosts.
- **Opinionated security:** Keychain for secrets; no user-edited credential files.
- **Minimal surface:** not a file manager; Finder is the browser after mount.
- **Project-owned official rclone binary** for reliable `mount` on Mac.
- Branding may stay “Wasabi” for your stack, but architecture is **rclone multi-backend**.

### 6.3 Side-by-side

| Dimension | RClone Manager | Our app (redesign) |
|-----------|----------------|--------------------|
| Primary job | Full rclone GUI + browser + jobs + serve | Mounts + host credentials |
| UI model | Large multi-panel desktop app | Menu bar + 1–2 focused windows |
| File browse | Built-in Nautilus | Finder via mounted path |
| Sync/copy jobs | First-class | Out of scope v1 |
| Serve (WebDAV/SFTP) | Yes | Out of scope v1 |
| Credentials | Its own settings / rclone config | **Keychain-first** |
| Assumes existing rclone.conf | Often works with system rclone | **Managed private config** |
| macOS mount binary | Downloads capable rclone | Same idea: **official** binary, not brew |
| Scope | Power users / all remotes / all jobs | Fast “is it mounted?” + fix mounts |
| Windows | Supported | Planned (same model) |

### 6.4 Is the main difference “we don’t use brew rclone”?

**No. That is one technical prerequisite, not the product difference.**

1. **Brew vs official** — Both our app and any serious mount GUI must avoid brew’s mount-less macOS build (or use `nfsmount` instead of FUSE mount). That levels the field for “can mount at all.”
2. **Product difference** — RClone Manager is a **full suite**. We are a **narrow mount + hosts manager** with menu-bar status and Keychain-centric secrets.
3. **UX difference** — We optimize for “see mounts, toggle them, add a host/bucket without editing conf files,” not for remote file management UI.
4. **Ops difference** — We deliberately **do not** require the user to pre-configure `rclone config` or keep JSON in `$HOME`.

If we only swapped brew → official binary and kept the current SwiftBar dialog mess, we would still not be “done.” The redesign is about **configuration model and UI**, with the correct rclone binary as foundation.

---

## 7. Migration plan (from current bash app)

1. One-shot import on first launch of new app:
   - Read `~/.wasabi.json` if present → Keychain for a default host.
   - Read `config/mounts.json` → mounts table.
   - Optionally import matching section from `~/.config/rclone/rclone.conf` if remote name matches.
2. Leave old files in place but **stop reading** them after successful import (optionally delete with user consent).
3. Retire SwiftBar plugin once NSStatusItem lives in the app (or keep a thin plugin that only opens the app via URL scheme).

---

## 8. Implementation sketch (next engineering phase)

Suggested stack for macOS-native feel + Keychain:

| Layer | Choice |
|-------|--------|
| UI | SwiftUI app + `MenuBarExtra` (menu bar stays; better than SwiftBar long-term) |
| Short-term menu | **SwiftBar** plugin (current) until app ships |
| Storage | SQLite (GRDB) or AppStorage + files for non-secrets |
| Secrets | Keychain via Security framework |
| rclone | Existing `vendor/rclone` + ensure-download |
| Mount | `fuse` and `nfs` per mount; capability detection |
| Distribute | **Signed + notarized DMG** ([PACKAGING.md](./PACKAGING.md)) |
| Windows later | Tauri or WinUI; same state schema |

Phased delivery:

1. **P0** — Capability detection + dual mount_kind (partially done in bash); Keychain + managed hosts.  
2. **P1** — SwiftUI Mounts + Hosts window; FUSE/NFS picker; install-macFUSE help.  
3. **P2** — Menu bar in-app; DMG build + notarization; import old configs.  
4. **P3** — Windows port.

Keep bash tools as `bin/` for debugging; UI becomes source of truth.

---

## 9. Decisions to confirm before coding

1. **App name / bundle id** — keep “Wasabi” vs rename to “CloudMount” / “YourAmaryllis Mounts”?  
2. **Hosts vs tabs** — separate windows or one window with tabs? (Design above supports both; recommend **one window, two tabs** for simplicity.)  
3. **Share managed rclone.conf with CLI** — expose “Copy CLI snippet” that uses `--config` and never prints secrets.  
4. **macFUSE vs fuse-t** — document dependency; optional install link in Hosts empty state.

---

## 10. Summary

- Redesign consolidates configuration **inside the app**, secrets in **Keychain**, and **hosts + mounts** as first-class objects with managed rclone config.  
- The app remains a **mount-centric rclone front-end**, not a clone of RClone Manager’s full suite.  
- Using the **official rclone binary** (not brew) is **necessary for FUSE `mount` on macOS**, and is shared wisdom with other mount GUIs — but it is **not** the only or main product differentiator versus RClone Manager.

Once this design is accepted, implementation can replace the current SwiftBar/osascript stack incrementally without preserving `~/.wasabi.json` or user-edited `mounts.json` as part of the public contract.
