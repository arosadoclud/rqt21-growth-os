import type {
  AIUsageSummary,
  Asset,
  AssetStatus,
  AssetType,
  AssetUpdate,
  AssetVariant,
  AssetVariantCreate,
  AutomationRule,
  AutomationRuleCreate,
  AutomationRuleUpdate,
  AutomationSummary,
  Brand,
  BrandCreate,
  BrandUpdate,
  BrandVoiceProfile,
  BrandVoiceWrite,
  Campaign,
  CampaignCreate,
  CampaignUpdate,
  ContentCreate,
  ContentItem,
  CouncilDecisionResult,
  CreateContentFromJob,
  DashboardSummary,
  EditorialItem,
  EditorialItemCreate,
  Funnel,
  GenerateThumbnailRequest,
  GenerationJob,
  GenerationJobCreate,
  HeadlineConfig,
  HeadlineConfigWrite,
  HeadlinePendingPhoto,
  InitUploadRequest,
  InitUploadResponse,
  Lead,
  LeadActivity,
  LeadActivityCreate,
  LeadCreate,
  LeadStatus,
  LoginRequest,
  LoginResponse,
  MeResponse,
  Member,
  MemberCreate,
  MemberUpdate,
  Notification,
  Organization,
  OrganizationCreate,
  Phase3Dashboard,
  Product,
  ProductCreate,
  ProductUpdate,
  Publication,
  PublicationAttempt,
  PublicationCreate,
  PublicationUpdate,
  PublishingConnection,
  PublishingConnectionCreate,
  PublishingConnectionUpdate,
  PublishingSummary,
  Review,
  SignedUrlResponse,
  StoryConfig,
  StoryConfigWrite,
  StoryPendingPhoto,
  TrackingLink,
  TrackingLinkCreate,
  TrackingLinkUpdate,
  ValidationResult,
} from "@rqt21/contracts";

