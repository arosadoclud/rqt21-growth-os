import { test, expect } from "./fixtures";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8100";

test.describe.configure({ mode: "serial" });

async function login(page: import("@playwright/test").Page, email: string, password: string) {
  const response = await page.request.post(`${API_URL}/api/v1/auth/login`, {
    data: { email, password },
    headers: { "content-type": "application/json" },
  });
  expect(response.ok()).toBe(true);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("full growth flow: brand → product → campaign → content → link → click → dashboard", async ({
  page,
  seeded,
  request,
}) => {
  await login(page, seeded.owner.email, seeded.owner.password);

  const tag = Math.random().toString(36).slice(2, 8);

  // 1) Create brand
  await page.goto("/brands");
  await page.getByRole("button", { name: "Nueva marca" }).click();
  const brandDialog = page.getByRole("dialog", { name: "Nueva marca" });
  await brandDialog.getByLabel("Nombre").fill(`Brand ${tag}`);
  await brandDialog.getByLabel("Slug").fill(`brand-${tag}`);
  await brandDialog.getByRole("button", { name: "Crear marca" }).click();
  await expect(page.getByText(`brand-${tag}`).first()).toBeVisible();

  // 2) Create product
  await page.goto("/products");
  await page.getByRole("button", { name: "Nuevo producto" }).click();
  const productDialog = page.getByRole("dialog", { name: "Nuevo producto" });
  await productDialog.getByLabel("Nombre").fill(`Prod ${tag}`);
  await productDialog.getByLabel("Slug").fill(`prod-${tag}`);
  await productDialog
    .getByLabel("URL de checkout")
    .fill("https://checkout.example.com/prod");
  await productDialog.getByRole("button", { name: "Crear producto" }).click();
  await expect(page.getByText(`Prod ${tag}`).first()).toBeVisible();

  // 3) Create campaign
  await page.goto("/campaigns");
  await page.getByRole("button", { name: "Nueva campaña" }).click();
  const campaignDialog = page.getByRole("dialog", { name: "Nueva campaña" });
  await campaignDialog.getByLabel("Nombre").fill(`Camp ${tag}`);
  await campaignDialog.getByLabel("Slug").fill(`camp-${tag}`);
  await campaignDialog.getByRole("button", { name: "Crear campaña" }).click();
  await expect(page.getByText(`Camp ${tag}`).first()).toBeVisible();

  // 4) Create content
  await page.goto("/content");
  await page.getByRole("button", { name: "Nuevo contenido" }).click();
  const contentDialog = page.getByRole("dialog", { name: "Nuevo contenido" });
  await contentDialog.getByLabel("Título").fill(`Reel ${tag}`);
  await contentDialog.getByRole("button", { name: "Crear contenido" }).click();
  await expect(page.getByText(`Reel ${tag}`).first()).toBeVisible();

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

  await login(page, salesEmail, salesPassword);

  // Switch active org to the owner's org so we're inside a valid tenant.
  await page.evaluate((id) => {
    window.localStorage.setItem("rqt21.currentOrgId", id);
  }, seeded.ownerOrg.id);
  await page.goto("/brands");
  await expect(
    page.getByText("Tu rol puede consultar las marcas, pero no crearlas ni modificarlas."),
  ).toBeVisible();
});
