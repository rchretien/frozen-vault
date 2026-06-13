#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${PI_BASE_URL:-https://raspberrypi.local}}"
BASE_URL="${BASE_URL%/}"

if ! command -v curl >/dev/null 2>&1; then
  printf 'curl is required but was not found in PATH.\n' >&2
  exit 1
fi

printf 'Checking static CSS through Nginx...\n'
curl --fail --silent --show-error --insecure --head \
  "${BASE_URL}/backend/static/css/app.css" >/dev/null

printf 'Checking generated HTML for mixed-content local URLs...\n'
html="$(curl --fail --silent --show-error --insecure "${BASE_URL}/")"
if grep -q "http://" <<<"${html}"; then
  printf 'Found insecure http:// URLs in generated HTML.\n' >&2
  exit 1
fi

printf 'Pi deployment checks passed for %s.\n' "${BASE_URL}"
