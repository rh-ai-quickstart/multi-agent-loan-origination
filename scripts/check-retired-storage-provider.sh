#!/usr/bin/env bash
# Reject the retired object-store provider in active configuration and code.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
targets=("$@")
if [ "${#targets[@]}" -eq 0 ]; then
  targets=("$root")
fi

if rg --hidden --glob '!.git/**' --glob '!.claude/**' --glob '!.codex/**' \
  --glob '!.agents/**' --glob '!docs/plans/**' \
  --glob '!check-retired-storage-provider.sh' -n -i '[m]inio' "${targets[@]}"; then
  echo "The retired object-store provider is not permitted in active configuration or code." >&2
  exit 1
fi
