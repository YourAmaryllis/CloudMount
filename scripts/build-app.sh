#!/usr/bin/env bash
# Assemble CloudMount.app: native Swift menu-bar shell (mac-app/) wrapping
# the Python core (Contents/Resources/wasabi/), same layout the old
# bash-launcher build used. Requires a Swift toolchain (Xcode or CLT).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
APP="$DIST/CloudMount.app"
CONTENTS="$APP/Contents"
MACOS="$CONTENTS/MacOS"
RES="$CONTENTS/Resources"
VERSION="$(tr -d '[:space:]' <"$ROOT/VERSION" 2>/dev/null || echo "0.0.1")"
MAC_APP="$ROOT/mac-app"
SWIFT_CONFIG="${SWIFT_CONFIG:-release}"

rm -rf "$APP"
mkdir -p "$MACOS" "$RES"

# Copy project payload into Resources (rclone/python resolve relative to
# this tree; mac-app/ itself is excluded, it's not part of the app payload)
rsync -a \
  --exclude dist \
  --exclude '.git' \
  --exclude 'logs' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.github' \
  --exclude 'mac-app' \
  "$ROOT/" "$RES/wasabi/"

# Build the native Swift menu-bar shell. Release builds are universal
# (arm64 + x86_64) — the old pure-Python launcher ran on any Mac, and a
# compiled binary built plain on Apple Silicon CI would silently be
# arm64-only, breaking Intel Macs entirely rather than just running slower.
if [[ "$SWIFT_CONFIG" == "release" ]]; then
  ( cd "$MAC_APP" && swift build -c release --arch arm64 --arch x86_64 )
  SWIFT_BIN="$MAC_APP/.build/apple/Products/Release/CloudMountBar"
else
  ( cd "$MAC_APP" && swift build -c "$SWIFT_CONFIG" )
  SWIFT_BIN="$MAC_APP/.build/$SWIFT_CONFIG/CloudMountBar"
fi
cp "$SWIFT_BIN" "$MACOS/CloudMount"
chmod +x "$MACOS/CloudMount"

# Info.plist — LSUIElement: menu-bar only, no Dock icon, no app menu bar.
cat >"$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>CloudMount</string>
  <key>CFBundleDisplayName</key><string>CloudMount</string>
  <key>CFBundleIdentifier</key><string>com.youramaryllis.cloudmount</string>
  <key>CFBundleVersion</key><string>${VERSION}</string>
  <key>CFBundleShortVersionString</key><string>${VERSION}</string>
  <key>CFBundleExecutable</key><string>CloudMount</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

# Ad-hoc sign: LSUIElement / MenuBarExtra need a real bundle identity to
# behave reliably (same reason mac-app/Scripts/build-app.sh signs its own
# standalone test build). No Developer ID yet, so this is local-only.
codesign --force --deep --sign - "$APP"

# Do NOT bake rclone into the app by default — first run downloads into
# ~/Library/Application Support/YourAmaryllis/CloudMount/bin/<platform>/

echo "Built: $APP (v${VERSION})"
echo "Run:   open \"$APP\""
echo "Note: rclone downloads on first setup to Application Support (not into /Applications)."
