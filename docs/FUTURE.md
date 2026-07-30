# Future enhancements

Ideas that fit CloudMount’s scope: **light tray + mounts + hosts**, not a full remote file manager.

Status is informal. Prefer small, shippable steps over redesigns.

## High priority

| Idea | Why | Notes |
|------|-----|--------|
| **Auto-mount on login / tray start** | After reboot, remount without clicking through the UI | Per-mount toggle; skip if already up; surface auth failures (e.g. AWS SSO) without looping forever |
| **AWS session death while mounted** | SSO can expire mid-day | Detect dead mount / auth errors; toast + optional one-click **AWS login** and remount — only on failure, not proactive polling |
| **Code signing** | Gatekeeper / SmartScreen friction | Notarize macOS DMG; sign Windows installer when certs are available |
| **Read-only mount** | Safer “cloud only” use | Pass rclone `--read-only` (or equivalent); per-mount checkbox |

## Nice to have

| Idea | Why | Notes |
|------|-----|--------|
| **Tray: open local path / copy remote path** | Faster than the web UI for daily use | One click from the mount submenu |
| **Lightweight health** | Notice dead mounts sooner | Occasional `lsd`/head on mounted remotes; red tray badge — no full tree walk |
| **Import from existing `rclone.conf`** | Easier for people who already use rclone | Map remotes → hosts; detect profile vs static keys where possible |
| **Linux tray** | Same product shape as Windows | `pystray` already used on Windows; document FUSE requirements |

## Maybe later (easy to overbuild)

- Scheduled unmount / “unmount when idle”
- Bidirectional sync UI
- Multi-account storage browser
- Competing with full apps (RClone Manager–style panels)

## Explicitly out of scope (for now)

- Replacing backup products (Time Machine, Borg, restic UIs)
- Full remote file manager (copy/move/rename trees as primary UX)
- Reimplementing AWS SSO or Roles Anywhere (use `~/.aws` profiles + CLI)

## Done (reference)

Shipped items live in the README and release notes; don’t duplicate long history here. Highlights:

- FUSE / NFS (macOS), WinFsp (Windows), system tray
- Keychain / Credential Manager for secrets
- S3 static keys + **AWS profile** (SSO login on failure only)
- Slim S3 host form; Proton Drive support
- Public releases: macOS DMG + Windows setup/zip

## How to add ideas

1. Prefer a short row in **High priority** or **Nice to have**.  
2. Say *why* in one line.  
3. If it fights “light menu-bar tool,” put it under **Maybe later** or **Out of scope**.
