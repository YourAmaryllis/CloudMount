#!/usr/bin/env bash
# Shared helpers for wasabi menu-bar mounts (macOS first; Windows-ready structure).
# shellcheck disable=SC2034

set -euo pipefail

# SwiftBar / xbar use a tiny PATH — put Homebrew + system bins first.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

WASABI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export WASABI_ROOT

# Primary editable store (UI + CLI). YAML is legacy fallback only.
WASABI_CONFIG_JSON="${WASABI_CONFIG_JSON:-$WASABI_ROOT/config/mounts.json}"
WASABI_CONFIG_YAML="${WASABI_CONFIG_YAML:-$WASABI_ROOT/config/mounts.yaml}"
WASABI_LOG_DIR="${WASABI_LOG_DIR:-$WASABI_ROOT/logs}"
WASABI_CREDS_FILE="${WASABI_CREDS_FILE:-$HOME/.wasabi.json}"
RCLONE_VENDOR_DIR="${RCLONE_VENDOR_DIR:-$WASABI_ROOT/vendor/rclone}"
DEFAULT_RCLONE_REMOTE="${DEFAULT_RCLONE_REMOTE:-wasabi}"

os_name() {
  case "$(uname -s)" in
    Darwin) echo "darwin" ;;
    Linux) echo "linux" ;;
    MINGW*|MSYS*|CYGWIN*|Windows_NT) echo "windows" ;;
    *) uname -s | tr '[:upper:]' '[:lower:]' ;;
  esac
}

arch_name() {
  case "$(uname -m)" in
    arm64|aarch64) echo "arm64" ;;
    x86_64|amd64) echo "amd64" ;;
    i386|i686) echo "386" ;;
    *) uname -m ;;
  esac
}

platform_key() {
  echo "$(os_name)-$(arch_name)"
}

rclone_bin() {
  local bin
  if [[ "$(os_name)" == "windows" ]]; then
    bin="$RCLONE_VENDOR_DIR/$(platform_key)/rclone.exe"
  else
    bin="$RCLONE_VENDOR_DIR/$(platform_key)/rclone"
  fi
  echo "$bin"
}

expand_path() {
  local p="$1"
  case "$p" in
    "~") echo "$HOME" ;;
    "~/"*) echo "$HOME/${p:2}" ;;
    *) echo "$p" ;;
  esac
}

prefer_tilde_path() {
  local p="$1"
  local home="${HOME%/}"
  if [[ "$p" == "$home" ]]; then
    echo "~"
  elif [[ "$p" == "$home/"* ]]; then
    echo "~/${p#"$home"/}"
  else
    echo "$p"
  fi
}

