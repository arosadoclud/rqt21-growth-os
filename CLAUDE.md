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
  `alembic/versions/0001` a `0007`. Cada una debe tener `downgrade()`
  probado (ver `tests/test_migrations.py`). **Al agregar una migración
  nueva, actualizar también el stamp hardcodeado en
  `tests/conftest.py::_prepare_schema`** (`INSERT INTO alembic_version
  ...`) — los tests usan `Base.metadata.create_all()` + ese stamp fijo en
  vez de correr las migraciones reales, así que si no se actualiza,
  `test_ready_reports_db_and_migrations` falla (mismatch entre el head
  real de Alembic y el stamp de prueba).
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
- [x] R2/S3 real para assets — configurado en producción (Railway, ver
  sección "Producción real desplegada" más abajo): bucket
  `rqt21-production-assets` en Cloudflare R2. **Nota:** local sigue en
  `StorageProvider=MOCK` (`apps/api/.env`) — solo producción tiene R2 real.
- [ ] Migrar el System User base token a la app "RTQ21 RECETAS" propia
  (agregarle el rol de app) en vez de usar "Kingdom Studio RTM", para
  mantener los dos proyectos separados. Cosmético/organizativo, no bloquea
  nada — la publicación real ya funciona con el token actual.
- [ ] Sentry (`ERROR_REPORTER=sentry` + `SENTRY_DSN`) — todavía no
  configurado ni en local ni en producción. Sin esto, un error en Railway
  solo se ve mirando `railway logs` a mano, no hay alerta ni dashboard.

## Generación de contenido con IA real (2026-07-24)

Decisión del usuario: **texto/hashtags con Claude (Anthropic), imágenes
con DALL-E/gpt-image-1 (OpenAI)** — no Gemini (su suscripción "Plus" es
de consumo, no da acceso a la API de desarrollador; lo mismo aplica a
ChatGPT Plus/Claude Pro — todas requieren una API key aparte con
facturación propia: console.anthropic.com / platform.openai.com).

- **Texto:** `AnthropicAIProvider` (`app/ai/providers.py`) ya existía
  desde Fase 4, solo pendiente de `ANTHROPIC_API_KEY` +
  `AI_PROVIDER=ANTHROPIC` en `apps/api/.env` — **aún no configurado en
  esta sesión, el usuario todavía no compartió esa key** — **actualizado:
  ya se configuró (`ANTHROPIC_API_KEY` + `AI_PROVIDER=ANTHROPIC` +
  `AI_MODEL=claude-sonnet-5` en `apps/api/.env`) y se probó con una
  generación real de `SOCIAL_POST` para RQT21; resultado correcto: título
  en MAYÚSCULAS con emojis, sin asteriscos/guiones/markdown, caption con
  párrafos naturales, CTA, y exactamente 5 hashtags específicos del tema.
  **Gotcha encontrado**: `AI_MODEL` traía el default `mock-editorial-v1`
  (placeholder pensado solo para el proveedor MOCK) — con `AI_PROVIDER=ANTHROPIC`
  y ese modelo, la API de Anthropic respondía 404 (modelo inexistente);
  hubo que fijar `AI_MODEL=claude-sonnet-5` explícitamente en `.env`. La
  plantilla por defecto (`app/ai/templates.py::_DEFAULT_USER_TEMPLATE`,
  ahora versión `-v2`) exige caption+cta ≤200 palabras, exactamente 5
  hashtags específicos del post (no genéricos), y título en MAYÚSCULAS sin
  markdown (emojis sí permitidos) — ver sección "Ajustes de calidad de
  generación" más abajo para el detalle de ese cambio y el gotcha de
  versión de plantillas que lo acompaña.
- **Imágenes:** nuevo `GenerationType.IMAGE_ASSET` (migración
  `0007_image_generation` — agrega el valor al CHECK constraint de
  `prompt_templates.generation_type`). Nuevo módulo
  `app/ai/image_providers.py` (`OpenAIImageProvider`, modelo
  `gpt-image-1` vía `/v1/images/generations`, pide `b64_json` para no
  depender de una URL temporal de OpenAI). Gateado por
  `AI_IMAGE_PROVIDER=OPENAI` (flag separado de `AI_PROVIDER`, mismo
  patrón "nunca se activa solo con la key" del resto del proyecto) +
  `OPENAI_API_KEY` — **ambos ya configurados y probados con una llamada
  real**: generó una imagen real (1024x1024) de un plato de pizza keto de
  brócoli, guardada como `Asset` real vía el pipeline de storage
  existente.
- **`app/ai/runner.py::_run_image_generation`**: al completarse, sube los
  bytes generados con `get_storage_provider().upload(...)` y crea un
  `Asset` (`asset_type=IMAGE`, `status=READY`) — el mismo pipeline que
  usa la carga manual de activos. `job.output_payload` queda
  `{"asset_id", "asset_public_id", "prompt"}` en vez del JSON de texto
  (`GeneratedContent`).
