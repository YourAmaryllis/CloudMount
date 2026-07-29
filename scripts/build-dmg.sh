#!/usr/bin/env bash
# Build CloudMount.dmg (unsigned). Install create-dmg for a nicer layout.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
"$ROOT/scripts/build-app.sh"

APP="$DIST/CloudMount.app"
STAGE="$DIST/dmg-stage"
DMG="$DIST/CloudMount-0.2.0.dmg"
VOL="CloudMount"

rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

if command -v create-dmg >/dev/null 2>&1; then
  create-dmg \
    --volname "$VOL" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "CloudMount.app" 150 190 \
    --app-drop-link 450 190 \
    "$DMG" \
    "$STAGE"
else
  # hdiutil fallback
  RW="$DIST/CloudMount.rw.dmg"
  rm -f "$RW"
  hdiutil create -volname "$VOL" -srcfolder "$STAGE" -ov -format UDRW "$RW"
  hdiutil convert "$RW" -format UDZO -o "$DMG"
  rm -f "$RW"
fi

echo "DMG: $DMG"
echo "Note: not signed/notarized — right-click Open on first launch if Gatekeeper blocks."
