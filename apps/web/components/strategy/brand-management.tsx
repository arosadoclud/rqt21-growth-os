"use client";

import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Building2,
  CircleCheck,
  Globe2,
  Pencil,
  Plus,
  RefreshCw,
} from "lucide-react";
import type { Brand } from "@rqt21/contracts";

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
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";
import { cn } from "@/lib/utils";

import { formatStrategyDate, slugifyStrategy } from "./strategy-config";

type ActiveFilter = "all" | "active" | "inactive";

export function BrandManagement() {
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canWrite = canWriteGrowth(organization?.role);
  const [items, setItems] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Brand | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      setItems(await api.listBrands(currentOrgId));
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar las marcas.",
      );
    } finally {
      setLoading(false);
    }
  }, [currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => setPage(1), [activeFilter, pageSize, search]);

  const filteredItems = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("es");
    return items.filter((brand) => {
      if (activeFilter === "active" && !brand.is_active) return false;
      if (activeFilter === "inactive" && brand.is_active) return false;
      if (!query) return true;
      return [brand.name, brand.slug, brand.description, brand.website_url]
        .filter(Boolean)
        .some((value) => value!.toLocaleLowerCase("es").includes(query));
    });
  }, [activeFilter, items, search]);

  const columns: DataTableColumn<Brand>[] = [
    {
      key: "brand",
      label: "Marca",
      render: (brand) => (
        <div className="min-w-0">
          <p className="truncate font-semibold text-foreground">{brand.name}</p>
          <p className="mt-1 truncate text-xs text-muted-foreground">{brand.slug}</p>
        </div>
      ),
      mobileClassName: "items-start",
    },
    {
      key: "website",
      label: "Sitio web",
      render: (brand) =>
        brand.website_url ? (
          <a
            href={brand.website_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex max-w-64 items-center gap-1.5 truncate text-sm text-primary hover:underline"
          >
            <Globe2 className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{brand.website_url.replace(/^https?:\/\//, "")}</span>
          </a>
        ) : (
          <span className="text-sm text-muted-foreground">Sin sitio web</span>
        ),
    },
    {
      key: "status",
      label: "Estado",
      render: (brand) => (
        <StatusBadge
          label={brand.is_active ? "Activa" : "Inactiva"}
          tone={brand.is_active ? "success" : "neutral"}
        />
      ),
    },
    {
      key: "created",
      label: "Creada",
      render: (brand) => (
        <span className="text-sm text-muted-foreground">
          {formatStrategyDate(brand.created_at)}
        </span>
      ),
    },
    {
      key: "actions",
      label: "Acciones",
      render: (brand) =>
        canWrite ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setEditing(brand);
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
        Selecciona una organización para administrar sus marcas.
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
        eyebrow="Estrategia"
        title="Marcas"
        description="Administra las identidades comerciales que organizan productos, campañas, contenido y recursos."
        metadata={<StatusBadge label={`${items.length} marcas`} />}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
            {canWrite && (
              <Button size="sm" onClick={openCreate}>
                <Plus className="h-4 w-4" />
                Nueva marca
              </Button>
            )}
          </>
        }
      />

      {error && <InlineError>{error}</InlineError>}

      <section className="grid gap-4 sm:grid-cols-3" aria-label="Resumen de marcas">
        <MetricCard
          label="Total"
          value={items.length}
          helper="Identidades registradas"
          icon={Building2}
          loading={loading}
        />
        <MetricCard
          label="Activas"
          value={items.filter((brand) => brand.is_active).length}
          helper="Disponibles para operar"
          icon={CircleCheck}
          tone="positive"
          loading={loading}
        />
        <MetricCard
          label="Con sitio web"
          value={items.filter((brand) => Boolean(brand.website_url)).length}
          helper="Presencia digital vinculada"
          icon={Globe2}
          tone="info"
          loading={loading}
        />
      </section>

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchLabel="Buscar marcas"
        searchPlaceholder="Buscar por nombre, slug o sitio web…"
        hasFilters={Boolean(search || activeFilter !== "all")}
        onClear={() => {
          setSearch("");
          setActiveFilter("all");
        }}
      >
        <Select
          value={activeFilter}
          onChange={(event) => setActiveFilter(event.target.value as ActiveFilter)}
          aria-label="Filtrar marcas por estado"
          className="lg:w-44"
        >
          <option value="all">Todos los estados</option>
          <option value="active">Activas</option>
          <option value="inactive">Inactivas</option>
        </Select>
      </FilterBar>

      {!canWrite && (
        <p className="rounded-xl border border-border bg-interactive/35 px-4 py-3 text-sm text-muted-foreground">
          Tu rol puede consultar las marcas, pero no crearlas ni modificarlas.
        </p>
      )}

      <DataTable
        items={filteredItems}
        columns={columns}
        rowKey={(brand) => brand.id}
        loading={loading}
        emptyIcon={Building2}
        emptyTitle="No encontramos marcas"
        emptyDescription="Ajusta los filtros o crea la primera identidad comercial."
        emptyActionLabel={canWrite ? "Crear marca" : undefined}
        onEmptyAction={canWrite ? openCreate : undefined}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
        ariaLabel="Listado de marcas"
      />

      <BrandDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        currentOrgId={currentOrgId}
        brand={editing}
        onSaved={async () => {
          setDrawerOpen(false);
          await load();
        }}
      />
    </div>
  );
}

function BrandDrawer({
  open,
  onOpenChange,
  currentOrgId,
  brand,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentOrgId: string;
  brand: Brand | null;
  onSaved: () => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [description, setDescription] = useState("");
  const [website, setWebsite] = useState("");
  const [active, setActive] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName(brand?.name ?? "");
    setSlug(brand?.slug ?? "");
    setSlugTouched(Boolean(brand));
    setDescription(brand?.description ?? "");
    setWebsite(brand?.website_url ?? "");
    setActive(brand?.is_active ?? true);
    setError(null);
  }, [brand, open]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (brand) {
        await api.updateBrand(currentOrgId, brand.id, {
          name: name.trim(),
          description: description.trim() || null,
          website_url: website.trim() || null,
          is_active: active,
        });
      } else {
        await api.createBrand(currentOrgId, {
          name: name.trim(),
          slug: slug.trim(),
          description: description.trim() || null,
          website_url: website.trim() || null,
        });
      }
      await onSaved();
    } catch (saveError) {
      setError(
        saveError instanceof ApiError
          ? saveError.detail
          : "No pudimos guardar la marca.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={brand ? "Editar marca" : "Nueva marca"}
      description={
        brand
          ? "Actualiza la identidad y su disponibilidad en el producto."
          : "Crea la identidad principal que agrupará productos, campañas y contenido."
      }
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancelar
          </Button>
          <Button type="submit" form="brand-form" disabled={busy}>
            {busy ? "Guardando…" : brand ? "Guardar cambios" : "Crear marca"}
          </Button>
        </div>
      }
    >
      <form id="brand-form" onSubmit={submit} className="space-y-5">
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
        <FormField
          label="Slug"
          helper={brand ? "El identificador no cambia después de crear la marca." : "Se utiliza en URLs e integraciones."}
        >
          <Input
            required
            pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
            value={slug}
            readOnly={Boolean(brand)}
            className={brand ? "bg-muted" : undefined}
            onChange={(event) => {
              setSlug(event.target.value);
              setSlugTouched(true);
            }}
          />
        </FormField>
        <FormField label="Descripción" optional>
          <Textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={4}
          />
        </FormField>
        <FormField label="Sitio web" optional>
          <Input
            type="url"
            value={website}
            onChange={(event) => setWebsite(event.target.value)}
            placeholder="https://ejemplo.com"
          />
        </FormField>
        {brand && (
          <FormField label="Estado">
            <Select value={active ? "active" : "inactive"} onChange={(event) => setActive(event.target.value === "active")}>
              <option value="active">Activa</option>
              <option value="inactive">Inactiva</option>
            </Select>
          </FormField>
        )}
        {error && <InlineError>{error}</InlineError>}
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

function InlineError({ children }: { children: React.ReactNode }) {
  return (
    <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive">
      {children}
    </div>
  );
}
