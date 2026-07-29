# macOS packaging (DMG)

Goal: double-click install experience — not “clone a folder and symlink a SwiftBar plugin.”

## Target layout inside the DMG

```
CloudMount.dmg
  CloudMount.app          # or “Wasabi Mounts.app”
  Applications →          # standard drag target symlink
  README (optional)
```

### What the app contains (bundle)

```
CloudMount.app/Contents/
  MacOS/CloudMount              # launcher (Swift or bash stub → open UI / install plugin)
  Resources/
    vendor/rclone/darwin-arm64/rclone
    vendor/rclone/darwin-amd64/rclone   # fat app or separate builds
    plugins/rclone-mounts.10s.sh
    scripts/postinstall-helper.sh
  Info.plist
```

**Universal binary strategy (pick one):**

| Approach | Pros | Cons |
|----------|------|------|
| Two DMGs (arm64 / intel) | Smaller | Two downloads |
| One DMG, two rclone binaries, pick at runtime | One download | Larger |
| Universal rclone if available | Clean | Official may only ship per-arch zips |

We already pick arch at runtime (`ensure-rclone` / `platform_key`). DMG can ship **both** arch binaries under `Resources/vendor/rclone/`.

## Installer flow (first launch)

1. User drags **CloudMount.app** → `/Applications`.  
2. First open:  
   - Copy/link SwiftBar plugin into `~/Library/Application Support/SwiftBar/Plugins/` **or** use built-in `MenuBarExtra` (preferred long-term — no SwiftBar dependency).  
   - `ensure-rclone` if binaries missing.  
   - Capability wizard: detect FUSE / NFS; enable modes; help install macFUSE.  
3. Optional: Login Item for status menu.

**Short term (current bash stack):** app is a thin wrapper that:

- Runs `scripts/install-menubar.sh`  
- Opens “Setup” dialog (capabilities + instructions)  
- Leaves SwiftBar as menu host until native status item exists  

**Long term:** SwiftUI app owns menu bar; SwiftBar optional.

## Building a DMG (tooling)

### Option A — `create-dmg` (simple)

```bash
brew install create-dmg
create-dmg \
  --volname "CloudMount" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "CloudMount.app" 150 190 \
  --app-drop-link 450 190 \
  CloudMount-0.1.0.dmg \
  dist/CloudMount.app
```

### Option B — `appdmg` (JSON config)

```json
{
  "title": "CloudMount",
  "contents": [
    { "x": 150, "y": 200, "type": "file", "path": "dist/CloudMount.app" },
    { "x": 450, "y": 200, "type": "link", "path": "/Applications" }
  ]
}
```

### Option C — Xcode Archive → Organizer → Distribute (native Swift app)

Best when the UI is real SwiftUI; signs with Developer ID + notarization.

## Code signing & notarization (required for smooth Gatekeeper)

Without this, users get “app is damaged” / “can’t be opened”:

1. **Developer ID Application** certificate  
2. `codesign --deep --force --options runtime … CloudMount.app`  
3. Notarize: `xcrun notarytool submit …`  
4. Staple: `xcrun stapler staple CloudMount.app`  
5. Build DMG from stapled app; optionally notarize DMG too  

CI (GitHub Actions macos runner) can automate release DMGs.

## Scripts to add in-repo

| Script | Role |
|--------|------|
| `scripts/build-app-stub.sh` | Assemble `.app` from Resources + launcher |
| `scripts/build-dmg.sh` | create-dmg from `dist/` |
| `scripts/detect-capabilities` | JSON report for UI |
| `scripts/install-macfuse-help.sh` | brew cask or open website |

## User-facing install story

1. Download **CloudMount-x.y.z.dmg**  
2. Drag to Applications  
3. Open → allow if prompted  
4. Setup wizard: rclone ready · FUSE? · NFS? · Install macFUSE help  
5. Menu bar icon appears (SwiftBar or built-in)  
6. Open Mounts window → add host → mount  

No requirement to edit `~/.wasabi.json` or know about `rclone.conf` (after Keychain redesign).
