#!/usr/bin/env bash
# Manual staging deploy — run this FROM the staging host itself (or over
# SSH), inside the repo checkout. This is what deploy-staging.yml's SSH
# step effectively runs; kept as a standalone script so a first deploy or
# an emergency deploy doesn't require going through GitHub Actions.
#
# Usage: ./infra/scripts/deploy_staging.sh [git-ref]
set -euo pipefail

cd "$(dirname "$0")/../.."
REF="${1:-main}"

echo "==> Fetching and checking out $REF"
git fetch --all --tags
git checkout "$REF"
git pull --ff-only || true

if [ ! -f .env.staging ]; then
  echo "ERROR: .env.staging not found. Copy .env.staging.example and fill in real values first." >&2
  exit 1
fi

echo "==> Building and starting containers"
docker compose -f infra/docker-compose.staging.yml --env-file .env.staging build
docker compose -f infra/docker-compose.staging.yml --env-file .env.staging up -d

echo "==> Running migrations"
docker compose -f infra/docker-compose.staging.yml --env-file .env.staging exec -T api uv run alembic upgrade head

echo "==> Health check"
sleep 5
docker compose -f infra/docker-compose.staging.yml --env-file .env.staging exec -T api \
  curl -fsS http://127.0.0.1:8000/api/v1/ready

echo "==> Done. Deployed $REF to staging."
