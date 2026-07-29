# Packaging and install

## User install (recommended)

1. Download the DMG for your Mac from [Releases](https://github.com/arthurtsang/CloudMount/releases)  
   - **Apple Silicon:** `CloudMount-*-darwin-arm64.dmg`  
   - **Intel:** `CloudMount-*-darwin-amd64.dmg`  
2. Drag **CloudMount.app** to **Applications**  
3. Open the app (right-click → **Open** if Gatekeeper warns — builds are unsigned for now)  
4. Setup: rclone is downloaded if needed; check FUSE / NFS capabilities  
5. Add a host → add mounts → mount  

You do not need to edit rclone config files by hand. Secrets go in the macOS Keychain.

## What is in the DMG

```
CloudMount.dmg
  CloudMount.app
  Applications →          # drag target
```

### App bundle (simplified)

```
CloudMount.app/Contents/
  MacOS/CloudMount              # launcher
  Resources/…                   # app code
  Info.plist
```

**rclone is not required inside the DMG.** On first run the app downloads the official binary into Application Support:

```text
~/Library/Application Support/YourAmaryllis/CloudMount/
  bin/darwin-arm64/rclone    # or darwin-amd64
  rclone.conf
  state.json
  logs/
```

## Local build

```bash
./scripts/build-app.sh
./scripts/build-dmg.sh
# ARCH_SUFFIX=arm64|amd64 optional; default from uname -m
```

## CI release

[`.github/workflows/release-dmg.yml`](../.github/workflows/release-dmg.yml):

| Runner | Arch | Artifact |
|--------|------|----------|
| `macos-14` | arm64 | `CloudMount-<ver>-darwin-arm64.dmg` |
| `macos-13` | amd64 | `CloudMount-<ver>-darwin-amd64.dmg` |

Both DMGs are attached to one GitHub Release on this repository (`GITHUB_TOKEN`).

## Code signing & notarization

Without Developer ID + notarization, macOS may show “can’t be opened” / “damaged”:

1. Sign with **Developer ID Application**  
2. Notarize with `notarytool`  
3. Staple the app (and optionally the DMG)  

Current public builds may still be **unsigned**. Use right-click → Open until signing is enabled.