load_wasabi_env() {
  if [[ ! -f "$WASABI_CREDS_FILE" ]]; then
    echo "Missing credentials file: $WASABI_CREDS_FILE" >&2
    return 1
  fi
  export AWS_ACCESS_KEY_ID
  export AWS_SECRET_ACCESS_KEY
  # Prefer jq; fall back to python so SwiftBar never depends on a missing brew path
  if command -v jq >/dev/null 2>&1; then
    AWS_ACCESS_KEY_ID="$(jq -r '."access-key" // .accessKeyId // .AWS_ACCESS_KEY_ID // empty' "$WASABI_CREDS_FILE")"
    AWS_SECRET_ACCESS_KEY="$(jq -r '."secret-key" // .secretAccessKey // .AWS_SECRET_ACCESS_KEY // empty' "$WASABI_CREDS_FILE")"
  else
    eval "$(python3 - "$WASABI_CREDS_FILE" <<'PY'
import json, shlex, sys
from pathlib import Path
d = json.loads(Path(sys.argv[1]).read_text())
ak = d.get("access-key") or d.get("accessKeyId") or d.get("AWS_ACCESS_KEY_ID") or ""
sk = d.get("secret-key") or d.get("secretAccessKey") or d.get("AWS_SECRET_ACCESS_KEY") or ""
print("AWS_ACCESS_KEY_ID="+shlex.quote(ak))
print("AWS_SECRET_ACCESS_KEY="+shlex.quote(sk))
PY
)"
  fi
  if [[ -z "${AWS_ACCESS_KEY_ID:-}" || -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
    echo "Could not read access-key/secret-key from $WASABI_CREDS_FILE" >&2
    return 1
  fi
}

ensure_config_json() {
  if [[ -f "$WASABI_CONFIG_JSON" ]]; then
    return 0
  fi
  mkdir -p "$(dirname "$WASABI_CONFIG_JSON")"
  if [[ -f "$WASABI_CONFIG_YAML" ]]; then
    python3 - "$WASABI_CONFIG_YAML" "$WASABI_CONFIG_JSON" <<'PY'
import json, re, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text()
lines = []
for line in text.splitlines():
    if "#" in line:
        in_q = False
        out = []
        for ch in line:
            if ch in "\"'":
                in_q = not in_q
            if ch == "#" and not in_q:
                break
            out.append(ch)
        line = "".join(out)
    lines.append(line.rstrip())
mounts, cur, in_mounts = [], None, False
for line in lines:
    if not line.strip():
        continue
    if re.match(r"^mounts:\s*$", line):
        in_mounts = True
        continue
    if not in_mounts:
        continue
    m = re.match(r"^  - id:\s*(.+)$", line)
    if m:
        if cur:
            mounts.append(cur)
        cur = {"id": m.group(1).strip().strip("\"'"), "label": "", "remote": "", "path": "", "vfs_cache_mode": "full"}
        continue
    if cur is None:
        continue
    m = re.match(r"^    (label|remote|path|vfs_cache_mode):\s*(.+)$", line)
    if m:
        cur[m.group(1)] = m.group(2).strip().strip("\"'")
if cur:
    mounts.append(cur)
mounts = [m for m in mounts if m.get("id") and m.get("remote") and m.get("path")]
for m in mounts:
    m["label"] = m.get("label") or m["id"]
    m["vfs_cache_mode"] = m.get("vfs_cache_mode") or "full"
Path(sys.argv[2]).write_text(json.dumps({"mounts": mounts}, indent=2) + "\n")
PY
  else
    printf '%s\n' '{ "mounts": [] }' >"$WASABI_CONFIG_JSON"
  fi
}

# TSV: id label remote path vfs_cache_mode mount_kind
# mount_kind: fuse | nfs  (default fuse for older configs)
list_mounts_tsv() {
  ensure_config_json
  python3 - "$WASABI_CONFIG_JSON" <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text() or '{"mounts":[]}')
for m in data.get("mounts") or []:
    mid = (m.get("id") or "").strip()
    remote = (m.get("remote") or "").strip()
    path = (m.get("path") or "").strip()
    if not mid or not remote or not path:
        continue
    label = (m.get("label") or mid).strip()
    mode = (m.get("vfs_cache_mode") or "full").strip()
    kind = (m.get("mount_kind") or m.get("kind") or "fuse").strip().lower()
    if kind not in ("fuse", "nfs"):
        kind = "fuse"
    print("\t".join([mid, label, remote, path, mode, kind]))
PY
}

get_mount_by_id() {
  local want="$1" line
  while IFS= read -r line; do
    IFS=$'\t' read -r id label remote path mode kind <<<"$line"
    if [[ "$id" == "$want" ]]; then
      printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$id" "$label" "$remote" "$path" "$mode" "${kind:-fuse}"
      return 0
    fi
  done < <(list_mounts_tsv)
  return 1
}

