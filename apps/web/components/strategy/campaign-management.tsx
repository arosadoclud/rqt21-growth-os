"use client";

import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  CirclePause,
  Megaphone,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Send,
} from "lucide-react";
import type {
  Brand,
  Campaign,
  CampaignObjective,
  CampaignStatus,
  Platform,
  Product,
} from "@rqt21/contracts";
import {
  CAMPAIGN_OBJECTIVES,
  CAMPAIGN_STATUSES,
  PLATFORMS,
} from "@rqt21/contracts";

import {
  DataTable,
  type DataTableColumn,
} from "@/components/design-system/data-table";
import { Drawer } from "@/components/design-system/drawer";
import { FilterBar } from "@/components/design-system/filter-bar";
import { MetricCard } from "@/components/design-system/metric-card";
import { PageHeader } from "@/components/design-system/page-header";
import { StatusBadge } from "@/components/design-system/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";
import { cn } from "@/lib/utils";

import {
  CAMPAIGN_OBJECTIVE_LABELS,
  CAMPAIGN_STATUS_LABELS,
  CAMPAIGN_STATUS_TONES,
  formatMoney,
  formatStrategyDate,
  PLATFORM_LABELS,
  slugifyStrategy,
} from "./strategy-config";

export function CampaignManagement() {
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canWrite = canWriteGrowth(organization?.role);
  const [items, setItems] = useState<Campaign[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<CampaignStatus | "">("");
  const [platformFilter, setPlatformFilter] = useState<Platform | "">("");
  const [brandFilter, setBrandFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Campaign | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [campaignResult, brandResult, productResult] = await Promise.all([
        api.listCampaigns(currentOrgId),
        api.listBrands(currentOrgId),
        api.listProducts(currentOrgId),
      ]);
      setItems(campaignResult);
      setBrands(brandResult);
      setProducts(productResult);
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar las campañas.",
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
    [brandFilter, pageSize, platformFilter, search, statusFilter],
  );

  const brandNames = useMemo(
    () => Object.fromEntries(brands.map((brand) => [brand.id, brand.name])),
    [brands],
  );
  const productNames = useMemo(
    () => Object.fromEntries(products.map((product) => [product.id, product.name])),
    [products],
  );
  const filteredItems = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("es");
    return items.filter((campaign) => {
      if (statusFilter && campaign.status !== statusFilter) return false;
      if (platformFilter && campaign.platform !== platformFilter) return false;
      if (brandFilter && campaign.brand_id !== brandFilter) return false;
      if (!query) return true;
      return [campaign.name, campaign.slug, productNames[campaign.product_id ?? ""]]
        .filter(Boolean)
        .some((value) => value!.toLocaleLowerCase("es").includes(query));
    });
  }, [
    brandFilter,
    items,
    platformFilter,
    productNames,
    search,
    statusFilter,
  ]);

  const columns: DataTableColumn<Campaign>[] = [
    {
      key: "campaign",
      label: "Campaña",
      render: (campaign) => (
        <div className="min-w-0">
          <p className="truncate font-semibold text-foreground">{campaign.name}</p>
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {brandNames[campaign.brand_id] ?? "Marca vinculada"}
          </p>
        </div>
      ),
      mobileClassName: "items-start",
    },
    {
      key: "platform",
      label: "Canal",
      render: (campaign) => (
        <span className="text-sm text-muted-foreground">
          {PLATFORM_LABELS[campaign.platform]}
        </span>
      ),
    },
    {
      key: "objective",
      label: "Objetivo",
      render: (campaign) => (
        <span className="text-sm text-muted-foreground">
          {CAMPAIGN_OBJECTIVE_LABELS[campaign.objective]}
        </span>
      ),
    },
    {
      key: "product",
      label: "Producto",
      render: (campaign) => (
        <span className="text-sm text-muted-foreground">
          {campaign.product_id
            ? productNames[campaign.product_id] ?? "Producto vinculado"
            : "Sin producto"}
        </span>
      ),
    },
    {
      key: "status",
      label: "Estado",
      render: (campaign) => (
        <StatusBadge
          label={CAMPAIGN_STATUS_LABELS[campaign.status]}
          tone={CAMPAIGN_STATUS_TONES[campaign.status]}
        />
      ),
    },
    {
      key: "period",
      label: "Periodo",
      render: (campaign) => (
        <span className="text-xs text-muted-foreground">
          {campaign.starts_at ? formatStrategyDate(campaign.starts_at) : "Sin inicio"}
          {" – "}
          {campaign.ends_at ? formatStrategyDate(campaign.ends_at) : "continuo"}
        </span>
      ),
    },
    {
      key: "actions",
      label: "Acciones",
      render: (campaign) =>
        canWrite ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setEditing(campaign);
              setDrawerOpen(true);
            }}
          >
            <Pencil className="h-3.5 w-3.5" />
            Editar
          </Button>
        ) : (
          <span className="text-xs text-muted-foreground">Solo lectura</span>
        ),
      className: "w-28",
    },
  ];

  if (!currentOrgId) {
    return (
      <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
        Selecciona una organización para administrar sus campañas.
      </div>
    );
  }

  const openCreate = () => {
    setEditing(null);
    setDrawerOpen(true);
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Activación comercial"
        title="Campañas"
        description="Coordina canales, objetivos, productos y periodos de cada iniciativa de crecimiento."
        metadata={<StatusBadge label={`${items.length} campañas`} />}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
            {canWrite && brands.length > 0 && (
              <Button size="sm" onClick={openCreate}>
                <Plus className="h-4 w-4" />
                Nueva campaña
              </Button>
            )}
          </>
        }
      />

      {error && <InlineError>{error}</InlineError>}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Resumen de campañas">
        <MetricCard
          label="Total"
          value={items.length}
          helper="Iniciativas registradas"
          icon={Megaphone}
          loading={loading}
        />
        <MetricCard
          label="Activas"
          value={items.filter((campaign) => campaign.status === "ACTIVE").length}
          helper="En ejecución"
          icon={Play}
          tone="positive"
          loading={loading}
        />
        <MetricCard
          label="Pausadas"
          value={items.filter((campaign) => campaign.status === "PAUSED").length}
          helper="Detenidas temporalmente"
          icon={CirclePause}
          tone="warning"
          loading={loading}
        />
        <MetricCard
          label="Canales activos"
          value={new Set(items.filter((campaign) => campaign.status === "ACTIVE").map((campaign) => campaign.platform)).size}
          helper="Plataformas en uso"
          icon={Send}
          tone="info"
          loading={loading}
        />
      </section>

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchLabel="Buscar campañas"
        searchPlaceholder="Buscar por campaña, slug o producto…"
        hasFilters={Boolean(search || statusFilter || platformFilter || brandFilter)}
        onClear={() => {
          setSearch("");
          setStatusFilter("");
          setPlatformFilter("");
          setBrandFilter("");
        }}
      >
        <Select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as CampaignStatus | "")}
          aria-label="Filtrar campañas por estado"
          className="lg:w-40"
        >
          <option value="">Todos los estados</option>
          {CAMPAIGN_STATUSES.map((status) => (
            <option key={status} value={status}>{CAMPAIGN_STATUS_LABELS[status]}</option>
          ))}
        </Select>
        <Select
          value={platformFilter}
          onChange={(event) => setPlatformFilter(event.target.value as Platform | "")}
          aria-label="Filtrar campañas por canal"
          className="lg:w-40"
        >
          <option value="">Todos los canales</option>
          {PLATFORMS.map((platform) => (
            <option key={platform} value={platform}>{PLATFORM_LABELS[platform]}</option>
          ))}
        </Select>
        <Select
          value={brandFilter}
          onChange={(event) => setBrandFilter(event.target.value)}
          aria-label="Filtrar campañas por marca"
          className="lg:w-44"
        >
          <option value="">Todas las marcas</option>
          {brands.map((brand) => (
            <option key={brand.id} value={brand.id}>{brand.name}</option>
          ))}
        </Select>
      </FilterBar>

      {brands.length === 0 && !loading && canWrite && (
        <p className="rounded-xl border border-warning/25 bg-warning/5 px-4 py-3 text-sm text-warning">
          Crea una marca antes de registrar campañas.
        </p>
      )}
      {!canWrite && (
        <p className="rounded-xl border border-border bg-interactive/35 px-4 py-3 text-sm text-muted-foreground">
          Tu rol puede consultar campañas, pero no crearlas ni modificarlas.
        </p>
      )}

      <DataTable
        items={filteredItems}
        columns={columns}
        rowKey={(campaign) => campaign.id}
        loading={loading}
        emptyIcon={Megaphone}
        emptyTitle="No encontramos campañas"
        emptyDescription="Ajusta los filtros o crea la primera iniciativa de crecimiento."
        emptyActionLabel={canWrite && brands.length > 0 ? "Crear campaña" : undefined}
        onEmptyAction={canWrite && brands.length > 0 ? openCreate : undefined}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
        ariaLabel="Listado de campañas"
      />

      <CampaignDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        currentOrgId={currentOrgId}
        campaign={editing}
        brands={brands}
        products={products}
        onSaved={async () => {
          setDrawerOpen(false);
          await load();
        }}
      />
    </div>
  );
}

