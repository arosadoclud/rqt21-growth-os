"use client";

import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Download,
  Edit3,
  FileText,
  ImageIcon,
  Plus,
  RefreshCw,
  Ruler,
  Sparkles,
  Trash2,
} from "lucide-react";
import type {
  Asset,
  AssetVariant,
  Brand,
  ThumbnailContentStyle,
  ThumbnailFormat,
  VariantType,
} from "@rqt21/contracts";
import { VARIANT_TYPES } from "@rqt21/contracts";

import { AssetPreviewSurface } from "@/components/assets/asset-preview";
import { ConfirmationDialog } from "@/components/design-system/confirmation-dialog";
import { Drawer } from "@/components/design-system/drawer";
import { MetricCard } from "@/components/design-system/metric-card";
import { PageHeader } from "@/components/design-system/page-header";
import { SectionHeader } from "@/components/design-system/section-header";
import { StatusBadge } from "@/components/design-system/status-badge";
import { LoadingSkeleton, StatePanel } from "@/components/design-system/state-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";
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
  VARIANT_STATUS_LABELS,
  VARIANT_STATUS_TONES,
  VARIANT_TYPE_LABELS,
} from "./asset-config";

const THUMBNAIL_CONTENT_STYLES: {
  value: ThumbnailContentStyle;
  label: string;
}[] = [
  { value: "receta", label: "Receta" },
  { value: "curiosidad", label: "Curiosidad" },
  { value: "encuesta", label: "Encuesta" },
  { value: "antes_despues", label: "Antes / Después" },
  { value: "receta_rapida", label: "Receta rápida" },
  { value: "educativo", label: "Educativo" },
];