is_mounted() {
  local path
  path="$(expand_path "$1")"
  if mount 2>/dev/null | grep -F " on ${path} " >/dev/null 2>&1; then
    return 0
  fi
  if mount 2>/dev/null | grep -E " on ${path%/}(/)? " >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

rclone_pid_for() {
  local remote="$1"
  local path
  path="$(expand_path "$2")"
  pgrep -f "rclone mount ${remote} ${path}" 2>/dev/null | head -1 || true
}

ensure_log_dir() {
  mkdir -p "$WASABI_LOG_DIR"
}

log_action() {
  ensure_log_dir
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  printf '[%s] %s\n' "$ts" "$*" >>"$WASABI_LOG_DIR/actions.log"
}

# --- macOS UI (no Accessibility / System Events) ---
# Uses standard AppleScript dialogs only. Activates Finder so the dialog is frontmost
# when launched from a background SwiftBar plugin process.

_ui_escape_as() {
  # Escape for AppleScript double-quoted string
  python3 -c 'import sys; print(sys.argv[1].replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n"))' "$1"
}

ui_alert() {
  local msg="$1" title="${2:-Wasabi Mounts}"
  log_action "alert: $title — $msg"
  if [[ "$(os_name)" != "darwin" ]]; then
    echo "$title: $msg" >&2
    return 0
  fi
  local t m
  t="$(_ui_escape_as "$title")"
  m="$(_ui_escape_as "$msg")"
  /usr/bin/osascript <<EOF >/dev/null 2>>"$WASABI_LOG_DIR/ui.log" || true
try
  tell application "Finder" to activate
end try
display dialog "$m" with title "$t" buttons {"OK"} default button "OK" giving up after 120
EOF
}

ui_notify() {
  local msg="$1" title="${2:-Wasabi Mounts}"
  log_action "notify: $title — $msg"
  if [[ "$(os_name)" != "darwin" ]]; then
    echo "$title: $msg"
    return 0
  fi
  local t m
  t="$(_ui_escape_as "$title")"
  m="$(_ui_escape_as "$msg")"
  /usr/bin/osascript <<EOF >/dev/null 2>>"$WASABI_LOG_DIR/ui.log" || true
display notification "$m" with title "$t"
EOF
}

ui_confirm() {
  local msg="$1" title="${2:-Wasabi Mounts}"
  local t m
  t="$(_ui_escape_as "$title")"
  m="$(_ui_escape_as "$msg")"
  /usr/bin/osascript <<EOF 2>>"$WASABI_LOG_DIR/ui.log"
try
  tell application "Finder" to activate
end try
try
  display dialog "$m" with title "$t" buttons {"Cancel", "OK"} default button "OK"
  return "yes"
on error
  return "no"
end try
EOF
}

ui_text() {
  local prompt="$1" default="${2:-}" title="${3:-Wasabi Mounts}"
  local t p d
  t="$(_ui_escape_as "$title")"
  p="$(_ui_escape_as "$prompt")"
  d="$(_ui_escape_as "$default")"
  /usr/bin/osascript <<EOF 2>>"$WASABI_LOG_DIR/ui.log"
try
  tell application "Finder" to activate
end try
try
  set r to display dialog "$p" with title "$t" default answer "$d" buttons {"Cancel", "OK"} default button "OK"
  return text returned of r
on error
  return ""
end try
EOF
}

ui_choose() {
  local prompt="$1"
  shift
  if [[ "$#" -eq 0 ]]; then
    echo ""
    return 1
  fi
  # Build AppleScript list via python for safe quoting
  local prompt_esc list_as
  prompt_esc="$(_ui_escape_as "$prompt")"
  list_as="$(python3 -c '
import sys
items = sys.argv[1:]
print(", ".join("\"" + i.replace("\\\\","\\\\\\\\").replace("\"","\\\\\"") + "\"" for i in items))
' "$@")"
  /usr/bin/osascript <<EOF 2>>"$WASABI_LOG_DIR/ui.log"
try
  tell application "Finder" to activate
end try
try
  set opts to {$list_as}
  set c to choose from list opts with prompt "$prompt_esc" without multiple selections allowed
  if c is false then return ""
  return item 1 of c
on error
  return ""
end try
EOF
}

ui_choose_folder() {
  local prompt="${1:-Choose local mount folder}"
  local p
  p="$(_ui_escape_as "$prompt")"
  /usr/bin/osascript <<EOF 2>>"$WASABI_LOG_DIR/ui.log"
try
  tell application "Finder" to activate
end try
try
  set f to choose folder with prompt "$p"
  return POSIX path of f
on error
  return ""
end try
EOF
}

# Launch a CLI command fully detached so SwiftBar cannot kill it when the
# plugin action returns. No Accessibility required.
detach_exec() {
  # Usage: detach_exec <logfile> <cmd> [args...]
  local logfile="$1"
  shift
  ensure_log_dir
  python3 - "$logfile" "$@" <<'PY'
import os, sys, subprocess
from pathlib import Path

logfile = Path(sys.argv[1])
cmd = sys.argv[2:]
logfile.parent.mkdir(parents=True, exist_ok=True)
logf = open(logfile, "a", buffering=1)
env = os.environ.copy()
# New session so we survive SwiftBar's process-group cleanup
subprocess.Popen(
    cmd,
    stdout=logf,
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
    env=env,
    start_new_session=True,
    close_fds=True,
)
print("started", " ".join(cmd), file=logf)
PY
}
