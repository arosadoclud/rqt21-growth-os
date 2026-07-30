"use client";

import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  CircleDollarSign,
  FilePenLine,
  Package,
  Pencil,
  Plus,
  RefreshCw,
  ShoppingCart,
} from "lucide-react";
import type { Brand, Product, ProductStatus } from "@rqt21/contracts";
import { PRODUCT_STATUSES } from "@rqt21/contracts";

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

import {
  formatMoney,
  PRODUCT_STATUS_LABELS,
  PRODUCT_STATUS_TONES,
  slugifyStrategy,
} from "./strategy-config";

export function ProductManagement() {
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canWrite = canWriteGrowth(organization?.role);
  const [items, setItems] = useState<Product[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<ProductStatus | "">("");
  const [brandFilter, setBrandFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [productResult, brandResult] = await Promise.all([
        api.listProducts(currentOrgId),
        api.listBrands(currentOrgId),
      ]);
      setItems(productResult);
      setBrands(brandResult);
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar los productos.",
      );
    } finally {
      setLoading(false);
    }
  }, [currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => setPage(1), [brandFilter, pageSize, search, statusFilter]);

  const brandNames = useMemo(
    () => Object.fromEntries(brands.map((brand) => [brand.id, brand.name])),
    [brands],
  );
  const filteredItems = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("es");
    return items.filter((product) => {
      if (statusFilter && product.status !== statusFilter) return false;
      if (brandFilter && product.brand_id !== brandFilter) return false;
      if (!query) return true;
      return [product.name, product.slug, product.description]
        .filter(Boolean)
        .some((value) => value!.toLocaleLowerCase("es").includes(query));
    });
  }, [brandFilter, items, search, statusFilter]);

  const columns: DataTableColumn<Product>[] = [
    {
      key: "product",
      label: "Producto",
      render: (product) => (
        <div className="min-w-0">
          <p className="truncate font-semibold text-foreground">{product.name}</p>
          <p className="mt-1 truncate text-xs text-muted-foreground">{product.slug}</p>
        </div>
      ),
      mobileClassName: "items-start",
    },
    {
      key: "brand",
      label: "Marca",
      render: (product) => (
        <span className="text-sm text-muted-foreground">
          {brandNames[product.brand_id] ?? "Marca vinculada"}
        </span>
      ),
    },
    {
      key: "price",
      label: "Precio",
      render: (product) => (
        <span className="font-medium text-foreground">
          {formatMoney(product.price, product.currency)}
        </span>
      ),
    },
    {
      key: "status",
      label: "Estado",
      render: (product) => (
        <StatusBadge
          label={PRODUCT_STATUS_LABELS[product.status]}
          tone={PRODUCT_STATUS_TONES[product.status]}
        />
      ),
    },
    {
      key: "checkout",
      label: "Checkout",
      render: (product) =>
        product.checkout_url ? (
          <a
            href={product.checkout_url}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-primary hover:underline"
          >
            Abrir enlace
          </a>
        ) : (
          <span className="text-sm text-muted-foreground">Sin enlace</span>
        ),
    },
    {
      key: "actions",
      label: "Acciones",
      render: (product) =>
        canWrite ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setEditing(product);
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
        Selecciona una organización para administrar sus productos.
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
        eyebrow="Oferta comercial"
        title="Productos"
        description="Organiza la oferta, precios y destinos de compra utilizados en campañas y contenido."
        metadata={<StatusBadge label={`${items.length} productos`} />}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
            {canWrite && brands.length > 0 && (
              <Button size="sm" onClick={openCreate}>
                <Plus className="h-4 w-4" />
                Nuevo producto
              </Button>
            )}
          </>
        }
      />

      {error && <InlineError>{error}</InlineError>}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Resumen de productos">
        <MetricCard
          label="Total"
          value={items.length}
          helper="Productos registrados"
          icon={Package}
          loading={loading}
        />
        <MetricCard
          label="Activos"
          value={items.filter((product) => product.status === "ACTIVE").length}
          helper="Disponibles en operación"
          icon={ShoppingCart}
          tone="positive"
          loading={loading}
        />
        <MetricCard
          label="Borradores"
          value={items.filter((product) => product.status === "DRAFT").length}
          helper="Pendientes de publicar"
          icon={FilePenLine}
          tone="warning"
          loading={loading}
        />
        <MetricCard
          label="Con precio"
          value={items.filter((product) => Boolean(product.price)).length}
          helper="Oferta económica definida"
          icon={CircleDollarSign}
          tone="info"
          loading={loading}
        />
      </section>

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchLabel="Buscar productos"
        searchPlaceholder="Buscar por nombre, slug o descripción…"
        hasFilters={Boolean(search || statusFilter || brandFilter)}
        onClear={() => {
          setSearch("");
          setStatusFilter("");
          setBrandFilter("");
        }}
      >
        <Select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as ProductStatus | "")}
          aria-label="Filtrar productos por estado"
          className="lg:w-44"
        >
          <option value="">Todos los estados</option>
          {PRODUCT_STATUSES.map((status) => (
            <option key={status} value={status}>{PRODUCT_STATUS_LABELS[status]}</option>
          ))}
        </Select>
        <Select
          value={brandFilter}
          onChange={(event) => setBrandFilter(event.target.value)}
          aria-label="Filtrar productos por marca"
          className="lg:w-48"
        >
          <option value="">Todas las marcas</option>
          {brands.map((brand) => (
            <option key={brand.id} value={brand.id}>{brand.name}</option>
          ))}
        </Select>
      </FilterBar>

      {brands.length === 0 && !loading && canWrite && (
        <p className="rounded-xl border border-warning/25 bg-warning/5 px-4 py-3 text-sm text-warning">
          Crea una marca antes de registrar productos.
        </p>
      )}
      {!canWrite && (
        <p className="rounded-xl border border-border bg-interactive/35 px-4 py-3 text-sm text-muted-foreground">
          Tu rol puede consultar productos, pero no crearlos ni modificarlos.
        </p>
      )}

      <DataTable
        items={filteredItems}
        columns={columns}
        rowKey={(product) => product.id}
        loading={loading}
        emptyIcon={Package}
        emptyTitle="No encontramos productos"
        emptyDescription="Ajusta los filtros o registra la primera oferta comercial."
        emptyActionLabel={canWrite && brands.length > 0 ? "Crear producto" : undefined}
        onEmptyAction={canWrite && brands.length > 0 ? openCreate : undefined}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
        ariaLabel="Listado de productos"
      />

      <ProductDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        currentOrgId={currentOrgId}
        product={editing}
        brands={brands}
        onSaved={async () => {
          setDrawerOpen(false);
          await load();
        }}
      />
    </div>
  );
}

