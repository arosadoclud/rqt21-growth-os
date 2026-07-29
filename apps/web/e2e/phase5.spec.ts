import { execFileSync } from "node:child_process";
import path from "node:path";
import { test, expect } from "./fixtures";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8100";

test.describe.configure({ mode: "serial", timeout: 60_000 });

const TINY_PNG = Buffer.from(
  "89504e470d0a1a0a" + "00".repeat(200),
  "hex",
);

async function csrf(request: import("@playwright/test").APIRequestContext) {
  const cookies = (await request.storageState()).cookies;
  return cookies.find((c) => c.name === "rqt_csrf")?.value ?? "";
}

async function addMember(
  request: import("@playwright/test").APIRequestContext,
  orgId: string,
  token: string,
  email: string,
  password: string,
  role: string,
) {
  const r = await request.post(`${API_URL}/api/v1/organizations/${orgId}/members`, {
    data: { email, full_name: email.split("@")[0], password, role },
    headers: {
      "content-type": "application/json",
      "x-csrf-token": token,
      "x-organization-id": orgId,
    },
  });
  expect(r.status(), `add member ${email} as ${role}`).toBe(201);
}

async function loginUI(page: import("@playwright/test").Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill(password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 10_000 });
}

async function csrfFromPage(page: import("@playwright/test").Page) {
  const cookies = await page.context().cookies();
  return cookies.find((c) => c.name === "rqt_csrf")?.value ?? "";
}

async function setOrg(page: import("@playwright/test").Page, orgId: string) {
  await page.evaluate((id) => {
    window.localStorage.setItem("rqt21.currentOrgId", id);
  }, orgId);
}

async function apiJson(
  request: import("@playwright/test").APIRequestContext,
  method: "GET" | "POST" | "PATCH",
  path: string,
  orgId: string,
  token: string,
  data?: unknown,
) {
  const r = await request.fetch(`${API_URL}${path}`, {
    method,
    data,
    headers: {
      "content-type": "application/json",
      "x-csrf-token": token,
      "x-organization-id": orgId,
    },
  });
  return r;
}

/** Runs the one-shot publish_due worker against the same DB the e2e API
 * instance is using. Mirrors apps/api/e2e/README.md's local setup. */