- **`app/ai/runner.py::_build_image_prompt`**: el prompt que se manda a
  DALL-E se arma directo desde `input_payload["raw_input"]` (topic +
  audience), **no** desde el texto renderizado por `render_prompt()` —
  ese texto trae el wrapper `<user_input>...</user_input>` pensado para
  que un modelo de TEXTO "escriba" un prompt, no para mandarlo tal cual a
  una API de imágenes. La primera prueba (antes de este fix) generó una
  imagen con texto de marca superpuesto porque DALL-E tomó ese wrapper
  instructivo literalmente; el prompt reconstruido agrega explícitamente
  "No text, no words, no letters, no captions, no logos, no watermarks".
- Frontend: `IMAGE_ASSET` agregado a `GENERATION_TYPES`
  (`packages/contracts`); `generation-jobs/[id]/page.tsx` muestra una
  vista previa de la imagen (vía `assetDownloadUrl`) en vez del layout de
  texto para este tipo de job.
- **Bug preexistente encontrado de paso (no arreglado, fuera de
  alcance):** `LocalStorageProvider.create_signed_url()`
  (`app/storage/provider.py`) genera URLs `/api/v1/assets/_local-file/...`
  pero **ese endpoint no existe** — nadie lo implementó. Los archivos sí
  se escriben bien a disco (`./data/assets/...`), solo la descarga vía
  HTTP con `STORAGE_PROVIDER=LOCAL` está rota. No afecta S3/R2 ni MOCK.
- Tests: `tests/test_image_generation.py` (usa `MockImageProvider`, nunca
  llama a OpenAI real, mismo patrón que el resto del proyecto).

## Identidad de marca permanente + selector de tipo de contenido (2026-07-24)

- **`BrandVoiceProfile.visual_style`** (migración `0008_brand_voice_visual_style`,
  columna `String(4000)`, editable en `/brand-voice`): describe fondo, paleta,
  tipografía y estilo fotográfico de la marca. `runner.py::_build_image_prompt`
  lo inyecta en cada generación de `IMAGE_ASSET` de esa marca — si está vacío,
  cae a un estilo genérico sin texto ni logo. Así el criterio de diseño de
  RQT21 (fondo negro mate, paleta negro/blanco/verde esmeralda/verde lima,
  tipografía condensada tipo Bebas Neue, fotografía hiperrealista) queda
  permanente y no hay que repetirlo en cada prompt.
- **Logo real superpuesto, no dibujado por la IA**
  (`app/ai/logo_overlay.py::apply_brand_logo`): un modelo de imágenes nunca
  reproduce un logo específico de forma consistente pixel a pixel, así que en
  vez de pedírselo por texto, el logo oficial (archivo real, no descripción)
  se compone encima del PNG generado con Pillow, en la esquina inferior
  izquierda (22% del ancho del flyer, margen 4%), justo antes de subirlo a
  storage. Se activa por convención de nombre de archivo:
  `app/ai/brand_assets/{brand.slug}_logo.png` (transparente) — si no existe
  el archivo para esa marca, no se hace nada (capa opcional, nunca bloquea la
  generación). El logo de RQT21 vive en
  `app/ai/brand_assets/recetas-que-transforman-21_logo.png` (no es un asset
  gestionado por el sistema de biblioteca de activos, es un archivo de marca
  fijo del código, igual que las plantillas de prompt).
- **Importante**: por eso `visual_style` de RQT21 le pide explícitamente al
  modelo de imágenes que **deje vacía la esquina inferior izquierda** (sin
  texto, sin ícono, sin logo dibujado por él) — antes de este ajuste el
  modelo dibujaba su propio intento de logo ahí mismo y quedaba superpuesto
  con el logo real, chocando visualmente. Verificado con dos generaciones
  reales de prueba (bowl de salmón, wrap de pollo): el logo real queda limpio
  y los íconos de beneficios se reacomodan a la derecha.
- Nueva dependencia: `pillow` (agregada a `apps/api/pyproject.toml`), usada
  solo para este compuesto de imagen — no se usa en ningún otro flujo.
- **Selector "¿Qué quieres crear?" en `/generate`**
  (`apps/web/app/(app)/generate/page.tsx`): en vez de un `<select>` crudo con
  el enum `GenerationType`, una grilla de 4 tarjetas (Reel / Publicación con
  foto / Publicación solo texto / Historia) que mapean a
  `REEL_SCRIPT`/`IMAGE_ASSET`/`SOCIAL_POST`/`STORY`. Nuevo valor de enum
  `GenerationType.STORY` agregado en la misma migración `0008` (extiende el
  CHECK constraint `ck_prompt_templates_generation_type_valid`) — usa la
  plantilla de texto genérica, no tiene plantilla propia todavía.

## Ajustes de calidad de generación (2026-07-24, sesión posterior)

- **`AI_IMAGE_SIZE` default cambiado de `1024x1024` a `1024x1536`**
  (`app/core/config.py`): el prompt siempre pedía formato vertical (9:16 /
  4:5) pero se generaba en lienzo cuadrado, así que el título del flyer se
  salía por el borde superior. Portrait real resuelve esto. Como
  contrapartida tarda más (~45-70s en vez de ~20-30s), así que
  `AI_REQUEST_TIMEOUT_SECONDS` también subió de 45 a 90 — con el default
  viejo la generación en portrait daba timeout siempre.
