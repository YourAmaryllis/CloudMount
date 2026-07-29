#!/usr/bin/env bash
# Dev install: setup + menubar + print next steps
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)/.."
cd "$ROOT"
chmod +x bin/cloudmount scripts/*.sh plugins/*.sh 2>/dev/null || true
python3 bin/cloudmount setup
python3 bin/cloudmount install-menubar
echo
echo "Open UI:  python3 bin/cloudmount gui"
echo "Status:   python3 bin/cloudmount status"
echo "Or:       open dist/CloudMount.app  (after scripts/build-app.sh)"
