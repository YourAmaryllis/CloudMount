#!/usr/bin/env bash
# Assemble CloudMount.app (unsigned stub for local testing / CI).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
APP="$DIST/CloudMount.app"
CONTENTS="$APP/Contents"
MACOS="$CONTENTS/MacOS"
RES="$CONTENTS/Resources"
VERSION="$(tr -d '[:space:]' <"$ROOT/VERSION" 2>/dev/null || echo "0.0.1")"

rm -rf "$APP"
mkdir -p "$MACOS" "$RES"

# Copy project payload into Resources
rsync -a \
  --exclude dist \
  --exclude '.git' \
  --exclude 'logs' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.github' \
  "$ROOT/" "$RES/wasabi/"

# Launcher
cat >"$MACOS/CloudMount" <<'LAUNCH'
#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RES="$HERE/../Resources"
export CLOUDMOUNT_RESOURCES="$RES"
export CLOUDMOUNT_APP_EXE="$HERE/CloudMount"
export PYTHONPATH="$RES/wasabi${PYTHONPATH:+:$PYTHONPATH}"
# Prefer python3 from path
PY="$(command -v python3 || true)"
if [[ -z "$PY" ]]; then
  osascript -e 'display alert "CloudMount" message "python3 not found. Install Python 3 or Xcode CLT."'
  exit 1
fi
# Run setup (rclone download, migration, SwiftBar wiring) then open GUI.
# Logged instead of discarded so first-run failures are diagnosable.
LOGDIR="$HOME/Library/Application Support/YourAmaryllis/CloudMount/logs"
mkdir -p "$LOGDIR" 2>/dev/null || true
"$PY" "$RES/wasabi/bin/cloudmount" setup >>"$LOGDIR/setup.log" 2>&1 || true
exec "$PY" "$RES/wasabi/bin/cloudmount" gui --port 8765
LAUNCH
chmod +x "$MACOS/CloudMount"

# Info.plist
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
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

# Do NOT bake rclone into the app by default — first run downloads into
# ~/Library/Application Support/YourAmaryllis/CloudMount/bin/<platform>/

echo "Built: $APP (v${VERSION})"
echo "Run:   open \"$APP\""
echo "Note: rclone downloads on first setup to Application Support (not into /Applications)."
