import type {
  Asset,
  AssetStatus,
  AssetType,
  VariantStatus,
  VariantType,
} from "@rqt21/contracts";

import type { StatusTone } from "@/components/design-system/status-badge";

export const ASSET_TYPE_LABELS: Record<AssetType, string> = {
  IMAGE: "Imagen",
  VIDEO: "Video",
  DOCUMENT: "Documento",
  AUDIO: "Audio",
  THUMBNAIL: "Miniatura",
  OTHER: "Otro",
};

export const ASSET_STATUS_LABELS: Record<AssetStatus, string> = {
  UPLOADING: "Subiendo",
  PROCESSING: "Procesando",
  READY: "Disponible",
  REJECTED: "Rechazado",
  FAILED: "Fallido",
  ARCHIVED: "Archivado",
};

export const ASSET_STATUS_TONES: Record<AssetStatus, StatusTone> = {
  UPLOADING: "info",
  PROCESSING: "warning",
  READY: "success",
  REJECTED: "danger",
  FAILED: "danger",
  ARCHIVED: "neutral",
};

export const VARIANT_TYPE_LABELS: Record<VariantType, string> = {
  ORIGINAL: "Original",
  FEED: "Feed",
  PORTRAIT: "Vertical",
  STORY: "Historia",
  REEL: "Reel",
  THUMBNAIL: "Miniatura",
  SQUARE: "Cuadrado",
  LANDSCAPE: "Horizontal",
  CUSTOM: "Personalizado",
};

export const VARIANT_STATUS_LABELS: Record<VariantStatus, string> = {
  PENDING: "Pendiente",
  READY: "Disponible",
  FAILED: "Fallido",
};

export const VARIANT_STATUS_TONES: Record<VariantStatus, StatusTone> = {
  PENDING: "warning",
  READY: "success",
  FAILED: "danger",
};

export function formatAssetSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 KB";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(bytes >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
}

export function formatAssetDate(value: string): string {
  return new Intl.DateTimeFormat("es", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

export function assetDimensions(asset: Asset): string {
  return asset.width && asset.height ? `${asset.width} × ${asset.height} px` : "Sin dimensiones";
}

export function assetPreviewUrl(url: string): string {
  if (!url.startsWith("/")) return url;
  return `${process.env.NEXT_PUBLIC_API_URL ?? ""}${url}`;
}

export function canRenderAssetUrl(url: string): boolean {
  return url.startsWith("/") || url.startsWith("http://") || url.startsWith("https://");
}
