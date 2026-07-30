import type {
  AutomationActionType,
  AutomationTriggerType,
  ConnectionStatus,
  Platform,
  PublishingProviderName,
  Role,
} from "@rqt21/contracts";

import type { StatusTone } from "@/components/design-system/status-badge";

export const ROLE_LABELS: Record<Role, string> = {
  OWNER: "Propietario",
  ADMIN: "Administrador",
  MARKETER: "Marketing",
  SALES: "Ventas",
  ANALYST: "Analista",
  VIEWER: "Observador",
};

export const ROLE_DESCRIPTIONS: Record<Role, string> = {
  OWNER: "Control total de la organización y sus administradores.",
  ADMIN: "Administra configuración, equipo y automatizaciones.",
  MARKETER: "Gestiona estrategia, contenido y recursos.",
  SALES: "Trabaja con leads, publicaciones y seguimiento comercial.",
  ANALYST: "Consulta datos agregados sin información privada.",
  VIEWER: "Acceso de lectura limitado.",
};

export const ROLE_TONES: Record<Role, StatusTone> = {
  OWNER: "accent",
  ADMIN: "info",
  MARKETER: "success",
  SALES: "warning",
  ANALYST: "neutral",
  VIEWER: "neutral",
};

export const CONNECTION_STATUS_LABELS: Record<ConnectionStatus, string> = {
  PENDING: "Pendiente",
  ACTIVE: "Activa",
  EXPIRED: "Token expirado",
  REVOKED: "Revocada",
  ERROR: "Con error",
  DISABLED: "Deshabilitada",
};

export const CONNECTION_STATUS_TONES: Record<ConnectionStatus, StatusTone> = {
  PENDING: "warning",
  ACTIVE: "success",
  EXPIRED: "warning",
  REVOKED: "danger",
  ERROR: "danger",
  DISABLED: "neutral",
};

export const PUBLISHING_PROVIDER_LABELS: Record<PublishingProviderName, string> = {
  MOCK: "Simulado",
  MANUAL: "Publicación manual",
  META: "Meta",
  LINKEDIN: "LinkedIn",
  YOUTUBE: "YouTube",
  TIKTOK: "TikTok",
  PINTEREST: "Pinterest",
};

export const OPERATIONS_PLATFORM_LABELS: Record<Platform, string> = {
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

export const AUTOMATION_TRIGGER_LABELS: Record<AutomationTriggerType, string> = {
  CONTENT_APPROVED: "Contenido aprobado",
  CALENDAR_ITEM_DUE: "Vencimiento en calendario",
  PUBLICATION_FAILED: "Publicación fallida",
  LEAD_CREATED: "Lead creado",
  LEAD_STATUS_CHANGED: "Cambio de estado del lead",
};

export const AUTOMATION_ACTION_LABELS: Record<AutomationActionType, string> = {
  CREATE_PUBLICATION_DRAFT: "Crear borrador de publicación",
  GENERATE_TRACKING_LINK: "Generar enlace de seguimiento",
  SCHEDULE_RETRY: "Programar reintento",
  CREATE_LEAD_ACTIVITY: "Registrar actividad del lead",
  SEND_INTERNAL_NOTIFICATION: "Enviar notificación interna",
};

export interface AutomationTemplate {
  trigger: AutomationTriggerType;
  action: AutomationActionType;
  label: string;
  description: string;
}

export const AUTOMATION_TEMPLATES: AutomationTemplate[] = [
  {
    trigger: "CONTENT_APPROVED",
    action: "CREATE_PUBLICATION_DRAFT",
    label: "Contenido aprobado → crear borrador de publicación",
    description: "Prepara el siguiente paso sin publicar automáticamente.",
  },
  {
    trigger: "CONTENT_APPROVED",
    action: "GENERATE_TRACKING_LINK",
    label: "Contenido aprobado → generar enlace de seguimiento",
    description: "Crea un enlace medible cuando la pieza queda aprobada.",
  },
  {
    trigger: "PUBLICATION_FAILED",
    action: "SCHEDULE_RETRY",
    label: "Publicación fallida → programar reintento",
    description: "Reintenta una distribución fallida bajo las reglas del sistema.",
  },
  {
    trigger: "PUBLICATION_FAILED",
    action: "SEND_INTERNAL_NOTIFICATION",
    label: "Publicación fallida → notificar",
    description: "Avisa al equipo para que pueda intervenir.",
  },
  {
    trigger: "LEAD_CREATED",
    action: "CREATE_LEAD_ACTIVITY",
    label: "Lead creado → registrar actividad",
    description: "Añade contexto automático al timeline del lead.",
  },
  {
    trigger: "LEAD_STATUS_CHANGED",
    action: "CREATE_LEAD_ACTIVITY",
    label: "Cambio de estado de lead → registrar actividad",
    description: "Documenta automáticamente cada cambio de etapa.",
  },
  {
    trigger: "LEAD_STATUS_CHANGED",
    action: "SEND_INTERNAL_NOTIFICATION",
    label: "Cambio de estado de lead → notificar",
    description: "Informa al equipo cuando cambia una oportunidad.",
  },
  {
    trigger: "CALENDAR_ITEM_DUE",
    action: "SEND_INTERNAL_NOTIFICATION",
    label: "Vencimiento de calendario → notificar",
    description: "Avisa cuando una pieza editorial llega a su fecha.",
  },
];

export function formatOperationsDate(value: string | null | undefined): string {
  if (!value) return "Sin actividad";
  return new Intl.DateTimeFormat("es", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
