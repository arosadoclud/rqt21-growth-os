from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.council import aggregate, run_council
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.ai import BrandVoiceProfile, CouncilReview, GenerationJob, PublicLeadSource
from app.models.assets import Asset, AssetVariant
from app.models.automation import AutomationRule, Notification
from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.content import ContentItem
from app.models.editorial import EditorialCalendarItem, Review
from app.models.enums import (
    AIProvider,
    AssetStatus,
    AssetType,
    AttemptStatus,
    AutomationActionType,
    AutomationTriggerType,
    CampaignObjective,
    CampaignStatus,
    ConnectionStatus,
    ContentFormat,
    ContentStatus,
    ContentType,
    EditorialPlatform,
    EditorialStatus,
    GenerationStatus,
    GenerationType,
    LeadActivityType,
    LeadSource,
    LeadStatus,
    NotificationType,
    Platform,
    Priority,
    ProductStatus,
    PublicationStatus,
    PublicationType,
    PublishingProviderName,
    ReviewDecision,
    ReviewType,
    SourceSystem,
    StorageProviderName,
    VariantStatus,
    VariantType,
)
from app.models.lead import Lead, LeadActivity
from app.models.membership import Membership, Role
from app.models.organization import Organization
from app.models.product import Product
from app.models.publishing import Publication, PublicationAttempt, PublishingConnection
from app.models.tracking import TrackingLink
from app.models.user import User
from app.publishing.crypto import encrypt_credentials
from app.utils.phone import InvalidPhoneNumber, normalize_phone
from app.utils.public_id import make as make_public_id
from app.utils.public_token import generate as generate_token
from app.utils.short_code import generate as generate_short_code


def _get_or_create_org(db: Session) -> Organization:
    org = db.execute(
        select(Organization).where(Organization.slug == settings.seed_org_slug)
    ).scalar_one_or_none()
    if org is None:
        org = Organization(
            name=settings.seed_org_name,
            slug=settings.seed_org_slug,
            country_code="DO",
            timezone="America/Santo_Domingo",
            currency="USD",
        )
        db.add(org)
        db.flush()
        print(f"[seed] org {org.slug}")
    elif org.country_code != "DO" or org.timezone != "America/Santo_Domingo":
        org.country_code = "DO"
        org.timezone = "America/Santo_Domingo"
        org.currency = org.currency or "USD"
        db.flush()
    return org


def _get_or_create_owner(db: Session, org: Organization) -> User:
    user = db.execute(
        select(User).where(User.email == settings.seed_owner_email.lower())
    ).scalar_one_or_none()
    if user is None:
        user = User(
            email=settings.seed_owner_email.lower(),
            full_name=settings.seed_owner_name,
            password_hash=hash_password(settings.seed_owner_password),
        )
        db.add(user)
        db.flush()
        print(f"[seed] user {user.email}")

    m = db.execute(
        select(Membership).where(
            Membership.user_id == user.id, Membership.organization_id == org.id
        )
    ).scalar_one_or_none()
    if m is None:
        db.add(Membership(user_id=user.id, organization_id=org.id, role=Role.OWNER))
        print(f"[seed] OWNER {user.email} @ {org.slug}")
    return user


def _get_or_create_brand(db: Session, org: Organization) -> Brand:
    brand = db.execute(
        select(Brand).where(
            Brand.organization_id == org.id, Brand.slug == "recetas-que-transforman-21"
        )
    ).scalar_one_or_none()
    if brand is None:
        brand = Brand(
            organization_id=org.id,
            public_id=make_public_id("br"),
            name="Recetas Que Transforman 21",
            slug="recetas-que-transforman-21",
            description="Sistema de recetas keto para transformar tu salud en 21 días.",
        )
        db.add(brand)
        db.flush()
        print(f"[seed] brand {brand.slug}")
    return brand


def _get_or_create_product(db: Session, org: Organization, brand: Brand) -> Product:
    p = db.execute(
        select(Product).where(
            Product.organization_id == org.id, Product.slug == "120-recetas-transforma-21"
        )
    ).scalar_one_or_none()
    if p is None:
        p = Product(
            organization_id=org.id,
            brand_id=brand.id,
            public_id=make_public_id("pr"),
            name="120 Recetas + Acompañamiento por WhatsApp",
            slug="120-recetas-transforma-21",
            description="Programa completo: 120 recetas keto + acompañamiento por WhatsApp durante 21 días.",
            price=Decimal("97.00"),
            currency="USD",
            checkout_url="https://checkout.example.com/rqt21-120",
            status=ProductStatus.ACTIVE,
        )
        db.add(p)
        db.flush()
        print(f"[seed] product {p.slug}")
    return p


def _campaign(
    db: Session,
    org: Organization,
    brand: Brand,
    product: Product,
    slug: str,
    name: str,
    platform: Platform,
    objective: CampaignObjective,
) -> Campaign:
    c = db.execute(
        select(Campaign).where(
            Campaign.organization_id == org.id, Campaign.slug == slug
        )
    ).scalar_one_or_none()
    if c is None:
        c = Campaign(
            organization_id=org.id,
            brand_id=brand.id,
            product_id=product.id,
            public_id=make_public_id("cm"),
            name=name,
            slug=slug,
            objective=objective,
            platform=platform,
            status=CampaignStatus.ACTIVE,
        )
        db.add(c)
        db.flush()
        print(f"[seed] campaign {c.slug}")
    return c


