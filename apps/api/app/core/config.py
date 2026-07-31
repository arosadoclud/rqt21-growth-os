from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str | None:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / ".env"
        if candidate.exists():
            return str(candidate)
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg://rqt:rqt@localhost:5432/rqt",
        alias="DATABASE_URL",
    )
    test_database_url: str | None = Field(default=None, alias="TEST_DATABASE_URL")

    jwt_secret: str = Field(default="dev-insecure-secret-change-me", alias="JWT_SECRET")
    ip_hash_secret: str = Field(default="", alias="IP_HASH_SECRET")
    tracking_base_url: str = Field(
        default="http://localhost:8000", alias="TRACKING_BASE_URL"
    )
    jwt_access_ttl_seconds: int = Field(default=900, alias="JWT_ACCESS_TTL_SECONDS")
    jwt_refresh_ttl_seconds: int = Field(default=60 * 60 * 24 * 30, alias="JWT_REFRESH_TTL_SECONDS")

    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    cookie_domain: str | None = Field(default=None, alias="COOKIE_DOMAIN")
    cookie_samesite: str = Field(default="lax", alias="COOKIE_SAMESITE")  # lax|strict|none

    # Rate limits
    rl_login_ip_limit: int = Field(default=10, alias="RL_LOGIN_IP_LIMIT")
    rl_login_email_limit: int = Field(default=5, alias="RL_LOGIN_EMAIL_LIMIT")
    rl_login_window_seconds: int = Field(default=60, alias="RL_LOGIN_WINDOW_SECONDS")
    rl_refresh_ip_limit: int = Field(default=60, alias="RL_REFRESH_IP_LIMIT")
    rl_refresh_window_seconds: int = Field(default=60, alias="RL_REFRESH_WINDOW_SECONDS")

    # Public endpoints
    public_lead_rate_limit: int = Field(default=20, alias="PUBLIC_LEAD_RATE_LIMIT")
    public_lead_window_seconds: int = Field(default=60, alias="PUBLIC_LEAD_WINDOW_SECONDS")
    public_redirect_rate_limit: int = Field(default=600, alias="PUBLIC_REDIRECT_RATE_LIMIT")
    public_redirect_window_seconds: int = Field(
        default=60, alias="PUBLIC_REDIRECT_WINDOW_SECONDS"
    )
    lead_dedup_window_minutes: int = Field(default=10, alias="LEAD_DEDUP_WINDOW_MINUTES")

    # Assisted editorial generation. Secrets remain process-only.
    ai_provider: str = Field(default="MOCK", alias="AI_PROVIDER")
    ai_model: str = Field(default="mock-editorial-v1", alias="AI_MODEL")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY", repr=False)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY", repr=False)
    # Portrait image generation (1024x1536) routinely takes 45-70s — the
    # old 45s default worked for square images but timed out portrait ones.
    ai_request_timeout_seconds: int = Field(default=90, alias="AI_REQUEST_TIMEOUT_SECONDS")
    # The default text schema always asks for title+hook+script+caption+cta
    # plus hashtags/visual_notes/stock_search_terms arrays, even for
    # generation types (SOCIAL_POST, STORY) that don't strictly need a
    # script. In Spanish that routinely runs 1800-2200 tokens — the old
    # 2000 default got cut mid-JSON on real content (confirmed via a direct
    # repro against the real Anthropic provider), which read to users as
    # "La IA no pudo generar el texto: provider output failed schema
    # validation" with no indication it was a truncation, not a real
    # failure. 3200 leaves real headroom without materially changing cost
    # (tokens are billed on what's actually generated, not the cap).
    ai_max_output_tokens: int = Field(default=3200, alias="AI_MAX_OUTPUT_TOKENS")
    ai_monthly_budget_usd: float = Field(default=100.0, alias="AI_MONTHLY_BUDGET_USD")
    ai_daily_job_limit_per_org: int = Field(default=100, alias="AI_DAILY_JOB_LIMIT_PER_ORG")
    ai_daily_job_limit_per_user: int = Field(default=30, alias="AI_DAILY_JOB_LIMIT_PER_USER")
    ai_image_provider: str = Field(default="MOCK", alias="AI_IMAGE_PROVIDER")
    # Free, keyless zero-cost fallback (Pollinations.ai) used when the
    # primary image provider hits a rate limit or quota error — never
    # activates on its own, only when explicitly set and different from
    # ai_image_provider (same "flag beyond the key" convention as the rest
    # of this codebase).
    ai_image_fallback_provider: str = Field(default="", alias="AI_IMAGE_FALLBACK_PROVIDER")
    openai_image_model: str = Field(default="gpt-image-1", alias="OPENAI_IMAGE_MODEL")
    # Portrait by default — brand flyers are designed as vertical posts/reels
    # (4:5, 9:16); a square canvas made headline text overflow the top edge
    # since the prompt asks for a vertical composition the canvas couldn't fit.
    ai_image_size: str = Field(default="1024x1536", alias="AI_IMAGE_SIZE")
    # gpt-image-1 defaults to "auto" quality if unset, which is noticeably
    # worse at rendering legible text (titles, logos) than "high" — the
    # ChatGPT product always requests high quality, which is part of why
    # images generated there look sharper than the API default. "high"
    # costs more per image and is slower; not configurable per-brand today.
    ai_image_quality: str = Field(default="high", alias="AI_IMAGE_QUALITY")

    # Video generation (VIDEO_ASSET): script via ai_provider (above), one
    # image per scene via ai_image_provider (above), narration via a TTS
    # provider gated behind its own flag (same "never activates on the key
    # alone" convention), assembled into an MP4 with a bundled ffmpeg build
    # (imageio-ffmpeg — no system package required).
    ai_tts_provider: str = Field(default="MOCK", alias="AI_TTS_PROVIDER")
    # Free fallback voice (ElevenLabs, 10k chars/month free tier) used when
    # the primary TTS provider hits a quota/outage error — same opt-in
    # convention as ai_image_fallback_provider above.
    ai_tts_fallback_provider: str = Field(default="", alias="AI_TTS_FALLBACK_PROVIDER")
    openai_tts_model: str = Field(default="gpt-4o-mini-tts", alias="OPENAI_TTS_MODEL")
    # "nova" reads Spanish narration naturally and consistently as a female
    # voice — every generated video should sound like the same narrator.
    openai_tts_voice: str = Field(default="nova", alias="OPENAI_TTS_VOICE")
    elevenlabs_api_key: str = Field(default="", alias="ELEVENLABS_API_KEY", repr=False)
    # "Jessica" — a free-tier premade voice (ElevenLabs' Spanish shared-library
    # voices require a paid plan even once added to the account's own
    # collection). Not a native Spanish accent, but the multilingual model
    # still reads Spanish narration naturally.
    elevenlabs_voice_id: str = Field(default="cgSgspJ2msm6clMCkdW9", alias="ELEVENLABS_VOICE_ID")
    ai_video_max_scenes: int = Field(default=5, alias="AI_VIDEO_MAX_SCENES")
    # STOCK_FOOTAGE: real licensed clips of people/food prep per scene
    # (Pexels). IMAGES (default): the original AI-generated-stills slideshow.
    ai_video_scene_source: str = Field(default="IMAGES", alias="AI_VIDEO_SCENE_SOURCE")
    pexels_api_key: str = Field(default="", alias="PEXELS_API_KEY", repr=False)

    # Asset storage
    storage_provider: str = Field(default="LOCAL", alias="STORAGE_PROVIDER")
    storage_bucket: str = Field(default="", alias="STORAGE_BUCKET")
    storage_region: str = Field(default="", alias="STORAGE_REGION")
    storage_endpoint: str = Field(default="", alias="STORAGE_ENDPOINT")
    storage_access_key: str = Field(default="", alias="STORAGE_ACCESS_KEY", repr=False)
    storage_secret_key: str = Field(default="", alias="STORAGE_SECRET_KEY", repr=False)
    asset_signed_url_ttl_seconds: int = Field(
        default=300, alias="ASSET_SIGNED_URL_TTL_SECONDS"
    )
    asset_max_image_mb: int = Field(default=15, alias="ASSET_MAX_IMAGE_MB")
    asset_max_video_mb: int = Field(default=250, alias="ASSET_MAX_VIDEO_MB")
    asset_max_document_mb: int = Field(default=25, alias="ASSET_MAX_DOCUMENT_MB")

    # Publishing / retries
    publish_max_attempts: int = Field(default=5, alias="PUBLISH_MAX_ATTEMPTS")
    publish_retry_base_seconds: int = Field(default=60, alias="PUBLISH_RETRY_BASE_SECONDS")
    publish_retry_max_seconds: int = Field(default=3600, alias="PUBLISH_RETRY_MAX_SECONDS")
    credentials_encryption_key: str = Field(
        default="", alias="CREDENTIALS_ENCRYPTION_KEY", repr=False
    )
    meta_access_token: str = Field(default="", alias="META_ACCESS_TOKEN", repr=False)
    automation_max_executions_per_rule: int = Field(
        default=1000, alias="AUTOMATION_MAX_EXECUTIONS_PER_RULE"
    )

    # Security
    trusted_hosts: str = Field(default="*", alias="TRUSTED_HOSTS")
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # Phase 6A — distributed infrastructure (all default to the
    # in-process/mock backends used since Phase 1-5; switching to the
    # distributed backend is opt-in via env vars, never automatic).
    redis_url: str = Field(default="", alias="REDIS_URL")
    queue_backend: str = Field(default="inline", alias="QUEUE_BACKEND")  # inline|redis
    scheduler_backend: str = Field(default="memory", alias="SCHEDULER_BACKEND")  # memory|redis
    error_reporter: str = Field(default="none", alias="ERROR_REPORTER")  # none|sentry
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN", repr=False)
    secrets_provider: str = Field(default="env", alias="SECRETS_PROVIDER")  # env only for now
    log_format: str = Field(default="text", alias="LOG_FORMAT")  # text|json

    # Meta OAuth (Phase 6B fills these in; absent = adapter stays dormant).
    meta_app_id: str = Field(default="", alias="META_APP_ID")
    meta_app_secret: str = Field(default="", alias="META_APP_SECRET", repr=False)
    meta_oauth_redirect_uri: str = Field(default="", alias="META_OAUTH_REDIRECT_URI")
    meta_webhook_verify_token: str = Field(
        default="", alias="META_WEBHOOK_VERIFY_TOKEN", repr=False
    )
    meta_graph_api_version: str = Field(default="v21.0", alias="META_GRAPH_API_VERSION")
    meta_publishing_enabled: bool = Field(default=False, alias="META_PUBLISHING_ENABLED")

    # Auto-approval agent (opt-in). NEVER enable in production unless you
    # intentionally want machine decisions to approve/reject editorial
    # content. Defaults to False.
    enable_auto_approval: bool = Field(default=False, alias="ENABLE_AUTO_APPROVAL")
    # Score thresholds (0-100) for the auto-approval decision. If the
    # council aggregate score >= approve_threshold -> auto-approve. If
    # <= reject_threshold -> auto-reject. Otherwise the content will be
    # marked CHANGES_REQUESTED.
    # NOTE: the six reviewers in app.ai.council each start from a fixed base
    # score below 100 (92/90/93/91/100/86) and only ever subtract points, so
    # the highest average a perfect submission can ever reach is exactly
    # 92.0 — a threshold of 95 (the old default) was mathematically
    # unreachable and silently made auto-approval a no-op that could only
    # ever reject or request changes. 88 sits just below that real ceiling.
    auto_approval_approve_threshold: int = Field(default=88, alias="AUTO_APPROVAL_APPROVE_THRESHOLD")
    auto_approval_reject_threshold: int = Field(default=60, alias="AUTO_APPROVAL_REJECT_THRESHOLD")

    @property
    def trusted_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_staging(self) -> bool:
        return self.environment.lower() == "staging"

    def production_config_errors(self) -> list[str]:
        """Hard requirements before this process is allowed to serve
        production traffic. Called once at startup (see app.main); never
        silently downgrades a misconfigured production deploy to insecure
        defaults."""
        errors: list[str] = []
        if self.jwt_secret in ("", "dev-insecure-secret-change-me") or len(self.jwt_secret) < 32:
            errors.append("JWT_SECRET must be set to a long random value")
        if not self.cookie_secure:
            errors.append("COOKIE_SECURE must be true in production")
        if "*" in self.cors_origins_list:
            errors.append("CORS_ORIGINS must not include '*' in production")
        if not self.credentials_encryption_key:
            errors.append("CREDENTIALS_ENCRYPTION_KEY must be set in production")
        if self.storage_provider.upper() in ("LOCAL", "MOCK"):
            errors.append("STORAGE_PROVIDER must be S3 or R2 in production")
        if self.queue_backend == "redis" and not self.redis_url:
            errors.append("REDIS_URL is required when QUEUE_BACKEND=redis")
        if self.scheduler_backend == "redis" and not self.redis_url:
            errors.append("REDIS_URL is required when SCHEDULER_BACKEND=redis")
        return errors

    seed_owner_email: str = Field(default="owner@rqt21.dev", alias="SEED_OWNER_EMAIL")
    seed_owner_password: str = Field(default="Owner!2026Local", alias="SEED_OWNER_PASSWORD")
    seed_owner_name: str = Field(default="RQT21 Owner", alias="SEED_OWNER_NAME")
    seed_org_name: str = Field(default="RQT21", alias="SEED_ORG_NAME")
    seed_org_slug: str = Field(default="rqt21", alias="SEED_ORG_SLUG")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
