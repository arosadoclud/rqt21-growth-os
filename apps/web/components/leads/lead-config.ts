import type {
  LeadActivity,
  LeadActivityType,
  LeadSource,
  LeadStatus,
} from "@rqt21/contracts";
import {
  AtSign,
  CalendarCheck,
  FileCheck2,
  History,
  Import,
  MessageCircle,
  MessageSquareText,
  PhoneCall,
  Trophy,
  UserPlus,
  XCircle,
} from "lucide-react";

import type { StatusTone } from "@/components/design-system/status-badge";

export const LEAD_STATUS_LABELS: Record<LeadStatus, string> = {
  NEW: "Nuevo",
  CONTACTED: "Contactado",
  QUALIFIED: "Calificado",
  PROPOSAL: "Propuesta enviada",
  WON: "Ganado",
  LOST: "Perdido",
  ARCHIVED: "Archivado",
};

export const LEAD_STATUS_TONES: Record<LeadStatus, StatusTone> = {
  NEW: "info",
  CONTACTED: "accent",
  QUALIFIED: "warning",
  PROPOSAL: "warning",
  WON: "success",
  LOST: "danger",
  ARCHIVED: "neutral",
};

export const LEAD_SOURCE_LABELS: Record<LeadSource, string> = {
  LANDING_PAGE: "Página de captura",
  WHATSAPP: "WhatsApp",
  INSTAGRAM: "Instagram",
  FACEBOOK: "Facebook",
  META_ADS: "Anuncios de Meta",
  ORGANIC: "Orgánico",
  REFERRAL: "Referido",
  MANUAL: "Carga manual",
  IMPORT: "Importación",
  OTHER: "Otro",
};

export const ACTIVITY_LABELS: Record<LeadActivityType, string> = {
  CREATED: "Lead creado",
  STATUS_CHANGED: "Estado actualizado",
  NOTE_ADDED: "Nota añadida",
  CONTACT_ATTEMPT: "Intento de contacto",
  WHATSAPP_SENT: "WhatsApp enviado",
  EMAIL_SENT: "Correo enviado",
  MEETING_SCHEDULED: "Reunión programada",
  PROPOSAL_SENT: "Propuesta enviada",
  WON: "Lead ganado",
  LOST: "Lead perdido",
  IMPORTED: "Lead importado",
};

export const ACTIVITY_ICONS: Record<LeadActivityType, typeof History> = {
  CREATED: UserPlus,
  STATUS_CHANGED: History,
  NOTE_ADDED: MessageSquareText,
  CONTACT_ATTEMPT: PhoneCall,
  WHATSAPP_SENT: MessageCircle,
  EMAIL_SENT: AtSign,
  MEETING_SCHEDULED: CalendarCheck,
  PROPOSAL_SENT: FileCheck2,
  WON: Trophy,
  LOST: XCircle,
  IMPORTED: Import,
};

export const ACTIVITY_OPTIONS: LeadActivityType[] = [
  "NOTE_ADDED",
  "CONTACT_ATTEMPT",
  "WHATSAPP_SENT",
  "EMAIL_SENT",
  "MEETING_SCHEDULED",
  "PROPOSAL_SENT",
];

export function formatLeadDate(value: string) {
  return new Date(value).toLocaleString("es", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function leadName(lead: { first_name: string; last_name: string | null }) {
  return `${lead.first_name}${lead.last_name ? ` ${lead.last_name}` : ""}`;
}

export function activityDescription(activity: LeadActivity) {
  const from = activity.metadata.from;
  const to = activity.metadata.to;
  if (
    typeof from === "string" &&
    typeof to === "string" &&
    from in LEAD_STATUS_LABELS &&
    to in LEAD_STATUS_LABELS
  ) {
    return `${LEAD_STATUS_LABELS[from as LeadStatus]} → ${LEAD_STATUS_LABELS[to as LeadStatus]}`;
  }
  if (activity.description === "Lead created") return "El lead fue añadido al CRM.";
  if (activity.description === "Archived") return "El lead fue archivado.";
  return activity.description;
}
