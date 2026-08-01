from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    ai_usage,
    analytics,
    assets,
    auth,
    auto_approval,
    automations,
    brand_voice,
    brands,
    campaigns,
    content_items,
    editorial,
    generation_jobs,
    headline,
    health,
    leads,
    me,
    notifications,
    organizations,
    products,
    public_lead_sources,
    publications,
    publishing_connections,
    reviews,
    tracking_links,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(organizations.router)
api_router.include_router(brands.router)
api_router.include_router(products.router)
api_router.include_router(campaigns.router)
api_router.include_router(content_items.router)
api_router.include_router(reviews.router)
api_router.include_router(tracking_links.router)
api_router.include_router(editorial.router)
api_router.include_router(leads.router)
api_router.include_router(public_lead_sources.router)
api_router.include_router(brand_voice.router)
api_router.include_router(generation_jobs.router)
api_router.include_router(headline.router)
api_router.include_router(ai_usage.router)
api_router.include_router(assets.router)
api_router.include_router(publishing_connections.router)
api_router.include_router(publications.router)
api_router.include_router(publications.publishing_router)
api_router.include_router(automations.router)
api_router.include_router(notifications.router)
api_router.include_router(analytics.router)
api_router.include_router(auto_approval.router)
