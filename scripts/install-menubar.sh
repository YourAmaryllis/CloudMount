#!/usr/bin/env bash
# Install the menu-bar plugin into SwiftBar or xbar plugins folder.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_SRC="$ROOT/plugins/rclone-mounts.10s.sh"

chmod +x \
  "$ROOT/bin/ensure-rclone" \
  "$ROOT/bin/wasabi-mount" \
  "$ROOT/bin/wasabi-unmount" \
  "$ROOT/bin/wasabi-status" \
  "$ROOT/scripts/mount-all.sh" \
  "$PLUGIN_SRC"

# Fetch official rclone for this Mac (arm64 or amd64)
"$ROOT/bin/ensure-rclone"

# Prefer SwiftBar, then xbar
candidates=(
  "$HOME/Library/Application Support/SwiftBar/Plugins"
  "$HOME/Library/Application Support/xbar/plugins"
  "$HOME/Library/Application Support/xbar/xbar/plugins"
)

target_dir=""
for d in "${candidates[@]}"; do
  if [[ -d "$d" ]]; then
    target_dir="$d"
    break
  fi
done

if [[ -z "$target_dir" ]]; then
  # Default: create SwiftBar plugins dir (install SwiftBar from brew cask)
  target_dir="$HOME/Library/Application Support/SwiftBar/Plugins"
  mkdir -p "$target_dir"
  echo "Created $target_dir"
  echo "If you don't have a host yet, install one of:"
  echo "  brew install --cask swiftbar   # recommended"
  echo "  brew install --cask xbar"
fi

link="$target_dir/rclone-mounts.10s.sh"
ln -sfn "$PLUGIN_SRC" "$link"
chmod +x "$link"

echo "Linked plugin:"
echo "  $link -> $PLUGIN_SRC"
echo
echo "Menu bar host:"
if [[ -d "/Applications/SwiftBar.app" ]]; then
  echo "  SwiftBar found — open it (or restart) to load the plugin."
  open -a SwiftBar 2>/dev/null || true
elif [[ -d "/Applications/xbar.app" ]]; then
  echo "  xbar found — open it (or restart) to load the plugin."
  open -a xbar 2>/dev/null || true
else
  echo "  No host app found yet. Install SwiftBar:"
  echo "    brew install --cask swiftbar"
  echo "  Then re-run this script or open SwiftBar and point it at:"
  echo "    $target_dir"
fi

echo
echo "CLI smoke test:"
"$ROOT/bin/wasabi-status"
echo
echo "Mount one:  $ROOT/bin/wasabi-mount nas"
echo "Unmount:    $ROOT/bin/wasabi-unmount nas"
