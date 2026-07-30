"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AudioLines,
  Download,
  ExternalLink,
  File,
  FileText,
  ImageIcon,
  LockKeyhole,
  Trash2,
  Video,
} from "lucide-react";
import type { Asset } from "@rqt21/contracts";

import { Drawer } from "@/components/design-system/drawer";
import { StatusBadge } from "@/components/design-system/status-badge";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

import {
  assetDimensions,
  assetPreviewUrl,
  ASSET_STATUS_LABELS,
  ASSET_STATUS_TONES,
  ASSET_TYPE_LABELS,
  canRenderAssetUrl,
  formatAssetDate,
  formatAssetSize,
} from "./asset-config";

export function AssetThumbnail({
  asset,
  previewUrl,
  className,
}: {
  asset: Asset;
  previewUrl?: string | null;
  className?: string;
}) {
  const renderable = previewUrl && canRenderAssetUrl(previewUrl);
  const Icon =
    asset.asset_type === "IMAGE" || asset.asset_type === "THUMBNAIL"
      ? ImageIcon
      : asset.asset_type === "VIDEO"
        ? Video
        : asset.asset_type === "AUDIO"
          ? AudioLines
          : asset.asset_type === "DOCUMENT"
            ? FileText
            : File;

  if (
    renderable &&
    (asset.asset_type === "IMAGE" || asset.asset_type === "THUMBNAIL")
  ) {
    return (
      // Signed asset URLs are intentionally dynamic and cannot use Next Image host allowlists.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={previewUrl}
        alt={asset.alt_text || `Vista previa de ${asset.original_filename}`}
        className={cn("h-full w-full object-cover", className)}
      />
    );
  }

  return (
    <span
      className={cn(
        "flex h-full w-full flex-col items-center justify-center gap-3 bg-gradient-to-br from-interactive via-card to-muted/70 text-muted-foreground",
        className,
      )}
      aria-hidden
    >
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-border bg-elevated/80 shadow-sm">
        <Icon className="h-5 w-5" />
      </span>
      <span className="text-[10px] font-semibold uppercase tracking-[0.16em]">
        {ASSET_TYPE_LABELS[asset.asset_type]}
      </span>
    </span>
  );
}

export function AssetPreviewSurface({
  asset,
  previewUrl,
  loading,
  error,
  onLoad,
}: {
  asset: Asset;
  previewUrl: string | null;
  loading: boolean;
  error: string | null;
  onLoad?: () => void;
}) {
  if (loading) {
    return (
      <div className="flex min-h-72 items-center justify-center rounded-2xl border border-border bg-interactive/40">
        <span className="text-sm text-muted-foreground">Preparando vista previa…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" className="flex min-h-72 items-center justify-center rounded-2xl border border-dashed border-destructive/30 bg-destructive/5 p-6 text-center text-sm text-destructive">
        {error}
      </div>
    );
  }

  if (!previewUrl || !canRenderAssetUrl(previewUrl)) {
    return (
      <div className="relative min-h-72 overflow-hidden rounded-2xl border border-border">
        <AssetThumbnail asset={asset} className="absolute inset-0" />
        {previewUrl?.startsWith("mock://") && (
          <p className="absolute inset-x-5 bottom-5 rounded-xl border border-border bg-elevated/90 p-3 text-center text-xs text-muted-foreground backdrop-blur">
            El almacenamiento simulado no entrega una vista visual del archivo.
          </p>
        )}
      </div>
    );
  }

  if (asset.asset_type === "IMAGE" || asset.asset_type === "THUMBNAIL") {
    return (
      <div className="flex min-h-72 items-center justify-center overflow-hidden rounded-2xl border border-border bg-interactive/40">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={previewUrl}
          alt={asset.alt_text || `Vista previa de ${asset.original_filename}`}
          className="max-h-[32rem] w-full object-contain"
          onLoad={onLoad}
        />
      </div>
    );
  }

  if (asset.asset_type === "VIDEO") {
    return (
      <video
        src={previewUrl}
        controls
        preload="metadata"
        className="max-h-[32rem] w-full rounded-2xl border border-border bg-black"
        onLoadedMetadata={onLoad}
      >
        Tu navegador no puede reproducir este video.
      </video>
    );
  }

  if (asset.asset_type === "AUDIO") {
    return (
      <div className="rounded-2xl border border-border bg-interactive/40 p-8">
        <AssetThumbnail asset={asset} className="min-h-44 rounded-xl" />
        <audio src={previewUrl} controls className="mt-5 w-full" onLoadedMetadata={onLoad}>
          Tu navegador no puede reproducir este audio.
        </audio>
      </div>
    );
  }

  if (asset.asset_type === "DOCUMENT" && asset.mime_type === "application/pdf") {
    return (
      <iframe
        src={previewUrl}
        title={`Vista previa de ${asset.original_filename}`}
        className="h-[32rem] w-full rounded-2xl border border-border bg-white"
        onLoad={onLoad}
      />
    );
  }

  return (
    <div className="relative min-h-72 overflow-hidden rounded-2xl border border-border">
      <AssetThumbnail asset={asset} className="absolute inset-0" />
    </div>
  );
}

