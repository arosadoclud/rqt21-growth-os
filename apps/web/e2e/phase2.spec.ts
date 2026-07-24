import { test, expect } from "./fixtures";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8100";

test.describe.configure({ mode: "serial" });

test("full growth flow: brand → product → campaign → content → link → click → dashboard", async ({
  page,
  seeded,
  request,
}) => {
  // Log in via UI so the SPA takes over from there.
  await page.goto("/login");
  await page.getByLabel("Correo").fill(seeded.owner.email);
  await page.getByLabel("Contraseña").fill(seeded.owner.password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  const tag = Math.random().toString(36).slice(2, 8);

  // 1) Create brand
  await page.goto("/brands");
  await page.getByLabel("Nombre").fill(`Brand ${tag}`);
  await page.getByLabel("Slug").fill(`brand-${tag}`);
  await page.getByRole("button", { name: "Crear marca" }).click();
  await expect(page.getByText(`brand-${tag}`)).toBeVisible();

  // 2) Create product
  await page.goto("/products");
  await page.getByLabel("Nombre").fill(`Prod ${tag}`);
  await page.getByLabel("Slug").fill(`prod-${tag}`);
  await page
    .getByLabel("Checkout URL")
    .fill("https://checkout.example.com/prod");
  await page.getByRole("button", { name: "Crear producto" }).click();
  await expect(page.getByText(`Prod ${tag}`)).toBeVisible();

  // 3) Create campaign
  await page.goto("/campaigns");
  await page.getByLabel("Nombre").fill(`Camp ${tag}`);
  await page.getByLabel("Slug").fill(`camp-${tag}`);
  await page.getByRole("button", { name: "Crear campaña" }).click();
  await expect(page.getByText(`Camp ${tag}`)).toBeVisible();

  // 4) Create content
  await page.goto("/content");
  await page.getByLabel("Título").fill(`Reel ${tag}`);
  await page.getByRole("button", { name: "Crear contenido" }).click();
  await expect(page.getByText(`Reel ${tag}`)).toBeVisible();

  // 5) Create tracking link — wait for the API response so we can assert the
  // exact short_code returned rather than racing the DOM refresh.
  await page.goto("/tracking-links");
  const createLinkResponse = page.waitForResponse(
    (r) =>
      r.url().includes("/api/v1/tracking-links") &&
      r.request().method() === "POST",
  );
  await page
    .getByLabel("URL destino")
    .fill("https://checkout.example.com/prod?ref=e2e");
  await page.getByLabel("utm_source").fill("instagram");
  await page.getByLabel("utm_campaign").fill(`camp-${tag}`);
  await page.getByRole("button", { name: "Generar enlace" }).click();
  const createdLink = await (await createLinkResponse).json();
  expect(createdLink.utm_source).toBe("instagram");
  const shortCode = createdLink.short_code as string;
  expect(shortCode.length).toBeGreaterThan(4);

  // 6) Hit the redirect endpoint directly to record a click.
  const redir = await request.get(`${API_URL}/r/${shortCode}`, {
    maxRedirects: 0,
  });
  expect(redir.status()).toBe(307);
  const loc = redir.headers()["location"];
  expect(loc).toContain("utm_source=instagram");
  expect(loc).toContain("checkout.example.com/prod");

  // 7) Dashboard reflects the click — wait for the summary API to return
  // and confirm the response includes at least our click.
  const dashResponse = page.waitForResponse(
    (r) =>
      r.url().includes("/api/v1/analytics/dashboard/summary") &&
      r.request().method() === "GET",
  );
  await page.goto("/dashboard");
  const dash = await (await dashResponse).json();
  expect(dash.clicks_total).toBeGreaterThan(0);
  await expect(page.getByText("Clics totales")).toBeVisible();
});

test("SALES user cannot create a brand from the UI", async ({ page, seeded, request }) => {
  // Add "other" (an ADMIN seeded by fixtures) as SALES to the owner's org.
  // Easier: log in as owner, add a fresh sales user to their org via API.
  const owner = seeded.owner;
  const loginR = await request.post(`${API_URL}/api/v1/auth/login`, {
    data: { email: owner.email, password: owner.password },
    headers: { "content-type": "application/json" },
  });
  expect(loginR.status()).toBe(200);
  const cookies = (await request.storageState()).cookies;
  const csrf = cookies.find((c) => c.name === "rqt_csrf")?.value ?? "";

  const salesEmail = `sales-${Math.random().toString(36).slice(2, 8)}@example.com`;
  const salesPassword = "Password1!Sales";
  const addMember = await request.post(
    `${API_URL}/api/v1/organizations/${seeded.ownerOrg.id}/members`,
    {
      data: {
        email: salesEmail,
        full_name: "Sales E2E",
        password: salesPassword,
        role: "SALES",
      },
      headers: {
        "content-type": "application/json",
        "x-csrf-token": csrf,
        "x-organization-id": seeded.ownerOrg.id,
      },
    },
  );
  expect(addMember.status()).toBe(201);
  await request.post(`${API_URL}/api/v1/auth/logout`, {});

  // Log in as SALES in the browser.
  await page.goto("/login");
  await page.getByLabel("Correo").fill(salesEmail);
  await page.getByLabel("Contraseña").fill(salesPassword);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // Switch active org to the owner's org so we're inside a valid tenant.
  await page.evaluate((id) => {
    window.localStorage.setItem("rqt21.currentOrgId", id);
  }, seeded.ownerOrg.id);
  await page.goto("/brands");
  await expect(
    page.getByText("Tu rol no permite crear marcas."),
  ).toBeVisible();
});