- **`app/ai/logo_overlay.py`**: además de pegar el logo real, ahora pinta un
  parche sólido (`_BACKDROP_COLOR`, negro casi puro, esquinas redondeadas)
  detrás del logo antes de componerlo. Motivo: pedirle al modelo por texto
  que deje esa esquina vacía es "mejor esfuerzo" — a veces igual dibuja su
  propio ícono ahí y choca con el logo real. El parche garantiza un
  resultado limpio sin depender de que el modelo obedezca la instrucción.
  Asume fondo negro de marca (documentado en el código) — si algún día se
  agrega una marca con fondo claro habría que hacer este color configurable
  por marca en vez de una constante.
- **`app/ai/runner.py::_build_image_prompt`**: agrega, para cualquier marca
  con `visual_style` definido (no solo RQT21), una instrucción de margen de
  seguridad del 10% en los cuatro bordes + "si el título es largo, reduce el
  tamaño de fuente en vez de dejarlo cortado" + formato de título en
  mayúsculas sin markdown — vive en código, no en `visual_style`, porque es
  un comportamiento del modelo de imágenes, no una decisión de diseño de
  marca.
- **`app/ai/templates.py`**: `_DEFAULT_USER_TEMPLATE` (usado por
  SOCIAL_POST/REEL_SCRIPT/STORY/CONTENT_IDEAS) ahora exige explícitamente
  título en MAYÚSCULAS sin asteriscos/guiones/markdown (emojis sí
  permitidos), y que los 5 hashtags sean los más relevantes para ESE post en
  particular, nunca genéricos. **Gotcha de versión de plantillas**: cambiar
  el texto de una plantilla default en código no alcanza — `get_active_template`
  buscaba la plantilla activa por `(organization_id, generation_type)` sin
  mirar la versión, así que devolvía la fila vieja de la DB para siempre.
  Se corrigió agregando lógica en `get_active_template` para retirar
  (`is_active=False`) un default de sistema (`version` empieza con
  `"system-default-"`) cuyo `version` no coincide con
  `_default_version(generation_type)` actual, para que se cree la v2
  automáticamente en la próxima generación. `_default_version` pasó de
  `-v1` a `-v2` para reflejar este cambio de contenido. **Si se vuelve a
  tocar el texto de una plantilla default en el futuro, hay que subir el
  sufijo `-v2` → `-v3` otra vez** — si no, el cambio de código queda sin
  efecto silenciosamente para instalaciones ya en uso.
- Verificado con generaciones reales: imagen de prueba (bowl de camarones,
  1024x1536) con título completo dentro del cuadro y logo real limpio sobre
  su parche; job de texto de prueba confirmó `prompt_version =
  system-default-social_post-v2` con las nuevas reglas de formato en el
  prompt enviado (el contenido generado en sí sigue viniendo del proveedor
  MOCK — Claude/Anthropic real aún no configurado, ver sección anterior).
- **Claude/Anthropic real configurado y verificado** (sesión posterior,
  2026-07-24): `ANTHROPIC_API_KEY` + `AI_PROVIDER=ANTHROPIC` +
  `AI_MODEL=claude-sonnet-5` en `apps/api/.env`. Generación real de
  `SOCIAL_POST` confirmó título en MAYÚSCULAS con emojis, sin markdown,
  caption con párrafos naturales, CTA y exactamente 5 hashtags específicos.
  **Gotcha**: `AI_MODEL` traía el default `mock-editorial-v1` (placeholder
  solo para MOCK) — con `AI_PROVIDER=ANTHROPIC` y ese "modelo" la API real
  respondía 404; hubo que fijar `AI_MODEL` a un id real explícitamente.

## Wizard de generación con tarjetas + gestor de cuentas (2026-07-24/25)

- **`/generate`** ya no es un formulario plano: ahora es un wizard de 3
  pasos con tarjetas (`apps/web/app/(app)/generate/page.tsx`) — 1) elegir
  Facebook o Instagram (con un toggle para "otra plataforma": TikTok,
  YouTube, Email…), 2) elegir tipo de contenido (Reel / Historia /
  Publicación con foto / Publicación solo texto / Video), 3) completar el
  brief. Chips de navegación arriba del formulario permiten volver a
  cambiar cualquiera de las dos primeras elecciones sin perder el progreso.
- **`/publishing/connections`** rediseñado como grid de tarjetas en vez de
  tabla — cada cuenta muestra insignia de plataforma, marca, estado,
  proveedor y última verificación de un vistazo; el formulario de alta
  ahora es un panel que se despliega con un botón "Agregar cuenta" en vez
  de estar siempre visible. **`lucide-react` no exporta íconos `Facebook`
  ni `Instagram`** (ya había pasado antes en `manual/page.tsx`) — se usan
  insignias de texto ("f" / "IG") en vez de íconos de marca.
- Alcance explícitamente descartado por ahora: extraer/descargar contenido
  de terceros en TikTok/Pinterest para republicarlo como propio — viola
  los términos de servicio de esas plataformas y probablemente derechos de
  autor. Si en el futuro se conectan esas plataformas, debe ser vía sus
  APIs oficiales y limitado a las cuentas propias del usuario.

## Generación de video con guion (VIDEO_ASSET) — 2026-07-25