function runWorker() {
  const apiRoot = path.resolve(__dirname, "../../api");
  const dbUrl =
    process.env.TEST_DATABASE_URL ||
    "postgresql+psycopg://rqt:rqt@localhost:5433/rqt_test";
  execFileSync("uv", ["run", "python", "-m", "app.workers.publish_due"], {
    cwd: apiRoot,
    env: { ...process.env, DATABASE_URL: dbUrl },
    stdio: "pipe",
  });
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function apiUploadReadyAsset(
  request: import("@playwright/test").APIRequestContext,
  orgId: string,
  token: string,
  brandId: string,
  filename: string,
) {
  const initRes = await apiJson(request, "POST", "/api/v1/assets/init-upload", orgId, token, {
    filename,
    mime_type: "image/png",
    size_bytes: TINY_PNG.length,
    asset_type: "IMAGE",
    brand_id: brandId,
    alt_text: "Activo de prueba E2E",
  });
  expect(initRes.status()).toBe(201);
  const init = await initRes.json();
  const completeRes = await apiJson(request, "POST", "/api/v1/assets/complete-upload", orgId, token, {
    asset_id: init.asset_id,
    content_base64: TINY_PNG.toString("base64"),
  });
  expect(completeRes.status()).toBe(200);
  return completeRes.json();
}

async function ownerSetup(request: import("@playwright/test").APIRequestContext, orgId: string, token: string) {
  const brandRes = await apiJson(request, "POST", "/api/v1/brands", orgId, token, {
    name: `E2E5 Brand ${Date.now()}`,
    slug: `e2e5-brand-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
  });
  expect(brandRes.status()).toBe(201);
  const brand = await brandRes.json();

  const contentRes = await apiJson(request, "POST", "/api/v1/content-items", orgId, token, {
    brand_id: brand.id,
    title: `E2E5 Content ${Date.now()}`,
  });
  expect(contentRes.status()).toBe(201);
  const content = await contentRes.json();

  const approveRes = await apiJson(
    request,
    "POST",
    `/api/v1/content-items/${content.id}/approve`,
    orgId,
    token,
    { score: 90 },
  );
  expect(approveRes.status()).toBe(201);

  return { brand, content };
}

test("Flow 1: manual publication end to end (MARKETER)", async ({ page, seeded, request, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await request.post(`${API_URL}/api/v1/auth/login`, {
    data: { email: seeded.owner.email, password: seeded.owner.password },
    headers: { "content-type": "application/json" },
  });
  const ownerToken = await csrf(request);
  const orgId = seeded.ownerOrg.id;

  const mktEmail = `mkt5-${Date.now()}@example.com`;
  const mktPassword = "Password1!Marketer";
  await addMember(request, orgId, ownerToken, mktEmail, mktPassword, "MARKETER");

  const { brand, content } = await ownerSetup(request, orgId, ownerToken);

  const connRes = await apiJson(request, "POST", "/api/v1/publishing-connections", orgId, ownerToken, {
    brand_id: brand.id,
    platform: "INSTAGRAM",
    provider: "MANUAL",
    account_name: "Equipo social E2E",
  });
  expect(connRes.status()).toBe(201);
  const connection = await connRes.json();

  await request.post(`${API_URL}/api/v1/auth/logout`, {});

  await loginUI(page, mktEmail, mktPassword);
  await setOrg(page, orgId);

  // Upload a READY asset via the UI.
  await page.goto("/assets");
  await expect(page.getByRole("heading", { name: "Biblioteca de activos" })).toBeVisible();
  const uploadForm = page.locator("form", { hasText: "Subir activo" });
  await uploadForm.getByLabel("Marca").selectOption({ label: brand.name });
  await uploadForm.getByLabel("Archivo").setInputFiles({
    name: "lasagna.png",
    mimeType: "image/png",
    buffer: TINY_PNG,
  });
  await uploadForm.getByLabel(/Texto alternativo/).fill("Lasaña keto servida en mesa");
  const uploadResp = page.waitForResponse(
    (r) => r.url().includes("/complete-upload") && r.request().method() === "POST",
  );
  await uploadForm.getByRole("button", { name: "Subir" }).click();
  const uploadedAsset = await (await uploadResp).json();
  expect(uploadedAsset.status).toBe("READY");

  // Prepare an Instagram publication using the approved content + MANUAL connection.
  await page.goto("/publishing");
  await expect(page.getByRole("heading", { name: "Publicaciones" })).toBeVisible();
  const pubForm = page.locator("form", { hasText: "Preparar publicación" });
  await pubForm.getByLabel("Marca").selectOption({ label: brand.name });
  await pubForm.getByLabel("Contenido aprobado").selectOption({ label: content.title });
  await pubForm.getByLabel("Conexión").selectOption(connection.id);
  await pubForm.getByLabel("Activo (READY)").selectOption({ label: "lasagna.png" });
  await pubForm.getByLabel("Caption").fill("Pequeños cambios, resultados sostenibles.");
  const createPubResp = page.waitForResponse(
    (r) => r.url().endsWith("/api/v1/publications") && r.request().method() === "POST",
  );
  await pubForm.getByRole("button", { name: "Crear borrador" }).click();
  const pub = await (await createPubResp).json();
  expect(pub.status).toBe("DRAFT");

  await page.goto(`/publishing/${pub.id}`);
  await expect(page.getByRole("heading", { name: /INSTAGRAM/ })).toBeVisible();

  const validateResp = page.waitForResponse(
    (r) => r.url().includes("/validate") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Validar" }).click();
  const validation = await (await validateResp).json();
  expect(validation.ok).toBe(true);

  await page.getByRole("button", { name: "Copiar caption" }).click();

  const markResp = page.waitForResponse(
    (r) => r.url().includes("/mark-published") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Marcar publicado manualmente" }).click();
  await page
    .getByLabel("URL de la publicación externa")
    .fill("https://instagram.com/p/e2e5-manual");
  await page.getByRole("button", { name: "Confirmar publicación manual" }).click();
  const marked = await (await markResp).json();
  expect(marked.status).toBe("PUBLISHED");
  expect(marked.external_url).toBe("https://instagram.com/p/e2e5-manual");

  await expect(page.getByText("PUBLISHED")).toBeVisible();

  // Confirm it shows up as published on the dashboard summary.
  await page.goto("/dashboard");
  await expect(page.getByText("Producción asistida")).toBeVisible();
});

test("Flow 2: MOCK automatic publication via connection + scheduler worker (ADMIN)", async ({
  page,
  seeded,
  request,
}) => {
  await request.post(`${API_URL}/api/v1/auth/login`, {
    data: { email: seeded.owner.email, password: seeded.owner.password },
    headers: { "content-type": "application/json" },
  });
  const ownerToken = await csrf(request);
  const orgId = seeded.ownerOrg.id;

  const adminEmail = `admin5-${Date.now()}@example.com`;
  const adminPassword = "Password1!Admin";
  await addMember(request, orgId, ownerToken, adminEmail, adminPassword, "ADMIN");

  const { brand, content } = await ownerSetup(request, orgId, ownerToken);
  const asset = await apiUploadReadyAsset(request, orgId, ownerToken, brand.id, "auto-flow2.png");

  await request.post(`${API_URL}/api/v1/auth/logout`, {});
  await loginUI(page, adminEmail, adminPassword);
  await setOrg(page, orgId);

  // Create a MOCK connection through the UI.
  await page.goto("/publishing/connections");
  await expect(
    page.getByRole("heading", { name: "Cuentas de Facebook e Instagram" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Agregar cuenta" }).click();
  const connForm = page.getByRole("form", { name: "Agregar cuenta" });
  await connForm.getByLabel("Marca").selectOption({ label: brand.name });
  await connForm.getByLabel(/Nombre de la cuenta/).fill("rqt21.mock.e2e");
  const createConnResp = page.waitForResponse(
    (r) => r.url().includes("/publishing-connections") && r.request().method() === "POST",
  );
  await connForm.getByRole("button", { name: "Guardar cuenta" }).click();
  const connection = await (await createConnResp).json();
  expect(connection.status).toBe("ACTIVE");
  void asset;

  // Prepare and validate the publication.
  await page.goto("/publishing");
  const pubForm = page.locator("form", { hasText: "Preparar publicación" });
  await pubForm.getByLabel("Marca").selectOption({ label: brand.name });
  await pubForm.getByLabel("Contenido aprobado").selectOption({ label: content.title });
  await pubForm.getByLabel("Conexión").selectOption(connection.id);
  await pubForm.getByLabel("Activo (READY)").selectOption({ label: "auto-flow2.png" });
  await pubForm.getByLabel("Caption").fill("Publicación automática de prueba MOCK.");
  const createPubResp = page.waitForResponse(
    (r) => r.url().endsWith("/api/v1/publications") && r.request().method() === "POST",
  );
  await pubForm.getByRole("button", { name: "Crear borrador" }).click();
  const pub = await (await createPubResp).json();

  await page.goto(`/publishing/${pub.id}`);
  const validateResp = page.waitForResponse((r) => r.url().includes("/validate"));
  await page.getByRole("button", { name: "Validar" }).click();
  await validateResp;

  // Schedule it a few seconds in the future, then let the worker pick it up.
  const soonDate = new Date(Date.now() + 3000);
  const soonLocal = new Date(soonDate.getTime() - soonDate.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 19);
  const scheduleResp = page.waitForResponse(
    (r) => r.url().includes("/schedule") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Programar" }).click();
  await page.getByLabel("Fecha y hora").fill(soonLocal);
  await page.getByRole("button", { name: "Confirmar programación" }).click();
  const scheduled = await (await scheduleResp).json();
  expect(scheduled.status).toBe("SCHEDULED");

  await sleep(4000);
  runWorker();

  await page.reload();
  await expect(page.getByRole("heading", { name: /PUBLISHED/ })).toBeVisible({ timeout: 10_000 });

  await expect(page.getByText("SUCCEEDED")).toBeVisible();

  await page.goto("/notifications");
  await expect(page.getByText(/Publicación exitosa|Publication succeeded/i).first()).toBeVisible({
    timeout: 10_000,
  });
});

test("Flow 3: rate-limit sentinel triggers retry, succeeds after fix, attempts recorded", async ({
  page,
  seeded,
  request,
}) => {
  await request.post(`${API_URL}/api/v1/auth/login`, {
    data: { email: seeded.owner.email, password: seeded.owner.password },
    headers: { "content-type": "application/json" },
  });
  const ownerToken = await csrf(request);
  const orgId = seeded.ownerOrg.id;

  const { brand, content } = await ownerSetup(request, orgId, ownerToken);

  const connRes = await apiJson(request, "POST", "/api/v1/publishing-connections", orgId, ownerToken, {
    brand_id: brand.id,
    platform: "INSTAGRAM",
    provider: "MOCK",
    account_name: "rqt21.mock.retry",
  });
  const connection = await connRes.json();
  const asset = await apiUploadReadyAsset(request, orgId, ownerToken, brand.id, "retry-flow3.png");

  const pubRes = await apiJson(request, "POST", "/api/v1/publications", orgId, ownerToken, {
    content_item_id: content.id,
    brand_id: brand.id,
    publishing_connection_id: connection.id,
    asset_id: asset.id,
    platform: "INSTAGRAM",
    publication_type: "POST",
    caption: "Aviso __mock_rate_limit__ de prueba.",
  });
  const pub = await pubRes.json();

  const validateRes = await apiJson(request, "POST", `/api/v1/publications/${pub.id}/validate`, orgId, ownerToken);
  const validation = await validateRes.json();
  expect(validation.ok).toBe(true);

  await request.post(`${API_URL}/api/v1/auth/logout`, {});
  await loginUI(page, seeded.owner.email, seeded.owner.password);
  await setOrg(page, orgId);
  const pageToken = await csrfFromPage(page);

  await page.goto(`/publishing/${pub.id}`);
  const publishResp = page.waitForResponse(
    (r) => r.url().includes("/publish") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Publicar ahora (automático)" }).click();
  const afterFirst = await (await publishResp).json();
  expect(afterFirst.status).toBe("RETRY_SCHEDULED");
  await expect(page.getByRole("heading", { name: /RETRY_SCHEDULED/ })).toBeVisible();

  // Fix the underlying issue (remove the sentinel) before the retry fires —
  // mirrors a human correcting the caption after seeing the failure.
  const fixResp = await apiJson(
    page.request,
    "PATCH",
    `/api/v1/publications/${pub.id}`,
    orgId,
    pageToken,
    { caption: "Caption corregido, sin sentinel." },
  );
  expect(fixResp.status()).toBe(200);

  await sleep(6000);
  runWorker();

  await page.reload();
  await expect(page.getByRole("heading", { name: /PUBLISHED/ })).toBeVisible({ timeout: 10_000 });

  const attemptsRes = await apiJson(page.request, "GET", `/api/v1/publications/${pub.id}/attempts`, orgId, pageToken);
  const attempts = await attemptsRes.json();
  expect(attempts.length).toBeGreaterThanOrEqual(2);
  expect(attempts.some((a: { status: string }) => a.status === "RATE_LIMITED")).toBe(true);
  expect(attempts.some((a: { status: string }) => a.status === "SUCCEEDED")).toBe(true);
});

test("Flow 4: asset upload, alt text, and role-based security", async ({ page, seeded, request }) => {
  await request.post(`${API_URL}/api/v1/auth/login`, {
    data: { email: seeded.owner.email, password: seeded.owner.password },
    headers: { "content-type": "application/json" },
  });
  const ownerToken = await csrf(request);
  const orgId = seeded.ownerOrg.id;

  const mktEmail = `mkt5b-${Date.now()}@example.com`;
  const mktPassword = "Password1!Marketer";
  await addMember(request, orgId, ownerToken, mktEmail, mktPassword, "MARKETER");
  const analystEmail = `an5-${Date.now()}@example.com`;
  const analystPassword = "Password1!Analyst";
  await addMember(request, orgId, ownerToken, analystEmail, analystPassword, "ANALYST");
  const viewerEmail = `vw5-${Date.now()}@example.com`;
  const viewerPassword = "Password1!Viewer";
  await addMember(request, orgId, ownerToken, viewerEmail, viewerPassword, "VIEWER");

  const brandRes = await apiJson(request, "POST", "/api/v1/brands", orgId, ownerToken, {
    name: `E2E5 Sec Brand ${Date.now()}`,
    slug: `e2e5-sec-brand-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
  });
  const brand = await brandRes.json();

  await request.post(`${API_URL}/api/v1/auth/logout`, {});

  await loginUI(page, mktEmail, mktPassword);
  await setOrg(page, orgId);

  await page.goto("/assets");
  const uploadForm = page.locator("form", { hasText: "Subir activo" });
  await uploadForm.getByLabel("Marca").selectOption({ label: brand.name });
  await uploadForm.getByLabel("Archivo").setInputFiles({
    name: "security.png",
    mimeType: "image/png",
    buffer: TINY_PNG,
  });
  await uploadForm.getByLabel(/Texto alternativo/).fill("Foto de seguridad E2E");
  const uploadResp = page.waitForResponse(
    (r) => r.url().includes("/complete-upload") && r.request().method() === "POST",
  );
  await uploadForm.getByRole("button", { name: "Subir" }).click();
  const asset = await (await uploadResp).json();
  expect(asset.status).toBe("READY");

  await page.goto(`/assets/${asset.id}`);
  await expect(page.getByRole("heading", { name: "security.png" })).toBeVisible();
  await expect(page.getByText(/Foto de seguridad E2E/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Generar URL firmada" })).toBeVisible();

  await page.request.post(`${API_URL}/api/v1/auth/logout`, {});
  await page.evaluate(() => window.localStorage.clear());

  // ANALYST: sees the asset's metadata but never a signed/download URL.
  await loginUI(page, analystEmail, analystPassword);
  await setOrg(page, orgId);
  await page.goto(`/assets/${asset.id}`);
  await expect(page.getByRole("heading", { name: "security.png" })).toBeVisible();
  await expect(page.getByText(/Foto de seguridad E2E/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Generar URL firmada" })).toHaveCount(0);

  await page.request.post(`${API_URL}/api/v1/auth/logout`, {});
  await page.evaluate(() => window.localStorage.clear());

  // VIEWER: cannot administer connections.
  await loginUI(page, viewerEmail, viewerPassword);
  await setOrg(page, orgId);
  await page.goto("/publishing/connections");
  await expect(page.getByText(/no tiene acceso a las conexiones/i)).toBeVisible();

  await page.request.post(`${API_URL}/api/v1/auth/logout`, {});
  await page.evaluate(() => window.localStorage.clear());

  // Cross-org: a second, unrelated org must not be able to see this asset.
  await loginUI(page, seeded.other.email, seeded.other.password);
  await setOrg(page, seeded.otherOrg.id);
  await page.goto(`/assets/${asset.id}`);
  await expect(page.getByText("Activo no encontrado.")).toBeVisible();
});

test("Flow 5: automation creates a draft on content approval, never auto-publishes", async ({
  page,
  seeded,
  request,
}) => {
  await request.post(`${API_URL}/api/v1/auth/login`, {
    data: { email: seeded.owner.email, password: seeded.owner.password },
    headers: { "content-type": "application/json" },
  });
  const ownerToken = await csrf(request);
  const orgId = seeded.ownerOrg.id;

  const brandRes = await apiJson(request, "POST", "/api/v1/brands", orgId, ownerToken, {
    name: `E2E5 Auto Brand ${Date.now()}`,
    slug: `e2e5-auto-brand-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
  });
  const brand = await brandRes.json();

  const connRes = await apiJson(request, "POST", "/api/v1/publishing-connections", orgId, ownerToken, {
    brand_id: brand.id,
    platform: "INSTAGRAM",
    provider: "MOCK",
    account_name: "rqt21.mock.auto",
  });
  const connection = await connRes.json();

  await request.post(`${API_URL}/api/v1/auth/logout`, {});
  await loginUI(page, seeded.owner.email, seeded.owner.password);
  await setOrg(page, orgId);
  const pageToken = await csrfFromPage(page);

  await page.goto("/automations");
  await expect(page.getByRole("heading", { name: "Automatizaciones" })).toBeVisible();
  const autoForm = page.locator("form", { hasText: "Nueva automatización" });
  await autoForm.getByLabel("Plantilla").selectOption({
    label: "Contenido aprobado → crear borrador de publicación",
  });
  await autoForm.getByLabel("Nombre").fill(`E2E auto-draft ${Date.now()}`);
  await autoForm.getByLabel("Marca (opcional)").selectOption({ label: brand.name });
  await autoForm
    .getByLabel("Conexión de publicación destino")
    .selectOption(connection.id);
  const createRuleResp = page.waitForResponse(
    (r) => r.url().endsWith("/api/v1/automations") && r.request().method() === "POST",
  );
  await autoForm.getByRole("button", { name: "Crear automatización" }).click();
  const rule = await (await createRuleResp).json();
  expect(rule.is_active).toBe(true);

  const contentRes = await apiJson(page.request, "POST", "/api/v1/content-items", orgId, pageToken, {
    brand_id: brand.id,
    title: `E2E5 Auto Content ${Date.now()}`,
  });
  const content = await contentRes.json();

  await page.goto("/reviews");
  await page.getByRole("button", { name: new RegExp(content.title) }).click();
  const approveResp = page.waitForResponse(
    (r) => r.url().includes("/approve") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Aprobar" }).click();
  await approveResp;

  const pubListRes = await apiJson(
    page.request,
    "GET",
    `/api/v1/publications?content_item_id=${content.id}`,
    orgId,
    pageToken,
  );
  const pubs = await pubListRes.json();
  expect(pubs.length).toBe(1);
  expect(pubs[0].status).toBe("DRAFT");
  expect(pubs[0].published_at).toBeNull();

  await page.goto("/publishing");
  await expect(page.getByRole("link", { name: content.title })).toBeVisible();

  const ruleAfter = await apiJson(page.request, "GET", "/api/v1/automations", orgId, pageToken);
  const rules = await ruleAfter.json();
  const created = rules.find((r: { id: string }) => r.id === rule.id);
  expect(created.execution_count).toBeGreaterThanOrEqual(1);
});
