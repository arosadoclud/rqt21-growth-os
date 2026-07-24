# RQT21 Growth OS

Independent commercial-funnel platform for **Recetas Que Transforman 21**.
Content → trackable link → landing → WhatsApp/checkout → lead → follow-up → sale.

This repo currently contains **Phase 1**: monorepo scaffold, auth, RBAC, multi-tenancy, audit log.

## Stack

- **Backend:** FastAPI, SQLAlchemy 2, Alembic, Argon2, PyJWT.
- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind.
- **DB:** PostgreSQL 16.
- **Tooling:** uv (Python), pnpm (Node), Docker Compose.

## Repo layout

```
apps/
  api/          FastAPI service (Python 3.12+)
  web/          Next.js 14 UI
packages/
  contracts/    Shared TypeScript types
infra/
  docker-compose.yml
  Dockerfile.api
scripts/        Dev helpers
```

## Requirements

- Docker (for Postgres)
- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/)
- Node 20+ and [`pnpm`](https://pnpm.io/) (`corepack enable && corepack prepare pnpm@9 --activate`)

## Quick start

```bash
# 1) Copy env template
cp .env.example .env

# 2) Start Postgres
docker compose -f infra/docker-compose.yml up -d db

# 3) API deps + migrate + seed
cd apps/api
uv sync
uv run alembic upgrade head
uv run python -m app.seed

# 4) Run API (port 8000)
uv run uvicorn app.main:app --reload --port 8000

# 5) Web deps + dev (port 3000)
cd ../..
pnpm install
pnpm --filter web dev
```

Open http://localhost:3000 and log in with the seed credentials below.

### Seed credentials (local only)

- Email: `owner@rqt21.dev`
- Password: `Owner!2026Local`
- Organization: `RQT21`

## Scripts

Root scripts (run from repo root):

| Command | What it does |
|---|---|
| `pnpm install` | Install web workspace deps |
| `pnpm --filter web dev` | Start Next.js dev server on :3000 |
| `pnpm --filter web build` | Production build |
| `pnpm --filter web typecheck` | `tsc --noEmit` |
| `pnpm --filter web lint` | ESLint |

API scripts (run from `apps/api`):

| Command | What it does |
|---|---|
| `uv sync` | Install Python deps |
| `uv run uvicorn app.main:app --reload` | Start API on :8000 |
| `uv run alembic upgrade head` | Apply migrations |
| `uv run alembic downgrade base` | Roll back all migrations |
| `uv run python -m app.seed` | Load seed data |
| `uv run pytest` | Run tests |
| `uv run ruff check .` | Lint |

## Auth model

- **Access token:** JWT (HS256), 15 min, HttpOnly cookie `rqt_access`.
- **Refresh token:** opaque, hashed at rest, rotated on every refresh, revocable, 30 days, HttpOnly cookie `rqt_refresh`.
- **Current org:** header `X-Organization-Id` — the backend verifies membership on every request.
- **Passwords:** Argon2id.

## RBAC

Roles per membership: `OWNER`, `ADMIN`, `MARKETER`, `SALES`, `ANALYST`, `VIEWER`.
Endpoints declare the minimum required role via `require_role(...)`.

## Multi-tenancy

Every tenant-scoped row carries `organization_id`. Queries are always filtered
through `deps.current_org()`, which validates membership. Clients never dictate
tenancy — headers are treated as claims, not authority.

## Audit

The `audit_logs` table records login, logout, user create/update, role changes,
and organization membership changes. Written synchronously in the request path.

## API endpoints (v1)

| Method | Path | Role |
|---|---|---|
| POST | `/api/v1/auth/login` | public |
| POST | `/api/v1/auth/refresh` | cookie |
| POST | `/api/v1/auth/logout` | any |
| GET  | `/api/v1/me` | any |
| GET  | `/api/v1/organizations` | any |
| POST | `/api/v1/organizations` | any (creator becomes OWNER) |
| GET  | `/api/v1/organizations/{id}` | member |
| GET  | `/api/v1/organizations/{id}/members` | member |
| POST | `/api/v1/organizations/{id}/members` | OWNER/ADMIN |
| PATCH| `/api/v1/organizations/{id}/members/{member_id}` | OWNER/ADMIN |

## Testing

```bash
cd apps/api
# Requires a running Postgres reachable via TEST_DATABASE_URL
export TEST_DATABASE_URL=postgresql+psycopg://rqt:rqt@localhost:5433/rqt_test
uv run pytest -q
```

`docker compose -f infra/docker-compose.yml up -d db_test` starts a dedicated
test database on port 5433.

## Phase 6A — production infrastructure (prepared, not yet connected)

Redis-backed job queue (RQ) and scheduler, real S3/R2 storage provider, a
generic OAuth2 framework with a real Meta (Facebook/Instagram) client, a
real Graph API publishing provider, structured JSON logging, an
ErrorReporter abstraction (Sentry-ready), a secrets provider abstraction,
hardened production Docker images, staging/production docker-compose
files, and GitHub Actions deploy workflows with a manual-approval gate for
production — all built and tested against mocks (fakeredis, moto, httpx
MockTransport), so nothing here makes a real network call or costs money
until real credentials are supplied.

**Phase 6B** — connecting those to real accounts (Cloudflare R2, a Meta
Developer App, a staging/production host, GitHub Environments) — is a
setup/credentials task for a human, not code. See
[`infra/scripts/README.md`](infra/scripts/README.md) for the exact,
step-by-step checklist, plus operational runbooks (failed jobs,
rollback, backups).

## Roadmap

- **Phase 1:** monorepo, auth, RBAC, multi-tenancy, audit.
- **Phase 2:** Brands, products, campaigns, content, tracking links, analytics.
- **Phase 3:** Editorial calendar, reviews, leads, pipeline, public capture.
- **Phase 4:** AI generation (brand voice, prompt templates, council review), PII redaction.
- **Phase 5:** Asset library, publishing connections/publications (MOCK/MANUAL), retry worker, limited automations, notifications.
- **Phase 6A (this):** distributed queue/scheduler, real S3/R2, OAuth + Meta publishing framework, observability, production Docker/CI-CD — all mocked/inactive until Phase 6B.
- **Phase 6B:** connect real Cloudflare R2, a Meta Developer App, and a staging/production host — see `infra/scripts/README.md`.