Nuevo tipo de generación de punta a punta, sin depender de un modelo de IA
de video (caro/complejo): guion real (Claude) → una imagen de marca por
escena (DALL-E, mismo pipeline que `IMAGE_ASSET` — logo real compuesto,
`visual_style` de la marca) → narración (TTS) → ensamblado con ffmpeg en un
MP4 vertical listo para Reels/Historias. Verificado de punta a punta con
generación real (guion de Claude + 5 escenas de DALL-E + voz de OpenAI TTS
+ ffmpeg): video real de ~1080x1920, ~25s, con audio, subido como `Asset`
real.

- **`GenerationType.VIDEO_ASSET`** (migración `0009_video_generation`,
  agrega el valor al CHECK constraint de `prompt_templates.generation_type`
  — mismo patrón que `STORY` en la migración `0008`). Reutiliza la
  plantilla de texto genérica (`_DEFAULT_SYSTEM_INSTRUCTIONS`/
  `_DEFAULT_USER_TEMPLATE`, el mismo esquema `GeneratedContent` que
  `REEL_SCRIPT`/`SOCIAL_POST`) — no hizo falta una plantilla nueva:
  `visual_notes` se reutiliza como la lista de escenas y `script` como el
  texto de la narración.
- **`app/ai/runner.py::_run_video_generation`**: se dispara desde
  `run_generation_job` justo después de parsear el `GeneratedContent` del
  guion, cuando `job.generation_type == VIDEO_ASSET` (en vez de marcar el
  job COMPLETED con el texto crudo como hacen los demás tipos de texto).
  Toma hasta `AI_VIDEO_MAX_SCENES` (default 5) entradas de `visual_notes`
  como escenas; si el guion no trae ninguna, cae a un fallback de una sola
  escena (`hook` o `title`). Cada escena se genera con el mismo
  `_brand_visual_directives()` que usa el flyer de `IMAGE_ASSET` (extraído
  a una función compartida) — mismo estilo visual de marca, mismo logo real
  compuesto por escena (`app/ai/logo_overlay.py::apply_brand_logo`).
- **Concurrencia — gotcha real encontrado y corregido**: las escenas se
  generaban al principio en un `for` secuencial — con 4-5 escenas reales de
  DALL-E a 45-70s cada una, el job entero tardaba 3-6 minutos dentro de una
  sola petición HTTP síncrona (`InlineJobQueue`), y el timeout se disparaba
  antes de terminar. Se corrigió generando todas las escenas en paralelo
  con `asyncio.gather` (son independientes entre sí) — el tiempo total pasó
  a depender de UNA llamada a DALL-E en vez de N, ~65-90s en total con 5
  escenas reales.