def _content(
    db: Session,
    org: Organization,
    brand: Brand,
    campaign: Campaign,
    product: Product,
    slug_hint: str,
    title: str,
) -> ContentItem:
    external = f"seed-{slug_hint}"
    c = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == org.id,
            ContentItem.source_system == SourceSystem.MANUAL,
            ContentItem.external_id == external,
        )
    ).scalar_one_or_none()
    if c is None:
        c = ContentItem(
            organization_id=org.id,
            brand_id=brand.id,
            campaign_id=campaign.id,
            product_id=product.id,
            public_id=make_public_id("ct"),
            external_id=external,
            source_system=SourceSystem.MANUAL,
            platform=campaign.platform,
            content_type=ContentType.REEL,
            title=title,
            hook="Descubre cómo transformar tu alimentación",
            caption=None,
            cta="Ver recetas",
            status=ContentStatus.PUBLISHED,
        )
        db.add(c)
        db.flush()
        print(f"[seed] content {external}")
    return c


def _link(
    db: Session,
    org: Organization,
    brand: Brand,
    campaign: Campaign,
    content: ContentItem,
    product: Product,
) -> TrackingLink:
    existing = db.execute(
        select(TrackingLink).where(
            TrackingLink.organization_id == org.id,
            TrackingLink.content_id == content.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    for _ in range(6):
        code = generate_short_code()
        clash = db.execute(
            select(TrackingLink.id).where(TrackingLink.short_code == code)
        ).scalar_one_or_none()
        if clash is None:
            break
    else:
        raise RuntimeError("short_code collision during seed")

    link = TrackingLink(
        organization_id=org.id,
        brand_id=brand.id,
        product_id=product.id,
        campaign_id=campaign.id,
        content_id=content.id,
        public_id=make_public_id("tl"),
        short_code=code,
        destination_url=product.checkout_url or "https://example.com/checkout",
        utm_source=campaign.platform.value.lower(),
        utm_medium="social",
        utm_campaign=campaign.slug,
        utm_content=content.external_id or content.public_id,
    )
    db.add(link)
    db.flush()
    print(f"[seed] link {link.short_code} -> {content.title}")
    return link


def seed(db: Session) -> None:
    org = _get_or_create_org(db)
    owner = _get_or_create_owner(db, org)
    brand = _get_or_create_brand(db, org)
    product = _get_or_create_product(db, org, brand)

    ig = _campaign(
        db, org, brand, product,
        "instagram-organico",
        "Instagram Orgánico",
        Platform.INSTAGRAM,
        CampaignObjective.AWARENESS,
    )
    fb = _campaign(
        db, org, brand, product,
        "facebook-organico",
        "Facebook Orgánico",
        Platform.FACEBOOK,
        CampaignObjective.AWARENESS,
    )
    meta = _campaign(
        db, org, brand, product,
        "meta-ads-lanzamiento",
        "Meta Ads Lanzamiento",
        Platform.META_ADS,
        CampaignObjective.SALES,
    )

    contents = [
        (ig, "lasana-keto-de-calabacin", "Lasaña Keto de Calabacín"),
        (ig, "pizza-keto-de-brocoli", "Pizza Keto de Brócoli"),
        (fb, "bowl-keto-de-pollo", "Bowl Keto de Pollo"),
        (meta, "desayuno-keto-en-10-minutos", "Desayuno Keto en 10 Minutos"),
    ]
    seed_editorial_items = []
    for camp, slug_hint, title in contents:
        c = _content(db, org, brand, camp, product, slug_hint, title)
        link = _link(db, org, brand, camp, c, product)
        seed_editorial_items.append((camp, c, link))

    _seed_editorial(db, org, seed_editorial_items)
    _seed_leads(db, org, seed_editorial_items)
    _seed_ai(db, org, brand, owner)
    _seed_publishing(db, org, brand, owner, seed_editorial_items)

    db.commit()


def _seed_editorial(db: Session, org: Organization, items: list) -> None:
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    plans = [
        (0, EditorialStatus.PUBLISHED, Priority.MEDIUM, -14, ContentFormat.REEL),
        (0, EditorialStatus.PUBLISHED, Priority.MEDIUM, -7, ContentFormat.CAROUSEL),
        (1, EditorialStatus.PUBLISHED, Priority.HIGH, -5, ContentFormat.REEL),
        (2, EditorialStatus.SCHEDULED, Priority.HIGH, 2, ContentFormat.STORY),
        (1, EditorialStatus.SCHEDULED, Priority.MEDIUM, 3, ContentFormat.REEL),
        (3, EditorialStatus.APPROVED, Priority.URGENT, 5, ContentFormat.VIDEO),
        (2, EditorialStatus.IN_REVIEW, Priority.MEDIUM, 7, ContentFormat.CAROUSEL),
        (0, EditorialStatus.DRAFT, Priority.LOW, 10, ContentFormat.REEL),
        (3, EditorialStatus.IDEA, Priority.LOW, 14, ContentFormat.EMAIL),
        (1, EditorialStatus.NEEDS_REVISION, Priority.MEDIUM, 4, ContentFormat.STORY),
    ]

    for idx, (camp_ix, status, priority, day_offset, fmt) in enumerate(plans):
        camp, content, link = items[camp_ix]
        external = f"seed-eci-{idx}"
        existing = db.execute(
            select(EditorialCalendarItem).where(
                EditorialCalendarItem.organization_id == org.id,
                EditorialCalendarItem.notes == external,
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue

        sched = now + timedelta(days=day_offset)
        row = EditorialCalendarItem(
            organization_id=org.id,
            public_id=make_public_id("eci"),
            content_item_id=content.id,
            campaign_id=camp.id,
            brand_id=content.brand_id,
            product_id=content.product_id,
            platform=EditorialPlatform.INSTAGRAM
            if "instagram" in camp.slug or camp.platform == Platform.INSTAGRAM
            else EditorialPlatform.FACEBOOK,
            content_format=fmt,
            scheduled_for=sched
            if status in (EditorialStatus.SCHEDULED, EditorialStatus.PUBLISHED)
            else None,
            status=status,
            priority=priority,
            notes=external,
            published_at=sched if status == EditorialStatus.PUBLISHED else None,
            publication_url=(
                f"https://instagram.com/p/{content.public_id}"
                if status == EditorialStatus.PUBLISHED
                else None
            ),
        )
        db.add(row)
        db.flush()
        print(f"[seed] editorial {external} {status.value}")

    for _camp, content, _link in items[:2]:
        existing = db.execute(
            select(Review).where(
                Review.organization_id == org.id,
                Review.content_item_id == content.id,
                Review.comment == "seeded",
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        db.add(
            Review(
                organization_id=org.id,
                public_id=make_public_id("rv"),
                content_item_id=content.id,
                reviewer_user_id=None,
                review_type=ReviewType.GENERAL,
                decision=ReviewDecision.APPROVED,
                score=90,
                comment="seeded",
            )
        )


def _seed_leads(db: Session, org: Organization, items: list) -> None:
    from app.models.tracking import TrackingLink

    link_lookup = {content.id: link for _camp, content, link in items}
    campaign_lookup = {content.id: camp for camp, content, _link in items}
    content_lookup = {content.id: content for _camp, content, _link in items}

    plans = [
        ("Ana", "R.", "ana.r@example.com", None, None, LeadStatus.NEW, LeadSource.LANDING_PAGE, items[0][1].id, "s1"),
        ("Luis", "M.", None, "+51999111000", None, LeadStatus.CONTACTED, LeadSource.WHATSAPP, items[0][1].id, "s2"),
        ("Sofia", "C.", "sofia.c@example.com", None, None, LeadStatus.QUALIFIED, LeadSource.INSTAGRAM, items[1][1].id, "s3"),
        ("Carlos", "P.", "carlos.p@example.com", None, None, LeadStatus.WON, LeadSource.META_ADS, items[3][1].id, "s4"),
        ("Maria", None, None, "+34611222333", None, LeadStatus.LOST, LeadSource.WHATSAPP, items[2][1].id, "s5"),
        ("Diego", "V.", "diego.v@example.com", None, None, LeadStatus.NEW, LeadSource.ORGANIC, items[1][1].id, "s6"),
        ("Paula", "B.", "paula.b@example.com", None, None, LeadStatus.CONTACTED, LeadSource.LANDING_PAGE, items[0][1].id, "s7"),
        ("Rocío", None, "rocio@example.com", None, None, LeadStatus.QUALIFIED, LeadSource.META_ADS, items[3][1].id, "s8"),
        ("Miguel", "S.", None, None, "+525511223344", LeadStatus.NEW, LeadSource.WHATSAPP, items[2][1].id, "s9"),
        ("Lucía", "T.", "lucia.t@example.com", None, None, LeadStatus.WON, LeadSource.LANDING_PAGE, items[0][1].id, "s10"),
        ("José", "H.", "jose.h@example.com", None, None, LeadStatus.LOST, LeadSource.FACEBOOK, items[2][1].id, "s11"),
        ("Andrea", "Q.", "andrea.q@example.com", None, None, LeadStatus.QUALIFIED, LeadSource.INSTAGRAM, items[1][1].id, "s12"),
    ]

    for first, last, email, phone, whatsapp, status, source, content_id, ext in plans:
        existing = db.execute(
            select(Lead).where(
                Lead.organization_id == org.id,
                Lead.source_system == SourceSystem.MANUAL,
                Lead.external_id == ext,
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue

        link = link_lookup.get(content_id)
        camp = campaign_lookup.get(content_id)
        content = content_lookup.get(content_id)

        try:
            phone_e164 = normalize_phone(phone, org.country_code)
            whatsapp_e164 = normalize_phone(whatsapp, org.country_code)
        except InvalidPhoneNumber:
            print(f"[seed] skipping lead {ext}: unparseable phone/whatsapp")
            continue

        row = Lead(
            organization_id=org.id,
            public_id=make_public_id("ld"),
            brand_id=content.brand_id if content else None,
            product_id=content.product_id if content else None,
            campaign_id=camp.id if camp else None,
            content_item_id=content.id if content else None,
            tracking_link_id=link.id if link else None,
            first_name=first,
            last_name=last,
            email=email.lower() if email else None,
            phone=phone_e164,
            whatsapp=whatsapp_e164,
            source=source,
            status=status,
            utm_source=link.utm_source if link else None,
            utm_medium=link.utm_medium if link else None,
            utm_campaign=link.utm_campaign if link else None,
            external_id=ext,
            source_system=SourceSystem.MANUAL,
        )
        db.add(row)
        db.flush()
        db.add(
            LeadActivity(
                public_id=make_public_id("la"),
                organization_id=org.id,
                lead_id=row.id,
                actor_user_id=None,
                activity_type=LeadActivityType.CREATED,
                description="Seeded lead",
                activity_metadata={"seed": True, "external_id": ext},
            )
        )
        print(f"[seed] lead {ext} {status.value}")

    _ = TrackingLink  # keep import used


def _seed_ai(db: Session, org: Organization, brand: Brand, owner: User) -> None:
    from app.ai.templates import get_active_template

    bv = db.execute(
        select(BrandVoiceProfile).where(
            BrandVoiceProfile.organization_id == org.id, BrandVoiceProfile.brand_id == brand.id
        )
    ).scalar_one_or_none()
    if bv is None:
        bv = BrandVoiceProfile(
            organization_id=org.id,
            public_id=make_public_id("bvp"),
            brand_id=brand.id,
            audience="Mujeres y hombres 28-55 años en República Dominicana interesados en "
            "hábitos alimenticios saludables sin dietas extremas.",
            value_proposition="120 recetas keto prácticas + acompañamiento por WhatsApp "
            "durante 21 días para construir hábitos sostenibles.",
            tone="Cercano, motivador, premium sin ser elitista. Habla de tú.",
            preferred_terms=["hábitos sostenibles", "transformación", "acompañamiento"],
            forbidden_terms=["cura", "tratamiento médico", "resultados garantizados"],
            cta_style="Invitación directa a través del link en la bio o WhatsApp",
            compliance_notes="Nunca presentar el producto como tratamiento médico. No "
            "prometer pérdida de peso garantizada ni cifras específicas de kg perdidos.",
            language="es",
            country="DO",
            examples=[
                "Pequeños cambios, resultados sostenibles.",
                "21 días para construir hábitos que se quedan contigo.",
            ],
        )
        db.add(bv)
        db.flush()
        print("[seed] brand voice profile")

    source = db.execute(
        select(PublicLeadSource).where(
            PublicLeadSource.organization_id == org.id, PublicLeadSource.name == "Landing dev"
        )
    ).scalar_one_or_none()
    if source is None:
        source = PublicLeadSource(
            organization_id=org.id,
            public_id=make_public_id("pls"),
            brand_id=brand.id,
            name="Landing dev",
            public_token=generate_token(),
            allowed_origins=["http://localhost:3000"],
            is_active=True,
            default_utm_source="landing",
            default_utm_medium="organic",
            default_utm_campaign="dev-source",
        )
        db.add(source)
        db.flush()
        print(f"[seed] public lead source token={source.public_token[:8]}...")

    for gt in (GenerationType.SOCIAL_POST, GenerationType.REEL_SCRIPT, GenerationType.CONTENT_IDEAS):
        get_active_template(db, org.id, gt)
    db.flush()
    print("[seed] prompt templates ensured")

    good_output = {
        "title": "5 hábitos keto que sí puedes sostener",
        "hook": "Si crees que keto es solo restricción, mira esto.",
        "script": "Toma 1: primer plano del plato. Toma 2: preparación rápida. Toma 3: CTA.",
        "caption": "Pequeños cambios, resultados sostenibles. Descubre el enfoque de 21 días.",
        "cta": "Link en la bio para ver el programa completo",
        "hashtags": ["#ketodominicana", "#habitossaludables", "#recetaskeeto"],
        "visual_notes": ["Luz natural", "Primer plano del plato terminado"],
    }
    borderline_output = {
        "title": "Ideas rápidas",
        "hook": "",
        "script": "Contenido genérico sin gancho claro.",
        "caption": "Nunca es tarde.",
        "cta": "",
        "hashtags": ["#keto"] * 2,
        "visual_notes": [],
    }
    blocked_output = {
        "title": "Pierde 10 kg garantizado en 7 días",
        "hook": "Tratamiento médico para eliminar la grasa sin esfuerzo",
        "script": "Resultados garantizados 100% garantizado.",
        "caption": "Cura tus problemas de peso para siempre.",
        "cta": "Compra ya",
        "hashtags": ["#milagro"],
        "visual_notes": [],
    }

    def _existing_job(idempotency_key: str) -> GenerationJob | None:
        return db.execute(
            select(GenerationJob).where(
                GenerationJob.organization_id == org.id,
                GenerationJob.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()

    def _make_job(
        key: str,
        status: GenerationStatus,
        gen_type: GenerationType,
        topic: str,
        output: dict | None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> GenerationJob:
        existing = _existing_job(key)
        if existing is not None:
            return existing
        template = get_active_template(db, org.id, gen_type)
        job = GenerationJob(
            organization_id=org.id,
            public_id=make_public_id("gj"),
            brand_id=brand.id,
            product_id=None,
            campaign_id=None,
            requested_by_user_id=owner.id,
            generation_type=gen_type,
            status=status,
            provider=AIProvider.MOCK,
            model="mock-editorial-v1",
            prompt_version=template.version,
            input_payload={
                "system": template.system_instructions,
                "user": f"Topic: {topic}",
                "raw_input": {
                    "objective": "engagement",
                    "platform": "INSTAGRAM",
                    "topic": topic,
                    "audience": None,
                    "cta": None,
                    "notes": None,
                },
            },
            output_payload=output,
            error_code=error_code,
            error_message=error_message,
            idempotency_key=key,
        )
        if status == GenerationStatus.COMPLETED:
            job.input_tokens = 120
            job.output_tokens = 90
            job.estimated_cost = Decimal("0")
        db.add(job)
        db.flush()
        print(f"[seed] generation job {key} {status.value}")
        return job

    def _persist_council(job: GenerationJob, output: dict, topic: str) -> None:
        existing = db.execute(
            select(CouncilReview).where(CouncilReview.generation_job_id == job.id)
        ).scalars().first()
        if existing is not None:
            return
        from app.schemas.ai import GeneratedContent

        content = GeneratedContent.model_validate(output)
        outcomes = run_council(
            content,
            topic=topic,
            forbidden_terms=bv.forbidden_terms,
            preferred_terms=bv.preferred_terms,
            cta_style=bv.cta_style,
        )
        for outcome in outcomes:
            db.add(
                CouncilReview(
                    public_id=make_public_id("cr"),
                    organization_id=org.id,
                    generation_job_id=job.id,
                    content_item_id=job.content_item_id,
                    reviewer_type=outcome.reviewer_type,
                    score=outcome.score,
                    decision=outcome.decision,
                    summary=outcome.summary,
                    issues=outcome.issues,
                    recommendations=outcome.recommendations,
                    blocking_issues=outcome.blocking_issues,
                )
            )
        db.flush()
        _, decision, _ = aggregate(outcomes)
        print(f"[seed] council for {job.public_id}: {decision.value}")

    job_completed = _make_job(
        "seed-gj-completed",
        GenerationStatus.COMPLETED,
        GenerationType.REEL_SCRIPT,
        "hábitos keto sostenibles",
        good_output,
    )
    _persist_council(job_completed, good_output, "hábitos keto sostenibles")

    _make_job(
        "seed-gj-failed",
        GenerationStatus.FAILED,
        GenerationType.SOCIAL_POST,
        "receta rápida",
        None,
        error_code="provider_error",
        error_message="mock provider: simulated upstream error",
    )

    job_needs_revision = _make_job(
        "seed-gj-needs-revision",
        GenerationStatus.COMPLETED,
        GenerationType.CONTENT_IDEAS,
        "ideas de contenido",
        borderline_output,
    )
    _persist_council(job_needs_revision, borderline_output, "ideas de contenido")

    job_blocked = _make_job(
        "seed-gj-blocked",
        GenerationStatus.COMPLETED,
        GenerationType.SOCIAL_POST,
        "promesa de resultados",
        blocked_output,
    )
    _persist_council(job_blocked, blocked_output, "promesa de resultados")

    # Convert two COMPLETED jobs into ContentItem drafts, as required by the
    # seed spec — independent of what the Council recommended, matching the
    # rule that Council never auto-approves or auto-blocks content creation.
    for job, output, ext_suffix in (
        (job_completed, good_output, "completed"),
        (job_needs_revision, borderline_output, "needs-revision"),
    ):
        if job.content_item_id is not None:
            continue
        external_id = f"seed-ai-{ext_suffix}"
        existing_content = db.execute(
            select(ContentItem).where(
                ContentItem.organization_id == org.id,
                ContentItem.source_system == SourceSystem.MANUAL,
                ContentItem.external_id == external_id,
            )
        ).scalar_one_or_none()
        if existing_content is not None:
            job.content_item_id = existing_content.id
            db.flush()
            continue
        content = ContentItem(
            organization_id=org.id,
            brand_id=brand.id,
            public_id=make_public_id("ct"),
            external_id=external_id,
            source_system=SourceSystem.MANUAL,
            content_type=ContentType.REEL,
            title=output["title"],
            hook=output.get("hook") or None,
            caption=output.get("caption") or None,
            cta=output.get("cta") or None,
            status=ContentStatus.DRAFT,
        )
        db.add(content)
        db.flush()
        job.content_item_id = content.id
        db.flush()
        print(f"[seed] content item from {job.public_id}")


def _seed_publishing(
    db: Session, org: Organization, brand: Brand, owner: User, items: list
) -> None:
    """Phase 5: assets, variants, connections, publications, attempts,
    automation rules, notifications. Everything MOCK/MANUAL — no real files,
    no real credentials, no real network calls."""
    import hashlib
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    content0 = items[0][1]  # APPROVED (see _seed_editorial)
    content1 = items[1][1]  # APPROVED (see _seed_editorial)

    # --- assets -------------------------------------------------------
    asset_plans = [
        ("img-plato-lasana.jpg", AssetType.IMAGE, "image/jpeg", 480_000, AssetStatus.READY, "Plato de lasaña keto servido en mesa de madera", 1080, 1350),
        ("img-plato-pizza.jpg", AssetType.IMAGE, "image/jpeg", 610_000, AssetStatus.READY, "Pizza keto de brócoli recién horneada", 1080, 1080),
        ("img-bowl-pollo.png", AssetType.IMAGE, "image/png", 2_400_000, AssetStatus.READY, "Bowl keto de pollo con vegetales", 1200, 1500),
        ("img-desayuno.jpg", AssetType.IMAGE, "image/jpeg", 350_000, AssetStatus.READY, "Desayuno keto en 10 minutos", 1080, 1920),
        ("reel-preparacion.mp4", AssetType.VIDEO, "video/mp4", 18_500_000, AssetStatus.READY, None, 1080, 1920),
        ("reel-tips-keto.mp4", AssetType.VIDEO, "video/mp4", 22_100_000, AssetStatus.READY, None, 1080, 1920),
        ("img-borrosa.jpg", AssetType.IMAGE, "image/jpeg", 95_000, AssetStatus.REJECTED, None, 400, 300),
        ("video-formato-invalido.mov", AssetType.VIDEO, "video/quicktime", 40_200_000, AssetStatus.REJECTED, None, None, None),
        ("img-empaque.jpg", AssetType.IMAGE, "image/jpeg", 275_000, AssetStatus.READY, "Empaque del programa 120 recetas", 1080, 1080),
        ("thumb-portada.png", AssetType.THUMBNAIL, "image/png", 120_000, AssetStatus.READY, "Portada de la serie de recetas", 800, 800),
    ]
    assets: list[Asset] = []
    for fname, atype, mime, size, status, alt, width, height in asset_plans:
        existing = db.execute(
            select(Asset).where(
                Asset.organization_id == org.id, Asset.original_filename == fname
            )
        ).scalar_one_or_none()
        if existing is not None:
            assets.append(existing)
            continue
        checksum = hashlib.sha256(f"seed-asset-{fname}".encode()).hexdigest()
        duration = 24 if atype == AssetType.VIDEO else None
        row = Asset(
            organization_id=org.id,
            public_id=make_public_id("as"),
            brand_id=brand.id,
            content_item_id=content0.id if fname.startswith("img-plato-lasana") else None,
            uploaded_by_user_id=owner.id,
            asset_type=atype,
            status=status,
            storage_provider=StorageProviderName.MOCK,
            storage_key=f"{org.id}/seed-{fname}",
            original_filename=fname,
            safe_filename=f"seed-{fname}",
            mime_type=mime,
            size_bytes=size,
            width=width,
            height=height,
            duration_seconds=duration,
            checksum_sha256=checksum,
            alt_text=alt,
            caption=None,
            asset_metadata={"seed": True},
            archived_at=None,
        )
        db.add(row)
        db.flush()
        assets.append(row)
        print(f"[seed] asset {fname} {status.value}")

    ready_images = [a for a in assets if a.asset_type == AssetType.IMAGE and a.status == AssetStatus.READY]
    ready_videos = [a for a in assets if a.asset_type == AssetType.VIDEO and a.status == AssetStatus.READY]

    # --- asset variants -------------------------------------------------
    if ready_images:
        base = ready_images[0]
        existing = db.execute(
            select(AssetVariant).where(
                AssetVariant.organization_id == org.id, AssetVariant.asset_id == base.id
            )
        ).scalars().first()
        if existing is None:
            for platform, vtype, w, h in (
                ("INSTAGRAM", VariantType.STORY, 1080, 1920),
                ("INSTAGRAM", VariantType.SQUARE, 1080, 1080),
            ):
                variant = AssetVariant(
                    organization_id=org.id,
                    public_id=make_public_id("av"),
                    asset_id=base.id,
                    platform=platform,
                    variant_type=vtype,
                    width=w,
                    height=h,
                    duration_seconds=None,
                    storage_key=f"{org.id}/seed-variant-{vtype.value.lower()}-{base.public_id}",
                    mime_type=base.mime_type,
                    size_bytes=base.size_bytes // 2,
                    status=VariantStatus.READY,
                    transformation_spec={"seed": True, "crop": vtype.value},
                )
                db.add(variant)
            db.flush()
            print(f"[seed] variants for {base.public_id}")

    # --- publishing connections -------------------------------------------
    manual_conn = db.execute(
        select(PublishingConnection).where(
            PublishingConnection.organization_id == org.id,
            PublishingConnection.provider == PublishingProviderName.MANUAL,
        )
    ).scalar_one_or_none()
    if manual_conn is None:
        manual_conn = PublishingConnection(
            organization_id=org.id,
            public_id=make_public_id("pcn"),
            brand_id=brand.id,
            platform=Platform.INSTAGRAM,
            provider=PublishingProviderName.MANUAL,
            account_name="Manual — equipo social",
            external_account_id=None,
            status=ConnectionStatus.ACTIVE,
            capabilities=["POST", "REEL", "STORY"],
            credentials_encrypted=None,
            token_expires_at=None,
            last_verified_at=now,
            created_by_user_id=owner.id,
        )
        db.add(manual_conn)
        db.flush()
        print("[seed] connection MANUAL")

    mock_conn = db.execute(
        select(PublishingConnection).where(
            PublishingConnection.organization_id == org.id,
            PublishingConnection.provider == PublishingProviderName.MOCK,
        )
    ).scalar_one_or_none()
    if mock_conn is None:
        mock_conn = PublishingConnection(
            organization_id=org.id,
            public_id=make_public_id("pcn"),
            brand_id=brand.id,
            platform=Platform.INSTAGRAM,
            provider=PublishingProviderName.MOCK,
            account_name="rqt21.mock",
            external_account_id="mock-account-1",
            status=ConnectionStatus.ACTIVE,
            capabilities=["POST", "REEL", "STORY", "CAROUSEL"],
            credentials_encrypted=encrypt_credentials({"access_token": "seed-mock-token-0000"}),
            token_expires_at=now + timedelta(days=60),
            last_verified_at=now,
            created_by_user_id=owner.id,
        )
        db.add(mock_conn)
        db.flush()
        print("[seed] connection MOCK")

    # --- publications -------------------------------------------------
    def _existing_pub(idem_key: str) -> Publication | None:
        return db.execute(
            select(Publication).where(
                Publication.organization_id == org.id, Publication.idempotency_key == idem_key
            )
        ).scalar_one_or_none()

    def _make_pub(
        key_suffix: str,
        content: ContentItem,
        connection: PublishingConnection,
        status: PublicationStatus,
        *,
        caption: str,
        scheduled_for: datetime | None = None,
        published_at: datetime | None = None,
        external_url: str | None = None,
        external_publication_id: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
        attempt_count: int = 0,
        next_retry_at: datetime | None = None,
        asset: Asset | None = None,
    ) -> Publication:
        idem_key = hashlib.sha256(
            f"seed:{org.id}:{key_suffix}".encode()
        ).hexdigest()[:32]
        existing = _existing_pub(idem_key)
        if existing is not None:
            return existing
        row = Publication(
            organization_id=org.id,
            public_id=make_public_id("pub"),
            content_item_id=content.id,
            editorial_calendar_item_id=None,
            brand_id=brand.id,
            campaign_id=content.campaign_id,
            product_id=content.product_id,
            publishing_connection_id=connection.id,
            asset_id=asset.id if asset else None,
            asset_variant_id=None,
            platform=connection.platform,
            publication_type=PublicationType.REEL if content.content_type == ContentType.REEL else PublicationType.POST,
            status=status,
            caption=caption,
            title=content.title,
            cta=content.cta,
            hashtags=["#ketodominicana", "#habitossaludables"],
            scheduled_for=scheduled_for,
            timezone="America/Santo_Domingo",
            external_publication_id=external_publication_id,
            external_url=external_url,
            published_at=published_at,
            failure_code=failure_code,
            failure_message=failure_message,
            attempt_count=attempt_count,
            next_retry_at=next_retry_at,
            idempotency_key=idem_key,
            created_by_user_id=owner.id,
            approved_by_user_id=owner.id if status != PublicationStatus.DRAFT else None,
        )
        db.add(row)
        db.flush()
        print(f"[seed] publication {row.public_id} {status.value}")
        return row

    asset0 = ready_images[0] if ready_images else None
    asset1 = ready_videos[0] if ready_videos else None

    pub_draft_1 = _make_pub(
        "draft-1", content0, mock_conn, PublicationStatus.DRAFT,
        caption="Pequeños cambios, resultados sostenibles. #ketodominicana", asset=asset0,
    )
    _make_pub(
        "draft-2", content1, manual_conn, PublicationStatus.DRAFT,
        caption="Pizza keto lista en minutos.", asset=asset0,
    )
    _make_pub(
        "ready-1", content0, mock_conn, PublicationStatus.READY,
        caption="Lasaña keto que sí puedes sostener. Link en la bio.", asset=asset0,
    )
    _make_pub(
        "scheduled-1", content1, mock_conn, PublicationStatus.SCHEDULED,
        caption="Pizza keto de brócoli — receta completa en el programa 21 días.",
        scheduled_for=now + timedelta(days=2), asset=asset0,
    )
    _make_pub(
        "scheduled-2", content0, manual_conn, PublicationStatus.SCHEDULED,
        caption="Reel: preparación paso a paso de la lasaña keto.",
        scheduled_for=now + timedelta(days=3), asset=asset1,
    )
    pub_published_1 = _make_pub(
        "published-1", content1, mock_conn, PublicationStatus.PUBLISHED,
        caption="Ya está publicado: bowl keto de pollo.",
        published_at=now - timedelta(days=1),
        external_url="https://mock.local/p/seed-published-1",
        external_publication_id="mock-seed-published-1",
        attempt_count=1,
        asset=asset0,
    )
    _make_pub(
        "published-2", content0, manual_conn, PublicationStatus.PUBLISHED,
        caption="Publicado manualmente por el equipo social.",
        published_at=now - timedelta(days=3),
        external_url="https://instagram.com/p/seed-manual-1",
        attempt_count=1,
        asset=asset1,
    )
    pub_failed_1 = _make_pub(
        "failed-1", content1, mock_conn, PublicationStatus.FAILED,
        caption="Intento fallido de publicación automática.",
        failure_code="permanent_error",
        failure_message="mock provider: simulated permanent error",
        attempt_count=1,
        asset=asset0,
    )

    # --- publication attempts (append-only) -----------------------------
    def _ensure_attempt(
        pub: Publication, number: int, status: AttemptStatus, *, external_id: str | None = None,
        error_code: str | None = None, error_message: str | None = None,
    ) -> None:
        existing = db.execute(
            select(PublicationAttempt).where(
                PublicationAttempt.publication_id == pub.id,
                PublicationAttempt.attempt_number == number,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return
        started = now - timedelta(hours=1)
        db.add(
            PublicationAttempt(
                public_id=make_public_id("pa"),
                organization_id=org.id,
                publication_id=pub.id,
                attempt_number=number,
                provider=PublishingProviderName.MOCK,
                status=status,
                request_summary={"platform": pub.platform.value, "seed": True},
                response_summary={"raw_status": status.value.lower()},
                external_id=external_id,
                error_code=error_code,
                error_message=error_message,
                started_at=started,
                completed_at=started + timedelta(seconds=2),
            )
        )
        db.flush()

    _ensure_attempt(
        pub_published_1, 1, AttemptStatus.SUCCEEDED, external_id="mock-seed-published-1"
    )
    _ensure_attempt(
        pub_failed_1, 1, AttemptStatus.FAILED,
        error_code="permanent_error", error_message="mock provider: simulated permanent error",
    )

    # --- automation rules -------------------------------------------------
    rule_draft = db.execute(
        select(AutomationRule).where(
            AutomationRule.organization_id == org.id, AutomationRule.name == "Crear borrador al aprobar contenido"
        )
    ).scalar_one_or_none()
    if rule_draft is None:
        db.add(
            AutomationRule(
                organization_id=org.id,
                public_id=make_public_id("ar"),
                brand_id=brand.id,
                name="Crear borrador al aprobar contenido",
                trigger_type=AutomationTriggerType.CONTENT_APPROVED,
                conditions={},
                action_type=AutomationActionType.CREATE_PUBLICATION_DRAFT,
                action_config={"platform": "INSTAGRAM", "provider": "MOCK"},
                is_active=True,
                created_by_user_id=owner.id,
            )
        )
        print("[seed] automation rule: create draft on approval")

    rule_notify_failure = db.execute(
        select(AutomationRule).where(
            AutomationRule.organization_id == org.id, AutomationRule.name == "Notificar publicaciones fallidas"
        )
    ).scalar_one_or_none()
    if rule_notify_failure is None:
        db.add(
            AutomationRule(
                organization_id=org.id,
                public_id=make_public_id("ar"),
                brand_id=None,
                name="Notificar publicaciones fallidas",
                trigger_type=AutomationTriggerType.PUBLICATION_FAILED,
                conditions={},
                action_type=AutomationActionType.SEND_INTERNAL_NOTIFICATION,
                action_config={},
                is_active=True,
                created_by_user_id=owner.id,
            )
        )
        print("[seed] automation rule: notify on publication failure")
    db.flush()

    # --- notifications -------------------------------------------------
    notif_plans = [
        (NotificationType.CONTENT_APPROVED, "Contenido aprobado", f"'{content0.title}' fue aprobado.", "content_item", content0.public_id),
        (NotificationType.PUBLICATION_SUCCEEDED, "Publicación exitosa", f"'{pub_published_1.public_id}' se publicó correctamente.", "publication", pub_published_1.public_id),
        (NotificationType.PUBLICATION_FAILED, "Publicación fallida", f"'{pub_failed_1.public_id}' falló: error permanente simulado.", "publication", pub_failed_1.public_id),
        (NotificationType.ASSET_REJECTED, "Activo rechazado", "img-borrosa.jpg fue rechazado por calidad insuficiente.", "asset", None),
    ]
    for ntype, title, message, rtype, rpid in notif_plans:
        existing = db.execute(
            select(Notification).where(
                Notification.organization_id == org.id,
                Notification.user_id == owner.id,
                Notification.title == title,
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        db.add(
            Notification(
                organization_id=org.id,
                public_id=make_public_id("nt"),
                user_id=owner.id,
                notification_type=ntype,
                title=title,
                message=message,
                resource_type=rtype,
                resource_public_id=rpid,
                read_at=None,
            )
        )
        print(f"[seed] notification: {title}")

    db.flush()
    _ = pub_draft_1  # keep reference for readability/debug symmetry


def main() -> None:
    with SessionLocal() as db:
        seed(db)


if __name__ == "__main__":
    main()
