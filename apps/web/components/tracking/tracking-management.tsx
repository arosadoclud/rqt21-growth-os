"use client";

import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Check,
  Copy,
  Eye,
  Link2,
  MousePointerClick,
  Plus,
  Power,
  RefreshCw,
  RotateCcw,
  Target,
  Users,
} from "lucide-react";
import type {
  Brand,
  Campaign,
  ContentItem,
  Funnel,
  Product,
  TrackingLink,
  TrackingLinkUpdate,
} from "@rqt21/contracts";

import { ConfirmationDialog } from "@/components/design-system/confirmation-dialog";
import {
  DataTable,
  type DataTableColumn,
} from "@/components/design-system/data-table";
import { Drawer } from "@/components/design-system/drawer";
import { FilterBar } from "@/components/design-system/filter-bar";
import { MetricCard } from "@/components/design-system/metric-card";
import { PageHeader } from "@/components/design-system/page-header";
import { StatusBadge } from "@/components/design-system/status-badge";
import { StatePanel } from "@/components/design-system/state-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";
import { cn } from "@/lib/utils";

type LinkStatusFilter = "all" | "active" | "inactive" | "expired";

function isExpired(link: TrackingLink) {
  return Boolean(link.expires_at && new Date(link.expires_at).getTime() < Date.now());
}

function linkStatus(link: TrackingLink) {
  if (isExpired(link)) return { label: "Vencido", tone: "danger" as const };
  if (link.is_active) return { label: "Activo", tone: "success" as const };
  return { label: "Inactivo", tone: "neutral" as const };
}

