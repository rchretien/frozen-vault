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
  "${BASE_URL}/fridge-app/static/css/app.css" >/dev/null

printf 'Checking deployment metadata endpoint...\n'
curl --fail --silent --show-error --insecure \
  "${BASE_URL}/fridge-app/utils/deployment" >/dev/null

printf 'Checking generated HTML for mixed-content local URLs...\n'
html="$(curl --fail --silent --show-error --insecure "${BASE_URL}/fridge-app/")"
insecure_url_pattern='(href|src|action|hx-get|hx-post|hx-put|hx-delete)=["'"'"']http://'
if grep -Eiq "${insecure_url_pattern}" <<<"${html}"; then
  printf 'Found insecure URL-bearing http:// references in generated HTML.\n' >&2
  grep -Ein "${insecure_url_pattern}" <<<"${html}" >&2
  exit 1
fi

printf 'Pi deployment checks passed for %s.\n' "${BASE_URL}"
