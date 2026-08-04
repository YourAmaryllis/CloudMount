#!/usr/bin/env bash
# <xbar.title>CloudMount</xbar.title>
# <xbar.version>v0.2.2</xbar.version>
# <xbar.author>YourAmaryllis</xbar.author>
# <xbar.desc>Cloud mounts — open UI, mount/unmount (SwiftBar host)</xbar.desc>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>true</swiftbar.hideLastUpdated>
# <swiftbar.refreshOnOpen>true</swiftbar.refreshOnOpen>
#
# Actions use cloudmount-launch (absolute path). SwiftBar params after "|" are
# SPACE-separated. Launch is detached so GUI survives the menu click.
#
# Perf note: this runs every 5s for as long as SwiftBar is open, so it's kept
# to exactly 2 subprocess spawns — `cloudmount status --light` (skips the
# per-host Keychain probes the menu doesn't use) and one Python renderer.
# Do not reintroduce a separate spawn per parsed field.

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
LAUNCH="$ROOT/bin/cloudmount-launch"
CM="$ROOT/bin/cloudmount"

# Resolve python for status only
PY=""
for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  [[ -x "$c" ]] && PY="$c" && break
done
PY="${PY:-python3}"

status_json="$("$PY" "$CM" status --light 2>/dev/null || echo '{}')"

printf '%s' "$status_json" | "$PY" -c "
import json, sys
launch = sys.argv[1]
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}

summary = d.get('summary') or {}
up = summary.get('mounts_up', 0)
total = summary.get('mounts_total', 0)

if total == 0:
    print('☁ +')
elif up == total:
    print(f'☁ {up}')
else:
    print(f'☁ {up}/{total}')

print('---')
print(f'Open CloudMount… | bash={launch} param1=gui terminal=false refresh=true')

for m in d.get('mounts') or []:
    label = m.get('label') or m.get('id')
    mid = m.get('id')
    kind = m.get('mount_kind') or 'nfs'
    path = m.get('path') or ''
    if m.get('mounted'):
        print(f'✓ {label} ({kind})')
        print(f'--{path}')
        print(f'--Unmount | bash={launch} param1=unmount param2={mid} terminal=false refresh=true')
    else:
        print(f'○ {label} ({kind})')
        print(f'--Mount | bash={launch} param1=mount param2={mid} terminal=false refresh=true')
    print('---')

print(f'Mount all | bash={launch} param1=mount-all terminal=false refresh=true')
print(f'Unmount all | bash={launch} param1=unmount-all terminal=false refresh=true')
print('---')
print(f'Run setup | bash={launch} param1=setup terminal=false refresh=true')
print('Refresh | refresh=true')
print('---')
print(f'Quit CloudMount | bash={launch} param1=quit terminal=false refresh=true')
" "$LAUNCH"
