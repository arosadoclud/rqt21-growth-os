import type {
  AIProvider,
  CouncilDecision,
  CouncilReviewerType,
  GenerationStatus,
  GenerationType,
} from "@rqt21/contracts";

import type { StatusTone } from "@/components/design-system/status-badge";

export const GENERATION_STATUS_LABELS: Record<GenerationStatus, string> = {
  QUEUED: "En espera",
  RUNNING: "En proceso",
  COMPLETED: "Completada",
  FAILED: "Con error",
  CANCELLED: "Cancelada",
};

export const GENERATION_STATUS_TONES: Record<GenerationStatus, StatusTone> = {
  QUEUED: "neutral",
  RUNNING: "info",
  COMPLETED: "success",
  FAILED: "danger",
  CANCELLED: "warning",
};

export const GENERATION_TYPE_LABELS: Record<GenerationType, string> = {
  SOCIAL_POST: "Publicación social",
  REEL_SCRIPT: "Guion para reel",
  CAROUSEL: "Carrusel",
  EMAIL: "Correo",
  BLOG_OUTLINE: "Esquema de artículo",
  BLOG_ARTICLE: "Artículo",
  CTA_VARIATIONS: "Variaciones de CTA",
  CONTENT_IDEAS: "Ideas de contenido",
  IMAGE_ASSET: "Imagen",
  STORY: "Historia",
  VIDEO_ASSET: "Video",
  VOICE_OVER: "Voz en off",
};

export const AI_PROVIDER_LABELS: Record<AIProvider, string> = {
  ANTHROPIC: "Anthropic",
  OPENAI: "OpenAI",
  MOCK: "Entorno de prueba",
};

export const COUNCIL_DECISION_LABELS: Record<CouncilDecision, string> = {
  APPROVED: "Aprobado",
  NEEDS_REVISION: "Requiere ajustes",
  REJECTED: "Rechazado",
  BLOCKED: "Bloqueado",
};

export const COUNCIL_DECISION_TONES: Record<CouncilDecision, StatusTone> = {
  APPROVED: "success",
  NEEDS_REVISION: "warning",
  REJECTED: "danger",
  BLOCKED: "danger",
};

export const COUNCIL_REVIEWER_LABELS: Record<CouncilReviewerType, string> = {
  BRAND: "Coherencia de marca",
  SEO: "Descubrimiento y SEO",
  EMOTIONAL_TONE: "Tono emocional",
  CTA: "Llamada a la acción",
  COMPLIANCE: "Cumplimiento",
  DEVILS_ADVOCATE: "Riesgos y objeciones",
};

export function formatIntelligenceDate(value?: string | null) {
  if (!value) return "Sin registro";
  return new Intl.DateTimeFormat("es", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatCompactNumber(value: number) {
  return new Intl.NumberFormat("es", { notation: "compact", maximumFractionDigits: 1 }).format(
    value,
  );
}

export function formatCost(value?: string | null) {
  if (value === null || value === undefined) return "Sin datos";
  return new Intl.NumberFormat("es", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(Number(value));
}
