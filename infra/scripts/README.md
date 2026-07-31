# Operación de Fase 6

Esta guía cubre dos cosas separadas:

1. **Fase 6B — qué crear y pegar** para activar cada pieza que la Fase 6A dejó
   preparada pero inactiva.
2. **Runbooks de operación** — qué hacer cuando algo falla en staging/producción.

Todo lo que menciona esta guía ya existe en código (probado con mocks); nada de
esto requiere escribir código nuevo, solo crear cuentas/recursos reales y pegar
sus valores en variables de entorno.

---

## Fase 6B: qué crear, en orden

### 1. Base de datos administrada (Postgres)

Cualquier proveedor sirve (Railway, Render, Supabase, RDS, Neon, etc.). Solo
necesitas la cadena de conexión.

- Pega el resultado en `DATABASE_URL` dentro de `.env.production` (y de
  `.env.staging` si usas un proveedor administrado ahí también en vez del
  contenedor `db` que trae `docker-compose.staging.yml` por defecto).

### 2. Redis administrado

Igual: Railway/Upstash/Redis Cloud/ElastiCache, lo que prefieras.

- Pega la URL en `REDIS_URL`.
- Pon `QUEUE_BACKEND=redis` y `SCHEDULER_BACKEND=redis` para activar
  `RedisJobQueue` y `RedisScheduler` (antes de esto, el sistema sigue
  funcionando exactamente como en las Fases 1-5, solo que en un solo proceso).

### 3. Storage S3 o Cloudflare R2

**R2 (recomendado, sin costos de salida de datos):**
1. Crea una cuenta de Cloudflare, activa R2.
2. Crea un bucket (ej. `rqt21-staging-assets`).
3. Genera credenciales de API R2 (Access Key + Secret Key).
4. Copia el "Account ID" — el endpoint es
   `https://<account-id>.r2.cloudflarestorage.com`.

Rellena en tu `.env.*`:
```
STORAGE_PROVIDER=R2
STORAGE_BUCKET=rqt21-staging-assets
STORAGE_REGION=auto
STORAGE_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
STORAGE_ACCESS_KEY=...
STORAGE_SECRET_KEY=...
```

**S3:** mismo procedimiento sin `STORAGE_ENDPOINT` (déjalo vacío) y
`STORAGE_PROVIDER=S3` con tu región real.

### 4. Meta App (Facebook Login + Instagram Graph)

