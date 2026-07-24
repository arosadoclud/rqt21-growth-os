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

**Objetivo actual:** publicar de verdad en la página de Facebook
"Recetasquetransforman21" (ID real `1228107327050361`, cuenta de
Instagram vinculada `17841413032834214`) vía Meta Graph API.

**Datos reales ya confirmados (no el ID viejo `61591717576400`, que era
incorrecto):**
- Página: **Recetasquetransforman21**, `page_id = 1228107327050361`.
- Instagram Business Account vinculada: `17841413032834214`.
- App de Meta usada para generar tokens: **"RTQ21 RECETAS-IG"** (Andy
  Robinson como Administrador — ver "Roles de la app").
- El flujo de **Instagram Login / OAuth interactivo** de esta app da
  "Rol de desarrollador insuficiente" de forma consistente (probado dos
  veces). **Camino que sí funciona:** Graph API Explorer
  (developers.facebook.com/tools/explorer), generar un **User Access
  Token** ahí mismo con permisos `pages_show_list`,
  `pages_read_engagement`, `pages_manage_posts`, y luego
  `GET /me/accounts?fields=id,name,access_token,instagram_business_account`
  para obtener el Page Access Token directamente — evita el diálogo de
  OAuth por completo.

**Mecanismo de renovación — patrón "Kingdom Studio" (implementado):**
guardar un Page Access Token estático es frágil (Meta puede invalidarlo
sin aviso, y cada vez hay que volver a pegar uno nuevo a mano). Por eso,
igual que el proyecto separado del usuario **Kingdom Studio**
(`https://github.com/arosadoclud/kingdom-studio`, cuenta GitHub distinta
`arosadoclud`, en producción real en Railway+Vercel+Supabase, que resuelve
tokens de página a partir de un `FACEBOOK_BASE_ACCESS_TOKEN` de larga
duración), RQT21 ahora soporta guardar un **token base** en vez de un
token de página estático:

- Implementado en `app/publishing/meta_token_resolver.py`
  (`resolve_page_access_token`, `resolve_connection_access_token`), cableado
  en `_execute_publish` (`app/api/v1/publications.py`) y `verify_connection`
  (`app/api/v1/publishing_connections.py`). Tests:
  `tests/test_meta_token_resolver.py`.
- Si `credentials.base_access_token` está presente en la conexión, se
  resuelve un token de página **fresco en cada llamada** vía
  `GET /{page_id}?fields=access_token&access_token=<base_token>` — nunca
  se guarda el token de página en sí. Si falla la resolución, cae a `""`
  (mismo comportamiento que "no configurado", sin romper el flujo).
- Si no hay `base_access_token`, usa `credentials.access_token` estático
  (comportamiento legado, compatible con conexiones ya existentes).
- **Recomendación para el token base:** usar un **System User token**
  de Business Manager (no expira solo) en vez de un User Access Token de
  Graph API Explorer (dura ~60 días o menos). Para el uso manual actual
  (probar en una sola página) un User Access Token de Graph API Explorer
  basta, pero para Fase 6B en producción conviene migrar a un System User.
- **Importante para conexiones `platform=INSTAGRAM`:** la Graph API solo
  resuelve tokens contra un `page_id` de Facebook
  (`GET /{page_id}?fields=access_token`) — no existe el equivalente para
  un ID de cuenta de Instagram directamente. En una conexión de
  Instagram, `external_account_id` es el ID de la cuenta de Instagram (el
  destino real de publicación), así que hay que guardar además
  `credentials.page_id` con el ID de la página de Facebook vinculada. En
  una conexión de Facebook no hace falta (son el mismo ID).
- `verify_connection` (`/publishing-connections/{id}/verify`) ya NO
  reutiliza `MetaPublishingProvider.validate()` para META — ese método es
  un chequeo local (sin red) que además exige `asset_public_url` para
  INSTAGRAM, lo cual siempre fallaba en un simple "ping" de verificación
  sin activo. Ahora usa `verify_meta_account_reachable()`
  (`meta_token_resolver.py`), que sí hace una llamada real a la Graph API
  contra `external_account_id` con el token resuelto.

