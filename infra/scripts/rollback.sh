#!/usr/bin/env bash
# Rollback production to a previous commit. Rebuilds and redeploys that
# commit's code — this is a CODE rollback, not a database rollback. If the
# bad deploy included a migration, read the "Rollback" section in
# infra/scripts/README.md before running this: rolling back code while a
# newer migration is still applied can break the older code's assumptions.
#
# Usage: ./infra/scripts/rollback.sh <git-sha> [staging|production]
set -euo pipefail

cd "$(dirname "$0")/../.."
SHA="${1:?usage: rollback.sh <git-sha> [staging|production]}"
TARGET="${2:-production}"

if [ "$TARGET" != "staging" ] && [ "$TARGET" != "production" ]; then
  echo "ERROR: second argument must be 'staging' or 'production'" >&2
  exit 1
fi

ENV_FILE=".env.${TARGET}"
COMPOSE_FILE="infra/docker-compose.${TARGET}.yml"
if [ "$TARGET" = "production" ]; then COMPOSE_FILE="infra/docker-compose.prod.yml"; fi

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found." >&2
  exit 1
fi

echo "About to roll back $TARGET to $SHA. Type 'yes' to continue:"
read -r CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Aborted."
  exit 1
fi

git fetch --all --tags
git checkout "$SHA"

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

echo "==> Rolled back $TARGET to $SHA."
echo "==> This did NOT run 'alembic downgrade' — see infra/scripts/README.md if the bad deploy included a migration."
