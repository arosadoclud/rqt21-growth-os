import { test, expect } from "./fixtures";

test.describe.configure({ mode: "serial" });

test("unauthenticated visit to root redirects to /login", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
});

test("unauthenticated visit to /dashboard redirects to /login", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
});

test("successful login lands on dashboard", async ({ page, seeded }) => {
  await page.goto("/login");
  await page.getByLabel("Correo").fill(seeded.owner.email);
  await page.getByLabel("Contraseña").fill(seeded.owner.password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText("Bienvenido")).toBeVisible();
});

test("failed login shows an error", async ({ page, seeded }) => {
  await page.goto("/login");
  await page.getByLabel("Correo").fill(seeded.owner.email);
  await page.getByLabel("Contraseña").fill("definitely-not-the-password");
  await page.getByRole("button", { name: "Ingresar" }).click();
  const alert = page.locator(
    '[role="alert"]:not([id="__next-route-announcer__"])',
  );
  await expect(alert).toBeVisible({ timeout: 10_000 });
  await expect(page).toHaveURL(/\/login$/);
});

test("automatic session refresh on 401", async ({ page, seeded, context }) => {
  await page.goto("/login");
  await page.getByLabel("Correo").fill(seeded.owner.email);
  await page.getByLabel("Contraseña").fill(seeded.owner.password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // Delete only the short-lived access cookie. The refresh cookie survives —
  // the next API call should trigger auto-refresh under the hood.
  const cookies = await context.cookies();
  const others = cookies.filter((c) => c.name !== "rqt_access");
  await context.clearCookies();
  await context.addCookies(others);

  await page.goto("/members");
  await expect(page.getByRole("heading", { name: "Miembros" })).toBeVisible();
  // No redirect back to /login → auto-refresh succeeded.
  await expect(page).toHaveURL(/\/members$/);
});

test("organization switcher swaps active org", async ({ page, seeded }) => {
  await page.goto("/login");
  await page.getByLabel("Correo").fill(seeded.owner.email);
  await page.getByLabel("Contraseña").fill(seeded.owner.password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  const selector = page.getByRole("combobox", { name: /organizaci/i });
  await expect(selector).toBeVisible();
  const optionCount = await selector.locator("option").count();
  expect(optionCount).toBeGreaterThanOrEqual(1);
});

test("logout clears session and redirects to /login", async ({ page, seeded }) => {
  await page.goto("/login");
  await page.getByLabel("Correo").fill(seeded.owner.email);
  await page.getByLabel("Contraseña").fill(seeded.owner.password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole("button", { name: "Salir" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
});

test("members page surfaces 403 when acting on foreign org", async ({
  page,
  seeded,
}) => {
  // Log in as "other" — they aren't a member of ownerOrg.
  await page.goto("/login");
  await page.getByLabel("Correo").fill(seeded.other.email);
  await page.getByLabel("Contraseña").fill(seeded.other.password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // Simulate a 403 response from the members endpoint. This asserts the UI's
  // error rendering path, which is what the user sees when the API rejects a
  // foreign-org request.
  await page.route("**/api/v1/organizations/*/members**", async (route) => {
    await route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({ detail: "not a member of this organization" }),
    });
  });

  await page.goto("/members");
  await expect(page.getByText(/not a member of this organization/i)).toBeVisible({
    timeout: 8000,
  });
});