// Empty string = relative paths ("/api/v1/..."), routed through the
// same-origin proxy in next.config.mjs (API_PROXY_TARGET) in production.
// Local dev sets NEXT_PUBLIC_API_URL explicitly (see .env.example) to talk
// to the API directly without a proxy.
const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail || `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export { ApiError };

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ");
    }
    return JSON.stringify(data);
  } catch {
    return res.statusText;
  }
}

const CSRF_COOKIE = "rqt_csrf";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=", 2)[1]) : null;
}

async function raw(
  path: string,
  init: RequestInit = {},
  orgId?: string | null,
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  if (orgId) headers.set("X-Organization-Id", orgId);

  const method = (init.method || "GET").toUpperCase();
  if (!SAFE_METHODS.has(method) && !headers.has("X-CSRF-Token")) {
    const token = readCookie(CSRF_COOKIE);
    if (token) headers.set("X-CSRF-Token", token);
  }

  return fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
}

let refreshInFlight: Promise<boolean> | null = null;

async function refresh(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const r = await raw("/api/v1/auth/refresh", { method: "POST" });
        return r.ok;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

export async function request<T>(
  path: string,
  init: RequestInit = {},
  orgId?: string | null,
): Promise<T> {
  let res = await raw(path, init, orgId);
  if (res.status === 401 && !path.startsWith("/api/v1/auth/")) {
    const ok = await refresh();
    if (ok) {
      res = await raw(path, init, orgId);
    }
  }
  if (!res.ok) {
    const detail = await parseError(res);
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  login: (body: LoginRequest) =>
    request<LoginResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  logout: () => request<void>("/api/v1/auth/logout", { method: "POST" }),
  me: () => request<MeResponse>("/api/v1/me"),
  listOrgs: () => request<Organization[]>("/api/v1/organizations"),
  createOrg: (body: OrganizationCreate) =>
    request<Organization>("/api/v1/organizations", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listMembers: (orgId: string) =>
    request<Member[]>(`/api/v1/organizations/${orgId}/members`, {}, orgId),
  addMember: (orgId: string, body: MemberCreate) =>
    request<Member>(
      `/api/v1/organizations/${orgId}/members`,
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  updateMember: (orgId: string, memberId: string, body: MemberUpdate) =>
    request<Member>(
      `/api/v1/organizations/${orgId}/members/${memberId}`,
      { method: "PATCH", body: JSON.stringify(body) },
      orgId,
    ),

  // Phase 2 — Brands
  listBrands: (orgId: string) =>
    request<Brand[]>("/api/v1/brands", {}, orgId),
  createBrand: (orgId: string, body: BrandCreate) =>
    request<Brand>(
      "/api/v1/brands",
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  updateBrand: (orgId: string, id: string, body: BrandUpdate) =>
    request<Brand>(
      `/api/v1/brands/${id}`,
      { method: "PATCH", body: JSON.stringify(body) },
      orgId,
    ),
  deleteBrand: (orgId: string, id: string) =>
    request<void>(`/api/v1/brands/${id}`, { method: "DELETE" }, orgId),

  // Products
  listProducts: (orgId: string) =>
    request<Product[]>("/api/v1/products", {}, orgId),
  createProduct: (orgId: string, body: ProductCreate) =>
    request<Product>(
      "/api/v1/products",
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  updateProduct: (orgId: string, id: string, body: ProductUpdate) =>
    request<Product>(
      `/api/v1/products/${id}`,
      { method: "PATCH", body: JSON.stringify(body) },
      orgId,
    ),

  // Campaigns
  listCampaigns: (orgId: string) =>
    request<Campaign[]>("/api/v1/campaigns", {}, orgId),
  createCampaign: (orgId: string, body: CampaignCreate) =>
    request<Campaign>(
      "/api/v1/campaigns",
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  updateCampaign: (orgId: string, id: string, body: CampaignUpdate) =>
    request<Campaign>(
      `/api/v1/campaigns/${id}`,
      { method: "PATCH", body: JSON.stringify(body) },
      orgId,
    ),

  // Content items
  listContent: (orgId: string) =>
    request<ContentItem[]>("/api/v1/content-items", {}, orgId),
  createContent: (orgId: string, body: ContentCreate) =>
    request<ContentItem>(
      "/api/v1/content-items",
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  deleteContent: (orgId: string, id: string) =>
    request<void>(`/api/v1/content-items/${id}`, { method: "DELETE" }, orgId),

  // Tracking links
  listTrackingLinks: (orgId: string) =>
    request<TrackingLink[]>("/api/v1/tracking-links", {}, orgId),
  createTrackingLink: (orgId: string, body: TrackingLinkCreate) =>
    request<TrackingLink>(
      "/api/v1/tracking-links",
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  updateTrackingLink: (orgId: string, id: string, body: TrackingLinkUpdate) =>
    request<TrackingLink>(
      `/api/v1/tracking-links/${id}`,
      { method: "PATCH", body: JSON.stringify(body) },
      orgId,
    ),
  regenerateShortCode: (orgId: string, id: string) =>
    request<TrackingLink>(
      `/api/v1/tracking-links/${id}/regenerate-code`,
      { method: "POST" },
      orgId,
    ),

  // Dashboard
  dashboardSummary: (orgId: string) =>
    request<DashboardSummary>("/api/v1/analytics/dashboard/summary", {}, orgId),

  // Phase 3 - Editorial calendar
  listEditorial: (orgId: string) =>
    request<EditorialItem[]>("/api/v1/editorial-calendar", {}, orgId),
  createEditorial: (orgId: string, body: EditorialItemCreate) =>
    request<EditorialItem>(
      "/api/v1/editorial-calendar",
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  scheduleEditorial: (
    orgId: string,
    id: string,
    body: { scheduled_for: string; timezone?: string },
  ) =>
    request<EditorialItem>(
      `/api/v1/editorial-calendar/${id}/schedule`,
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  markPublished: (
    orgId: string,
    id: string,
    body: { publication_url: string; published_at?: string },
  ) =>
    request<EditorialItem>(
      `/api/v1/editorial-calendar/${id}/mark-published`,
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  cancelEditorial: (orgId: string, id: string) =>
    request<EditorialItem>(
      `/api/v1/editorial-calendar/${id}/cancel`,
      { method: "POST" },
      orgId,
    ),

  // Reviews
  listReviews: (orgId: string, contentId: string) =>
    request<Review[]>(
      `/api/v1/content-items/${contentId}/reviews`,
      {},
      orgId,
    ),
  submitForReview: (orgId: string, contentId: string, comment?: string) =>
    request<Review>(
      `/api/v1/content-items/${contentId}/submit-review`,
      { method: "POST", body: JSON.stringify({ comment }) },
      orgId,
    ),
  approveContent: (orgId: string, contentId: string, body: { comment?: string; score?: number }) =>
    request<Review>(
      `/api/v1/content-items/${contentId}/approve`,
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  requestChanges: (orgId: string, contentId: string, body: { comment?: string }) =>
    request<Review>(
      `/api/v1/content-items/${contentId}/request-changes`,
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  rejectContent: (orgId: string, contentId: string, body: { comment?: string }) =>
    request<Review>(
      `/api/v1/content-items/${contentId}/reject`,
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),

  // Leads
  listLeads: (orgId: string, params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<Lead[]>(`/api/v1/leads${qs}`, {}, orgId);
  },
  createLead: (orgId: string, body: LeadCreate) =>
    request<Lead>(
      "/api/v1/leads",
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  getLead: (orgId: string, id: string) =>
    request<Lead>(`/api/v1/leads/${id}`, {}, orgId),
  changeLeadStatus: (orgId: string, id: string, status: LeadStatus, note?: string) =>
    request<Lead>(
      `/api/v1/leads/${id}/status`,
      { method: "POST", body: JSON.stringify({ status, note }) },
      orgId,
    ),
  listLeadActivities: (orgId: string, id: string) =>
    request<LeadActivity[]>(`/api/v1/leads/${id}/activities`, {}, orgId),
  createLeadActivity: (orgId: string, id: string, body: LeadActivityCreate) =>
    request<LeadActivity>(
      `/api/v1/leads/${id}/activities`,
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  exportLeadsUrl: (orgId: string) =>
    `${API_URL}/api/v1/leads/export`,

  // Phase 3 analytics
  phase3Dashboard: (orgId: string) =>
    request<Phase3Dashboard>("/api/v1/analytics/dashboard/phase3", {}, orgId),
  campaignFunnel: (orgId: string, id: string) =>
    request<Funnel>(`/api/v1/analytics/campaigns/${id}/funnel`, {}, orgId),
  contentFunnel: (orgId: string, id: string) =>
    request<Funnel>(`/api/v1/analytics/content/${id}/funnel`, {}, orgId),
  linkFunnel: (orgId: string, id: string) =>
    request<Funnel>(`/api/v1/analytics/tracking-links/${id}/funnel`, {}, orgId),

  // Phase 4 — Brand voice
  getBrandVoice: (orgId: string, brandId: string) =>
    request<BrandVoiceProfile>(`/api/v1/brand-voice/${brandId}`, {}, orgId),
  upsertBrandVoice: (orgId: string, brandId: string, body: BrandVoiceWrite) =>
    request<BrandVoiceProfile>(
      `/api/v1/brand-voice/${brandId}`,
      { method: "PUT", body: JSON.stringify(body) },
      orgId,
    ),

  // Generation jobs
  listGenerationJobs: (orgId: string, params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<GenerationJob[]>(`/api/v1/generation-jobs${qs}`, {}, orgId);
  },
  createGenerationJob: (orgId: string, body: GenerationJobCreate) =>
    request<GenerationJob>(
      "/api/v1/generation-jobs",
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  getGenerationJob: (orgId: string, id: string) =>
    request<GenerationJob>(`/api/v1/generation-jobs/${id}`, {}, orgId),
  cancelGenerationJob: (orgId: string, id: string) =>
    request<GenerationJob>(
      `/api/v1/generation-jobs/${id}/cancel`,
      { method: "POST" },
      orgId,
    ),
  retryGenerationJob: (orgId: string, id: string) =>
    request<GenerationJob>(
      `/api/v1/generation-jobs/${id}/retry`,
      { method: "POST" },
      orgId,
    ),
  runCouncil: (orgId: string, id: string) =>
    request<CouncilDecisionResult>(
      `/api/v1/generation-jobs/${id}/run-council`,
      { method: "POST" },
      orgId,
    ),
  getCouncil: (orgId: string, id: string) =>
    request<CouncilDecisionResult>(
      `/api/v1/generation-jobs/${id}/council`,
      {},
      orgId,
    ),
  createContentFromJob: (orgId: string, id: string, body: CreateContentFromJob) =>
    request<ContentItem>(
      `/api/v1/generation-jobs/${id}/create-content-item`,
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),

  // AI usage
  aiUsageSummary: (orgId: string) =>
    request<AIUsageSummary>("/api/v1/ai-usage/summary", {}, orgId),

  // Phase 5 — Assets
  listAssets: (orgId: string, params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<Asset[]>(`/api/v1/assets${qs}`, {}, orgId);
  },
  getAsset: (orgId: string, id: string) => request<Asset>(`/api/v1/assets/${id}`, {}, orgId),
  initUpload: (orgId: string, body: InitUploadRequest) =>
    request<InitUploadResponse>(
      "/api/v1/assets/init-upload",
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  completeUpload: (orgId: string, body: { asset_id: string; content_base64: string }) =>
    request<Asset>(
      "/api/v1/assets/complete-upload",
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  updateAsset: (orgId: string, id: string, body: AssetUpdate) =>
    request<Asset>(
      `/api/v1/assets/${id}`,
      { method: "PATCH", body: JSON.stringify(body) },
      orgId,
    ),
  archiveAsset: (orgId: string, id: string) =>
    request<Asset>(`/api/v1/assets/${id}/archive`, { method: "POST" }, orgId),
  assetDownloadUrl: (orgId: string, id: string) =>
    request<SignedUrlResponse>(`/api/v1/assets/${id}/download-url`, {}, orgId),
  listAssetVariants: (orgId: string, id: string) =>
    request<AssetVariant[]>(`/api/v1/assets/${id}/variants`, {}, orgId),
  createAssetVariant: (orgId: string, id: string, body: AssetVariantCreate) =>
    request<AssetVariant>(
      `/api/v1/assets/${id}/variants`,
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  generateThumbnail: (orgId: string, id: string, body: GenerateThumbnailRequest) =>
    request<AssetVariant>(
      `/api/v1/assets/${id}/generate-thumbnail`,
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  generateAssetAltText: (orgId: string, id: string) =>
    request<Asset>(`/api/v1/assets/${id}/generate-alt-text`, { method: "POST" }, orgId),

  // Publishing connections
  listConnections: (orgId: string) =>
    request<PublishingConnection[]>("/api/v1/publishing-connections", {}, orgId),
  getConnection: (orgId: string, id: string) =>
    request<PublishingConnection>(`/api/v1/publishing-connections/${id}`, {}, orgId),
  createConnection: (orgId: string, body: PublishingConnectionCreate) =>
    request<PublishingConnection>(
      "/api/v1/publishing-connections",
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  updateConnection: (orgId: string, id: string, body: PublishingConnectionUpdate) =>
    request<PublishingConnection>(
      `/api/v1/publishing-connections/${id}`,
      { method: "PATCH", body: JSON.stringify(body) },
      orgId,
    ),
  verifyConnection: (orgId: string, id: string) =>
    request<PublishingConnection>(
      `/api/v1/publishing-connections/${id}/verify`,
      { method: "POST" },
      orgId,
    ),
  revokeConnection: (orgId: string, id: string) =>
    request<PublishingConnection>(
      `/api/v1/publishing-connections/${id}/revoke`,
      { method: "POST" },
      orgId,
    ),
  disableConnection: (orgId: string, id: string) =>
    request<PublishingConnection>(
      `/api/v1/publishing-connections/${id}/disable`,
      { method: "POST" },
      orgId,
    ),

  // Publications
  listPublications: (orgId: string, params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<Publication[]>(`/api/v1/publications${qs}`, {}, orgId);
  },
  getPublication: (orgId: string, id: string) =>
    request<Publication>(`/api/v1/publications/${id}`, {}, orgId),
  createPublication: (orgId: string, body: PublicationCreate) =>
    request<Publication>(
      "/api/v1/publications",
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  updatePublication: (orgId: string, id: string, body: PublicationUpdate) =>
    request<Publication>(
      `/api/v1/publications/${id}`,
      { method: "PATCH", body: JSON.stringify(body) },
      orgId,
    ),
  deletePublication: (orgId: string, id: string) =>
    request<void>(`/api/v1/publications/${id}`, { method: "DELETE" }, orgId),
  validatePublication: (orgId: string, id: string) =>
    request<ValidationResult>(
      `/api/v1/publications/${id}/validate`,
      { method: "POST" },
      orgId,
    ),
  schedulePublication: (
    orgId: string,
    id: string,
    body: { scheduled_for: string; timezone?: string },
  ) =>
    request<Publication>(
      `/api/v1/publications/${id}/schedule`,
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  publishPublication: (orgId: string, id: string) =>
    request<Publication>(`/api/v1/publications/${id}/publish`, { method: "POST" }, orgId),
  retryPublication: (orgId: string, id: string) =>
    request<Publication>(`/api/v1/publications/${id}/retry`, { method: "POST" }, orgId),
  cancelPublication: (orgId: string, id: string) =>
    request<Publication>(`/api/v1/publications/${id}/cancel`, { method: "POST" }, orgId),
  markPublicationPublished: (
    orgId: string,
    id: string,
    body: { external_url: string; published_at?: string },
  ) =>
    request<Publication>(
      `/api/v1/publications/${id}/mark-published`,
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  listPublicationAttempts: (orgId: string, id: string) =>
    request<PublicationAttempt[]>(`/api/v1/publications/${id}/attempts`, {}, orgId),
  publishingQueue: (orgId: string) =>
    request<Publication[]>("/api/v1/publishing/queue", {}, orgId),
  publishingSummary: (orgId: string) =>
    request<PublishingSummary>("/api/v1/publishing/summary", {}, orgId),

  // Automations
  listAutomations: (orgId: string) =>
    request<AutomationRule[]>("/api/v1/automations", {}, orgId),
  createAutomation: (orgId: string, body: AutomationRuleCreate) =>
    request<AutomationRule>(
      "/api/v1/automations",
      { method: "POST", body: JSON.stringify(body) },
      orgId,
    ),
  updateAutomation: (orgId: string, id: string, body: AutomationRuleUpdate) =>
    request<AutomationRule>(
      `/api/v1/automations/${id}`,
      { method: "PATCH", body: JSON.stringify(body) },
      orgId,
    ),
  automationSummary: (orgId: string) =>
    request<AutomationSummary>("/api/v1/automations/summary", {}, orgId),

  // Notifications
  listNotifications: (orgId: string, unreadOnly?: boolean) =>
    request<Notification[]>(
      `/api/v1/notifications${unreadOnly ? "?unread_only=true" : ""}`,
      {},
      orgId,
    ),
  markNotificationRead: (orgId: string, id: string) =>
    request<Notification>(`/api/v1/notifications/${id}/read`, { method: "POST" }, orgId),

  // Headline: automatic keto-recipe content cycle
  getHeadlineConfig: (orgId: string, brandId: string) =>
    request<HeadlineConfig>(`/api/v1/headline-config/${brandId}`, {}, orgId),
  updateHeadlineConfig: (orgId: string, brandId: string, body: HeadlineConfigWrite) =>
    request<HeadlineConfig>(
      `/api/v1/headline-config/${brandId}`,
      { method: "PUT", body: JSON.stringify(body) },
      orgId,
    ),
  runHeadlineNow: (orgId: string, brandId: string) =>
    request<HeadlineConfig>(
      `/api/v1/headline-config/${brandId}/run-now`,
      { method: "POST" },
      orgId,
    ),
  listHeadlineHistory: (orgId: string, brandId: string) =>
    request<ContentItem[]>(`/api/v1/headline-config/${brandId}/history`, {}, orgId),
  listHeadlinePendingPhotos: (orgId: string, brandId: string) =>
    request<HeadlinePendingPhoto[]>(`/api/v1/headline-config/${brandId}/pending-photos`, {}, orgId),

  // Historias: short, conversational follower-connection content cycle
  getStoryConfig: (orgId: string, brandId: string) =>
    request<StoryConfig>(`/api/v1/story-config/${brandId}`, {}, orgId),
  updateStoryConfig: (orgId: string, brandId: string, body: StoryConfigWrite) =>
    request<StoryConfig>(
      `/api/v1/story-config/${brandId}`,
      { method: "PUT", body: JSON.stringify(body) },
      orgId,
    ),
  runStoryNow: (orgId: string, brandId: string) =>
    request<StoryConfig>(
      `/api/v1/story-config/${brandId}/run-now`,
      { method: "POST" },
      orgId,
    ),
  listStoryHistory: (orgId: string, brandId: string) =>
    request<ContentItem[]>(`/api/v1/story-config/${brandId}/history`, {}, orgId),
  listStoryPendingPhotos: (orgId: string, brandId: string) =>
    request<StoryPendingPhoto[]>(`/api/v1/story-config/${brandId}/pending-photos`, {}, orgId),
};

export type { AssetStatus, AssetType };
