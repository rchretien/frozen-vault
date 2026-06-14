#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="docker-compose-prod.yml"
ENV_FILE=".env-prod"
IMAGE_REF="${IMAGE_REF:-ghcr.io/rchretien/fridge-app:latest}"

export IMAGE_REF

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

IMAGE_DIGEST="$(docker image inspect "${IMAGE_REF}" --format '{{index .RepoDigests 0}}' 2>/dev/null || true)"
IMAGE_DIGEST="${IMAGE_DIGEST:-unknown}"
DEPLOYED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

export IMAGE_DIGEST DEPLOYED_AT

printf 'Deploying image: %s\n' "${IMAGE_REF}"
printf 'Image digest: %s\n' "${IMAGE_DIGEST}"
printf 'Deployment timestamp: %s\n' "${DEPLOYED_AT}"

printf 'Starting production stack...\n'
"${compose[@]}" up -d --remove-orphans

printf 'Current container status:\n'
"${compose[@]}" ps
