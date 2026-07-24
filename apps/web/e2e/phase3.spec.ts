import { test, expect } from "./fixtures";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8100";

test.describe.configure({ mode: "serial" });

async function apiLogin(request: import("@playwright/test").APIRequestContext, email: string, password: string) {
  const r = await request.post(`${API_URL}/api/v1/auth/login`, {
    data: { email, password },
    headers: { "content-type": "application/json" },
  });
  expect(r.status()).toBe(200);
}

async function csrf(request: import("@playwright/test").APIRequestContext) {
  const cookies = (await request.storageState()).cookies;
  return cookies.find((c) => c.name === "rqt_csrf")?.value ?? "";
}

test("full editorial → lead → funnel flow", async ({ page, seeded, request }) => {
  await apiLogin(request, seeded.owner.email, seeded.owner.password);
  const token = await csrf(request);

  // Look up the seed OWNER org (RQT21) — that's the one the SPA opens on
  // first login for this user, so all API prep must target it too.
  const orgList = await request.get(`${API_URL}/api/v1/organizations`);
  const orgs: Array<{ id: string; slug: string }> = await orgList.json();
  const seedOrg = orgs.find((o) => o.slug === "rqt21") || orgs[0];
  const targetOrg = seedOrg.id;

  // Prepare brand, content, tracking link via API (fast + deterministic).
  const brand = await request.post(`${API_URL}/api/v1/brands`, {
    data: { name: `E2E ${Date.now()}`, slug: `e2e-${Date.now()}` },
    headers: {
      "content-type": "application/json",
      "x-csrf-token": token,
      "x-organization-id": targetOrg,
    },
  });
  expect(brand.status()).toBe(201);
  const brandId = (await brand.json()).id;

  const camp = await request.post(`${API_URL}/api/v1/campaigns`, {
    data: {
      brand_id: brandId,
      name: "E2E Camp",
      slug: `e2e-camp-${Date.now()}`,
      objective: "SALES",
      platform: "INSTAGRAM",
      status: "ACTIVE",
    },
    headers: {
      "content-type": "application/json",
      "x-csrf-token": token,
      "x-organization-id": targetOrg,
    },
  });
  const campaignId = (await camp.json()).id;

  const content = await request.post(`${API_URL}/api/v1/content-items`, {
    data: { brand_id: brandId, campaign_id: campaignId, title: "E2E Reel" },
    headers: {
      "content-type": "application/json",
      "x-csrf-token": token,
      "x-organization-id": targetOrg,
    },
  });
  const contentId = (await content.json()).id;

  const link = await request.post(`${API_URL}/api/v1/tracking-links`, {
    data: {
      brand_id: brandId,
      campaign_id: campaignId,
      content_id: contentId,
      destination_url: "https://example.com/e2e",
      utm_source: "instagram",
      utm_campaign: "e2e",
    },
    headers: {
      "content-type": "application/json",
      "x-csrf-token": token,
      "x-organization-id": targetOrg,
    },
  });
  const linkBody = await link.json();

  // Log into the UI as owner.
  await page.goto("/login");
  await page.getByLabel("Correo").fill(seeded.owner.email);
  await page.getByLabel("Contraseña").fill(seeded.owner.password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // Switch to owner org so we act inside it.
  await page.evaluate((id) => {
    window.localStorage.setItem("rqt21.currentOrgId", id);
  }, targetOrg);

  // Add the content to the editorial calendar via the UI.
  const brandsResp = page.waitForResponse(
    (r) => r.url().includes("/api/v1/brands") && r.request().method() === "GET",
  );
  const contentsResp = page.waitForResponse(
    (r) => r.url().includes("/api/v1/content-items") && r.request().method() === "GET",
  );
  await page.goto("/calendar");
  await brandsResp;
  await contentsResp;
  await expect(page.getByRole("heading", { name: "Nuevo elemento" })).toBeVisible({ timeout: 10_000 });
  // Ensure the content select has our E2E Reel option.
  const form = page.locator("form", { hasText: "Nuevo elemento" });
  await form.getByLabel("Contenido").selectOption({ label: "E2E Reel" });
  const scheduleFor = new Date(Date.now() + 24 * 3600 * 1000).toISOString();
  await form.getByLabel("Estado").selectOption({ value: "SCHEDULED" });
  await form.getByLabel(/Fecha programada/i).fill(scheduleFor);
  const editorialCreateResponse = page.waitForResponse(
    (r) =>
      r.url().includes("/api/v1/editorial-calendar") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Añadir al calendario" }).click();
  const editorialResp = await editorialCreateResponse;
  expect(editorialResp.status()).toBe(201);

  // Approve the content via reviews.
  await page.goto("/reviews");
  await page.getByRole("button", { name: /E2E Reel/ }).first().click();
  const approveResponse = page.waitForResponse(
    (r) => r.url().includes("/approve") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Aprobar" }).click();
  const approveResp = await approveResponse;
  expect(approveResp.status()).toBe(201);

  // Public lead capture via API (simulating landing page).
  const pubLead = await request.post(`${API_URL}/public/leads`, {
    data: {
      first_name: "PublicLead",
      email: "public.e2e@example.com",
      tracking_code: linkBody.short_code,
    },
    headers: { "content-type": "application/json" },
  });
  expect(pubLead.status()).toBe(201);

  // Verify lead exists and is attributed to the campaign.
  const leadsList = await request.get(
    `${API_URL}/api/v1/leads?campaign_id=${campaignId}`,
    {
      headers: {
        "x-organization-id": targetOrg,
      },
    },
  );
  const leads = await leadsList.json();
  expect(leads.length).toBe(1);
  const publicLeadId = leads[0].id;
  expect(leads[0].utm_source).toBe("instagram");

  // Move to QUALIFIED then WON via the UI on lead detail.
  await page.goto(`/leads/${publicLeadId}`);
  await expect(page.getByRole("heading", { name: /PublicLead/ })).toBeVisible();
  const qResp = page.waitForResponse(
    (r) => r.url().includes("/status") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Calificado" }).click();
  await qResp;
  const wResp = page.waitForResponse(
    (r) => r.url().includes("/status") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Ganado" }).click();
  await wResp;

  // Verify funnel via the API.
  const funnel = await request.get(
    `${API_URL}/api/v1/analytics/campaigns/${campaignId}/funnel`,
    { headers: { "x-organization-id": targetOrg } },
  );
  const f = await funnel.json();
  expect(f.leads).toBe(1);
  expect(f.won_leads).toBe(1);
  expect(f.lead_to_won_rate).toBe(100.0);

  // Dashboard shows the new state.
  await page.goto("/dashboard");
  await expect(page.getByText("Operación editorial")).toBeVisible();
  await expect(page.getByText("Conversión")).toBeVisible();
});

async function findTargetOrg(
  request: import("@playwright/test").APIRequestContext,
): Promise<string> {
  const r = await request.get(`${API_URL}/api/v1/organizations`);
  const orgs: Array<{ id: string; slug: string }> = await r.json();
  return (orgs.find((o) => o.slug === "rqt21") || orgs[0]).id;
}

test("MARKETER can submit for review but not approve", async ({ page, seeded, request }) => {
  await apiLogin(request, seeded.owner.email, seeded.owner.password);
  const token = await csrf(request);
  const targetOrg = await findTargetOrg(request);

  const email = `mkt-${Math.random().toString(36).slice(2, 8)}@example.com`;
  const password = "Password1!Marketer";
  const r = await request.post(
    `${API_URL}/api/v1/organizations/${targetOrg}/members`,
    {
      data: { email, full_name: "M", password, role: "MARKETER" },
      headers: {
        "content-type": "application/json",
        "x-csrf-token": token,
        "x-organization-id": targetOrg,
      },
    },
  );
  expect(r.status()).toBe(201);
  await request.post(`${API_URL}/api/v1/auth/logout`, {});

  await page.goto("/login");
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill(password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.evaluate((id) => {
    window.localStorage.setItem("rqt21.currentOrgId", id);
  }, targetOrg);

  await page.goto("/reviews");
  await page.getByRole("button", { name: /E2E Reel|Lasaña|Pizza/ }).first().click();
  await expect(
    page.getByText(/Tu rol permite enviar a revisión pero no aprobar/i),
  ).toBeVisible();
});

test("ANALYST cannot see PII contact or export", async ({ page, seeded, request }) => {
  await apiLogin(request, seeded.owner.email, seeded.owner.password);
  const token = await csrf(request);
  const targetOrg = await findTargetOrg(request);

  const email = `an-${Math.random().toString(36).slice(2, 8)}@example.com`;
  const password = "Password1!Analyst";
  await request.post(
    `${API_URL}/api/v1/organizations/${targetOrg}/members`,
    {
      data: { email, full_name: "A", password, role: "ANALYST" },
      headers: {
        "content-type": "application/json",
        "x-csrf-token": token,
        "x-organization-id": targetOrg,
      },
    },
  );
  await request.post(`${API_URL}/api/v1/auth/logout`, {});

  // Seed at least one lead via owner API so the list has PII to hide.
  await apiLogin(request, seeded.owner.email, seeded.owner.password);
  const t2 = await csrf(request);
  await request.post(`${API_URL}/api/v1/leads`, {
    data: { first_name: "PIILead", email: "pii@example.com" },
    headers: {
      "content-type": "application/json",
      "x-csrf-token": t2,
      "x-organization-id": targetOrg,
    },
  });
  await request.post(`${API_URL}/api/v1/auth/logout`, {});

  await page.goto("/login");
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill(password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.evaluate((id) => {
    window.localStorage.setItem("rqt21.currentOrgId", id);
  }, targetOrg);

  await page.goto("/leads");
  await expect(page.getByText("PIILead")).toBeVisible();
  await expect(page.getByText("pii@example.com")).toHaveCount(0);
  // Export button is not shown for ANALYST.
  await expect(page.getByRole("link", { name: "Exportar CSV" })).toHaveCount(0);
});
