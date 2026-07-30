import type {
  ContentFormat,
  ContentItem,
  EditorialItem,
  EditorialPlatform,
  EditorialStatus,
  Priority,
  Publication,
} from "@rqt21/contracts";

import type { StatusTone } from "@/components/design-system/status-badge";

export type CalendarView = "month" | "week" | "list";

export interface CalendarEntry {
  item: EditorialItem;
  content?: ContentItem;
  publication?: Publication;
}

export const STATUS_LABELS: Record<EditorialStatus, string> = {
  IDEA: "Idea",
  DRAFT: "Borrador",
  IN_REVIEW: "En revisión",
  NEEDS_REVISION: "Solicita cambios",
  APPROVED: "Aprobado",
  SCHEDULED: "Programado",
  PUBLISHED: "Publicado",
  CANCELLED: "Cancelado",
  ARCHIVED: "Archivado",
};

export const STATUS_TONES: Record<EditorialStatus, StatusTone> = {
  IDEA: "neutral",
  DRAFT: "neutral",
  IN_REVIEW: "info",
  NEEDS_REVISION: "warning",
  APPROVED: "accent",
  SCHEDULED: "info",
  PUBLISHED: "success",
  CANCELLED: "danger",
  ARCHIVED: "neutral",
};

export const PLATFORM_LABELS: Record<EditorialPlatform, string> = {
  INSTAGRAM: "Instagram",
  FACEBOOK: "Facebook",
  TIKTOK: "TikTok",
  PINTEREST: "Pinterest",
  YOUTUBE: "YouTube",
  LINKEDIN: "LinkedIn",
  BLOG: "Blog",
  EMAIL: "Email",
  OTHER: "Otro",
};

export const FORMAT_LABELS: Record<ContentFormat, string> = {
  REEL: "Reel",
  STORY: "Historia",
  CAROUSEL: "Carrusel",
  IMAGE: "Imagen",
  VIDEO: "Video",
  ARTICLE: "Artículo",
  EMAIL: "Email",
  TEXT_POST: "Publicación de texto",
  OTHER: "Otro",
};

export const PRIORITY_LABELS: Record<Priority, string> = {
  LOW: "Baja",
  MEDIUM: "Media",
  HIGH: "Alta",
  URGENT: "Urgente",
};

export const PRIORITY_TONES: Record<Priority, StatusTone> = {
  LOW: "neutral",
  MEDIUM: "info",
  HIGH: "warning",
  URGENT: "danger",
};

export function dateKey(date: Date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

export function startOfWeek(date: Date) {
  const start = new Date(date);
  const day = start.getDay();
  start.setDate(start.getDate() - (day === 0 ? 6 : day - 1));
  start.setHours(0, 0, 0, 0);
  return start;
}

export function addDays(date: Date, amount: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + amount);
  return next;
}

export function isSameDay(first: Date, second: Date) {
  return dateKey(first) === dateKey(second);
}

export function formatShortDate(value: string | null) {
  if (!value) return "Sin fecha";
  return new Date(value).toLocaleString("es", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function toDateTimeLocal(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16);
}

export function toISOString(value: string) {
  return value ? new Date(value).toISOString() : null;
}

export function friendlyEditorialError(error: unknown, fallback: string) {
  const detail =
    typeof error === "object" && error && "detail" in error
      ? String((error as { detail: unknown }).detail)
      : "";
  const translations: Array<[string, string]> = [
    ["scheduled_for is required", "Selecciona una fecha y hora para programar el contenido."],
    ["archived items cannot be edited", "Los elementos archivados son de solo lectura."],
    ["cannot schedule a published or archived item", "Un elemento publicado o archivado no se puede reprogramar."],
    ["cannot publish an archived item", "Un elemento archivado no se puede marcar como publicado."],
    ["cannot cancel a published item", "Una publicación ya publicada no se puede cancelar."],
    ["not found", "El elemento ya no está disponible. Actualiza el calendario."],
  ];
  return translations.find(([key]) => detail.toLowerCase().includes(key))?.[1] ?? (detail || fallback);
}
