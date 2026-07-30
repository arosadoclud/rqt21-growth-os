import type {
  ContentStatus,
  ContentType,
  Platform,
  ReviewDecision,
  ReviewStatus,
  SourceSystem,
} from "@rqt21/contracts";

import type { StatusTone } from "@/components/design-system/status-badge";

export const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
  NOT_SUBMITTED: "Sin enviar",
  IN_REVIEW: "En revisión",
  APPROVED: "Aprobado",
  CHANGES_REQUESTED: "Cambios solicitados",
  REJECTED: "Rechazado",
};

export const REVIEW_STATUS_TONES: Record<ReviewStatus, StatusTone> = {
  NOT_SUBMITTED: "neutral",
  IN_REVIEW: "warning",
  APPROVED: "success",
  CHANGES_REQUESTED: "warning",
  REJECTED: "danger",
};

export const CONTENT_STATUS_LABELS: Record<ContentStatus, string> = {
  DRAFT: "Borrador",
  SCHEDULED: "Programado",
  PUBLISHED: "Publicado",
  ARCHIVED: "Archivado",
};

export const CONTENT_STATUS_TONES: Record<ContentStatus, StatusTone> = {
  DRAFT: "neutral",
  SCHEDULED: "info",
  PUBLISHED: "success",
  ARCHIVED: "neutral",
};

export const CONTENT_TYPE_LABELS: Record<ContentType, string> = {
  POST: "Publicación",
  REEL: "Reel",
  STORY: "Historia",
  VIDEO: "Video",
  ARTICLE: "Artículo",
  AD: "Anuncio",
  OTHER: "Otro",
};

export const PLATFORM_LABELS: Record<Platform, string> = {
  INSTAGRAM: "Instagram",
  FACEBOOK: "Facebook",
  TIKTOK: "TikTok",
  YOUTUBE: "YouTube",
  WHATSAPP: "WhatsApp",
  EMAIL: "Email",
  WEB: "Web",
  META_ADS: "Meta Ads",
  OTHER: "Otro",
};

export const SOURCE_LABELS: Record<SourceSystem, string> = {
  MANUAL: "Creado manualmente",
  KINGDOM_STUDIO: "Importado de Kingdom Studio",
  IMPORT: "Importado",
};

export const REVIEW_DECISION_LABELS: Record<ReviewDecision, string> = {
  APPROVED: "Aprobado",
  NEEDS_REVISION: "Solicita cambios",
  REJECTED: "Rechazado",
};

export const REVIEW_DECISION_TONES: Record<ReviewDecision, StatusTone> = {
  APPROVED: "success",
  NEEDS_REVISION: "warning",
  REJECTED: "danger",
};

export function formatEditorialDate(value: string | null | undefined) {
  if (!value) return "Sin fecha";
  return new Date(value).toLocaleString("es", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function friendlyReviewError(error: unknown, fallback: string) {
  const detail =
    typeof error === "object" && error && "detail" in error
      ? String((error as { detail: unknown }).detail)
      : "";
  if (detail.includes("already submitted") || detail.includes("pending review")) {
    return "Este contenido ya está en revisión. Espera una decisión antes de volver a enviarlo.";
  }
  if (detail.includes("not enough permissions") || detail.includes("forbidden")) {
    return "Tu rol no tiene permiso para realizar esta acción.";
  }
  return detail || fallback;
}