function CampaignDrawer({
  open,
  onOpenChange,
  currentOrgId,
  campaign,
  brands,
  products,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentOrgId: string;
  campaign: Campaign | null;
  brands: Brand[];
  products: Product[];
  onSaved: () => Promise<void>;
}) {
  const [brandId, setBrandId] = useState("");
  const [productId, setProductId] = useState("");
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [platform, setPlatform] = useState<Platform>("INSTAGRAM");
  const [objective, setObjective] = useState<CampaignObjective>("SALES");
  const [status, setStatus] = useState<CampaignStatus>("DRAFT");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [budget, setBudget] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setBrandId(campaign?.brand_id ?? brands[0]?.id ?? "");
    setProductId(campaign?.product_id ?? "");
    setName(campaign?.name ?? "");
    setSlug(campaign?.slug ?? "");
    setSlugTouched(Boolean(campaign));
    setPlatform(campaign?.platform ?? "INSTAGRAM");
    setObjective(campaign?.objective ?? "SALES");
    setStatus(campaign?.status ?? "DRAFT");
    setStartsAt(toDateTimeInput(campaign?.starts_at));
    setEndsAt(toDateTimeInput(campaign?.ends_at));
    setBudget(campaign?.budget ?? "");
    setError(null);
  }, [brands, campaign, open]);

  const availableProducts = products.filter((product) => product.brand_id === brandId);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!brandId) return;
    if (startsAt && endsAt && new Date(endsAt) < new Date(startsAt)) {
      setError("La fecha de cierre debe ser posterior al inicio.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (campaign) {
        await api.updateCampaign(currentOrgId, campaign.id, {
          name: name.trim(),
          product_id: productId || null,
          platform,
          objective,
          status,
          starts_at: toApiDate(startsAt),
          ends_at: toApiDate(endsAt),
          budget: budget || null,
        });
      } else {
        await api.createCampaign(currentOrgId, {
          brand_id: brandId,
          product_id: productId || null,
          name: name.trim(),
          slug: slug.trim(),
          platform,
          objective,
          status,
          starts_at: toApiDate(startsAt),
          ends_at: toApiDate(endsAt),
          budget: budget || null,
        });
      }
      await onSaved();
    } catch (saveError) {
      setError(
        saveError instanceof ApiError
          ? saveError.detail
          : "No pudimos guardar la campaña.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={campaign ? "Editar campaña" : "Nueva campaña"}
      description="Define el objetivo, canal, oferta y periodo de esta iniciativa."
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancelar
          </Button>
          <Button type="submit" form="campaign-form" disabled={busy || !brandId}>
            {busy ? "Guardando…" : campaign ? "Guardar cambios" : "Crear campaña"}
          </Button>
        </div>
      }
    >
      <form id="campaign-form" onSubmit={submit} className="space-y-5">
        <FormField label="Marca">
          <Select
            value={brandId}
            disabled={Boolean(campaign)}
            className={campaign ? "bg-muted" : undefined}
            onChange={(event) => {
              setBrandId(event.target.value);
              setProductId("");
            }}
          >
            {brands.map((brand) => (
              <option key={brand.id} value={brand.id}>{brand.name}</option>
            ))}
          </Select>
        </FormField>
        <FormField label="Producto" optional>
          <Select value={productId} onChange={(event) => setProductId(event.target.value)}>
            <option value="">Sin producto vinculado</option>
            {availableProducts.map((product) => (
              <option key={product.id} value={product.id}>{product.name}</option>
            ))}
          </Select>
        </FormField>
        <FormField label="Nombre">
          <Input
            required
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              if (!slugTouched) setSlug(slugifyStrategy(event.target.value));
            }}
          />
        </FormField>
        <FormField label="Slug" helper={campaign ? "No cambia después de crear la campaña." : "Identificador estable para URLs e integraciones."}>
          <Input
            required
            pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
            value={slug}
            readOnly={Boolean(campaign)}
            className={campaign ? "bg-muted" : undefined}
            onChange={(event) => {
              setSlug(event.target.value);
              setSlugTouched(true);
            }}
          />
        </FormField>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Canal">
            <Select value={platform} onChange={(event) => setPlatform(event.target.value as Platform)}>
              {PLATFORMS.map((value) => (
                <option key={value} value={value}>{PLATFORM_LABELS[value]}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Objetivo">
            <Select value={objective} onChange={(event) => setObjective(event.target.value as CampaignObjective)}>
              {CAMPAIGN_OBJECTIVES.map((value) => (
                <option key={value} value={value}>{CAMPAIGN_OBJECTIVE_LABELS[value]}</option>
              ))}
            </Select>
          </FormField>
        </div>
        <FormField label="Estado">
          <Select value={status} onChange={(event) => setStatus(event.target.value as CampaignStatus)}>
            {CAMPAIGN_STATUSES.map((value) => (
              <option key={value} value={value}>{CAMPAIGN_STATUS_LABELS[value]}</option>
            ))}
          </Select>
        </FormField>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Inicio" optional>
            <Input type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} />
          </FormField>
          <FormField label="Cierre" optional>
            <Input type="datetime-local" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} />
          </FormField>
        </div>
        <FormField label="Presupuesto" optional helper={budget ? formatMoney(budget) : "Importe estimado en USD."}>
          <Input type="number" min="0" step="0.01" value={budget} onChange={(event) => setBudget(event.target.value)} />
        </FormField>
        {error && <InlineError>{error}</InlineError>}
      </form>
    </Drawer>
  );
}

function toDateTimeInput(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function toApiDate(value: string): string | null {
  if (!value) return null;
  return new Date(value).toISOString();
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
