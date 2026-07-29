#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "$ROOT/lib/common.sh"

while IFS=$'\t' read -r id label st remote path; do
  if [[ "$st" != "1" ]]; then
    "$ROOT/bin/wasabi-mount" "$id" || true
  fi
done < <("$ROOT/bin/wasabi-status" --tsv)
