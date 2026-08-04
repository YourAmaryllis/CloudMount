#!/usr/bin/env bash
# Dev install: setup + print next steps
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)/.."
cd "$ROOT"
chmod +x bin/cloudmount scripts/*.sh 2>/dev/null || true
python3 bin/cloudmount setup
echo
echo "Open UI:    python3 bin/cloudmount gui"
echo "Status:     python3 bin/cloudmount status"
echo "Menu bar:   cd mac-app && ./Scripts/build-app.sh && open .build/CloudMountBar.app"
echo "Or:         open dist/CloudMount.app  (after scripts/build-app.sh)"
