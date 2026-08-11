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

echo "Submitting $DMG for notarization..."
SUBMIT_OUT="$(xcrun notarytool submit "$DMG" "${AUTH[@]}" --no-wait 2>&1)"
echo "$SUBMIT_OUT"
SUBMISSION_ID="$(echo "$SUBMIT_OUT" | grep -m1 '^  id:' | awk '{print $2}')"
if [[ -z "$SUBMISSION_ID" ]]; then
  echo "Could not parse a submission ID from notarytool's output — aborting." >&2
  exit 1
fi

# `notarytool wait` polls Apple until the submission reaches a terminal
# state. A first-time submission on a new Developer ID can sit "In
# Progress" for 30-60+ minutes, and a single transient network blip on the
# runner during that window kills `submit --wait` outright with no retry
# of its own — so poll it here instead: submission IDs are Apple-side and
# outlive our local connection, so re-invoking `wait` just resumes polling
# the same submission, cheaply. Only bail immediately on a genuine
# rejection (status: Invalid), not on a transient error.
ATTEMPTS=0
MAX_ATTEMPTS=10
while true; do
  if WAIT_OUT="$(xcrun notarytool wait "$SUBMISSION_ID" "${AUTH[@]}" 2>&1)"; then
    echo "$WAIT_OUT"
    break
  fi
  echo "$WAIT_OUT"
  if echo "$WAIT_OUT" | grep -q "status: Invalid"; then
    echo "Notarization rejected (Invalid) — not retrying. Run 'xcrun notarytool log $SUBMISSION_ID' for details." >&2
    exit 1
  fi
  ATTEMPTS=$((ATTEMPTS + 1))
  if (( ATTEMPTS >= MAX_ATTEMPTS )); then
    echo "Gave up after $ATTEMPTS retries waiting on submission $SUBMISSION_ID." >&2
    exit 1
  fi
  echo "Transient error waiting on submission $SUBMISSION_ID (attempt $ATTEMPTS/$MAX_ATTEMPTS) — retrying in 30s..." >&2
  sleep 30
done

xcrun stapler staple "$DMG"
echo "Notarized & stapled: $DMG"
