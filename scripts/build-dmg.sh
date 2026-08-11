#!/usr/bin/env bash
# Build CloudMount.dmg (unsigned). Install create-dmg for a nicer layout.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
VERSION="$(tr -d '[:space:]' <"$ROOT/VERSION" 2>/dev/null || echo "0.0.1")"
"$ROOT/scripts/build-app.sh"

APP="$DIST/CloudMount.app"
STAGE="$DIST/dmg-stage"
DMG="$DIST/CloudMount-${VERSION}.dmg"
VOL="CloudMount"

rm -rf "$STAGE"
rm -f "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -sf /Applications "$STAGE/Applications"

if command -v create-dmg >/dev/null 2>&1; then
  create-dmg \
    --volname "$VOL" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "CloudMount.app" 150 190 \
    --app-drop-link 450 190 \
    "$DMG" \
    "$STAGE" || true
  if [[ ! -f "$DMG" ]]; then
    echo "create-dmg failed; falling back to hdiutil" >&2
  fi
fi

if [[ ! -f "$DMG" ]]; then
  RW="$DIST/CloudMount.rw.dmg"
  rm -f "$RW"
  hdiutil create -volname "$VOL" -srcfolder "$STAGE" -ov -format UDRW "$RW"
  hdiutil convert "$RW" -format UDZO -o "$DMG"
  rm -f "$RW"
fi

echo "$DMG" >"$DIST/dmg-path.txt"
ls -lh "$DMG"
echo "DMG: $DMG"

if codesign -dv "$APP" 2>&1 | grep -q "Authority=Developer ID Application"; then
  echo "Signed with a Developer ID certificate. Run scripts/notarize-dmg.sh \"$DMG\" to notarize."
else
  echo "Note: not signed/notarized — right-click Open on first launch if Gatekeeper blocks."
fi
