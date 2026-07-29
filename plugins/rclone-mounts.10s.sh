#!/usr/bin/env bash
# <xbar.title>Wasabi Mounts</xbar.title>
# <xbar.version>v1.4</xbar.version>
# <xbar.author>YourAmaryllis</xbar.author>
# <xbar.desc>Menu-bar status, mount/unmount, configure Wasabi mounts (no Accessibility).</xbar.desc>
# <xbar.dependencies>bash,python3,curl,unzip,macFUSE</xbar.dependencies>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>true</swiftbar.hideLastUpdated>
# <swiftbar.refreshOnOpen>true</swiftbar.refreshOnOpen>
#
# CRITICAL SwiftBar / BitBar format:
#   Title | bash=/abs/path param1=arg1 param2=arg2 terminal=false refresh=true
#
# Parameters are separated by SPACES after the first "|", NOT by more "|" pipes.
# Using "| param1=..." causes SwiftBar to drop params → wasabi-action with no args
# → popup "wasabi-action: missing command".

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

SOURCE="${BASH_SOURCE[0]}"
while [[ -L "$SOURCE" ]]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
PLUGIN_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
ROOT="$(cd "$PLUGIN_DIR/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$ROOT/lib/common.sh"

ACTION="$ROOT/bin/wasabi-action"
STATUS_BIN="$ROOT/bin/wasabi-status"

# Emit one clickable menu line. Args become param1, param2, ...
action_line() {
  local title="$1"
  shift
  local parts=("bash=${ACTION}")
  local n=1
  for a in "$@"; do
    # Values must not contain spaces unless quoted; our ids/cmds don't.
    parts+=("param${n}=${a}")
    n=$((n + 1))
  done
  parts+=("terminal=false" "refresh=true")
  # Join with spaces after the title separator
  local joined
  joined="$(IFS=' '; echo "${parts[*]}")"
  echo "${title} | ${joined}"
}

total=0
up=0
rows=()
while IFS=$'\t' read -r id label st remote path; do
  total=$((total + 1))
  if [[ "$st" == "1" ]]; then
    up=$((up + 1))
  fi
  rows+=("$id|$label|$st|$remote|$path")
done < <("$STATUS_BIN" --tsv 2>/dev/null || true)

if [[ "$total" -eq 0 ]]; then
  echo "☁ +"
  echo "---"
  echo "No mounts yet"
  action_line "Add mount..." config add
  action_line "Configure..." config
  echo "---"
  action_line "Debug: ping log" ping
  action_line "Ensure rclone binary" ensure-rclone
  echo "Open logs | bash=/usr/bin/open param1=${ROOT}/logs terminal=false"
  echo "Refresh | refresh=true"
  exit 0
fi

if [[ "$up" -eq 0 ]]; then
  echo "☁ 0/${total}"
elif [[ "$up" -eq "$total" ]]; then
  echo "☁ ${up}"
else
  echo "☁ ${up}/${total}"
fi

echo "---"

for row in "${rows[@]}"; do
  IFS='|' read -r id label st remote path <<<"$row"
  if [[ "$st" == "1" ]]; then
    echo "✓ ${label}  (${id})"
    echo "${remote} -> ${path}"
    action_line "  Unmount ${label}" unmount "$id"
    echo "  Open in Finder | bash=/usr/bin/open param1=${path} terminal=false"
  else
    echo "○ ${label}  (${id})"
    echo "${remote} -> ${path}"
    action_line "  Mount ${label}" mount "$id"
  fi
  echo "---"
done

action_line "Mount all" mount-all
action_line "Unmount all" unmount-all
echo "---"
action_line "Add mount..." config add
action_line "Edit mount..." config edit
action_line "Remove mount..." config remove
action_line "Configure..." config
echo "---"
action_line "Debug: ping log" ping
action_line "Ensure rclone binary" ensure-rclone
echo "Open logs | bash=/usr/bin/open param1=${ROOT}/logs terminal=false"
echo "Open mounts.json | bash=/usr/bin/open param1=${ROOT}/config/mounts.json terminal=false"
echo "Refresh | refresh=true"
