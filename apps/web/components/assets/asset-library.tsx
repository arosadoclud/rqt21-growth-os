"use client";

import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  FileWarning,
  Filter,
  Grid2X2,
  Images,
  List,
  Plus,
  RefreshCw,
  Search,
  Upload,
  Video,
} from "lucide-react";
import type { Asset, AssetStatus, AssetType, Brand } from "@rqt21/contracts";
import { ASSET_STATUSES, ASSET_TYPES } from "@rqt21/contracts";

import { ConfirmationDialog } from "@/components/design-system/confirmation-dialog";
import { Drawer } from "@/components/design-system/drawer";
import { MetricCard } from "@/components/design-system/metric-card";
import { PageHeader } from "@/components/design-system/page-header";
import { Pagination } from "@/components/design-system/pagination";
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
  ASSET_STATUS_LABELS,
  ASSET_STATUS_TONES,
  ASSET_TYPE_LABELS,
  assetDimensions,
  formatAssetDate,
  formatAssetSize,
} from "./asset-config";
import { AssetPreviewDrawer, AssetThumbnail } from "./asset-preview";

type LibraryView = "grid" | "list";

export function AssetLibrary() {
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canWrite = canWriteGrowth(organization?.role);
  const canPreview = ["OWNER", "ADMIN", "MARKETER", "SALES"].includes(
    organization?.role ?? "",
  );

  const [items, setItems] = useState<Asset[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<AssetType | "">("");
  const [statusFilter, setStatusFilter] = useState<AssetStatus | "">("");
  const [brandFilter, setBrandFilter] = useState("");
  const [view, setView] = useState<LibraryView>("grid");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Asset | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({});

  useEffect(() => {
    const stored = window.localStorage.getItem("rqt21.assets.view");
    if (stored === "grid" || stored === "list") setView(stored);
  }, []);

  useEffect(() => {
    window.localStorage.setItem("rqt21.assets.view", view);
  }, [view]);

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const loadBrands = useCallback(async () => {
    if (!currentOrgId) return;
    try {
      setBrands(await api.listBrands(currentOrgId));
    } catch {
      setBrands([]);
    }
  }, [currentOrgId]);

  const loadAssets = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (query) params.q = query;
      if (typeFilter) params.asset_type = typeFilter;
      if (statusFilter) params.status = statusFilter;
      if (brandFilter) params.brand_id = brandFilter;
      setItems(await api.listAssets(currentOrgId, params));
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar la biblioteca.",
      );
    } finally {
      setLoading(false);
    }
  }, [brandFilter, currentOrgId, query, statusFilter, typeFilter]);

  useEffect(() => {
    void loadBrands();
  }, [loadBrands]);

  useEffect(() => {
    void loadAssets();
  }, [loadAssets]);

  useEffect(() => setPage(1), [brandFilter, pageSize, query, statusFilter, typeFilter]);

  const brandNames = useMemo(
    () => Object.fromEntries(brands.map((brand) => [brand.id, brand.name])),
    [brands],
  );
  const pageItems = items.slice((page - 1) * pageSize, page * pageSize);
  const imageCount = items.filter(
    (asset) => asset.asset_type === "IMAGE" || asset.asset_type === "THUMBNAIL",
  ).length;
  const videoCount = items.filter((asset) => asset.asset_type === "VIDEO").length;
  const missingAltCount = items.filter(
    (asset) =>
      (asset.asset_type === "IMAGE" || asset.asset_type === "THUMBNAIL") &&
      !asset.alt_text,
  ).length;
  const hasFilters = Boolean(search || typeFilter || statusFilter || brandFilter);

  const rememberPreviewUrl = useCallback((assetId: string, url: string) => {
    setPreviewUrls((current) => ({ ...current, [assetId]: url }));
  }, []);

  const archiveAsset = async () => {
    if (!currentOrgId || !deleteTarget) return;
    setDeleting(true);
    setError(null);
    try {
      await api.archiveAsset(currentOrgId, deleteTarget.id);
      setDeleteTarget(null);
      setSelectedAsset(null);
      await loadAssets();
    } catch (archiveError) {
      setError(
        archiveError instanceof ApiError
          ? archiveError.detail
          : "No pudimos eliminar el recurso de la biblioteca.",
      );
    } finally {
      setDeleting(false);
    }
  };

  if (!currentOrgId) {
    return (
      <StatePanel
        icon={Images}
        title="Selecciona una organización"
        description="La biblioteca aparecerá cuando elijas una organización."
      />
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Recursos creativos"
        title="Biblioteca de recursos"
        description="Organiza imágenes, videos, documentos y audios; revisa sus metadatos antes de utilizarlos en contenido."
        metadata={
          <>
            <StatusBadge label={`${items.length} recursos`} />
            {!canPreview && (
              <span className="text-xs text-muted-foreground">
                Acceso limitado a metadatos
              </span>
            )}
          </>
        }
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void loadAssets()}
              disabled={loading}
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
            {canWrite && (
              <Button size="sm" onClick={() => setUploadOpen(true)}>
                <Upload className="h-4 w-4" />
                Subir recurso
              </Button>
            )}
          </>
        }
      />

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive"
        >
          {error}
        </div>
      )}

      <section
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
        aria-label="Resumen de recursos"
      >
        <MetricCard
          label="Resultados"
          value={items.length}
          helper="Con los filtros actuales"
          icon={Images}
          tone="neutral"
          loading={loading}
        />
        <MetricCard
          label="Imágenes"
          value={imageCount}
          helper="Incluye miniaturas"
          icon={Images}
          tone="info"
          loading={loading}
        />
        <MetricCard
          label="Videos"
          value={videoCount}
          helper="Recursos audiovisuales"
          icon={Video}
          tone="positive"
          loading={loading}
        />
        <MetricCard
          label="Sin texto alternativo"
          value={missingAltCount}
          helper="Pendientes de accesibilidad"
          icon={FileWarning}
          tone={missingAltCount > 0 ? "warning" : "neutral"}
          loading={loading}
        />
      </section>

      <Card className="bg-card/80 shadow-none">
        <CardContent className="p-4">
          <div className="grid gap-3 xl:grid-cols-[minmax(14rem,1fr)_12rem_12rem_12rem_auto]">
            <label className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Buscar por nombre o descripción…"
                className="pl-9"
                aria-label="Buscar recursos"
              />
            </label>
            <Select
              value={typeFilter}
              onChange={(event) => setTypeFilter(event.target.value as AssetType | "")}
              aria-label="Filtrar por tipo"
            >
              <option value="">Todos los tipos</option>
              {ASSET_TYPES.map((type) => (
                <option key={type} value={type}>{ASSET_TYPE_LABELS[type]}</option>
              ))}
            </Select>
            <Select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as AssetStatus | "")}
              aria-label="Filtrar por estado"
            >
              <option value="">Todos los estados</option>
              {ASSET_STATUSES.map((status) => (
                <option key={status} value={status}>{ASSET_STATUS_LABELS[status]}</option>
              ))}
            </Select>
            <Select
              value={brandFilter}
              onChange={(event) => setBrandFilter(event.target.value)}
              aria-label="Filtrar por marca"
            >
              <option value="">Todas las marcas</option>
              {brands.map((brand) => (
                <option key={brand.id} value={brand.id}>{brand.name}</option>
              ))}
            </Select>
            {hasFilters ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSearch("");
                  setQuery("");
                  setTypeFilter("");
                  setStatusFilter("");
                  setBrandFilter("");
                }}
              >
                Limpiar filtros
              </Button>
            ) : (
              <span className="flex items-center justify-end gap-2 text-xs text-muted-foreground">
                <Filter className="h-3.5 w-3.5" />
                Sin filtros
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">
          {loading ? "Actualizando biblioteca…" : `${items.length} resultados`}
        </p>
        <div
          className="flex rounded-lg border border-border bg-card p-1"
          role="group"
          aria-label="Vista de biblioteca"
        >
          <Button
            variant={view === "grid" ? "secondary" : "ghost"}
            size="icon"
            className="h-8 w-8"
            aria-label="Vista de cuadrícula"
            aria-pressed={view === "grid"}
            onClick={() => setView("grid")}
          >
            <Grid2X2 className="h-4 w-4" />
          </Button>
          <Button
            variant={view === "list" ? "secondary" : "ghost"}
            size="icon"
            className="h-8 w-8"
            aria-label="Vista de lista"
            aria-pressed={view === "list"}
            onClick={() => setView("list")}
          >
            <List className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {loading ? (
        <Card className="bg-card/80 shadow-none">
          <CardContent className="p-5"><LoadingSkeleton rows={6} /></CardContent>
        </Card>
      ) : items.length === 0 ? (
        <StatePanel
          icon={Images}
          title="No encontramos recursos"
          description="Ajusta los filtros o sube el primer archivo a esta biblioteca."
          actionLabel={canWrite ? "Subir recurso" : undefined}
          onAction={canWrite ? () => setUploadOpen(true) : undefined}
        />
      ) : view === "grid" ? (
        <div>
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {pageItems.map((asset) => (
              <li key={asset.id}>
                <button
                  type="button"
                  onClick={() => setSelectedAsset(asset)}
                  className="group w-full overflow-hidden rounded-2xl border border-border bg-card text-left shadow-sm transition hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-premium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={`Abrir vista previa de ${asset.original_filename}`}
                >
                  <span className="relative block aspect-[16/10] overflow-hidden border-b border-border">
                    <AssetThumbnail asset={asset} previewUrl={previewUrls[asset.id]} />
                    <span className="absolute left-3 top-3">
                      <StatusBadge
                        label={ASSET_STATUS_LABELS[asset.status]}
                        tone={ASSET_STATUS_TONES[asset.status]}
                        className="bg-elevated/90 backdrop-blur"
                      />
                    </span>
                  </span>
                  <span className="block p-4">
                    <span className="block truncate text-sm font-semibold text-foreground">
                      {asset.original_filename}
                    </span>
                    <span className="mt-1 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                      <span>{ASSET_TYPE_LABELS[asset.asset_type]}</span>
                      <span>{formatAssetSize(asset.size_bytes)}</span>
                    </span>
                    <span className="mt-3 block truncate text-xs text-muted-foreground">
                      {asset.brand_id ? brandNames[asset.brand_id] ?? "Marca vinculada" : "Sin marca"}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-5 overflow-hidden rounded-xl border border-border bg-card">
            <Pagination
              page={page}
              pageSize={pageSize}
              totalItems={items.length}
              pageSizeOptions={[12, 24, 48]}
              onPageChange={setPage}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setPage(1);
              }}
            />
          </div>
        </div>
      ) : (
        <Card className="overflow-hidden bg-card/85 shadow-none">
          <div className="hidden grid-cols-[5rem_minmax(12rem,1.4fr)_0.7fr_0.8fr_0.8fr_0.7fr] gap-4 border-b border-border bg-interactive/35 px-5 py-3 md:grid">
            <span className="sr-only">Miniatura</span>
            {["Archivo", "Tipo", "Marca", "Estado", "Subido"].map((label) => (
              <span key={label} className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                {label}
              </span>
            ))}
          </div>
          <ul className="divide-y divide-border">
            {pageItems.map((asset) => (
              <li key={asset.id}>
                <button
                  type="button"
                  onClick={() => setSelectedAsset(asset)}
                  className="grid w-full gap-3 px-4 py-4 text-left transition-colors hover:bg-interactive/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring md:grid-cols-[5rem_minmax(12rem,1.4fr)_0.7fr_0.8fr_0.8fr_0.7fr] md:items-center md:gap-4 md:px-5"
                >
                  <span className="h-14 overflow-hidden rounded-lg border border-border">
                    <AssetThumbnail asset={asset} previewUrl={previewUrls[asset.id]} />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold text-foreground">
                      {asset.original_filename}
                    </span>
                    <span className="mt-1 block text-xs text-muted-foreground">
                      {formatAssetSize(asset.size_bytes)} · {assetDimensions(asset)}
                    </span>
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {ASSET_TYPE_LABELS[asset.asset_type]}
                  </span>
                  <span className="truncate text-sm text-muted-foreground">
                    {asset.brand_id ? brandNames[asset.brand_id] ?? "Marca vinculada" : "Sin marca"}
                  </span>
                  <StatusBadge
                    label={ASSET_STATUS_LABELS[asset.status]}
                    tone={ASSET_STATUS_TONES[asset.status]}
                    className="w-fit"
                  />
                  <span className="text-xs text-muted-foreground">
                    {formatAssetDate(asset.created_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <Pagination
            page={page}
            pageSize={pageSize}
            totalItems={items.length}
            pageSizeOptions={[12, 24, 48]}
            onPageChange={setPage}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(1);
            }}
          />
        </Card>
      )}

      <UploadAssetDrawer
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        currentOrgId={currentOrgId}
        brands={brands}
        onUploaded={async (asset) => {
          setUploadOpen(false);
          await loadAssets();
          setSelectedAsset(asset);
        }}
      />

      <AssetPreviewDrawer
        open={Boolean(selectedAsset)}
        onOpenChange={(open) => {
          if (!open) setSelectedAsset(null);
        }}
        asset={selectedAsset}
        currentOrgId={currentOrgId}
        brandName={
          selectedAsset?.brand_id ? brandNames[selectedAsset.brand_id] : undefined
        }
        canPreview={canPreview}
        canWrite={canWrite}
        onRequestArchive={setDeleteTarget}
        onPreviewUrl={rememberPreviewUrl}
      />

      <ConfirmationDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => {
          if (!open && !deleting) setDeleteTarget(null);
        }}
        title="¿Eliminar de la biblioteca?"
        description={`“${deleteTarget?.original_filename ?? "Este recurso"}” dejará de estar disponible para nuevos usos. Conservaremos el archivo archivado para no romper publicaciones ni el historial.`}
        confirmLabel="Eliminar de la biblioteca"
        tone="danger"
        busy={deleting}
        onConfirm={archiveAsset}
      />
    </div>
  );
}

function UploadAssetDrawer({
  open,
  onOpenChange,
  currentOrgId,
  brands,
  onUploaded,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentOrgId: string;
  brands: Brand[];
  onUploaded: (asset: Asset) => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [brandId, setBrandId] = useState("");
  const [altText, setAltText] = useState("");
  const [caption, setCaption] = useState("");
  const [uploading, setUploading] = useState(false);
  const [genBusy, setGenBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const detectedType = file ? detectType(file) : null;

  useEffect(() => {
    if (!open) return;
    setFile(null);
    setBrandId(brands[0]?.id ?? "");
    setAltText("");
    setCaption("");
    setError(null);
  }, [brands, open]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;
    if (detectedType === "IMAGE" && !altText.trim()) {
      setError("Añade un texto alternativo para que la imagen sea accesible.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const init = await api.initUpload(currentOrgId, {
        filename: file.name,
        mime_type: file.type || "application/octet-stream",
        size_bytes: file.size,
        asset_type: detectedType ?? "OTHER",
        brand_id: brandId || null,
        alt_text: altText.trim() || null,
        caption: caption.trim() || null,
      });
      const completed = await api.completeUpload(currentOrgId, {
        asset_id: init.asset_id,
        content_base64: await fileToBase64(file),
      });
      let finalAsset = completed;
      // If image and no alt-text provided, attempt server-side generation
      if (detectedType === "IMAGE" && !altText.trim()) {
        try {
          setGenBusy(true);
          const generated = await api.generateAssetAltText(currentOrgId, completed.id);
          finalAsset = generated;
        } catch (genErr) {
          // non-fatal: surface error but still return uploaded asset
          setError(genErr instanceof ApiError ? genErr.detail : "No pudimos generar el texto alternativo automáticamente.");
        } finally {
          setGenBusy(false);
        }
      }
      await onUploaded(finalAsset);
    } catch (uploadError) {
      setError(
        uploadError instanceof ApiError
          ? uploadError.detail
          : "No pudimos subir el recurso.",
      );
    } finally {
      setUploading(false);
    }
  };

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title="Subir activo"
      description="Añade un archivo a la biblioteca y completa la información necesaria para reutilizarlo."
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={uploading}>
            Cancelar
          </Button>
          <Button type="submit" form="upload-asset-form" disabled={uploading || !file}>
            {uploading ? "Subiendo…" : "Subir"}
          </Button>
        </div>
      }
    >
      <form id="upload-asset-form" onSubmit={submit} className="space-y-5">
        <span className="sr-only">Subir activo</span>
        <FormField label="Archivo">
          <input
            type="file"
            required
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="block w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground file:mr-3 file:rounded-md file:border-0 file:bg-interactive file:px-3 file:py-1.5 file:text-xs file:font-medium"
          />
        </FormField>
        {file && (
          <div className="flex items-center justify-between gap-4 rounded-xl border border-border bg-interactive/40 p-4">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-foreground">{file.name}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {detectedType ? ASSET_TYPE_LABELS[detectedType] : "Archivo"} · {formatAssetSize(file.size)}
              </p>
            </div>
          </div>
        )}
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
          optional={detectedType !== "IMAGE"}
          helper="Describe lo que aparece en la imagen para personas que utilizan lectores de pantalla."
        >
          <Input
            value={altText}
            onChange={(event) => setAltText(event.target.value)}
            required={detectedType === "IMAGE"}
          />
        </FormField>
        <FormField label="Descripción" optional>
          <Textarea
            value={caption}
            onChange={(event) => setCaption(event.target.value)}
            rows={4}
          />
        </FormField>
        {error && (
          <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}
      </form>
    </Drawer>
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

function detectType(file: File): AssetType {
  if (file.type.startsWith("image/")) return "IMAGE";
  if (file.type.startsWith("video/")) return "VIDEO";
  if (file.type.startsWith("audio/")) return "AUDIO";
  if (file.type === "application/pdf") return "DOCUMENT";
  return "OTHER";
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(",")[1] ?? "");
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