1. Ve a [developers.facebook.com](https://developers.facebook.com) y crea una
   App de tipo "Business".
2. Agrega el producto **Facebook Login** y **Instagram Graph API**.
3. En Facebook Login → Settings, agrega tu Redirect URI:
   `https://api-staging.example.com/api/v1/oauth/meta/callback` (ajusta al
   dominio real).
4. Copia el App ID y App Secret desde Settings → Basic.
5. Rellena:
   ```
   META_APP_ID=...
   META_APP_SECRET=...
   META_OAUTH_REDIRECT_URI=https://tu-dominio/api/v1/oauth/meta/callback
   ```
6. Deja `META_PUBLISHING_ENABLED=false` hasta que hayas probado el flujo de
   OAuth completo con una cuenta de prueba (Meta App en modo Development
   solo permite usuarios/páginas que agregues explícitamente como testers —
   no publica hacia cuentas reales por accidente).
7. Cuando estés listo para publicar de verdad: `META_PUBLISHING_ENABLED=true`.

`app.oauth.meta.MetaOAuthClient` y `app.publishing.adapters.MetaPublishingProvider`
ya implementan el flujo completo (authorize URL, exchange code, token de larga
duración, publicación real en Facebook/Instagram, mapeo de errores). No hay
nada más que programar para activarlo — solo estos valores.

### 5. Sentry (opcional pero recomendado)

1. Crea un proyecto en [sentry.io](https://sentry.io) (Python/FastAPI).
2. Copia el DSN.
3. `ERROR_REPORTER=sentry`, `SENTRY_DSN=...`.

### 6. Host de staging/producción

**Opción A — VPS con Docker** (Hetzner, DigitalOcean, un servidor propio):
`docker-compose.staging.yml`/`docker-compose.prod.yml` no asumen ninguna
plataforma en particular.

1. Instala Docker + Docker Compose en el servidor.
2. Clona el repo en `/opt/rqt21-growth-os`.
3. Copia `.env.staging.example` → `.env.staging` (o `.env.production`) y
   rellena todo lo anterior.
4. Primer deploy manual: `./infra/scripts/deploy_staging.sh` (o
   `deploy_production.sh <sha>`).

**Opción B — Vercel (frontend) + Railway (API/Postgres/Redis), sin dominio
propio (recomendado para arrancar rápido):**

1. **Railway**: crea un proyecto con 3 piezas —
   - Un servicio apuntando a este repo, con "Dockerfile Path" =
     `infra/Dockerfile.api` y "Root Directory" = raíz del repo (el
     Dockerfile copia `apps/api` relativo a la raíz, no funciona con
     `apps/api` como root).
   - Plugin Postgres (te da `DATABASE_URL` automático).
   - Plugin Redis (te da `REDIS_URL` automático; opcional al inicio —
     sin esto, `QUEUE_BACKEND=inline`/`SCHEDULER_BACKEND=memory` funciona
     igual en una sola instancia).
   - Variables de entorno del servicio API: las mismas de
     `.env.production.example` (`JWT_SECRET`, `CREDENTIALS_ENCRYPTION_KEY`,
     `STORAGE_*`, `META_*`, claves de IA) más `COOKIE_SECURE=true`. **No
     hace falta `COOKIE_DOMAIN`** ni tocar `CORS_ORIGINS` para el dominio
     de Vercel — ver el punto del proxy más abajo.
   - Migraciones no corren solas al arrancar: después de cada deploy,
     `railway run uv run alembic upgrade head` (o vía la consola de
     Railway).
2. **Vercel**: importa el repo, Root Directory = `apps/web`. Variable de
   entorno **`API_PROXY_TARGET`** = la URL pública que te da Railway
   (ej. `https://rqt21-api-production.up.railway.app`, sin slash final).
   **No** definas `NEXT_PUBLIC_API_URL` en Vercel — dejarla vacía es lo
   que activa el proxy.
3. **Por qué un proxy en vez de llamar a Railway directo desde el
   navegador**: la sesión usa cookies HttpOnly (`app/cookies.py`). Si el
   frontend (`*.vercel.app`) y la API (`*.up.railway.app`) son dominios
   distintos, el navegador trata la llamada como cross-site — con
   `COOKIE_SAMESITE=lax` (el default) la cookie de sesión no viaja, y el
   login queda roto en producción aunque el código esté bien.
   `apps/web/next.config.mjs` define un `rewrites()` que reenvía
   `/api/v1/*` a `API_PROXY_TARGET` de forma transparente al navegador —
   este solo ve que le habló a su propio origen (`app.vercel.app`), así
   que la cookie que pone la API llega marcada como same-site. No hace
   falta comprar dominio ni tocar `SameSite=None` (que además es frágil
   por el bloqueo de cookies de terceros de Safari/Chrome). El costo es
   ninguno — es una función de config, no un servicio nuevo.
4. Actualiza `META_OAUTH_REDIRECT_URI` para que apunte al dominio real de
   Railway (ese sí es un redirect servidor-a-servidor desde Meta, no pasa
   por el navegador — no necesita el proxy).

### 7. GitHub Actions (deploy automático)

En **Settings → Secrets and variables → Actions** del repo, agrega:
- `STAGING_SSH_HOST`, `STAGING_SSH_USER`, `STAGING_SSH_KEY` (clave privada SSH
  con acceso al servidor de staging).
- `PROD_SSH_HOST`, `PROD_SSH_USER`, `PROD_SSH_KEY` — igual para producción.

En **Settings → Environments**:
- Crea el environment `staging` (sin protección — se despliega automático
  tras cada CI verde en `main`, ver `deploy-staging.yml`).
- Crea el environment `production` y en **Required reviewers** agrega al
  menos una persona. Esto es lo que convierte
  `deploy-production.yml`/`rollback.yml` en "requiere aprobación manual" —
  GitHub pausa el job hasta que alguien apruebe. No hay forma de configurar
  esto desde el YAML del workflow, solo desde esta pantalla.

Sin estos secretos, los workflows de deploy igual compilan y suben las
imágenes Docker a `ghcr.io` (gratis, no requiere nada adicional) pero
imprimen un aviso y no intentan conectarse a ningún servidor — no fallan
"rompiendo" nada, simplemente no hay a dónde desplegar todavía.

---

## Runbooks

### Publicaciones fallidas — panel y reprocesamiento

No hay un panel nuevo que construir: **`/publishing`** (filtro por estado
`FAILED`) y **`GET /api/v1/publications?failed_only=true`** ya son ese panel
desde la Fase 5. Para cada publicación fallida:
- `GET /api/v1/publications/{id}/attempts` — historial completo, nunca se
  borra.
- `POST /api/v1/publications/{id}/retry` (OWNER/ADMIN) — reprocesa a mano.
- El worker `app.workers.publish_due` reintenta automáticamente según
  `PUBLISH_MAX_ATTEMPTS`/`PUBLISH_RETRY_BASE_SECONDS` — ver
  `app/publishing/retry.py`.

### Limpieza de almacenamiento (banco de assets)

`app.workers.cleanup_published_assets` corre una vez al día (ver el
servicio `asset-cleanup-scheduler` en `docker-compose.prod.yml` /
`docker-compose.staging.yml`, o un cron externo apuntando al mismo
comando) y borra del bucket R2/S3 los archivos de cualquier `Asset` cuyas
publicaciones ya salieron en vivo — así el bucket no crece sin límite con
cada imagen/video generado. Reglas:
- Solo borra si **todas** las publicaciones que referencian ese asset están
  en `PUBLISHED` (o `CANCELLED`/`ARCHIVED`); si alguna sigue en
  `DRAFT`/`READY`/`SCHEDULED`/`PUBLISHING`/`RETRY_SCHEDULED`/`FAILED`, el
  asset se deja intacto.
- Espera `ASSET_CLEANUP_AFTER_DAYS` (default 2) días desde la publicación
  más reciente antes de borrar — período de gracia por si hace falta
  revisar algo justo después de publicar.
- Nunca borra la fila del `Asset` en la base de datos, solo el archivo:
  la fila queda con `status=ARCHIVED` para conservar el historial de qué
  se publicó y cuándo.
- Un asset que nunca se adjuntó a ninguna publicación no lo toca — esto no
  es una limpieza general de la biblioteca, solo de lo que ya se publicó.

### Estado de conexiones

**`/publishing/connections`** ya muestra estado (`ACTIVE`/`ERROR`/`REVOKED`/
`EXPIRED`) y el botón "Verificar" llama a `POST
/publishing-connections/{id}/verify`, que para Meta ahora usará
`MetaOAuthClient.debug_token()` una vez haya un token real conectado (Fase 6B).

### Trabajos atascados (jobs stuck)

- Generación IA: `GET /api/v1/generation-jobs?status=RUNNING` — si un job
  lleva más de `AI_REQUEST_TIMEOUT_SECONDS` en `RUNNING`, el proceso que lo
  ejecutaba murió sin terminar. Con `QUEUE_BACKEND=redis`, revisa
  `rq worker` — RQ marca jobs muertos como `failed` automáticamente tras el
  timeout del `Retry`; con `QUEUE_BACKEND=inline` (default) esto no debería
  pasar porque el job corre síncronamente en el mismo request.
- Publicaciones: `GET /api/v1/publications?status=PUBLISHING` — un estado
  `PUBLISHING` que no avanza indica un worker caído a mitad de
  `_execute_publish`. Como la reclamación es atómica
  (`UPDATE ... WHERE status = X`), es seguro simplemente correr
  `python -m app.workers.publish_due` de nuevo una vez el proceso caído ya
  no exista — no duplicará el intento si otro worker ya lo tomó.

### Rollback

1. Rollback de código: `infra/scripts/rollback.sh <sha-anterior> production`
   o el workflow `rollback.yml` (mismo gate de aprobación que producción).
2. Si el deploy que falló incluyó una migración nueva:
   - Si la migración es aditiva (agrega tablas/columnas nullable) — el
     rollback de código es seguro sin tocar la base de datos; el código
     viejo simplemente ignora las columnas nuevas.
   - Si la migración modificó/eliminó algo que el código viejo necesita,
     corre `uv run alembic downgrade <revisión-anterior>` ANTES de hacer
     el rollback de código (todas las migraciones de este proyecto, 0001 a
     0006, tienen `downgrade()` probado — ver `apps/api/tests/test_migrations.py`).

### Backups

- Postgres administrado: activa los backups automáticos del proveedor
  (todos los mencionados en la sección 1 los ofrecen) — no dependas de un
  script propio para esto.
- Si usas un Postgres autoalojado (contenedor `db` en
  `docker-compose.staging.yml`): programa `pg_dump` diario a un bucket S3/R2
  aparte del de assets, con al menos 7 días de retención. No incluido como
  script porque depende del proveedor de backup elegido — no hay una opción
  "genérica" razonable aquí.
- Assets (R2/S3): habilita versionado de objetos en el bucket si el
  proveedor lo soporta — protege contra un `DELETE` erróneo sin necesitar
  backups aparte.

### Webhooks de Meta

No implementados todavía (fuera del alcance de la Fase 6A — ver exclusiones
de la Fase 6). Cuando se agreguen, `META_WEBHOOK_VERIFY_TOKEN` ya está
reservado en la configuración para la verificación de suscripción.
