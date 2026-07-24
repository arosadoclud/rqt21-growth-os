# RQT21 Growth OS — contexto para Claude Code

Plataforma de marketing/CRM multi-tenant para "Recetas Que Transforman 21"
(RQT21). Monorepo: FastAPI (`apps/api`) + Next.js 14 (`apps/web`) +
PostgreSQL 16 + SQLAlchemy 2 + Alembic + Pydantic v2. Gestión de paquetes:
`uv` (Python) y `pnpm` (Node).

**Repo:** `https://github.com/andyRS/rqt21-growth-os` (privado).

## Estado de fases (todas verificadas: pytest, ruff, tsc, lint, build, E2E)

- **Fase 1**: monorepo, auth JWT (cookies HttpOnly, refresh rotativo con
  detección de reuso), RBAC (OWNER/ADMIN/MARKETER/SALES/ANALYST/VIEWER),
  multi-tenancy vía `organization_id`, audit log, CSRF, rate limiting.
- **Fase 2**: marcas, productos, campañas, contenido, tracking links,
  analítica de clics.
- **Fase 3**: calendario editorial, revisiones/aprobación, leads, pipeline,
  captura pública de leads.
- **Fase 4**: generación con IA (voz de marca, prompt templates
  versionados, Consejo de revisión de 6 revisores), redacción de PII,
  normalización de teléfonos.
- **Fase 5**: biblioteca de activos (S3/R2/MOCK), conexiones de
  publicación, publicaciones (proveedores MOCK/MANUAL/META), worker de
  reintentos con scheduler, automatizaciones limitadas (plantillas
  predefinidas, nunca código libre), notificaciones.
- **Fase 6A** (infraestructura de producción, todo simulable/mockeado):
  cola distribuida Redis+RQ, scheduler distribuido con locks Redis,
  storage S3/R2 real (boto3), framework OAuth genérico + cliente Meta
  real, `MetaPublishingProvider` real sobre Graph API (gateado detrás de
  `META_PUBLISHING_ENABLED` + token), logging JSON, ErrorReporter
  (Sentry-ready), SecretsProvider, Docker de producción, CI/CD con deploy
  a staging automático y a producción con aprobación manual.
- **Fase 6B** (en curso): conectar servicios reales — ver sección
  siguiente.

## Convenciones del proyecto (léelas antes de tocar código)

- Endpoints FastAPI son **síncronos** (`def`, no `async def`) salvo los
  adaptadores de proveedores externos (OAuth, Meta, storage), que sí son
  async y se invocan vía `asyncio.run(...)` desde el endpoint síncrono.
- Migraciones de Alembic **escritas a mano**, nunca autogeneradas.
  `alembic/versions/0001` a `0006`. Cada una debe tener `downgrade()`
  probado (ver `tests/test_migrations.py`).
- Todo dominio multi-tenant lleva `organization_id`; toda query se filtra
  por `deps.current_org()`.
- IDs públicos con prefijo por dominio vía `app.utils.public_id.make(prefix)`.
- Patrón Protocol + Mock: cualquier integración externa (`StorageProviderClient`,
  `PublishingProviderClient`, `JobQueue`, `Scheduler`, `OAuthProvider`,
  `ErrorReporter`, `SecretsProvider`) tiene una interfaz `Protocol`, una
  implementación MOCK usada en tests, y una implementación real gateada
  detrás de config — nunca se activa sola con solo tener credenciales;
  siempre requiere un flag explícito además (ej. `META_PUBLISHING_ENABLED`).
- Credenciales de conexiones de publicación se cifran con Fernet
  (`app.publishing.crypto`) y **nunca** se devuelven al frontend — solo
  los últimos 4 caracteres, y solo a OWNER/ADMIN.
- Auditoría: `app.audit.record(...)` antes de cada `db.commit()`, nunca
  loguea secretos/tokens/PII cruda.
- Tests de infraestructura real usan mocks deterministas: `fakeredis`
  (Redis/RQ), `moto` (S3/R2/Secrets Manager), `httpx.MockTransport`
  (OAuth/Graph API) — nunca llaman a un servicio real.

## Verificación completa

```bash
cd apps/api && uv run pytest -q && uv run ruff check .
cd ../.. && pnpm --filter web typecheck && pnpm --filter web lint && pnpm --filter web build
```

CI en GitHub Actions corre esto mismo en cada push a `main`
(`.github/workflows/ci.yml`), más deploy automático a staging
(`deploy-staging.yml`) y a producción con aprobación manual
(`deploy-production.yml`, gate por GitHub Environment "production").

## Fase 6B — en curso ahora mismo

**Objetivo actual:** conectar la página de Facebook "Recetas"
(ID `61591717576400`) a RQT21 para probar publicación real vía Meta Graph
API, sin pasar por el flujo OAuth interactivo completo (nos atoramos ahí
con "Rol de desarrollador insuficiente" al agregar un tester de
Instagram).

**Mecanismo elegido:** reusar el patrón ya funcional del proyecto separado
del usuario **Kingdom Studio**
(`https://github.com/arosadoclud/kingdom-studio`, cuenta GitHub distinta
`arosadoclud`, en producción real en Railway+Vercel+Supabase). Kingdom
Studio usa un token base de larga duración
(`FACEBOOK_BASE_ACCESS_TOKEN`, configurado en sus variables de Railway)
que ya tiene permiso sobre las páginas del usuario, y resuelve el token
específico de cualquier página con:

```bash
curl -G "https://graph.facebook.com/v25.0/61591717576400" --data-urlencode "fields=id,name,access_token" -H "Authorization: Bearer <TOKEN_BASE_REAL>"
```

(Comando en una sola línea — CMD de Windows no soporta continuación con
`\` como bash.)

**Siguiente paso pendiente:** el usuario debe copiar
`FACEBOOK_BASE_ACCESS_TOKEN` desde Railway (proyecto kingdom-studio →
Variables), correr el comando de arriba, y compartir el `access_token`
resultante (el de la página, no el token base).

**Con ese Page Access Token, los pasos técnicos en RQT21 son:**
1. Crear conexión en `/publishing/connections`: plataforma `FACEBOOK` (o
   `INSTAGRAM` si se publica en la cuenta de Instagram vinculada a esa
   página — confirmar cuál), proveedor `META`,
   `external_account_id = "61591717576400"`, credencial
   `access_token = <token resuelto>`.
2. Poner `META_PUBLISHING_ENABLED=true` en `apps/api/.env` y reiniciar la
   API.
3. Preparar una publicación real con un activo, validar, "Publicar
   ahora" — debe llamar a la Graph API real
   (`app.publishing.adapters.MetaPublishingProvider`, cableado para usar
   el token propio de cada conexión desde el commit `223d895`, no un
   token global).

**Checklist completa de Fase 6B (todo pendiente salvo lo anterior):**
ver `infra/scripts/README.md` para R2/S3, Sentry, host de
staging/producción, y secretos de GitHub Actions.