- **`app/ai/tts_providers.py`** (nuevo, mismo patrón Protocol+Mock+flag que
  el resto del proyecto): `MockTTSProvider` sintetiza silencio real (no
  bytes falsos) con el binario de ffmpeg embebido, de duración proporcional
  al texto — así los tests ejercitan el ensamblado real de audio sin
  llamar nunca a OpenAI. `OpenAITTSProvider` llama a
  `POST /v1/audio/speech` (modelo `gpt-4o-mini-tts` por defecto, voz
  `alloy`). Gateado por `AI_TTS_PROVIDER=OPENAI` (flag propio, separado de
  `AI_PROVIDER`/`AI_IMAGE_PROVIDER`, mismo "nunca se activa solo con la
  key") + `OPENAI_API_KEY` — **ya configurado y probado con una llamada
  real** en esta sesión.
- **`app/video/assembler.py`** (nuevo): `assemble_slideshow()` arma un MP4
  con el demuxer `concat` de ffmpeg — cada imagen de escena se muestra
  durante una porción igual de la duración total del audio de narración
  (duración leída del propio audio vía `ffmpeg -i ... -f null -` y regex
  sobre el `Duration:` de stderr, sin depender de `ffprobe`), escaladas y
  con letterbox a 1080x1920. **`imageio-ffmpeg`** (nueva dependencia)
  provee un binario de ffmpeg estático descargado por pip — no hace falta
  instalar ffmpeg en el sistema ni en la imagen Docker.
- **Gotcha de `sniff_mime`**: el header `ftyp` que produce ffmpeg no
  coincidía con las firmas exactas que ya existían en
  `app/storage/validation.py` (`\x00\x00\x00\x18ftyp` / `\x00\x00\x00\x1cftyp`
  — el tamaño del box varía según el encoder). Se corrigió detectando la
  marca `ftyp` en el offset 4 en vez de un prefijo de tamaño fijo.
- Costo estimado del job = costo de texto (Claude) + `_IMAGE_COST_USD ×
  número de escenas` (si `AI_IMAGE_PROVIDER=OPENAI`) + un estimado plano de
  TTS (si `AI_TTS_PROVIDER=OPENAI`) — igual que el resto del dashboard de
  costos, es solo informativo, no se factura a la organización.
- Frontend: `VIDEO_ASSET` agregado a `GENERATION_TYPES`
  (`packages/contracts`), tarjeta "Video" en el wizard de `/generate`;
  `generation-jobs/[id]/page.tsx` muestra un reproductor `<video>` (vía
  `assetDownloadUrl`, mismo mecanismo que la vista previa de imagen) en vez
  del layout de texto para este tipo de job.
- Tests: `tests/test_video_generation.py` (usa `MockAIProvider` +
  `MockImageProvider` + `MockTTSProvider`, nunca llama a un proveedor real
  — pero SÍ ejercita el ensamblado real de ffmpeg con imágenes/audio de
  prueba, produciendo un MP4 real y válido, mismo patrón que la validación
  de checksum/tamaño real en `test_image_generation.py`).
- **Limitación conocida, no arreglada**: igual que con los flyers de
  `IMAGE_ASSET`, el modelo de imágenes a veces sigue dibujando su propio
  texto/ícono de beneficio superpuesto parcialmente con el logo real en
  algunas escenas — es el mismo comportamiento "mejor esfuerzo" del modelo
  documentado más arriba, el parche sólido detrás del logo evita el choque
  pero no controla qué dibuja el modelo alrededor.

### Video con personas reales en movimiento (STOCK_FOOTAGE) — misma sesión

El usuario probó el primer video y pidió personas en movimiento (idealmente
preparando la comida), no un slideshow de fotos estáticas. Se evaluaron dos
caminos: (a) banco de video con licencia libre (Pexels — gratis, uso
comercial permitido, sin atribución requerida), o (b) IA imagen-a-video
(Runway/Luma/Kling) para animar las imágenes de marca ya generadas. El
usuario eligió (a). **Importante, ya evaluado y descartado antes**: nunca
se construye un scraper de contenido de terceros (TikTok/Instagram/etc.)
para "reutilizarlo como propio" — viola términos de servicio y derechos de
autor; Pexels es distinto porque su licencia permite explícitamente este
uso.

- **`app/video/stock_footage.py`** (nuevo, mismo patrón Protocol+Mock+flag):
  `MockStockVideoProvider` sintetiza un clip real con movimiento (patrón
  `testsrc2` de ffmpeg, que anima cada frame) vía el binario de ffmpeg
  embebido — offline, determinista, pero bytes de video reales para que los
  tests ejerciten el recorte/concat real. `PexelsVideoProvider` llama a
  `GET https://api.pexels.com/videos/search` (una escena = una búsqueda,
  usando el texto de la escena como query) y descarga el archivo mp4 de
  mejor resolución cercana a 720p-1080p del primer resultado.
- **Gateado por dos factores**: `AI_VIDEO_SCENE_SOURCE=STOCK_FOOTAGE` (vs.
  `IMAGES`, el default — el slideshow de imágenes de marca original) +
  presencia de `PEXELS_API_KEY` (sin la key, cae a `MockStockVideoProvider`
  aunque el flag esté en `STOCK_FOOTAGE`, así nunca rompe en un entorno sin
  la key configurada). **Ya activado en `apps/api/.env`
  (`AI_VIDEO_SCENE_SOURCE=STOCK_FOOTAGE`) — pendiente que el usuario
  consiga y comparta una `PEXELS_API_KEY` gratuita
  (https://www.pexels.com/api/) para que los clips sean reales en vez del
  video sintético de prueba.**
- **`app/video/assembler.py::assemble_from_clips`** (nuevo, junto al
  `assemble_slideshow` original que sigue usándose para el modo `IMAGES`):
  cada clip se normaliza por separado (loop si es más corto que su porción
  de tiempo asignada, `scale`+`crop` para llenar el cuadro sin barras
  negras — a diferencia del slideshow, aquí SÍ se recorta en vez de hacer
  letterbox, porque son clips reales, no flyers con texto que no se puede
  cortar), se le quita el audio original, y se concatenan con el demuxer
  `concat` de ffmpeg (mismos parámetros de codec en cada segmento, así que
  el concat es `-c copy`, sin recodificar dos veces) antes de mezclar la
  narración como única pista de audio.
- **`app/ai/runner.py::_run_video_generation`** ahora ramifica en
  `use_stock_footage = settings.ai_video_scene_source == "STOCK_FOOTAGE"`
  después de generar la narración: si es `STOCK_FOOTAGE`, busca un clip por
  escena en paralelo (`asyncio.gather`, mismo motivo de concurrencia que las
  imágenes) y llama a `assemble_from_clips`; si no, sigue el camino original
  de `IMAGE_ASSET` (imágenes de marca + logo compuesto) y
  `assemble_slideshow`. El costo estimado del job solo suma el costo de
  imágenes (`_IMAGE_COST_USD × escenas`) cuando NO se usa stock footage —
  Pexels es gratis, no tiene costo que sumar.
- Verificado de punta a punta con el pipeline real completo (guion real de
  Claude, `MockStockVideoProvider` en vez de Pexels por no tener la key
  aún, narración real de OpenAI TTS, ensamblado real con ffmpeg): job
  `COMPLETED` en ~30s, video real subido como `Asset`.
- Tests: `tests/test_video_generation.py::test_video_job_stock_footage_source_completes`
  (usa `monkeypatch.setattr(settings, "ai_video_scene_source", ...)`, mismo
  patrón que otros tests que necesitan forzar un flag de settings — ver
  `test_assets.py`).

## Respaldo gratuito para imagen/voz (Pollinations + ElevenLabs) — 2026-07-25

El usuario preguntó qué pasa cuando se agota el crédito de OpenAI en medio de
una campaña — pidió un respaldo automático y gratuito en vez de que el job
falle. Se agregó un patrón de **fallback en cadena** (primario → gratis) para
imagen y voz, mismo patrón Protocol+Mock+flag del resto del proyecto, nunca
se activa solo con la key.

- **`app/ai/image_providers.py`**: nuevo `PollinationsImageProvider` — sin
  cuenta, sin key, `GET https://image.pollinations.ai/prompt/{prompt}`
  (Stable-Diffusion-based). Nuevo `FallbackImageProvider(primary, fallback)`:
  reintenta contra el fallback solo en `ImageProviderRateLimited`/
  `ImageProviderError` (cuota agotada, caída del proveedor) — **no** en
  timeout, porque el fallback probablemente también daría timeout y duplicar
  la espera dentro de una petición HTTP síncrona es peor que fallar rápido.
  Nueva función `resolve_image_provider()` (usada por el runner en vez de
  `get_image_provider()` directo): envuelve el primario
  (`AI_IMAGE_PROVIDER`) con el fallback (`AI_IMAGE_FALLBACK_PROVIDER`) solo
  si este último está configurado y es distinto del primario.
- **`app/ai/tts_providers.py`**: mismo patrón — `ElevenLabsTTSProvider`
  (`POST /v1/text-to-speech/{voice_id}`, plan gratis 10k caracteres/mes,
  requiere `ELEVENLABS_API_KEY`), `FallbackTTSProvider`,
  `resolve_tts_provider()`.
- **`app/ai/runner.py`**: `_run_video_generation` y `_run_image_generation`
  (para el caso `OPENAI`) ahora llaman a `resolve_image_provider()`/
  `resolve_tts_provider()` en vez de `get_image_provider(settings...)`
  directo, así el fallback aplica en todos los flujos que generan con
  OpenAI, no solo video.
- **Nuevos settings** (`app/core/config.py`): `AI_IMAGE_FALLBACK_PROVIDER`
  (vacío por defecto), `AI_TTS_FALLBACK_PROVIDER` (vacío por defecto),
  `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` (default `21m00Tcm4TlvDq8ikWAM`,
  voz "Rachel" de ElevenLabs).
- **Ya activado en `apps/api/.env`**: `AI_IMAGE_FALLBACK_PROVIDER=POLLINATIONS`
  y `AI_TTS_FALLBACK_PROVIDER=ELEVENLABS` — **ambos probados con llamadas
  reales fuera del pipeline** (curl directo, no solo mocks): Pollinations
  devolvió un JPEG real 627x940 sin key; ElevenLabs devolvió un MP3 real de
  ~60KB con la key del usuario.
- **Gotcha de ElevenLabs plan gratis, ya resuelto**: la voz por defecto que
  usa el código (`ELEVENLABS_VOICE_ID` default `21m00Tcm4TlvDq8ikWAM`,
  "Rachel") da `402 payment_required` en el plan gratis — las voces
  premade de la librería no son usables vía API en free tier, solo voces
  propias de la cuenta. Se sobreescribió `ELEVENLABS_VOICE_ID` en `.env` a
  `CwhRBWXzGAHq8TQ4Fs17` ("Roger"), que sí está en la colección de voces de
  esta cuenta. Además, la API key nueva traía su propia cuota de créditos
  en 0 (`401 quota_exceeded`) independiente del límite mensual del plan
  (10k caracteres) — el usuario la subió desde el dashboard de ElevenLabs
  (Profile → API Keys) y la llamada real funcionó después.
- **Gotcha de conftest encontrado de paso**: los tests fallaban
  (`test_create_video_job_completes_and_creates_video_asset`) porque
  `apps/api/.env` ahora trae `AI_TTS_PROVIDER=OPENAI` y
  `AI_VIDEO_SCENE_SOURCE=STOCK_FOOTAGE` reales, pero `conftest.py` solo
  forzaba `AI_PROVIDER`/`AI_IMAGE_PROVIDER` a `MOCK` — el proveedor TTS real
  se activaba en tests con `OPENAI_API_KEY` vaciado y fallaba. Se agregó
  `AI_TTS_PROVIDER=MOCK`, `AI_VIDEO_SCENE_SOURCE=IMAGES` y
  `PEXELS_API_KEY=""` al bloque de overrides de `conftest.py` — **si se
  agrega un flag nuevo de proveedor real a `.env` en el futuro, hay que
  revisar este bloque también** para que no se cuele en los tests.
- Tests: `tests/test_free_fallback_providers.py` (7 tests, `httpx.MockTransport`
  para Pollinations/ElevenLabs, nunca llama a un proveedor real; cubre éxito,
  error de proveedor, y que el fallback se dispare en rate-limit/error pero
  no en timeout).

## Deploy a Vercel + Railway sin dominio propio — 2026-07-26

El usuario quiere producción ya, sin comprar dominio todavía: Vercel para
`apps/web`, un backend (Railway) para `apps/api`. El obstáculo real no es de
cuentas/infra sino de arquitectura: la sesión usa cookies HttpOnly
(`app/cookies.py`) y, sin dominio compartido, Vercel y Railway quedan en
orígenes distintos — con `COOKIE_SAMESITE=lax` (default) el navegador no
manda la cookie de sesión en las llamadas cross-site del frontend a la API,
así que el login se rompería en producción sin que el código tenga ningún
bug.

- **Solución implementada, sin dominio ni cambiar `SameSite`**: proxy
  transparente en `apps/web/next.config.mjs` (`rewrites()`) que reenvía
  `/api/v1/*` hacia `API_PROXY_TARGET` (la URL real de Railway). El
  navegador solo le habla a su propio origen (`*.vercel.app`); el salto a
  Railway ocurre servidor-a-servidor dentro de la infraestructura de
  Vercel, invisible para el navegador — por eso la cookie que pone la API
  llega marcada same-site sin necesitar `COOKIE_DOMAIN` ni tocar
  `CORS_ORIGINS` para el dominio de Vercel. `rewrites()` es un no-op
  (`return []`) si `API_PROXY_TARGET` no está seteado, así que no afecta
  local dev.
- **`apps/web/lib/api.ts`**: `API_URL` pasó de `|| "http://localhost:8000"`
  a `|| ""` — string vacío = rutas relativas (`/api/v1/...`), que es lo
  que necesita el proxy para funcionar. Local dev no se ve afectado porque
  `.env.local`/`.env.example` siempre setean `NEXT_PUBLIC_API_URL`
  explícito ahí. Verificado en el navegador: dashboard local cargó igual
  que antes, todas las llamadas siguieron yendo directo a
  `localhost:8010` (sin proxy, como se espera en dev).
- **Variables nuevas a configurar en el deploy** (documentado en
  `infra/scripts/README.md`, sección "Opción B"): en Vercel, seteá
  `API_PROXY_TARGET=https://<tu-servicio>.up.railway.app` y **no** setees
  `NEXT_PUBLIC_API_URL` (dejarla vacía es lo que activa el proxy). En
  Railway, las mismas variables de `.env.production.example` de siempre.
- **Si en el futuro se compra un dominio propio**, este proxy deja de ser
  necesario (se puede volver a `NEXT_PUBLIC_API_URL` directo +
  `COOKIE_DOMAIN=.tudominio.com`), pero no hay apuro — el proxy no tiene
  costo ni penalidad de mantenimiento, es solo una función de config.

## Producción real desplegada — 2026-07-28

RQT21 Growth OS quedó desplegado de punta a punta y verificado con login real:

- **Repo usado para el deploy:** `arosadoclud/rqt21-growth-os` (mirror privado
  del repo principal `andyRS/rqt21-growth-os` — la cuenta de Railway/Vercel
  del usuario está en `arosadoclud`, no en `andyRS`). Los dos remotos se
  mantienen sincronizados a mano: `git push origin main` (andyRS) +
  `git push arosadoclud main:main`, alternando la cuenta activa de `gh`
  (`gh auth switch --user <cuenta>`) antes de cada push porque el credential
  helper de git delega en la cuenta activa de `gh` (`gh auth setup-git`).
- **Frontend:** Vercel, proyecto conectado a `arosadoclud/rqt21-growth-os`,
  Root Directory `apps/web`, variable `API_PROXY_TARGET` apuntando a la URL
  de Railway (sin `NEXT_PUBLIC_API_URL`, activando el proxy documentado
  arriba). URL: `https://rqt21-growth-os-web.vercel.app`.
- **Backend:** Railway, proyecto `zealous-simplicity`, servicio `web`
  (nombre heredado del auto-detect inicial de Railway al conectar el repo —
  Railway asumió que era el frontend `apps/web` porque lo encontró antes
  que el Dockerfile de la API; quedó así, es solo un label, no afecta
  nada). Root Directory `/`, Dockerfile Path `/infra/Dockerfile.api`.
  **Gotchas reales encontrados y resueltos en este deploy:**
  - Railway escanea `pnpm-lock.yaml` del repo completo por vulnerabilidades
    conocidas antes de dejar buildear *cualquier* servicio, sin importar
    qué Dockerfile use ese servicio — bloqueó el primer build por
    `next@14.2.15` (CVE-2025-55184, CVE-2025-67779). Se resolvió subiendo
    `next` a `14.2.35` en el repo (commit `584e0d5`), no hay forma de
    bypassear el scanner desde la config de Railway.
  - Los campos "Custom Build Command" (`pnpm --filter web build`) y
    "Custom Start Command" (`pnpm --filter web start`) quedaron pegados
    del auto-detect inicial como proyecto Node — hay que vaciarlos los
    dos a mano (Settings → Build / Settings → Deploy) para que Railway
    use el Dockerfile tal cual en vez de pisarlo.
  - Networking → Public Networking traía el puerto por defecto en 8080;
    el Dockerfile expone 8000 fijo (no usa `$PORT`) — hay que editarlo a
    mano a 8000, si no da "Application failed to respond" aunque el
    deployment diga "Active".
  - `DATABASE_URL` que expone el plugin Postgres de Railway viene con
    esquema `postgresql://` (driver `psycopg2`, no instalado — el
    proyecto usa `psycopg` v3). Se reconstruyó a mano en las variables del
    servicio `web` como
    `postgresql+psycopg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}`
    usando las variables individuales del plugin en vez de
    `${{Postgres.DATABASE_URL}}` directo.
  - `app/main.py::_validate_production()` se niega a arrancar en
    `ENVIRONMENT=production` sin `STORAGE_PROVIDER` real (S3/R2) — es a
    propósito (ver Fase 6A), así que hubo que armar R2 antes de poder
    levantar el servicio en producción de verdad (ver punto siguiente).
- **Storage real (R2)**: bucket `rqt21-production-assets` en Cloudflare R2,
  token de API scopeado solo a ese bucket (Object Read & Write). Ya
  configurado en Railway (`STORAGE_PROVIDER=R2` + endpoint/keys) — el
  bloqueante de Fase 6B para publicar en Instagram con imagen real ya no
  aplica en producción.
- **Migraciones**: no corren solas al arrancar (nunca lo hicieron, ver
  Fase 6A). Se corrieron a mano desde la máquina local apuntando al proxy
  público de Postgres de Railway (`DATABASE_URL` con host
  `tokaido.proxy.rlwy.net:<puerto>` en vez del host interno
  `postgres.railway.internal`, que no es alcanzable desde fuera de la red
  de Railway) — `uv run alembic upgrade head` desde `apps/api`.
- **Primer usuario OWNER real**: la organización `rqt21` y el usuario
  OWNER (`andyrosadoars@gmail.com`) se crearon con un script mínimo
  ad-hoc que reusa `_get_or_create_org`/`_get_or_create_owner` de
  `app/seed.py` **sin correr el resto del seed de demo** (`seed()` trae
  datos ficticios completos — marcas, campañas, leads — pensados solo
  para desarrollo; nunca se corre en producción, ver nota existente en
  este archivo). No existe endpoint de auto-registro (`/auth` solo tiene
  login/refresh/logout, `POST /organizations` requiere ya estar
  autenticado) — si hace falta crear otra organización/owner en el
  futuro sin acceso a shell de producción, habría que agregar un endpoint
  de bootstrap protegido, no existe todavía.
- **CLI de Railway**: instalada (`npm install -g @railway/cli`), logueada
  como `arosado.blandino@gmail.com`, proyecto vinculado
  (`railway link --project zealous-simplicity`, `--service web` para
  targetear el servicio de la API). Usada para setear variables de entorno
  en batch (`railway variables --service web --set K=V ... --skip-deploys`)
  y disparar redeploys (`railway redeploy --service web --yes`) sin pasar
  por el dashboard.
- **Verificado real de punta a punta**: `POST /api/v1/auth/login` contra
  `https://rqt21-growth-os-web.vercel.app/api/v1/auth/login` (el dominio
  de Vercel, no el de Railway directo) devolvió `200 OK` con
  `Set-Cookie: rqt_access/rqt_refresh/rqt_csrf` con `SameSite=lax` +
  `Secure` sin `Domain` explícito — confirma que el proxy same-origin
  funciona como se diseñó, sin necesitar dominio propio.
- **Gotcha real de Vercel plan Hobby + repo privado**: Vercel bloqueó los
  primeros deploys automáticos disparados por push a
  `arosadoclud/rqt21-growth-os` con
  *"The deployment was blocked because the commit author did not have
  contributing access to the project on Vercel. The Hobby Plan does not
  support collaboration for private repositories."* — esto pasó aunque el
  autor del commit (`andyRS`, vía el email `andy337@hotmail.es`) ya fuera
  colaborador con permiso `push` en el repo de GitHub. Agregar el
  colaborador en GitHub **no alcanza**: en plan Hobby, un repo privado
  solo acepta deploys automáticos de commits cuyo autor coincide con el
  email verificado de la propia cuenta de Vercel (`arosadoclud`,
  `arosado.blandino@gmail.com`) — es una restricción de Vercel, no de
  GitHub. Se resolvió seteando `git config user.email
  arosado.blandino@gmail.com` **local al repo** (no `--global`, no toca
  la config general de la máquina) antes de comitear cualquier cambio que
  se vaya a pushear a `arosadoclud`. Alternativas si esto vuelve a
  trabar: hacer público el repo mirror, o subir a Vercel Pro ($20/mes).
- **CLI de Vercel**: instalada (`npm install -g vercel`), logueada como
  `arosadoclud`. **Gotcha propio, ya resuelto**: `vercel link` corrido
  desde dentro de `apps/web` sin especificar `--project` creó por error
  un proyecto nuevo vacío llamado `web` (duplicado, distinto del real
  `rqt21-growth-os-web`) — se borró con `vercel remove web --yes`. El
  comando correcto es `vercel link --yes --project rqt21-growth-os-web`.
  Además, como el proyecto tiene Root Directory=`apps/web` configurado en
  el dashboard, correr `vercel --prod` estando parado *dentro* de
  `apps/web` duplica la ruta (busca `apps/web/apps/web`, no existe) — hay
  que correrlo desde la raíz del repo con `--cwd`, o mover el `.vercel/`
  vinculado a la raíz.
