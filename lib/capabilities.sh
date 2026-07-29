#!/usr/bin/env bash
# Detect FUSE (macFUSE) and rclone nfsmount / mount support.
# shellcheck shell=bash

# Requires: common.sh already sourced (rclone_bin, os_name, WASABI_ROOT, etc.)

macfuse_installed() {
  [[ -d /Library/Filesystems/macfuse.fs ]] && return 0
  [[ -d /Library/Filesystems/osxfuse.fs ]] && return 0
  if pkgutil --pkgs 2>/dev/null | grep -qiE 'macfuse|osxfuse|fuse\.osxfuse'; then
    return 0
  fi
  # brew cask sometimes leaves this
  [[ -e /usr/local/lib/libfuse.dylib || -e /opt/homebrew/lib/libfuse.dylib ]] && return 0
  return 1
}

# rclone binary supports the FUSE `mount` subcommand (not brew-stripped).
rclone_has_fuse_mount() {
  local bin
  bin="$(rclone_bin)"
  [[ -x "$bin" ]] || return 1
  # Official builds with cmount advertise it in `rclone version`
  if "$bin" version 2>/dev/null | grep -q 'go/tags:.*cmount'; then
    return 0
  fi
  # brew builds often list commands but omit mount; check subcommand exists
  if ! "$bin" mount -h >/dev/null 2>&1; then
    return 1
  fi
  # Hard "command missing" only (avoid matching "not supported on Windows" in flags)
  local help
  help="$("$bin" mount -h 2>&1 || true)"
  if echo "$help" | grep -qiE 'unknown command ["`]?mount|Error: unknown command'; then
    return 1
  fi
  # Avoid head|grep under pipefail (SIGPIPE → false negative)
  if printf '%s' "$help" | grep -qiE 'Rclone mount allows|mount any of Rclone'; then
    return 0
  fi
  return 1
}

rclone_has_nfsmount() {
  local bin
  bin="$(rclone_bin)"
  [[ -x "$bin" ]] || return 1
  if ! "$bin" nfsmount -h >/dev/null 2>&1; then
    return 1
  fi
  local help
  help="$("$bin" nfsmount -h 2>&1 || true)"
  if printf '%s' "$help" | grep -qiE 'unknown command ["`]?nfsmount|Error: unknown command'; then
    return 1
  fi
  printf '%s' "$help" | grep -qiE 'Rclone nfsmount|nfsmount allows'
}

# fuse usable only if binary has mount AND macFUSE present
fuse_ready() {
  rclone_has_fuse_mount && macfuse_installed
}

nfs_ready() {
  rclone_has_nfsmount
}

# Print human + machine-readable capability report
print_capabilities() {
  local bin macfuse fuse_bin fuse_ok nfs_ok
  bin="$(rclone_bin 2>/dev/null || echo "")"
  macfuse=false
  fuse_bin=false
  fuse_ok=false
  nfs_ok=false
  macfuse_installed && macfuse=true
  [[ -x "$bin" ]] && rclone_has_fuse_mount && fuse_bin=true
  fuse_ready && fuse_ok=true
  nfs_ready && nfs_ok=true

  cat <<EOF
{
  "rclone_path": $(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "${bin:-}"),
  "rclone_present": $([[ -x "${bin:-}" ]] && echo true || echo false),
  "macfuse_installed": $macfuse,
  "rclone_has_fuse_mount": $fuse_bin,
  "fuse_ready": $fuse_ok,
  "nfs_ready": $nfs_ok
}
EOF
}

print_capabilities_human() {
  echo "=== Mount capabilities ==="
  echo "rclone: $(rclone_bin 2>/dev/null || echo missing)"
  if [[ -x "$(rclone_bin 2>/dev/null || echo /nonexistent)" ]]; then
    "$(rclone_bin)" version 2>/dev/null | head -2 || true
  fi
  echo
  if macfuse_installed; then
    echo "macFUSE:     installed"
  else
    echo "macFUSE:     NOT installed  → needed for FUSE mounts (rclone mount)"
  fi
  if rclone_has_fuse_mount; then
    echo "rclone mount (FUSE cmd): yes"
  else
    echo "rclone mount (FUSE cmd): no (wrong binary? re-run ensure-rclone)"
  fi
  if fuse_ready; then
    echo "FUSE mounts: READY"
  else
    echo "FUSE mounts: not ready"
  fi
  if nfs_ready; then
    echo "NFS mounts:  READY (rclone nfsmount)"
  else
    echo "NFS mounts:  not ready"
  fi
}

# Open instructions / try brew install for macFUSE (user-approved).
help_install_macfuse() {
  if [[ "$(os_name)" != "darwin" ]]; then
    echo "macFUSE is only for macOS." >&2
    return 1
  fi
  echo "macFUSE is required for FUSE-style mounts (rclone mount)."
  echo
  if command -v brew >/dev/null 2>&1; then
    echo "Recommended (Homebrew):"
    echo "  brew install --cask macfuse"
    echo
    if [[ "${1:-}" == "--install" ]]; then
      brew install --cask macfuse
      return $?
    fi
  fi
  echo "Or download the installer:"
  echo "  https://macfuse.github.io/"
  echo
  echo "After install:"
  echo "  1. Allow the system extension in System Settings → Privacy & Security"
  echo "  2. Reboot if macOS asks"
  echo "  3. Run: wasabi-capabilities"
  echo
  if [[ "$(os_name)" == "darwin" ]]; then
    open "https://macfuse.github.io/" 2>/dev/null || true
  fi
}
