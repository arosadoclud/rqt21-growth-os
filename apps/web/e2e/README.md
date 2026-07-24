# Playwright e2e

## What runs

Playwright starts a Next.js dev server on port 3100 (overridable). The API is
**not** started by Playwright — start it separately, pointing at an isolated
Postgres, and pass `NEXT_PUBLIC_API_URL` to the tests.

## Local one-liner

```bash
# terminal A — clean API + DB
docker compose -f infra/docker-compose.yml up -d db_test
cd apps/api
TEST_DATABASE_URL=postgresql+psycopg://rqt:rqt@localhost:5433/rqt_test \
DATABASE_URL=postgresql+psycopg://rqt:rqt@localhost:5433/rqt_test \
JWT_SECRET=test-secret-abcdefghijklmnopqrstuvwxyz-01234567-XYZ \
CORS_ORIGINS=http://127.0.0.1:3100 \
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8100

# terminal B — playwright
cd apps/web
NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 pnpm test:e2e
```

The tests seed users via the API directly using an OWNER bootstrap that the
suite creates before every test.