**Estado real de Instagram (2026-07-24):** conexión creada
(`platform=INSTAGRAM`, `external_account_id=17841413032834214`,
`credentials={base_access_token, page_id=1228107327050361}`), verificada
`ACTIVE` de verdad contra la Graph API. **Publicar con imagen real
todavía falla** — no por el token, sino porque los activos en local usan
`StorageProvider=MOCK` (URLs `mock://...`, no accesibles desde internet);
Meta rechaza con `"Only photo or video can be accepted as media type."`
porque no puede descargar la imagen. Hace falta R2/S3 real (ver checklist
abajo) antes de poder publicar de verdad en Instagram.

**Config local:** `apps/api/.env` (gitignored) ahora existe con
`JWT_SECRET` y `CREDENTIALS_ENCRYPTION_KEY` fijos — **antes no existía
este archivo**, así que cada reinicio del servidor generaba credenciales
de publicación indescifrables (`InvalidToken` al desencriptar), porque la
clave de cifrado dependía de `JWT_SECRET` y este no estaba fijado. Con
`.env` fijo esto ya no debería repetirse. También tiene
`META_PUBLISHING_ENABLED=true`.

**Estado de la conexión — YA FUNCIONA de punta a punta (2026-07-24):**
la `PublishingConnection` (`id=936cf1e3-2aa3-4314-8c55-8ea4f14d6d37`,
`platform=FACEBOOK`, `provider=META`,
`external_account_id=1228107327050361`) tiene guardado un
`credentials.base_access_token` real: un **System User token** de
Business Manager ("administrador-automatico", acceso total a la página
Recetasquetransforman21, generado desde la app "Kingdom Studio RTM" en
lugar de "RTQ21 RECETAS" porque esa última todavía no tenía el system
user asignado como rol de app — pendiente si se quiere separar). Se
verificó (`/verify` → `status: ACTIVE`, resolviendo un token de página
fresco de verdad) y se publicó un post real de prueba:
`external_publication_id=1228107327050361_122111902413390585`,
`https://www.facebook.com/1228107327050361_122111902413390585`.

**Nota de infraestructura local:** Postgres corre en Docker
(`infra/docker-compose.yml`, servicios `db` → contenedor `rqt21_db`
puerto 5432, y `db_test` → contenedor `rqt21_db_test` puerto 5433, este
último requerido para correr `pytest`). Si Docker Desktop no está
corriendo, todas las peticiones a la API (y los tests) se cuelgan
(timeout) en vez de fallar rápido — si esto vuelve a pasar, primero
verificar `docker ps` y `docker compose -f infra/docker-compose.yml up -d
db db_test`. Redis NO es necesario en local (queda en
`QUEUE_BACKEND=inline` / `SCHEDULER_BACKEND=memory` por defecto).
`apps/web/.env.local` (gitignored) apunta `NEXT_PUBLIC_API_URL` al puerto
de la API local — ajustar si la API corre en otro puerto.
`.claude/launch.json` tiene la config para levantar el web dev server con
la herramienta de preview.

**Checklist completa de Fase 6B (lo básico de Meta ya funciona; pendiente
el resto):**
- [x] Conexión Meta real activa + publicación real de prueba en Facebook.
- [x] Conexión Meta real activa en Instagram también (mismo token base +
  `credentials.page_id` apuntando a la página vinculada) — falta solo
  storage real para poder publicar con imagen (ver siguiente punto).
- [ ] R2/S3 real para assets — bloqueante para publicar de verdad en
  Instagram (Meta necesita una URL de imagen pública real; en local solo
  hay `StorageProvider=MOCK`, que da URLs `mock://...` no descargables).
- [ ] Migrar el System User base token a la app "RTQ21 RECETAS" propia
  (agregarle el rol de app) en vez de usar "Kingdom Studio RTM", para
  mantener los dos proyectos separados.
- [ ] Ver `infra/scripts/README.md` para R2/S3, Sentry, host de
  staging/producción, y secretos de GitHub Actions — todo eso sigue
  pendiente.
