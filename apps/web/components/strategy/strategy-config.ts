import type {
  CampaignObjective,
  CampaignStatus,
  Platform,
  ProductStatus,
} from "@rqt21/contracts";

import type { StatusTone } from "@/components/design-system/status-badge";

export const PRODUCT_STATUS_LABELS: Record<ProductStatus, string> = {
  DRAFT: "Borrador",
  ACTIVE: "Activo",
  ARCHIVED: "Archivado",
};

export const PRODUCT_STATUS_TONES: Record<ProductStatus, StatusTone> = {
  DRAFT: "neutral",
  ACTIVE: "success",
  ARCHIVED: "neutral",
};

export const CAMPAIGN_STATUS_LABELS: Record<CampaignStatus, string> = {
  DRAFT: "Borrador",
  ACTIVE: "Activa",
  PAUSED: "Pausada",
  ARCHIVED: "Archivada",
};

export const CAMPAIGN_STATUS_TONES: Record<CampaignStatus, StatusTone> = {
  DRAFT: "neutral",
  ACTIVE: "success",
  PAUSED: "warning",
  ARCHIVED: "neutral",
};

export const CAMPAIGN_OBJECTIVE_LABELS: Record<CampaignObjective, string> = {
  AWARENESS: "Reconocimiento",
  TRAFFIC: "Tráfico",
  LEAD_GEN: "Generación de leads",
  SALES: "Ventas",
  ENGAGEMENT: "Interacción",
  OTHER: "Otro",
};

export const PLATFORM_LABELS: Record<Platform, string> = {
  INSTAGRAM: "Instagram",
  FACEBOOK: "Facebook",
  TIKTOK: "TikTok",
  YOUTUBE: "YouTube",
  WHATSAPP: "WhatsApp",
  EMAIL: "Correo",
  WEB: "Web",
  META_ADS: "Meta Ads",
  OTHER: "Otro",
};

export function slugifyStrategy(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function formatStrategyDate(value: string): string {
  return new Intl.DateTimeFormat("es", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

export function formatMoney(value: string | null, currency = "USD"): string {
  if (!value) return "Sin precio";
  const amount = Number(value);
  if (!Number.isFinite(amount)) return `${value} ${currency}`;
  return new Intl.NumberFormat("es", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount);
}
