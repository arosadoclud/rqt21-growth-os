import { test as base, expect, Page, APIRequestContext } from "@playwright/test";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8100";

async function apiPost(request: APIRequestContext, path: string, body: unknown) {
  return request.post(`${API_URL}${path}`, {
    data: body,
    headers: { "content-type": "application/json" },
  });
}

async function apiGet(request: APIRequestContext, path: string, headers: Record<string, string> = {}) {
  return request.get(`${API_URL}${path}`, { headers });
}

export interface Seeded {
  owner: { email: string; password: string; name: string };
  other: { email: string; password: string; name: string };
  ownerOrg: { id: string; slug: string; name: string };
  otherOrg: { id: string; slug: string; name: string };
}

/**
 * Seeds a clean pair of orgs+owners on every test using only the public API.
 * Assumes rate limits are permissive on the API under test.
 */
async function seedFreshData(request: APIRequestContext): Promise<Seeded> {
  const uniq = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  const owner = {
    email: `pw-owner-${uniq}@example.com`,
    password: "Password1!Playwright",
    name: `Owner ${uniq}`,
  };
  const other = {
    email: `pw-other-${uniq}@example.com`,
    password: "Password1!Playwright",
    name: `Other ${uniq}`,
  };

  // Owner registers by creating their org (first login is missing → we need a
  // way. In Phase 1 the only user-creation path is /members. We register
  // owners by logging in as the seed OWNER of the RQT21 org, then adding them
  // via /organizations/{seed_org}/members as ADMIN, then they create their own
  // orgs from there.)
  const seedEmail = process.env.SEED_OWNER_EMAIL || "owner@rqt21.dev";
  const seedPassword = process.env.SEED_OWNER_PASSWORD || "Owner!2026Local";

  const loginSeed = await apiPost(request, "/api/v1/auth/login", {
    email: seedEmail,
    password: seedPassword,
  });
  expect(loginSeed.status(), "seed login must succeed").toBe(200);
  const seedBody = await loginSeed.json();
  const seedOrgId: string = seedBody.organizations[0].id;

  // Cookie jar of `request` is now authenticated as seed OWNER.
  const seedCsrf = (await request.storageState()).cookies.find(
    (c) => c.name === "rqt_csrf",
  )?.value;

  const mk = async (person: typeof owner) => {
    const r = await request.post(
      `${API_URL}/api/v1/organizations/${seedOrgId}/members`,
      {
        data: {
          email: person.email,
          full_name: person.name,
          password: person.password,
          role: "ADMIN",
        },
        headers: {
          "content-type": "application/json",
          "x-csrf-token": seedCsrf || "",
        },
      },
    );
    expect(r.status(), `create member ${person.email}`).toBe(201);
  };
  await mk(owner);
  await mk(other);

  await apiPost(request, "/api/v1/auth/logout", {});

  const mkOrg = async (email: string, password: string, slug: string, name: string) => {
    const login = await apiPost(request, "/api/v1/auth/login", { email, password });
    expect(login.status()).toBe(200);
    const csrf = (await request.storageState()).cookies.find(
      (c) => c.name === "rqt_csrf",
    )?.value;
    const createOrg = await request.post(`${API_URL}/api/v1/organizations`, {
      data: { name, slug },
      headers: { "content-type": "application/json", "x-csrf-token": csrf || "" },
    });
    expect(createOrg.status(), `create org ${slug}`).toBe(201);
    const orgId: string = (await createOrg.json()).id;
    await apiPost(request, "/api/v1/auth/logout", {});
    return { id: orgId, slug, name };
  };

  const ownerOrg = await mkOrg(
    owner.email,
    owner.password,
    `pw-owner-org-${uniq}`,
    `Owner Org ${uniq}`,
  );
  const otherOrg = await mkOrg(
    other.email,
    other.password,
    `pw-other-org-${uniq}`,
    `Other Org ${uniq}`,
  );

  return { owner, other, ownerOrg, otherOrg };
}

export const test = base.extend<{ seeded: Seeded }>({
  seeded: async ({ request }, use) => {
    const data = await seedFreshData(request);
    await use(data);
  },
});

export { expect };
export type { Page };