export function TrackingManagement() {
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canWrite = canWriteGrowth(organization?.role);
  const [items, setItems] = useState<TrackingLink[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [contents, setContents] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<LinkStatusFilter>("all");
  const [brandFilter, setBrandFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [createOpen, setCreateOpen] = useState(false);
  const [selected, setSelected] = useState<TrackingLink | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [linkResult, brandResult, productResult, campaignResult, contentResult] =
        await Promise.all([
          api.listTrackingLinks(currentOrgId),
          api.listBrands(currentOrgId),
          api.listProducts(currentOrgId),
          api.listCampaigns(currentOrgId),
          api.listContent(currentOrgId),
        ]);
      setItems(linkResult);
      setBrands(brandResult);
      setProducts(productResult);
      setCampaigns(campaignResult);
      setContents(contentResult);
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar los enlaces rastreables.",
      );
    } finally {
      setLoading(false);
    }
  }, [currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(
    () => setPage(1),
    [brandFilter, pageSize, search, sourceFilter, statusFilter],
  );

  const brandNames = useMemo(
    () => Object.fromEntries(brands.map((brand) => [brand.id, brand.name])),
    [brands],
  );
  const campaignNames = useMemo(
    () => Object.fromEntries(campaigns.map((campaign) => [campaign.id, campaign.name])),
    [campaigns],
  );
  const sources = useMemo(
    () =>
      Array.from(
        new Set(items.map((link) => link.utm_source).filter((value): value is string => Boolean(value))),
      ).sort((left, right) => left.localeCompare(right, "es")),
    [items],
  );
  const filteredItems = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("es");
    return items.filter((link) => {
      if (brandFilter && link.brand_id !== brandFilter) return false;
      if (sourceFilter && link.utm_source !== sourceFilter) return false;
      if (statusFilter === "active" && (!link.is_active || isExpired(link))) return false;
      if (statusFilter === "inactive" && link.is_active) return false;
      if (statusFilter === "expired" && !isExpired(link)) return false;
      if (!query) return true;
      return [
        link.short_code,
        link.short_url,
        link.destination_url,
        link.utm_source ?? "",
        link.utm_campaign ?? "",
        brandNames[link.brand_id] ?? "",
        link.campaign_id ? campaignNames[link.campaign_id] ?? "" : "",
      ].some((value) => value.toLocaleLowerCase("es").includes(query));
    });
  }, [
    brandFilter,
    brandNames,
    campaignNames,
    items,
    search,
    sourceFilter,
    statusFilter,
  ]);

  const copy = async (link: TrackingLink) => {
    try {
      await navigator.clipboard.writeText(link.short_url);
      setCopiedId(link.id);
      window.setTimeout(() => setCopiedId(null), 1800);
    } catch {
      setError("No pudimos copiar el enlace. Selecciónalo manualmente desde el detalle.");
    }
  };

  const toggleActive = async (link: TrackingLink) => {
    if (!currentOrgId) return;
    setBusyId(link.id);
    setError(null);
    try {
      const updated = await api.updateTrackingLink(currentOrgId, link.id, {
        is_active: !link.is_active,
      });
      setItems((current) =>
        current.map((candidate) => (candidate.id === link.id ? updated : candidate)),
      );
      if (selected?.id === link.id) setSelected(updated);
    } catch (toggleError) {
      setError(
        toggleError instanceof ApiError
          ? toggleError.detail
          : "No pudimos cambiar el estado del enlace.",
      );
    } finally {
      setBusyId(null);
    }
  };

  const columns: DataTableColumn<TrackingLink>[] = [
    {
      key: "link",
      label: "Enlace",
      render: (link) => (
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => setSelected(link)}
            className="font-mono text-sm font-semibold text-primary hover:underline"
          >
            /{link.short_code}
          </button>
          <p className="mt-1 max-w-xs truncate text-xs text-muted-foreground">
            {link.destination_url}
          </p>
        </div>
      ),
      mobileClassName: "items-start",
    },
    {
      key: "attribution",
      label: "Atribución",
      render: (link) => (
        <div>
          <p className="text-sm text-foreground">
            {link.utm_source || "Sin fuente"}{" "}
            <span className="text-muted-foreground">/ {link.utm_medium || "sin medio"}</span>
          </p>
          <p className="mt-1 max-w-56 truncate text-xs text-muted-foreground">
            {link.utm_campaign || campaignNames[link.campaign_id ?? ""] || "Sin campaña UTM"}
          </p>
        </div>
      ),
    },
    {
      key: "brand",
      label: "Marca",
      render: (link) => (
        <span className="text-sm">{brandNames[link.brand_id] ?? "Marca vinculada"}</span>
      ),
    },
    {
      key: "status",
      label: "Estado",
      render: (link) => {
        const status = linkStatus(link);
        return <StatusBadge label={status.label} tone={status.tone} />;
      },
    },
    {
      key: "actions",
      label: "Acciones",
      render: (link) => (
        <div className="flex flex-wrap gap-1">
          <Button variant="ghost" size="sm" onClick={() => void copy(link)}>
            {copiedId === link.id ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copiedId === link.id ? "Copiado" : "Copiar"}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setSelected(link)}>
            <Eye className="h-3.5 w-3.5" />
            Ver detalle
          </Button>
          {canWrite && (
            <Button
              variant="outline"
              size="sm"
              disabled={busyId === link.id || isExpired(link)}
              onClick={() => void toggleActive(link)}
            >
              {link.is_active ? "Desactivar" : "Reactivar"}
            </Button>
          )}
        </div>
      ),
      className: "min-w-64",
    },
  ];

  if (!currentOrgId) {
    return (
      <StatePanel
        icon={Link2}
        title="Selecciona una organización"
        description="Los enlaces aparecerán cuando elijas una organización."
      />
    );
  }

  const active = items.filter((link) => link.is_active && !isExpired(link)).length;
  const expired = items.filter(isExpired).length;
  const attributed = items.filter((link) => link.utm_source || link.utm_campaign).length;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Medición y atribución"
        title="Enlaces rastreables"
        description="Crea enlaces cortos consistentes, controla su vigencia y conserva la atribución de campañas hasta la conversión."
        metadata={
          <>
            <StatusBadge
              label={canWrite ? "Gestión habilitada" : "Solo lectura"}
              tone={canWrite ? "success" : "neutral"}
            />
            <span className="text-xs text-muted-foreground">{items.length} enlaces registrados</span>
          </>
        }
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
            {canWrite && (
              <Button size="sm" onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" />
                Nuevo enlace
              </Button>
            )}
          </>
        }
      />

      {error && <InlineError>{error}</InlineError>}
      {!canWrite && (
        <div className="rounded-xl border border-border bg-card/60 px-4 py-3 text-sm text-muted-foreground">
          Tu rol puede consultar y copiar enlaces, pero no crearlos ni modificar su configuración.
        </div>
      )}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Resumen de enlaces">
        <MetricCard
          label="Enlaces activos"
          value={active}
          helper="Listos para redirigir"
          icon={Link2}
          tone="positive"
          loading={loading}
        />
        <MetricCard
          label="Con atribución"
          value={attributed}
          helper={`${items.length ? Math.round((attributed / items.length) * 100) : 0}% incluye parámetros UTM`}
          icon={Target}
          tone="info"
          loading={loading}
        />
        <MetricCard
          label="Fuentes"
          value={sources.length}
          helper="Canales identificados"
          icon={Users}
          loading={loading}
        />
        <MetricCard
          label="Vencidos"
          value={expired}
          helper="Ya no aceptan visitas"
          icon={Power}
          tone={expired ? "warning" : "neutral"}
          loading={loading}
        />
      </section>

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchLabel="Buscar enlaces"
        searchPlaceholder="Buscar por código, destino, fuente o campaña…"
        hasFilters={Boolean(
          search || brandFilter || sourceFilter || statusFilter !== "all",
        )}
        onClear={() => {
          setSearch("");
          setBrandFilter("");
          setSourceFilter("");
          setStatusFilter("all");
        }}
      >
        <Select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as LinkStatusFilter)}
          aria-label="Filtrar enlaces por estado"
          className="lg:w-40"
        >
          <option value="all">Todos los estados</option>
          <option value="active">Activos</option>
          <option value="inactive">Inactivos</option>
          <option value="expired">Vencidos</option>
        </Select>
        <Select
          value={brandFilter}
          onChange={(event) => setBrandFilter(event.target.value)}
          aria-label="Filtrar enlaces por marca"
          className="lg:w-48"
        >
          <option value="">Todas las marcas</option>
          {brands.map((brand) => (
            <option key={brand.id} value={brand.id}>{brand.name}</option>
          ))}
        </Select>
        <Select
          value={sourceFilter}
          onChange={(event) => setSourceFilter(event.target.value)}
          aria-label="Filtrar enlaces por fuente"
          className="lg:w-44"
        >
          <option value="">Todas las fuentes</option>
          {sources.map((source) => (
            <option key={source} value={source}>{source}</option>
          ))}
        </Select>
      </FilterBar>

      <DataTable
        items={filteredItems}
        columns={columns}
        rowKey={(link) => link.id}
        loading={loading}
        emptyIcon={Link2}
        emptyTitle="No encontramos enlaces"
        emptyDescription="Ajusta los filtros o crea el primer enlace para medir una campaña."
        emptyActionLabel={canWrite ? "Crear enlace" : undefined}
        onEmptyAction={canWrite ? () => setCreateOpen(true) : undefined}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        ariaLabel="Listado de enlaces rastreables"
      />

      <CreateTrackingDrawer
        open={createOpen}
        onOpenChange={setCreateOpen}
        currentOrgId={currentOrgId}
        brands={brands}
        products={products}
        campaigns={campaigns}
        contents={contents}
        onCreated={async () => {
          setCreateOpen(false);
          await load();
        }}
      />
      <TrackingDetailDrawer
        link={selected}
        onOpenChange={(open) => !open && setSelected(null)}
        currentOrgId={currentOrgId}
        canWrite={canWrite}
        brandName={selected ? brandNames[selected.brand_id] : undefined}
        campaignName={selected?.campaign_id ? campaignNames[selected.campaign_id] : undefined}
        onCopy={() => selected && void copy(selected)}
        onUpdated={(updated) => {
          setSelected(updated);
          setItems((current) =>
            current.map((candidate) => (candidate.id === updated.id ? updated : candidate)),
          );
        }}
      />
    </div>
  );
}