function ProductDrawer({
  open,
  onOpenChange,
  currentOrgId,
  product,
  brands,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentOrgId: string;
  product: Product | null;
  brands: Brand[];
  onSaved: () => Promise<void>;
}) {
  const [brandId, setBrandId] = useState("");
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [status, setStatus] = useState<ProductStatus>("DRAFT");
  const [checkout, setCheckout] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setBrandId(product?.brand_id ?? brands[0]?.id ?? "");
    setName(product?.name ?? "");
    setSlug(product?.slug ?? "");
    setSlugTouched(Boolean(product));
    setDescription(product?.description ?? "");
    setPrice(product?.price ?? "");
    setCurrency(product?.currency ?? "USD");
    setStatus(product?.status ?? "DRAFT");
    setCheckout(product?.checkout_url ?? "");
    setError(null);
  }, [brands, open, product]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!brandId) return;
    setBusy(true);
    setError(null);
    try {
      if (product) {
        await api.updateProduct(currentOrgId, product.id, {
          name: name.trim(),
          description: description.trim() || null,
          price: price || null,
          currency: currency.trim().toUpperCase(),
          checkout_url: checkout.trim() || null,
          status,
        });
      } else {
        await api.createProduct(currentOrgId, {
          brand_id: brandId,
          name: name.trim(),
          slug: slug.trim(),
          description: description.trim() || null,
          price: price || null,
          currency: currency.trim().toUpperCase(),
          checkout_url: checkout.trim() || null,
          status,
        });
      }
      await onSaved();
    } catch (saveError) {
      setError(
        saveError instanceof ApiError
          ? saveError.detail
          : "No pudimos guardar el producto.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={product ? "Editar producto" : "Nuevo producto"}
      description="Define la oferta comercial y el enlace al que dirigirás las conversiones."
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancelar
          </Button>
          <Button type="submit" form="product-form" disabled={busy || !brandId}>
            {busy ? "Guardando…" : product ? "Guardar cambios" : "Crear producto"}
          </Button>
        </div>
      }
    >
      <form id="product-form" onSubmit={submit} className="space-y-5">
        <FormField label="Marca">
          <Select
            value={brandId}
            disabled={Boolean(product)}
            className={product ? "bg-muted" : undefined}
            onChange={(event) => setBrandId(event.target.value)}
          >
            {brands.map((brand) => (
              <option key={brand.id} value={brand.id}>{brand.name}</option>
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
        <FormField label="Slug" helper={product ? "No cambia después de crear el producto." : "Identificador estable para URLs e integraciones."}>
          <Input
            required
            pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
            value={slug}
            readOnly={Boolean(product)}
            className={product ? "bg-muted" : undefined}
            onChange={(event) => {
              setSlug(event.target.value);
              setSlugTouched(true);
            }}
          />
        </FormField>
        <FormField label="Descripción" optional>
          <Textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={4} />
        </FormField>
        <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
          <FormField label="Precio" optional>
            <Input type="number" min="0" step="0.01" value={price} onChange={(event) => setPrice(event.target.value)} />
          </FormField>
          <FormField label="Moneda">
            <Input required maxLength={3} value={currency} onChange={(event) => setCurrency(event.target.value)} />
          </FormField>
        </div>
        <FormField label="Estado">
          <Select value={status} onChange={(event) => setStatus(event.target.value as ProductStatus)}>
            {PRODUCT_STATUSES.map((value) => (
              <option key={value} value={value}>{PRODUCT_STATUS_LABELS[value]}</option>
            ))}
          </Select>
        </FormField>
        <FormField label="URL de checkout" optional>
          <Input type="url" value={checkout} onChange={(event) => setCheckout(event.target.value)} placeholder="https://…" />
        </FormField>
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
