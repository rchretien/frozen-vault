#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="docker-compose-prod.yml"
ENV_FILE=".env-prod"

cd "${REPO_ROOT}"

required_files=(
  "${ENV_FILE}"
  "${COMPOSE_FILE}"
  "nginx.conf"
  "certs/raspberrypi.local.pem"
  "certs/raspberrypi.local-key.pem"
)

for file in "${required_files[@]}"; do
  if [[ ! -f "${file}" ]]; then
    printf 'Missing required file: %s\n' "${file}" >&2
    exit 1
  fi
done

if ! command -v docker >/dev/null 2>&1; then
  printf 'Docker is required but was not found in PATH.\n' >&2
  exit 1
fi

compose=(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")

printf 'Pulling latest API image...\n'
"${compose[@]}" pull api

printf 'Starting production stack...\n'
"${compose[@]}" up -d --remove-orphans

printf 'Current container status:\n'
"${compose[@]}" ps