export function AssetDetail({ assetId }: { assetId: string }) {
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canWrite = canWriteGrowth(organization?.role);
  const canPreview = ["OWNER", "ADMIN", "MARKETER", "SALES"].includes(
    organization?.role ?? "",
  );

  const [asset, setAsset] = useState<Asset | null>(null);
  const [variants, setVariants] = useState<AssetVariant[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [variantOpen, setVariantOpen] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);

  const load = useCallback(async () => {
    if (!currentOrgId || !assetId) return;
    setLoading(true);
    setError(null);
    try {
      const [assetResult, variantResult, brandResult] = await Promise.all([
        api.getAsset(currentOrgId, assetId),
        api.listAssetVariants(currentOrgId, assetId),
        api.listBrands(currentOrgId).catch(() => []),
      ]);
      setAsset(assetResult);
      setVariants(variantResult);
      setBrands(brandResult);
    } catch (loadError) {
      setAsset(null);
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar el recurso.",
      );
    } finally {
      setLoading(false);
    }
  }, [assetId, currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  const brandName = useMemo(
    () => brands.find((brand) => brand.id === asset?.brand_id)?.name,
    [asset?.brand_id, brands],
  );

  const getDownloadUrl = async () => {
    if (!currentOrgId || !asset) return;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const result = await api.assetDownloadUrl(currentOrgId, asset.id);
      setPreviewUrl(assetPreviewUrl(result.url));
    } catch (urlError) {
      setPreviewError(
        urlError instanceof ApiError
          ? urlError.detail
          : "No pudimos preparar el archivo.",
      );
    } finally {
      setPreviewLoading(false);
    }
  };

  const archive = async () => {
    if (!currentOrgId || !asset) return;
    setBusy(true);
    setError(null);
    try {
      await api.archiveAsset(currentOrgId, asset.id);
      setArchiveOpen(false);
      await load();
    } catch (archiveError) {
      setError(
        archiveError instanceof ApiError
          ? archiveError.detail
          : "No pudimos eliminar el recurso de la biblioteca.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (!currentOrgId) {
    return (
      <StatePanel
        title="Selecciona una organización"
        description="El detalle aparecerá cuando elijas una organización."
      />
    );
  }

  if (loading && !asset) {
    return (
      <Card className="bg-card/80 shadow-none">
        <CardContent className="p-5"><LoadingSkeleton rows={7} /></CardContent>
      </Card>
    );
  }

  if (!asset) {
    return (
      <StatePanel
        tone={error ? "error" : "neutral"}
        title="Activo no encontrado."
        description="El recurso no existe, pertenece a otra organización o ya no está disponible."
        actionLabel="Volver a la biblioteca"
        onAction={() => { window.location.href = "/assets"; }}
      />
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Detalle del recurso"
        title={asset.original_filename}
        description={`${ASSET_TYPE_LABELS[asset.asset_type]} · ${formatAssetSize(asset.size_bytes)} · añadido ${formatAssetDate(asset.created_at)}`}
        metadata={
          <>
            <StatusBadge
              label={ASSET_STATUS_LABELS[asset.status]}
              tone={ASSET_STATUS_TONES[asset.status]}
            />
            <span className="text-xs text-muted-foreground">{asset.public_id}</span>
          </>
        }
        actions={
          <>
            <Button variant="outline" size="sm" asChild>
              <Link href="/assets">
                <ArrowLeft className="h-4 w-4" />
                Biblioteca
              </Link>
            </Button>
            <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
            {canPreview && asset.status === "READY" && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => void getDownloadUrl()}
                disabled={previewLoading}
              >
                <Download className="h-4 w-4" />
                Generar URL firmada
              </Button>
            )}
            {canWrite && asset.status !== "ARCHIVED" && (
              <Button size="sm" onClick={() => setEditOpen(true)}>
                <Edit3 className="h-4 w-4" />
                Editar información
              </Button>
            )}
          </>
        }
      />

      {error && (
        <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(20rem,0.8fr)]">
        <div className="space-y-4">
          <SectionHeader
            title="Vista previa"
            description={
              canPreview
                ? "Genera un acceso temporal para revisar el archivo privado."
                : "Tu rol puede ver metadatos, pero no abrir el archivo privado."
            }
          />
          <AssetPreviewSurface
            asset={asset}
            previewUrl={previewUrl}
            loading={previewLoading}
            error={previewError}
          />
          {previewUrl && canRenderAssetUrl(previewUrl) && (
            <Button variant="outline" size="sm" asChild>
              <a href={previewUrl} target="_blank" rel="noreferrer">
                <Download className="h-4 w-4" />
                Abrir archivo en otra pestaña
              </a>
            </Button>
          )}
        </div>

        <div className="space-y-4">
          <SectionHeader title="Información" description="Datos técnicos y editoriales del recurso." />
          <Card className="bg-card/85 shadow-none">
            <CardContent className="p-5">
              <dl className="space-y-4 text-sm">
                <Metadata label="Marca" value={brandName ?? "Sin marca"} />
                <Metadata label="Formato" value={asset.mime_type || "Sin identificar"} />
                <Metadata label="Dimensiones" value={assetDimensions(asset)} />
                <Metadata
                  label="Duración"
                  value={
                    asset.duration_seconds
                      ? `${Math.round(asset.duration_seconds)} segundos`
                      : "No aplica"
                  }
                />
                <Metadata
                  label="Texto alternativo"
                  value={asset.alt_text || "Sin texto alternativo"}
                  warning={
                    (asset.asset_type === "IMAGE" || asset.asset_type === "THUMBNAIL") &&
                    !asset.alt_text
                  }
                />
                <Metadata label="Descripción" value={asset.caption || "Sin descripción"} />
                <Metadata
                  label="Identificador de integridad"
                  value={asset.checksum_sha256 || "Pendiente"}
                  mono
                />
              </dl>
              {typeof asset.metadata?.duplicate_of === "string" && (
                <div className="mt-5 rounded-xl border border-warning/25 bg-warning/5 p-3 text-xs text-warning">
                  Este archivo coincide con otro recurso de la biblioteca.
                </div>
              )}
              {canWrite && asset.status !== "ARCHIVED" && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-5 text-destructive hover:bg-destructive/10 hover:text-destructive"
                  onClick={() => setArchiveOpen(true)}
                >
                  <Trash2 className="h-4 w-4" />
                  Eliminar de la biblioteca
                </Button>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <section className="grid gap-4 sm:grid-cols-3" aria-label="Datos del archivo">
        <MetricCard
          label="Tamaño"
          value={formatAssetSize(asset.size_bytes)}
          helper="Peso del archivo original"
          icon={FileText}
        />
        <MetricCard
          label="Dimensiones"
          value={asset.width && asset.height ? `${asset.width} × ${asset.height}` : "—"}
          helper="Ancho y alto en píxeles"
          icon={Ruler}
        />
        <MetricCard
          label="Variantes"
          value={variants.length}
          helper="Adaptaciones generadas"
          icon={ImageIcon}
          tone="info"
        />
      </section>

      <section className="space-y-4">
        <SectionHeader
          title="Variantes"
          description="Adaptaciones del archivo para diferentes canales y formatos."
          action={
            canWrite && asset.status === "READY" ? (
              <Button size="sm" variant="outline" onClick={() => setVariantOpen(true)}>
                <Plus className="h-4 w-4" />
                Nueva variante
              </Button>
            ) : undefined
          }
        />
        {variants.length === 0 ? (
          <StatePanel
            compact
            title="Sin variantes"
            description="Cuando generes una adaptación para otra plataforma aparecerá aquí."
          />
        ) : (
          <Card className="overflow-hidden bg-card/85 shadow-none">
            <div className="hidden grid-cols-[1fr_1fr_1fr_0.8fr] gap-4 border-b border-border bg-interactive/35 px-5 py-3 sm:grid">
              {["Plataforma", "Formato", "Dimensiones", "Estado"].map((label) => (
                <span key={label} className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  {label}
                </span>
              ))}
            </div>
            <ul className="divide-y divide-border">
              {variants.map((variant) => (
                <li
                  key={variant.id}
                  className="grid gap-3 px-4 py-4 sm:grid-cols-[1fr_1fr_1fr_0.8fr] sm:items-center sm:gap-4 sm:px-5"
                >
                  <span className="text-sm font-medium text-foreground">{variant.platform}</span>
                  <span className="text-sm text-muted-foreground">
                    {VARIANT_TYPE_LABELS[variant.variant_type]}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {variant.width && variant.height
                      ? `${variant.width} × ${variant.height} px`
                      : "Automáticas"}
                  </span>
                  <StatusBadge
                    label={VARIANT_STATUS_LABELS[variant.status]}
                    tone={VARIANT_STATUS_TONES[variant.status]}
                    className="w-fit"
                  />
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>

      {canWrite && asset.status === "READY" && asset.asset_type === "VIDEO" && (
        <ThumbnailGenerator
          currentOrgId={currentOrgId}
          assetId={asset.id}
          onGenerated={load}
        />
      )}

      <EditAssetDrawer
        open={editOpen}
        onOpenChange={setEditOpen}
        currentOrgId={currentOrgId}
        asset={asset}
        brands={brands}
        onSaved={async () => {
          setEditOpen(false);
          await load();
        }}
      />

      <CreateVariantDrawer
        open={variantOpen}
        onOpenChange={setVariantOpen}
        currentOrgId={currentOrgId}
        assetId={asset.id}
        onCreated={async () => {
          setVariantOpen(false);
          await load();
        }}
      />

      <ConfirmationDialog
        open={archiveOpen}
        onOpenChange={(open) => {
          if (!busy) setArchiveOpen(open);
        }}
        title="¿Eliminar de la biblioteca?"
        description={`“${asset.original_filename}” dejará de estar disponible para nuevos usos. Se conservará archivado para proteger publicaciones e historial.`}
        confirmLabel="Eliminar de la biblioteca"
        tone="danger"
        busy={busy}
        onConfirm={archive}
      />
    </div>
  );
}

function EditAssetDrawer({
  open,
  onOpenChange,
  currentOrgId,
  asset,
  brands,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentOrgId: string;
  asset: Asset;
  brands: Brand[];
  onSaved: () => Promise<void>;
}) {
  const [altText, setAltText] = useState("");
  const [caption, setCaption] = useState("");
  const [brandId, setBrandId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [genBusy, setGenBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setAltText(asset.alt_text ?? "");
    setCaption(asset.caption ?? "");
    setBrandId(asset.brand_id ?? "");
    setError(null);
  }, [asset, open]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.updateAsset(currentOrgId, asset.id, {
        alt_text: altText.trim() || null,
        caption: caption.trim() || null,
        brand_id: brandId || null,
      });
      await onSaved();
    } catch (saveError) {
      setError(
        saveError instanceof ApiError
          ? saveError.detail
          : "No pudimos guardar los cambios.",
      );
    } finally {
      setBusy(false);
    }
  };

  const generateAlt = async () => {
    if (!currentOrgId) return;
    setGenBusy(true);
    setError(null);
    try {
      const updated = await api.generateAssetAltText(currentOrgId, asset.id);
      setAltText(updated.alt_text ?? "");
    } catch (genError) {
      setError(genError instanceof ApiError ? genError.detail : "No pudimos generar el texto alternativo.");
    } finally {
      setGenBusy(false);
    }
  };

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title="Editar información"
      description="Mejora la descripción y accesibilidad del recurso sin reemplazar el archivo."
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy || genBusy}>
            Cancelar
          </Button>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => void generateAlt()} disabled={busy || genBusy}>
              {genBusy ? "Generando…" : "Autogenerar"}
            </Button>
            <Button type="submit" form="edit-asset-form" disabled={busy || genBusy}>
              {busy ? "Guardando…" : "Guardar cambios"}
            </Button>
          </div>
        </div>
      }
    >
      <form id="edit-asset-form" onSubmit={submit} className="space-y-5">
        <FormField label="Marca" optional>
          <Select value={brandId} onChange={(event) => setBrandId(event.target.value)}>
            <option value="">Sin marca</option>
            {brands.map((brand) => (
              <option key={brand.id} value={brand.id}>{brand.name}</option>
            ))}
          </Select>
        </FormField>
        <FormField
          label="Texto alternativo"
          optional
          helper="Describe el contenido visual de forma clara y breve."
        >
          <Input value={altText} onChange={(event) => setAltText(event.target.value)} />
        </FormField>
        <FormField label="Descripción" optional>
          <Textarea value={caption} onChange={(event) => setCaption(event.target.value)} rows={5} />
        </FormField>
        {error && <InlineError>{error}</InlineError>}
      </form>
    </Drawer>
  );
}

function CreateVariantDrawer({
  open,
  onOpenChange,
  currentOrgId,
  assetId,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentOrgId: string;
  assetId: string;
  onCreated: () => Promise<void>;
}) {
  const [platform, setPlatform] = useState("INSTAGRAM");
  const [variantType, setVariantType] = useState<VariantType>("STORY");
  const [width, setWidth] = useState("1080");
  const [height, setHeight] = useState("1920");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setPlatform("INSTAGRAM");
    setVariantType("STORY");
    setWidth("1080");
    setHeight("1920");
    setError(null);
  }, [open]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createAssetVariant(currentOrgId, assetId, {
        platform: platform.trim(),
        variant_type: variantType,
        width: Number(width) || null,
        height: Number(height) || null,
      });
      await onCreated();
    } catch (createError) {
      setError(
        createError instanceof ApiError
          ? createError.detail
          : "No pudimos crear la variante.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title="Nueva variante"
      description="Prepara una adaptación del recurso para otro formato o canal."
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancelar
          </Button>
          <Button type="submit" form="create-variant-form" disabled={busy}>
            {busy ? "Creando…" : "Crear variante"}
          </Button>
        </div>
      }
    >
      <form id="create-variant-form" onSubmit={submit} className="space-y-5">
        <FormField label="Plataforma">
          <Input value={platform} onChange={(event) => setPlatform(event.target.value)} required />
        </FormField>
        <FormField label="Formato">
          <Select value={variantType} onChange={(event) => setVariantType(event.target.value as VariantType)}>
            {VARIANT_TYPES.map((type) => (
              <option key={type} value={type}>{VARIANT_TYPE_LABELS[type]}</option>
            ))}
          </Select>
        </FormField>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Ancho"><Input inputMode="numeric" value={width} onChange={(event) => setWidth(event.target.value)} /></FormField>
          <FormField label="Alto"><Input inputMode="numeric" value={height} onChange={(event) => setHeight(event.target.value)} /></FormField>
        </div>
        {error && <InlineError>{error}</InlineError>}
      </form>
    </Drawer>
  );
}

function ThumbnailGenerator({
  currentOrgId,
  assetId,
  onGenerated,
}: {
  currentOrgId: string;
  assetId: string;
  onGenerated: () => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [benefits, setBenefits] = useState(["", "", ""]);
  const [cta, setCta] = useState("");
  const [style, setStyle] = useState<ThumbnailContentStyle | "">("");
  const [format, setFormat] = useState<ThumbnailFormat>("vertical");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.generateThumbnail(currentOrgId, assetId, {
        title: title.trim(),
        subtitle: subtitle.trim() || null,
        benefits: benefits.map((benefit) => benefit.trim()).filter(Boolean),
        cta_banner: cta.trim() || null,
        content_style: style || null,
        format,
      });
      setTitle("");
      setSubtitle("");
      setBenefits(["", "", ""]);
      setCta("");
      await onGenerated();
    } catch (generateError) {
      setError(
        generateError instanceof ApiError
          ? generateError.detail
          : "No pudimos generar la miniatura.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="space-y-4">
      <SectionHeader
        title="Miniatura con IA"
        description="Crea una portada de video alineada con el contenido y formato final."
      />
      <Card className="bg-card/85 shadow-none">
        <CardContent className="p-5">
          <form onSubmit={submit} className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Título">
                <Input required maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} />
              </FormField>
              <FormField label="Subtítulo" optional>
                <Input maxLength={200} value={subtitle} onChange={(event) => setSubtitle(event.target.value)} />
              </FormField>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              {benefits.map((benefit, index) => (
                <FormField key={index} label={`Beneficio ${index + 1}`} optional>
                  <Input
                    maxLength={80}
                    value={benefit}
                    onChange={(event) =>
                      setBenefits((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? event.target.value : item,
                        ),
                      )
                    }
                  />
                </FormField>
              ))}
            </div>
            <div className="grid gap-4 lg:grid-cols-3">
              <FormField label="Llamado a la acción" optional>
                <Input maxLength={200} value={cta} onChange={(event) => setCta(event.target.value)} />
              </FormField>
              <FormField label="Estilo" optional>
                <Select value={style} onChange={(event) => setStyle(event.target.value as ThumbnailContentStyle | "")}>
                  <option value="">Sin estilo específico</option>
                  {THUMBNAIL_CONTENT_STYLES.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </Select>
              </FormField>
              <FormField label="Formato">
                <Select value={format} onChange={(event) => setFormat(event.target.value as ThumbnailFormat)}>
                  <option value="vertical">Vertical · Reel o historia</option>
                  <option value="facebook_horizontal">Horizontal · Facebook</option>
                </Select>
              </FormField>
            </div>
            {error && <InlineError>{error}</InlineError>}
            <Button type="submit" disabled={busy || !title.trim()}>
              <Sparkles className="h-4 w-4" />
              {busy ? "Generando…" : "Generar miniatura con IA"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </section>
  );
}

function Metadata({
  label,
  value,
  warning,
  mono,
}: {
  label: string;
  value: string;
  warning?: boolean;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={cn("mt-1 break-words font-medium text-foreground", warning && "text-warning", mono && "font-mono text-xs")}>
        {value}
      </dd>
    </div>
  );
}

function FormField({
  label,
  optional,
  helper,
  children,
}: {
  label: string;
  optional?: boolean;
  helper?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5 text-sm">
      <span className="font-medium text-foreground">
        {label}
        {optional && <span className="ml-1 font-normal text-muted-foreground">(opcional)</span>}
      </span>
      {children}
      {helper && <span className="block text-xs leading-5 text-muted-foreground">{helper}</span>}
    </label>
  );
}

function InlineError({ children }: { children: React.ReactNode }) {
  return (
    <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive">
      {children}
    </div>
  );
}