function CreateTrackingDrawer({
  open,
  onOpenChange,
  currentOrgId,
  brands,
  products,
  campaigns,
  contents,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentOrgId: string;
  brands: Brand[];
  products: Product[];
  campaigns: Campaign[];
  contents: ContentItem[];
  onCreated: () => Promise<void>;
}) {
  const [brandId, setBrandId] = useState("");
  const [productId, setProductId] = useState("");
  const [campaignId, setCampaignId] = useState("");
  const [contentId, setContentId] = useState("");
  const [destination, setDestination] = useState("");
  const [utmSource, setUtmSource] = useState("");
  const [utmMedium, setUtmMedium] = useState("social");
  const [utmCampaign, setUtmCampaign] = useState("");
  const [utmContent, setUtmContent] = useState("");
  const [utmTerm, setUtmTerm] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setBrandId(brands[0]?.id ?? "");
    setProductId("");
    setCampaignId("");
    setContentId("");
    setDestination("");
    setUtmSource("");
    setUtmMedium("social");
    setUtmCampaign("");
    setUtmContent("");
    setUtmTerm("");
    setExpiresAt("");
    setError(null);
  }, [brands, open]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!brandId) {
      setError("Selecciona una marca.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.createTrackingLink(currentOrgId, {
        brand_id: brandId,
        product_id: productId || null,
        campaign_id: campaignId || null,
        content_id: contentId || null,
        destination_url: destination,
        utm_source: utmSource || null,
        utm_medium: utmMedium || null,
        utm_campaign: utmCampaign || null,
        utm_content: utmContent || null,
        utm_term: utmTerm || null,
        expires_at: expiresAt
          ? new Date(`${expiresAt}T23:59:59`).toISOString()
          : null,
      });
      await onCreated();
    } catch (saveError) {
      setError(
        saveError instanceof ApiError
          ? saveError.detail
          : "No pudimos crear el enlace.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title="Nuevo enlace"
      description="Define el destino y la atribución que debe conservarse al redirigir."
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancelar
          </Button>
          <Button type="submit" form="tracking-create-form" disabled={busy || !brands.length}>
            {busy ? "Generando…" : "Generar enlace"}
          </Button>
        </div>
      }
    >
      <form id="tracking-create-form" onSubmit={submit} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Marca">
            <Select value={brandId} onChange={(event) => setBrandId(event.target.value)} required>
              <option value="">Selecciona una marca</option>
              {brands.map((brand) => (
                <option key={brand.id} value={brand.id}>{brand.name}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Producto" optional>
            <Select value={productId} onChange={(event) => setProductId(event.target.value)}>
              <option value="">Sin producto</option>
              {products.map((product) => (
                <option key={product.id} value={product.id}>{product.name}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Campaña" optional>
            <Select value={campaignId} onChange={(event) => setCampaignId(event.target.value)}>
              <option value="">Sin campaña</option>
              {campaigns.map((campaign) => (
                <option key={campaign.id} value={campaign.id}>{campaign.name}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Contenido" optional>
            <Select value={contentId} onChange={(event) => setContentId(event.target.value)}>
              <option value="">Sin contenido</option>
              {contents.map((content) => (
                <option key={content.id} value={content.id}>{content.title}</option>
              ))}
            </Select>
          </FormField>
        </div>
        <FormField label="URL destino" helper="Debe incluir https:// y apuntar a una página válida.">
          <Input
            required
            type="url"
            value={destination}
            onChange={(event) => setDestination(event.target.value)}
            placeholder="https://checkout.example.com/producto"
          />
        </FormField>
        <div className="rounded-xl border border-border bg-interactive/25 p-4">
          <p className="text-sm font-semibold text-foreground">Parámetros de atribución</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Se añadirán al destino sin reemplazar parámetros existentes.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <FormField label="utm_source">
              <Input value={utmSource} onChange={(event) => setUtmSource(event.target.value)} />
            </FormField>
            <FormField label="utm_medium">
              <Input value={utmMedium} onChange={(event) => setUtmMedium(event.target.value)} />
            </FormField>
            <FormField label="utm_campaign">
              <Input value={utmCampaign} onChange={(event) => setUtmCampaign(event.target.value)} />
            </FormField>
            <FormField label="utm_content">
              <Input value={utmContent} onChange={(event) => setUtmContent(event.target.value)} />
            </FormField>
            <FormField label="utm_term" className="sm:col-span-2">
              <Input value={utmTerm} onChange={(event) => setUtmTerm(event.target.value)} />
            </FormField>
          </div>
        </div>
        <FormField label="Fecha de vencimiento" optional helper="Al terminar ese día, el enlace dejará de redirigir.">
          <Input
            type="date"
            value={expiresAt}
            onChange={(event) => setExpiresAt(event.target.value)}
          />
        </FormField>
        {error && <InlineError>{error}</InlineError>}
      </form>
    </Drawer>
  );
}

function TrackingDetailDrawer({
  link,
  onOpenChange,
  currentOrgId,
  canWrite,
  brandName,
  campaignName,
  onCopy,
  onUpdated,
}: {
  link: TrackingLink | null;
  onOpenChange: (open: boolean) => void;
  currentOrgId: string;
  canWrite: boolean;
  brandName?: string;
  campaignName?: string;
  onCopy: () => void;
  onUpdated: (updated: TrackingLink) => void;
}) {
  const [form, setForm] = useState<TrackingLinkUpdate>({});
  const [funnel, setFunnel] = useState<Funnel | null>(null);
  const [loadingFunnel, setLoadingFunnel] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmRegenerate, setConfirmRegenerate] = useState(false);

  useEffect(() => {
    if (!link) return;
    setForm({
      destination_url: link.destination_url,
      utm_source: link.utm_source,
      utm_medium: link.utm_medium,
      utm_campaign: link.utm_campaign,
      utm_content: link.utm_content,
      utm_term: link.utm_term,
      expires_at: link.expires_at,
      is_active: link.is_active,
    });
    setError(null);
    setFunnel(null);
    setLoadingFunnel(true);
    void api
      .linkFunnel(currentOrgId, link.id)
      .then(setFunnel)
      .catch(() => setFunnel(null))
      .finally(() => setLoadingFunnel(false));
  }, [currentOrgId, link]);

  if (!link) return null;
  const status = linkStatus(link);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const updated = await api.updateTrackingLink(currentOrgId, link.id, form);
      onUpdated(updated);
    } catch (saveError) {
      setError(
        saveError instanceof ApiError
          ? saveError.detail
          : "No pudimos guardar el enlace.",
      );
    } finally {
      setBusy(false);
    }
  };

  const regenerate = async () => {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.regenerateShortCode(currentOrgId, link.id);
      onUpdated(updated);
      setConfirmRegenerate(false);
    } catch (regenerateError) {
      setError(
        regenerateError instanceof ApiError
          ? regenerateError.detail
          : "No pudimos renovar el código.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Drawer
        open
        onOpenChange={onOpenChange}
        title={`Detalle /${link.short_code}`}
        description="Consulta atribución y rendimiento, o actualiza el destino sin perder el historial."
        footer={
          canWrite ? (
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
                Cerrar
              </Button>
              <Button type="submit" form="tracking-detail-form" disabled={busy}>
                {busy ? "Guardando…" : "Guardar cambios"}
              </Button>
            </div>
          ) : (
            <div className="flex justify-end">
              <Button variant="outline" onClick={() => onOpenChange(false)}>Cerrar</Button>
            </div>
          )
        }
      >
        <div className="space-y-6">
          <Card className="bg-interactive/25 shadow-none">
            <CardContent className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <StatusBadge label={status.label} tone={status.tone} />
                <Button variant="outline" size="sm" onClick={onCopy}>
                  <Copy className="h-3.5 w-3.5" />
                  Copiar enlace corto
                </Button>
              </div>
              <p className="mt-4 break-all font-mono text-sm font-semibold text-foreground">
                {link.short_url}
              </p>
              <div className="mt-4 grid gap-3 text-xs text-muted-foreground sm:grid-cols-2">
                <p><span className="font-medium text-foreground">Marca:</span> {brandName ?? "Vinculada"}</p>
                <p><span className="font-medium text-foreground">Campaña:</span> {campaignName ?? "Sin campaña interna"}</p>
              </div>
            </CardContent>
          </Card>

          <section>
            <p className="text-sm font-semibold text-foreground">Rendimiento atribuido</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <MiniMetric
                icon={MousePointerClick}
                label="Clics"
                value={loadingFunnel ? "…" : funnel?.clicks ?? 0}
              />
              <MiniMetric
                icon={Users}
                label="Visitantes"
                value={loadingFunnel ? "…" : funnel?.unique_visitors ?? 0}
              />
              <MiniMetric
                icon={Target}
                label="Leads"
                value={loadingFunnel ? "…" : funnel?.leads ?? 0}
              />
            </div>
            {funnel && (
              <p className="mt-3 text-xs text-muted-foreground">
                Conversión clic a lead: {funnel.click_to_lead_rate.toFixed(1)}% · lead a venta:{" "}
                {funnel.lead_to_won_rate.toFixed(1)}%
              </p>
            )}
          </section>

          <form id="tracking-detail-form" onSubmit={save} className="space-y-5">
            <FormField label="URL destino">
              <Input
                required
                type="url"
                disabled={!canWrite}
                value={form.destination_url ?? ""}
                onChange={(event) => setForm({ ...form, destination_url: event.target.value })}
              />
            </FormField>
            <div className="grid gap-4 sm:grid-cols-2">
              {(["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"] as const).map(
                (field) => (
                  <FormField key={field} label={field} className={field === "utm_term" ? "sm:col-span-2" : undefined}>
                    <Input
                      disabled={!canWrite}
                      value={form[field] ?? ""}
                      onChange={(event) => setForm({ ...form, [field]: event.target.value || null })}
                    />
                  </FormField>
                ),
              )}
              <FormField label="Vencimiento" className="sm:col-span-2">
                <Input
                  type="datetime-local"
                  disabled={!canWrite}
                  value={form.expires_at ? form.expires_at.slice(0, 16) : ""}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      expires_at: event.target.value
                        ? new Date(event.target.value).toISOString()
                        : null,
                    })
                  }
                />
              </FormField>
              <FormField label="Estado" className="sm:col-span-2">
                <Select
                  disabled={!canWrite || isExpired(link)}
                  value={form.is_active ? "active" : "inactive"}
                  onChange={(event) =>
                    setForm({ ...form, is_active: event.target.value === "active" })
                  }
                >
                  <option value="active">Activo</option>
                  <option value="inactive">Inactivo</option>
                </Select>
              </FormField>
            </div>
            {error && <InlineError>{error}</InlineError>}
          </form>

          {canWrite && (
            <Card className="border-warning/25 bg-warning/5 shadow-none">
              <CardContent className="p-4">
                <p className="text-sm font-semibold text-foreground">Renovar código corto</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  El enlace anterior dejará de funcionar. El historial permanece asociado al mismo registro.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3"
                  onClick={() => setConfirmRegenerate(true)}
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Generar código nuevo
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      </Drawer>
      <ConfirmationDialog
        open={confirmRegenerate}
        onOpenChange={setConfirmRegenerate}
        title="¿Renovar el código corto?"
        description={`El código /${link.short_code} dejará de redirigir inmediatamente.`}
        confirmLabel="Renovar código"
        onConfirm={() => void regenerate()}
        busy={busy}
      />
    </>
  );
}

function MiniMetric({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <p className="metric-numbers mt-2 text-xl font-semibold">{value}</p>
    </div>
  );
}

function FormField({
  label,
  optional,
  helper,
  className,
  children,
}: {
  label: string;
  optional?: boolean;
  helper?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <label className={cn("block space-y-1.5 text-sm", className)}>
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
