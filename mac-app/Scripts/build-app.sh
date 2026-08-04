#!/bin/bash
# Builds the SwiftPM executable and wraps it in a real .app bundle.
# A bare `swift run` binary has no bundle identifier, so LSUIElement
# (no Dock icon) and MenuBarExtra don't behave reliably — this gives us a
# proper app to test against, same approach as ../../../lit/mac-app.
set -euo pipefail
cd "$(dirname "$0")/.."

CONFIGURATION="${1:-debug}"
APP_NAME="CloudMountBar"
APP_BUNDLE=".build/${APP_NAME}.app"

swift build -c "$CONFIGURATION"

rm -rf "$APP_BUNDLE"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

cp ".build/${CONFIGURATION}/${APP_NAME}" "$APP_BUNDLE/Contents/MacOS/${APP_NAME}"
cp "Resources/Info.plist" "$APP_BUNDLE/Contents/Info.plist"

codesign --force --deep --sign - "$APP_BUNDLE"

echo "Built: $APP_BUNDLE"
