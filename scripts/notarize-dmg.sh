#!/usr/bin/env bash
# Notarize + staple a DMG built by build-dmg.sh. No-ops (with a warning,
# not a failure) if no notarization credentials are set, so unsigned local/
# dev builds keep working unchanged.
#
# Credentials, checked in this order:
#   1. APPLE_API_KEY_ID / APPLE_API_ISSUER / APPLE_API_KEY_P8 — an App Store
#      Connect API key (APPLE_API_KEY_P8 is the base64 contents of the
#      downloaded .p8 file). What CI uses.
#   2. NOTARY_KEYCHAIN_PROFILE — a profile saved locally via:
#        xcrun notarytool store-credentials <profile> \
#          --apple-id you@example.com --team-id TEAMID \
#          --password APP_SPECIFIC_PASSWORD   # from appleid.apple.com
#   3. APPLE_ID / APPLE_TEAM_ID / APPLE_APP_SPECIFIC_PASSWORD directly.
#
# See the "Signing & notarization" section in the README for setup.
set -euo pipefail
DMG="${1:?usage: notarize-dmg.sh <path-to-dmg>}"

if [[ -n "${APPLE_API_KEY_P8:-}" ]]; then
  KEY_FILE="$(mktemp -t cloudmount-notary-key).p8"
  trap 'rm -f "$KEY_FILE"' EXIT
  echo "$APPLE_API_KEY_P8" | base64 --decode >"$KEY_FILE"
  AUTH=(--key "$KEY_FILE" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER")
elif [[ -n "${NOTARY_KEYCHAIN_PROFILE:-}" ]]; then
  AUTH=(--keychain-profile "$NOTARY_KEYCHAIN_PROFILE")
elif [[ -n "${APPLE_ID:-}" && -n "${APPLE_TEAM_ID:-}" && -n "${APPLE_APP_SPECIFIC_PASSWORD:-}" ]]; then
  AUTH=(--apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_APP_SPECIFIC_PASSWORD")
else
  echo "No notarization credentials set — skipping ($DMG stays signed but not notarized)." >&2
  exit 0
fi

echo "Submitting $DMG for notarization (this can take a while — first-time submissions on a new Developer ID can take 30+ minutes)..."
xcrun notarytool submit "$DMG" "${AUTH[@]}" --wait
xcrun stapler staple "$DMG"
echo "Notarized & stapled: $DMG"