export function AssetPreviewDrawer({
  open,
  onOpenChange,
  asset,
  currentOrgId,
  brandName,
  canPreview,
  canWrite,
  onRequestArchive,
  onPreviewUrl,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  asset: Asset | null;
  currentOrgId: string;
  brandName?: string;
  canPreview: boolean;
  canWrite: boolean;
  onRequestArchive: (asset: Asset) => void;
  onPreviewUrl?: (assetId: string, url: string) => void;
}) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPreview = useCallback(async () => {
    if (!asset || !canPreview || asset.status !== "READY") return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.assetDownloadUrl(currentOrgId, asset.id);
      const url = assetPreviewUrl(result.url);
      setPreviewUrl(url);
      onPreviewUrl?.(asset.id, url);
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos preparar la vista previa.",
      );
    } finally {
      setLoading(false);
    }
  }, [asset, canPreview, currentOrgId, onPreviewUrl]);

  useEffect(() => {
    setPreviewUrl(null);
    setError(null);
    if (open) void loadPreview();
  }, [loadPreview, open]);

  if (!asset) return null;

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={asset.original_filename}
      description={`${ASSET_TYPE_LABELS[asset.asset_type]} · ${formatAssetSize(asset.size_bytes)}`}
      className="max-w-2xl"
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
          {canWrite && asset.status !== "ARCHIVED" ? (
            <Button
              variant="ghost"
              className="text-destructive hover:bg-destructive/10 hover:text-destructive"
              onClick={() => onRequestArchive(asset)}
            >
              <Trash2 className="h-4 w-4" />
              Eliminar de la biblioteca
            </Button>
          ) : <span />}
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button variant="outline" onClick={() => onOpenChange(false)}>Cerrar</Button>
            <Button asChild>
              <Link href={`/assets/${asset.id}`}>
                Ver detalle
                <ExternalLink className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-5">
        <AssetPreviewSurface
          asset={asset}
          previewUrl={previewUrl}
          loading={loading}
          error={error}
        />

        {!canPreview && (
          <div className="flex gap-3 rounded-xl border border-border bg-interactive/40 p-4">
            <LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium text-foreground">Vista previa protegida</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                Tu rol puede consultar los metadatos, pero no acceder al archivo privado.
              </p>
            </div>
          </div>
        )}

        {asset.status !== "READY" && (
          <div className="rounded-xl border border-border bg-interactive/40 p-4 text-sm text-muted-foreground">
            La vista previa estará disponible cuando el recurso termine de procesarse.
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            label={ASSET_STATUS_LABELS[asset.status]}
            tone={ASSET_STATUS_TONES[asset.status]}
          />
          <span className="text-xs text-muted-foreground">{formatAssetDate(asset.created_at)}</span>
          {brandName && <span className="text-xs text-muted-foreground">· {brandName}</span>}
        </div>

        <dl className="grid gap-3 rounded-xl border border-border bg-card p-4 text-sm sm:grid-cols-2">
          <Metadata label="Dimensiones" value={assetDimensions(asset)} />
          <Metadata label="Formato" value={asset.mime_type || "Sin identificar"} />
          <Metadata label="Texto alternativo" value={asset.alt_text || "Sin texto alternativo"} />
          <Metadata label="Descripción" value={asset.caption || "Sin descripción"} />
        </dl>

        {previewUrl && canRenderAssetUrl(previewUrl) && (
          <Button variant="outline" size="sm" asChild>
            <a href={previewUrl} target="_blank" rel="noreferrer">
              <Download className="h-4 w-4" />
              Abrir archivo
            </a>
          </Button>
        )}
      </div>
    </Drawer>
  );
}

function Metadata({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-words font-medium text-foreground">{value}</dd>
    </div>
  );
}
