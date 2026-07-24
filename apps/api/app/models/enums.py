from __future__ import annotations

import enum


class ProductStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class CampaignStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"


class CampaignObjective(str, enum.Enum):
    AWARENESS = "AWARENESS"
    TRAFFIC = "TRAFFIC"
    LEAD_GEN = "LEAD_GEN"
    SALES = "SALES"
    ENGAGEMENT = "ENGAGEMENT"
    OTHER = "OTHER"


class Platform(str, enum.Enum):
    INSTAGRAM = "INSTAGRAM"
    FACEBOOK = "FACEBOOK"
    TIKTOK = "TIKTOK"
    YOUTUBE = "YOUTUBE"
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    WEB = "WEB"
    META_ADS = "META_ADS"
    OTHER = "OTHER"


class ContentType(str, enum.Enum):
    POST = "POST"
    REEL = "REEL"
    STORY = "STORY"
    VIDEO = "VIDEO"
    ARTICLE = "ARTICLE"
    AD = "AD"
    OTHER = "OTHER"


class ContentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class SourceSystem(str, enum.Enum):
    MANUAL = "MANUAL"
    KINGDOM_STUDIO = "KINGDOM_STUDIO"
    IMPORT = "IMPORT"


class EditorialPlatform(str, enum.Enum):
    """Editorial calendar target platforms. Overlaps with Platform on purpose —
    editorial items may include LinkedIn/Pinterest/Blog which aren't tracked as
    ad platforms elsewhere."""
    INSTAGRAM = "INSTAGRAM"
    FACEBOOK = "FACEBOOK"
    TIKTOK = "TIKTOK"
    PINTEREST = "PINTEREST"
    YOUTUBE = "YOUTUBE"
    LINKEDIN = "LINKEDIN"
    BLOG = "BLOG"
    EMAIL = "EMAIL"
    OTHER = "OTHER"


class ContentFormat(str, enum.Enum):
    REEL = "REEL"
    STORY = "STORY"
    CAROUSEL = "CAROUSEL"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    ARTICLE = "ARTICLE"
    EMAIL = "EMAIL"
    TEXT_POST = "TEXT_POST"
    OTHER = "OTHER"


class EditorialStatus(str, enum.Enum):
    IDEA = "IDEA"
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    NEEDS_REVISION = "NEEDS_REVISION"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    PUBLISHED = "PUBLISHED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class Priority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class ReviewType(str, enum.Enum):
    BRAND = "BRAND"
    COPY = "COPY"
    SEO = "SEO"
    CTA = "CTA"
    VISUAL = "VISUAL"
    COMPLIANCE = "COMPLIANCE"
    GENERAL = "GENERAL"


class ReviewDecision(str, enum.Enum):
    APPROVED = "APPROVED"
    NEEDS_REVISION = "NEEDS_REVISION"
    REJECTED = "REJECTED"


class LeadSource(str, enum.Enum):
    LANDING_PAGE = "LANDING_PAGE"
    WHATSAPP = "WHATSAPP"
    INSTAGRAM = "INSTAGRAM"
    FACEBOOK = "FACEBOOK"
    META_ADS = "META_ADS"
    ORGANIC = "ORGANIC"
    REFERRAL = "REFERRAL"
    MANUAL = "MANUAL"
    IMPORT = "IMPORT"
    OTHER = "OTHER"


class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    PROPOSAL = "PROPOSAL"
    WON = "WON"
    LOST = "LOST"
    ARCHIVED = "ARCHIVED"


class LeadActivityType(str, enum.Enum):
    CREATED = "CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    NOTE_ADDED = "NOTE_ADDED"
    CONTACT_ATTEMPT = "CONTACT_ATTEMPT"
    WHATSAPP_SENT = "WHATSAPP_SENT"
    EMAIL_SENT = "EMAIL_SENT"
    MEETING_SCHEDULED = "MEETING_SCHEDULED"
    PROPOSAL_SENT = "PROPOSAL_SENT"
    WON = "WON"
    LOST = "LOST"
    IMPORTED = "IMPORTED"


class GenerationType(str, enum.Enum):
    SOCIAL_POST = "SOCIAL_POST"
    REEL_SCRIPT = "REEL_SCRIPT"
    CAROUSEL = "CAROUSEL"
    EMAIL = "EMAIL"
    BLOG_OUTLINE = "BLOG_OUTLINE"
    BLOG_ARTICLE = "BLOG_ARTICLE"
    CTA_VARIATIONS = "CTA_VARIATIONS"
    CONTENT_IDEAS = "CONTENT_IDEAS"
    IMAGE_ASSET = "IMAGE_ASSET"


class GenerationStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AIProvider(str, enum.Enum):
    ANTHROPIC = "ANTHROPIC"
    OPENAI = "OPENAI"
    MOCK = "MOCK"


class CouncilReviewerType(str, enum.Enum):
    BRAND = "BRAND"
    SEO = "SEO"
    EMOTIONAL_TONE = "EMOTIONAL_TONE"
    CTA = "CTA"
    COMPLIANCE = "COMPLIANCE"
    DEVILS_ADVOCATE = "DEVILS_ADVOCATE"


class CouncilDecision(str, enum.Enum):
    APPROVED = "APPROVED"
    NEEDS_REVISION = "NEEDS_REVISION"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


# ---------- Phase 5: assets, publishing, automations ----------

class AssetType(str, enum.Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    DOCUMENT = "DOCUMENT"
    AUDIO = "AUDIO"
    THUMBNAIL = "THUMBNAIL"
    OTHER = "OTHER"


class AssetStatus(str, enum.Enum):
    UPLOADING = "UPLOADING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class StorageProviderName(str, enum.Enum):
    LOCAL = "LOCAL"
    S3 = "S3"
    R2 = "R2"
    MOCK = "MOCK"


class VariantType(str, enum.Enum):
    ORIGINAL = "ORIGINAL"
    FEED = "FEED"
    PORTRAIT = "PORTRAIT"
    STORY = "STORY"
    REEL = "REEL"
    THUMBNAIL = "THUMBNAIL"
    SQUARE = "SQUARE"
    LANDSCAPE = "LANDSCAPE"
    CUSTOM = "CUSTOM"


class VariantStatus(str, enum.Enum):
    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"


class ConnectionStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    ERROR = "ERROR"
    DISABLED = "DISABLED"


class PublishingProviderName(str, enum.Enum):
    MOCK = "MOCK"
    MANUAL = "MANUAL"
    META = "META"
    LINKEDIN = "LINKEDIN"
    YOUTUBE = "YOUTUBE"
    TIKTOK = "TIKTOK"
    PINTEREST = "PINTEREST"


class PublicationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    SCHEDULED = "SCHEDULED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class PublicationType(str, enum.Enum):
    POST = "POST"
    REEL = "REEL"
    STORY = "STORY"
    CAROUSEL = "CAROUSEL"
    VIDEO = "VIDEO"
    ARTICLE = "ARTICLE"
    EMAIL = "EMAIL"
    OTHER = "OTHER"


class AttemptStatus(str, enum.Enum):
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    CANCELLED = "CANCELLED"


class AutomationTriggerType(str, enum.Enum):
    CONTENT_APPROVED = "CONTENT_APPROVED"
    CALENDAR_ITEM_DUE = "CALENDAR_ITEM_DUE"
    PUBLICATION_FAILED = "PUBLICATION_FAILED"
    LEAD_CREATED = "LEAD_CREATED"
    LEAD_STATUS_CHANGED = "LEAD_STATUS_CHANGED"


class AutomationActionType(str, enum.Enum):
    CREATE_PUBLICATION_DRAFT = "CREATE_PUBLICATION_DRAFT"
    GENERATE_TRACKING_LINK = "GENERATE_TRACKING_LINK"
    SCHEDULE_RETRY = "SCHEDULE_RETRY"
    CREATE_LEAD_ACTIVITY = "CREATE_LEAD_ACTIVITY"
    SEND_INTERNAL_NOTIFICATION = "SEND_INTERNAL_NOTIFICATION"


class NotificationType(str, enum.Enum):
    CONTENT_APPROVED = "CONTENT_APPROVED"
    PUBLICATION_UPCOMING = "PUBLICATION_UPCOMING"
    PUBLICATION_SUCCEEDED = "PUBLICATION_SUCCEEDED"
    PUBLICATION_FAILED = "PUBLICATION_FAILED"
    ASSET_REJECTED = "ASSET_REJECTED"
    CONNECTION_EXPIRED = "CONNECTION_EXPIRED"
    AI_BUDGET_NEAR_LIMIT = "AI_BUDGET_NEAR_LIMIT"
    LEAD_WON = "LEAD_WON"
