#!/usr/bin/env bash
# Manual production deploy — same shape as deploy_staging.sh, but requires
# explicit confirmation since it's production. Prefer deploy-production.yml
# (GitHub Actions, with its manual-approval Environment gate) for normal
# deploys; this script exists for emergency/first-time bootstrap use.
#
# Usage: ./infra/scripts/deploy_production.sh <git-ref>
set -euo pipefail

cd "$(dirname "$0")/../.."
REF="${1:?usage: deploy_production.sh <git-ref>}"

if [ ! -f .env.production ]; then
  echo "ERROR: .env.production not found. Copy .env.production.example and fill in real values first." >&2
  exit 1
fi

echo "About to deploy '$REF' to PRODUCTION. Type 'yes' to continue:"
read -r CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Aborted."
  exit 1
fi

echo "==> Fetching and checking out $REF"
git fetch --all --tags
git checkout "$REF"

echo "==> Building and starting containers"
docker compose -f infra/docker-compose.prod.yml --env-file .env.production build
docker compose -f infra/docker-compose.prod.yml --env-file .env.production up -d

echo "==> Running migrations"
docker compose -f infra/docker-compose.prod.yml --env-file .env.production exec -T api uv run alembic upgrade head

echo "==> Health check"
sleep 5
docker compose -f infra/docker-compose.prod.yml --env-file .env.production exec -T api \
  curl -fsS http://127.0.0.1:8000/api/v1/ready

echo "==> Done. Deployed $REF to production."
echo "==> Record this SHA somewhere — infra/scripts/rollback.sh needs it if this deploy needs reverting."
