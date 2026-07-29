export const ROLES = [
  "OWNER",
  "ADMIN",
  "MARKETER",
  "SALES",
  "ANALYST",
  "VIEWER",
] as const;
export type Role = (typeof ROLES)[number];

export interface UserPublic {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
}

export interface OrganizationSummary {
  id: string;
  name: string;
  slug: string;
  role: Role;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
}

export interface MeResponse {
  user: UserPublic;
  organizations: OrganizationSummary[];
}
export type LoginResponse = MeResponse;

export interface LoginRequest {
  email: string;
  password: string;
}

export interface Member {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: Role;
}
export interface MemberCreate {
  email: string;
  full_name: string;
  password: string;
  role: Role;
}
export interface MemberUpdate {
  role: Role;
}
export interface OrganizationCreate {
  name: string;
  slug: string;
}

// -------- Phase 2 --------

export const PRODUCT_STATUSES = ["DRAFT", "ACTIVE", "ARCHIVED"] as const;
export type ProductStatus = (typeof PRODUCT_STATUSES)[number];

export const CAMPAIGN_STATUSES = ["DRAFT", "ACTIVE", "PAUSED", "ARCHIVED"] as const;
export type CampaignStatus = (typeof CAMPAIGN_STATUSES)[number];

export const CAMPAIGN_OBJECTIVES = [
  "AWARENESS",
  "TRAFFIC",
  "LEAD_GEN",
  "SALES",
  "ENGAGEMENT",
  "OTHER",
] as const;
export type CampaignObjective = (typeof CAMPAIGN_OBJECTIVES)[number];

export const PLATFORMS = [
  "INSTAGRAM",
  "FACEBOOK",
  "TIKTOK",
  "YOUTUBE",
  "WHATSAPP",
  "EMAIL",
  "WEB",
  "META_ADS",
  "OTHER",
] as const;
export type Platform = (typeof PLATFORMS)[number];

export const CONTENT_TYPES = [
  "POST",
  "REEL",
  "STORY",
  "VIDEO",
  "ARTICLE",
  "AD",
  "OTHER",
] as const;
export type ContentType = (typeof CONTENT_TYPES)[number];

export const CONTENT_STATUSES = [
  "DRAFT",
  "SCHEDULED",
  "PUBLISHED",
  "ARCHIVED",
] as const;
export type ContentStatus = (typeof CONTENT_STATUSES)[number];

export const REVIEW_STATUSES = [
  "NOT_SUBMITTED",
  "IN_REVIEW",
  "APPROVED",
  "CHANGES_REQUESTED",
  "REJECTED",
] as const;
export type ReviewStatus = (typeof REVIEW_STATUSES)[number];

export const SOURCE_SYSTEMS = ["MANUAL", "KINGDOM_STUDIO", "IMPORT"] as const;
export type SourceSystem = (typeof SOURCE_SYSTEMS)[number];

export interface Brand {
  id: string;
  public_id: string;
  name: string;
  slug: string;
  description: string | null;
  website_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
export interface BrandCreate {
  name: string;
  slug: string;
  description?: string | null;
  website_url?: string | null;
}
export interface BrandUpdate {
  name?: string;
  description?: string | null;
  website_url?: string | null;
  is_active?: boolean;
}

export interface Product {
  id: string;
  public_id: string;
  brand_id: string;
  name: string;
  slug: string;
  description: string | null;
  price: string | null;
  currency: string;
  checkout_url: string | null;
  status: ProductStatus;
  created_at: string;
  updated_at: string;
}
export interface ProductCreate {
  brand_id: string;
  name: string;
  slug: string;
  description?: string | null;
  price?: string | null;
  currency?: string;
  checkout_url?: string | null;
  status?: ProductStatus;
}
export interface ProductUpdate {
  name?: string;
  description?: string | null;
  price?: string | null;
  currency?: string;
  checkout_url?: string | null;
  status?: ProductStatus;
}

export interface Campaign {
  id: string;
  public_id: string;
  brand_id: string;
  product_id: string | null;
  name: string;
  slug: string;
  objective: CampaignObjective;
  platform: Platform;
  status: CampaignStatus;
  starts_at: string | null;
  ends_at: string | null;
  budget: string | null;
  created_at: string;
  updated_at: string;
}
export interface CampaignCreate {
  brand_id: string;
  product_id?: string | null;
  name: string;
  slug: string;
  objective?: CampaignObjective;
  platform?: Platform;
  status?: CampaignStatus;
  starts_at?: string | null;
  ends_at?: string | null;
  budget?: string | null;
}
export interface CampaignUpdate {
  name?: string;
  objective?: CampaignObjective;
  platform?: Platform;
  status?: CampaignStatus;
  starts_at?: string | null;
  ends_at?: string | null;
  budget?: string | null;
  product_id?: string | null;
}

export interface ContentItem {
  id: string;
  public_id: string;
  brand_id: string;
  campaign_id: string | null;
  product_id: string | null;
  external_id: string | null;
  source_system: SourceSystem;
  platform: Platform;
  content_type: ContentType;
  title: string;
  hook: string | null;
  caption: string | null;
  cta: string | null;
  media_url: string | null;
  publication_url: string | null;
  status: ContentStatus;
  review_status: ReviewStatus;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}
export interface ContentCreate {
  brand_id: string;
  campaign_id?: string | null;
  product_id?: string | null;
  external_id?: string | null;
  source_system?: SourceSystem;
  platform?: Platform;
  content_type?: ContentType;
  title: string;
  hook?: string | null;
  caption?: string | null;
  cta?: string | null;
  media_url?: string | null;
  publication_url?: string | null;
  status?: ContentStatus;
  published_at?: string | null;
}

export interface TrackingLink {
  id: string;
  public_id: string;
  brand_id: string;
  product_id: string | null;
  campaign_id: string | null;
  content_id: string | null;
  short_code: string;
  short_url: string;
  final_url: string;
  destination_url: string;
  utm_source: string | null;
  utm_medium: string | null;
  utm_campaign: string | null;
  utm_content: string | null;
  utm_term: string | null;
  is_active: boolean;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
}
export interface TrackingLinkCreate {
  brand_id: string;
  product_id?: string | null;
  campaign_id?: string | null;
  content_id?: string | null;
  destination_url: string;
  utm_source?: string | null;
  utm_medium?: string | null;
  utm_campaign?: string | null;
  utm_content?: string | null;
  utm_term?: string | null;
  expires_at?: string | null;
}
export interface TrackingLinkUpdate {
  destination_url?: string;
  utm_source?: string | null;
  utm_medium?: string | null;
  utm_campaign?: string | null;
  utm_content?: string | null;
  utm_term?: string | null;
  expires_at?: string | null;
  is_active?: boolean;
}

export interface CampaignSummary {
  campaign_id: string;
  campaign_name: string;
  total_clicks: number;
  unique_visitors: number;
  active_links: number;
  content_count: number;
}
export interface ContentSummary {
  content_id: string;
  content_title: string;
  total_clicks: number;
  unique_visitors: number;
  active_links: number;
}
export interface DashboardSummary {
  campaigns_total: number;
  contents_total: number;
  active_links: number;
  clicks_total: number;
  top_campaigns: CampaignSummary[];
  top_contents: ContentSummary[];
}

// -------- Phase 3 --------

export const EDITORIAL_PLATFORMS = [
  "INSTAGRAM",
  "FACEBOOK",
  "TIKTOK",
  "PINTEREST",
  "YOUTUBE",
  "LINKEDIN",
  "BLOG",
  "EMAIL",
  "OTHER",
] as const;
export type EditorialPlatform = (typeof EDITORIAL_PLATFORMS)[number];

export const CONTENT_FORMATS = [
  "REEL",
  "STORY",
  "CAROUSEL",
  "IMAGE",
  "VIDEO",
  "ARTICLE",
  "EMAIL",
  "TEXT_POST",
  "OTHER",
] as const;
export type ContentFormat = (typeof CONTENT_FORMATS)[number];

export const EDITORIAL_STATUSES = [
  "IDEA",
  "DRAFT",
  "IN_REVIEW",
  "NEEDS_REVISION",
  "APPROVED",
  "SCHEDULED",
  "PUBLISHED",
  "CANCELLED",
  "ARCHIVED",
] as const;
export type EditorialStatus = (typeof EDITORIAL_STATUSES)[number];

export const PRIORITIES = ["LOW", "MEDIUM", "HIGH", "URGENT"] as const;
export type Priority = (typeof PRIORITIES)[number];

export const REVIEW_TYPES = [
  "BRAND",
  "COPY",
  "SEO",
  "CTA",
  "VISUAL",
  "COMPLIANCE",
  "GENERAL",
] as const;
export type ReviewType = (typeof REVIEW_TYPES)[number];

export const REVIEW_DECISIONS = [
  "APPROVED",
  "NEEDS_REVISION",
  "REJECTED",
] as const;
export type ReviewDecision = (typeof REVIEW_DECISIONS)[number];

export const LEAD_SOURCES = [
  "LANDING_PAGE",
  "WHATSAPP",
  "INSTAGRAM",
  "FACEBOOK",
  "META_ADS",
  "ORGANIC",
  "REFERRAL",
  "MANUAL",
  "IMPORT",
  "OTHER",
] as const;
export type LeadSource = (typeof LEAD_SOURCES)[number];

export const LEAD_STATUSES = [
  "NEW",
  "CONTACTED",
  "QUALIFIED",
  "PROPOSAL",
  "WON",
  "LOST",
  "ARCHIVED",
] as const;
export type LeadStatus = (typeof LEAD_STATUSES)[number];

export const LEAD_ACTIVITY_TYPES = [
  "CREATED",
  "STATUS_CHANGED",
  "NOTE_ADDED",
  "CONTACT_ATTEMPT",
  "WHATSAPP_SENT",
  "EMAIL_SENT",
  "MEETING_SCHEDULED",
  "PROPOSAL_SENT",
  "WON",
  "LOST",
  "IMPORTED",
] as const;
export type LeadActivityType = (typeof LEAD_ACTIVITY_TYPES)[number];

export interface EditorialItem {
  id: string;
  public_id: string;
  content_item_id: string;
  brand_id: string;
  campaign_id: string | null;
  product_id: string | null;
  assigned_to_user_id: string | null;
  created_by_user_id: string | null;
  platform: EditorialPlatform;
  content_format: ContentFormat;
  scheduled_for: string | null;
  timezone: string;
  status: EditorialStatus;
  priority: Priority;
  notes: string | null;
  published_at: string | null;
  publication_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface EditorialItemCreate {
  content_item_id: string;
  brand_id: string;
  campaign_id?: string | null;
  product_id?: string | null;
  assigned_to_user_id?: string | null;
  platform?: EditorialPlatform;
  content_format?: ContentFormat;
  scheduled_for?: string | null;
  timezone?: string;
  status?: EditorialStatus;
  priority?: Priority;
  notes?: string | null;
}

export interface Review {
  id: string;
  public_id: string;
  content_item_id: string;
  reviewer_user_id: string | null;
  review_type: ReviewType;
  decision: ReviewDecision;
  score: number | null;
  comment: string | null;
  created_at: string;
  updated_at: string;
}

export interface Lead {
  id: string;
  public_id: string;
  brand_id: string | null;
  product_id: string | null;
  campaign_id: string | null;
  content_item_id: string | null;
  tracking_link_id: string | null;
  first_name: string;
  last_name: string | null;
  email: string | null;
  phone: string | null;
  whatsapp: string | null;
  source: LeadSource;
  status: LeadStatus;
  country: string | null;
  city: string | null;
  notes: string | null;
  utm_source: string | null;
  utm_medium: string | null;
  utm_campaign: string | null;
  utm_content: string | null;
  utm_term: string | null;
  external_id: string | null;
  source_system: string | null;
  created_at: string;
  updated_at: string;
}

export interface LeadCreate {
  first_name: string;
  last_name?: string | null;
  email?: string | null;
  phone?: string | null;
  whatsapp?: string | null;
  source?: LeadSource;
  brand_id?: string | null;
  product_id?: string | null;
  campaign_id?: string | null;
  content_item_id?: string | null;
  tracking_link_id?: string | null;
  utm_source?: string | null;
  utm_medium?: string | null;
  utm_campaign?: string | null;
  utm_content?: string | null;
  utm_term?: string | null;
  status?: LeadStatus;
  notes?: string | null;
}

export interface LeadActivity {
  id: string;
  public_id: string;
  lead_id: string;
  actor_user_id: string | null;
  activity_type: LeadActivityType;
  description: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface LeadActivityCreate {
  activity_type: LeadActivityType;
  description: string;
  metadata?: Record<string, unknown>;
}

export interface EditorialSummary {
  pending_review: number;
  scheduled_this_week: number;
  published_this_month: number;
  upcoming: Array<{
    id: string;
    public_id: string;
    platform: string;
    scheduled_for: string | null;
    status: string;
    content_item_id: string;
  }>;
}

export interface LeadsSummary {
  new_leads: number;
  qualified_leads: number;
  won_leads: number;
  lost_leads: number;
  total_leads: number;
  conversion_qualified_rate: number;
  conversion_won_rate: number;
  top_campaigns: Array<{ campaign_id: string; campaign_name: string; leads: number }>;
  top_contents: Array<{ content_id: string; content_title: string; leads: number }>;
  top_links: Array<{ tracking_link_id: string; short_code: string; leads: number }>;
}

export interface Funnel {
  clicks: number;
  unique_visitors: number;
  leads: number;
  qualified_leads: number;
  won_leads: number;
  click_to_lead_rate: number;
  lead_to_won_rate: number;
}

export interface Phase3Dashboard {
  editorial: EditorialSummary;
  leads: LeadsSummary;
}

// -------- Phase 4: AI generation --------

export const GENERATION_TYPES = [
  "SOCIAL_POST",
  "REEL_SCRIPT",
  "CAROUSEL",
  "EMAIL",
  "BLOG_OUTLINE",
  "BLOG_ARTICLE",
  "CTA_VARIATIONS",
  "CONTENT_IDEAS",
  "IMAGE_ASSET",
  "STORY",
  "VIDEO_ASSET",
  "VOICE_OVER",
] as const;
export type GenerationType = (typeof GENERATION_TYPES)[number];

export const GENERATION_STATUSES = [
  "QUEUED",
  "RUNNING",
  "COMPLETED",
  "FAILED",
  "CANCELLED",
] as const;
export type GenerationStatus = (typeof GENERATION_STATUSES)[number];

export const AI_PROVIDERS = ["ANTHROPIC", "OPENAI", "MOCK"] as const;
export type AIProvider = (typeof AI_PROVIDERS)[number];

export const COUNCIL_REVIEWER_TYPES = [
  "BRAND",
  "SEO",
  "EMOTIONAL_TONE",
  "CTA",
  "COMPLIANCE",
  "DEVILS_ADVOCATE",
] as const;
export type CouncilReviewerType = (typeof COUNCIL_REVIEWER_TYPES)[number];

export const COUNCIL_DECISIONS = [
  "APPROVED",
  "NEEDS_REVISION",
  "REJECTED",
  "BLOCKED",
] as const;
export type CouncilDecision = (typeof COUNCIL_DECISIONS)[number];

export interface GenerationInput {
  objective: string;
  platform: string;
  topic: string;
  audience?: string | null;
  cta?: string | null;
  notes?: string | null;
}

export interface GenerationJobCreate {
  brand_id: string;
  product_id?: string | null;
  campaign_id?: string | null;
  generation_type: GenerationType;
  input: GenerationInput;
  idempotency_key?: string | null;
}

export interface GeneratedContent {
  title?: string;
  hook?: string | null;
  script?: string | null;
  caption?: string | null;
  cta?: string | null;
  hashtags?: string[];
  visual_notes?: string[];
  ideas?: string[];
  stock_search_terms?: string[];
  // IMAGE_ASSET jobs return this shape instead — same output_payload field,
  // a different result kind (see app.ai.runner._run_image_generation).
  asset_id?: string;
  asset_public_id?: string;
  prompt?: string;
  // VIDEO_ASSET jobs (see app.ai.runner._run_video_generation): asset_id /
  // asset_public_id above plus the underlying script fields, and how many
  // scene images were generated.
  scene_count?: number;
}

export interface GenerationJob {
  id: string;
  public_id: string;
  brand_id: string;
  product_id: string | null;
  campaign_id: string | null;
  requested_by_user_id: string;
  generation_type: GenerationType;
  status: GenerationStatus;
  provider: AIProvider;
  model: string;
  prompt_version: string;
  input_payload: Record<string, unknown> | null;
  output_payload: GeneratedContent | null;
  error_code: string | null;
  error_message: string | null;
  stage: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost: string | null;
  started_at: string | null;
  completed_at: string | null;
  content_item_id: string | null;
  created_at: string;
  updated_at: string;
  visibility: "full" | "restricted";
}

export interface CouncilReview {
  id: string;
  public_id: string;
  generation_job_id: string;
  content_item_id: string | null;
  reviewer_type: CouncilReviewerType;
  score: number;
  decision: CouncilDecision;
  summary: string;
  issues: string[];
  recommendations: string[];
  blocking_issues: string[];
  created_at: string;
}

export interface CouncilDecisionResult {
  score: number;
  decision: CouncilDecision;
  reviews: CouncilReview[];
  issues: string[];
  recommendations: string[];
  blocking_issues: string[];
  created_at: string;
}

export interface CreateContentFromJob {
  title?: string | null;
  hook?: string | null;
  caption?: string | null;
  cta?: string | null;
}

export interface AIUsageSummary {
  jobs_total: number;
  jobs_completed: number;
  jobs_failed: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost: string;
  monthly_budget: string;
  by_provider: Record<string, number>;
  by_type: Record<string, number>;
  by_brand: Record<string, number>;
}

export interface BrandVoiceWrite {
  brand_id: string;
  audience: string;
  value_proposition: string;
  tone: string;
  preferred_terms: string[];
  forbidden_terms: string[];
  cta_style: string;
  compliance_notes: string;
  language: string;
  country: string;
  examples: string[];
  visual_style: string;
}

export interface BrandVoiceProfile extends BrandVoiceWrite {
  id: string;
  public_id: string;
  created_at: string;
  updated_at: string;
}

export interface PublicLeadSourceCreate {
  name: string;
  brand_id?: string | null;
  product_id?: string | null;
  campaign_id?: string | null;
  allowed_origins?: string[];
  expires_at?: string | null;
  default_utm_source?: string | null;
  default_utm_medium?: string | null;
  default_utm_campaign?: string | null;
}

export interface PublicLeadSource extends PublicLeadSourceCreate {
  id: string;
  public_id: string;
  public_token: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// -------- Phase 5: assets, publishing, automations --------

export const ASSET_TYPES = ["IMAGE", "VIDEO", "DOCUMENT", "AUDIO", "THUMBNAIL", "OTHER"] as const;
export type AssetType = (typeof ASSET_TYPES)[number];

export const ASSET_STATUSES = [
  "UPLOADING",
  "PROCESSING",
  "READY",
  "REJECTED",
  "FAILED",
  "ARCHIVED",
] as const;
export type AssetStatus = (typeof ASSET_STATUSES)[number];

export const STORAGE_PROVIDERS = ["LOCAL", "S3", "R2", "MOCK"] as const;
export type StorageProviderName = (typeof STORAGE_PROVIDERS)[number];

export const VARIANT_TYPES = [
  "ORIGINAL",
  "FEED",
  "PORTRAIT",
  "STORY",
  "REEL",
  "THUMBNAIL",
  "SQUARE",
  "LANDSCAPE",
  "CUSTOM",
] as const;
export type VariantType = (typeof VARIANT_TYPES)[number];

export const VARIANT_STATUSES = ["PENDING", "READY", "FAILED"] as const;
export type VariantStatus = (typeof VARIANT_STATUSES)[number];

export const CONNECTION_STATUSES = [
  "PENDING",
  "ACTIVE",
  "EXPIRED",
  "REVOKED",
  "ERROR",
  "DISABLED",
] as const;
export type ConnectionStatus = (typeof CONNECTION_STATUSES)[number];

export const PUBLISHING_PROVIDERS = [
  "MOCK",
  "MANUAL",
  "META",
  "LINKEDIN",
  "YOUTUBE",
  "TIKTOK",
  "PINTEREST",
] as const;
export type PublishingProviderName = (typeof PUBLISHING_PROVIDERS)[number];

export const PUBLICATION_STATUSES = [
  "DRAFT",
  "READY",
  "SCHEDULED",
  "PUBLISHING",
  "PUBLISHED",
  "FAILED",
  "RETRY_SCHEDULED",
  "CANCELLED",
  "ARCHIVED",
] as const;
export type PublicationStatus = (typeof PUBLICATION_STATUSES)[number];

export const PUBLICATION_TYPES = [
  "POST",
  "REEL",
  "STORY",
  "CAROUSEL",
  "VIDEO",
  "ARTICLE",
  "EMAIL",
  "OTHER",
] as const;
export type PublicationType = (typeof PUBLICATION_TYPES)[number];

export const ATTEMPT_STATUSES = ["STARTED", "SUCCEEDED", "FAILED", "RATE_LIMITED", "CANCELLED"] as const;
export type AttemptStatus = (typeof ATTEMPT_STATUSES)[number];

export const AUTOMATION_TRIGGER_TYPES = [
  "CONTENT_APPROVED",
  "CALENDAR_ITEM_DUE",
  "PUBLICATION_FAILED",
  "LEAD_CREATED",
  "LEAD_STATUS_CHANGED",
] as const;
export type AutomationTriggerType = (typeof AUTOMATION_TRIGGER_TYPES)[number];

export const AUTOMATION_ACTION_TYPES = [
  "CREATE_PUBLICATION_DRAFT",
  "GENERATE_TRACKING_LINK",
  "SCHEDULE_RETRY",
  "CREATE_LEAD_ACTIVITY",
  "SEND_INTERNAL_NOTIFICATION",
] as const;
export type AutomationActionType = (typeof AUTOMATION_ACTION_TYPES)[number];

export const NOTIFICATION_TYPES = [
  "CONTENT_APPROVED",
  "PUBLICATION_UPCOMING",
  "PUBLICATION_SUCCEEDED",
  "PUBLICATION_FAILED",
  "ASSET_REJECTED",
  "CONNECTION_EXPIRED",
  "AI_BUDGET_NEAR_LIMIT",
  "LEAD_WON",
] as const;
export type NotificationType = (typeof NOTIFICATION_TYPES)[number];

export interface Asset {
  id: string;
  public_id: string;
  brand_id: string | null;
  product_id: string | null;
  content_item_id: string | null;
  uploaded_by_user_id: string | null;
  asset_type: AssetType;
  status: AssetStatus;
  storage_provider: StorageProviderName;
  original_filename: string;
  safe_filename: string;
  mime_type: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  checksum_sha256: string;
  alt_text: string | null;
  caption: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface InitUploadRequest {
  filename: string;
  mime_type: string;
  size_bytes: number;
  asset_type: AssetType;
  brand_id?: string | null;
  product_id?: string | null;
  content_item_id?: string | null;
  alt_text?: string | null;
  caption?: string | null;
}

export interface InitUploadResponse {
  asset_id: string;
  storage_provider: StorageProviderName;
  upload_method: string;
  max_size_bytes: number;
}

export interface AssetUpdate {
  alt_text?: string | null;
  caption?: string | null;
  content_item_id?: string | null;
  brand_id?: string | null;
  product_id?: string | null;
}

export interface SignedUrlResponse {
  url: string;
  expires_in_seconds: number;
}

export interface AssetVariant {
  id: string;
  public_id: string;
  asset_id: string;
  platform: string;
  variant_type: VariantType;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  mime_type: string;
  size_bytes: number;
  status: VariantStatus;
  transformation_spec: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AssetVariantCreate {
  platform: string;
  variant_type: VariantType;
  width?: number | null;
  height?: number | null;
  duration_seconds?: number | null;
}

export type ThumbnailFormat = "vertical" | "facebook_horizontal";
export type ThumbnailContentStyle =
  | "receta"
  | "curiosidad"
  | "encuesta"
  | "antes_despues"
  | "receta_rapida"
  | "educativo";

export interface GenerateThumbnailRequest {
  title: string;
  subtitle?: string | null;
  benefits?: string[];
  cta_banner?: string | null;
  content_style?: ThumbnailContentStyle | null;
  format?: ThumbnailFormat;
}

export interface PublishingConnection {
  id: string;
  public_id: string;
  brand_id: string;
  platform: Platform;
  provider: PublishingProviderName;
  account_name: string;
  external_account_id: string | null;
  status: ConnectionStatus;
  capabilities: string[];
  credentials_last_four: string | null;
  token_expires_at: string | null;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PublishingConnectionCreate {
  brand_id: string;
  platform: Platform;
  provider: PublishingProviderName;
  account_name: string;
  external_account_id?: string | null;
  capabilities?: string[];
  credentials?: Record<string, unknown> | null;
  token_expires_at?: string | null;
}

export interface PublishingConnectionUpdate {
  account_name?: string;
  capabilities?: string[];
  credentials?: Record<string, unknown> | null;
  token_expires_at?: string | null;
}

export interface Publication {
  id: string;
  public_id: string;
  content_item_id: string;
  editorial_calendar_item_id: string | null;
  brand_id: string;
  campaign_id: string | null;
  product_id: string | null;
  publishing_connection_id: string;
  asset_id: string | null;
  asset_variant_id: string | null;
  platform: Platform;
  publication_type: PublicationType;
  status: PublicationStatus;
  caption: string;
  title: string | null;
  cta: string | null;
  hashtags: string[];
  scheduled_for: string | null;
  timezone: string;
  external_publication_id: string | null;
  external_url: string | null;
  published_at: string | null;
  failure_code: string | null;
  failure_message: string | null;
  attempt_count: number;
  next_retry_at: string | null;
  idempotency_key: string;
  created_by_user_id: string | null;
  approved_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface PublicationCreate {
  content_item_id: string;
  editorial_calendar_item_id?: string | null;
  brand_id: string;
  campaign_id?: string | null;
  product_id?: string | null;
  publishing_connection_id: string;
  asset_id?: string | null;
  asset_variant_id?: string | null;
  platform: Platform;
  publication_type: PublicationType;
  caption?: string;
  title?: string | null;
  cta?: string | null;
  hashtags?: string[];
  idempotency_key?: string | null;
}

export interface PublicationUpdate {
  caption?: string;
  title?: string | null;
  cta?: string | null;
  hashtags?: string[];
  asset_id?: string | null;
  asset_variant_id?: string | null;
}

export interface ValidationResult {
  ok: boolean;
  errors: string[];
  warnings: string[];
}

export interface PublicationAttempt {
  id: string;
  public_id: string;
  publication_id: string;
  attempt_number: number;
  provider: PublishingProviderName;
  status: AttemptStatus;
  request_summary: Record<string, unknown>;
  response_summary: Record<string, unknown>;
  external_id: string | null;
  error_code: string | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
}

export interface PublishingSummary {
  scheduled: number;
  published: number;
  failed: number;
  success_rate: number;
  retries: number;
  by_platform: Record<string, number>;
  upcoming_7_days: number;
  connections_with_error: number;
}

export interface AutomationRule {
  id: string;
  public_id: string;
  brand_id: string | null;
  name: string;
  trigger_type: AutomationTriggerType;
  conditions: Record<string, unknown>;
  action_type: AutomationActionType;
  action_config: Record<string, unknown>;
  is_active: boolean;
  created_by_user_id: string | null;
  execution_count: number;
  last_executed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AutomationRuleCreate {
  brand_id?: string | null;
  name: string;
  trigger_type: AutomationTriggerType;
  conditions?: Record<string, unknown>;
  action_type: AutomationActionType;
  action_config?: Record<string, unknown>;
  is_active?: boolean;
}

export interface AutomationRuleUpdate {
  name?: string;
  conditions?: Record<string, unknown>;
  action_config?: Record<string, unknown>;
  is_active?: boolean;
}

export interface AutomationSummary {
  active_rules: number;
  total_executions: number;
  loop_preventions: number;
}

export interface Notification {
  id: string;
  public_id: string;
  user_id: string;
  notification_type: NotificationType;
  title: string;
  message: string;
  resource_type: string | null;
  resource_public_id: string | null;
  read_at: string | null;
  created_at: string;
}
