"use client";

import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  CircleAlert,
  Link2,
  Pencil,
  Plus,
  RefreshCw,
  ShieldCheck,
  Unplug,
  Wifi,
} from "lucide-react";
import type {
  Brand,
  ConnectionStatus,
  Platform,
  PublishingConnection,
  PublishingProviderName,
} from "@rqt21/contracts";
import {
  CONNECTION_STATUSES,
  PLATFORMS,
  PUBLISHING_PROVIDERS,
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
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canAdmin } from "@/lib/ui";
import { cn } from "@/lib/utils";

import {
  CONNECTION_STATUS_LABELS,
  CONNECTION_STATUS_TONES,
  formatOperationsDate,
  OPERATIONS_PLATFORM_LABELS,
  PUBLISHING_PROVIDER_LABELS,
} from "./operations-config";

type ConnectionAction = "revoke" | "disable";

export function ConnectionManagement() {
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canManage = canAdmin(organization?.role);
  const isViewer = organization?.role === "VIEWER";
  const [items, setItems] = useState<PublishingConnection[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<ConnectionStatus | "">("");
  const [platformFilter, setPlatformFilter] = useState<Platform | "">("");
  const [brandFilter, setBrandFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [createOpen, setCreateOpen] = useState(false);
  const [selected, setSelected] = useState<PublishingConnection | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<{
    connection: PublishingConnection;
    action: ConnectionAction;
  } | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId || isViewer) return;
    setLoading(true);
    setError(null);
    try {
      const [connectionResult, brandResult] = await Promise.all([
        api.listConnections(currentOrgId),
        api.listBrands(currentOrgId),
      ]);
      setItems(connectionResult);
      setBrands(brandResult);
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar las conexiones.",
      );
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, isViewer]);

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
  const filteredItems = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("es");
    return items.filter((connection) => {
      if (statusFilter && connection.status !== statusFilter) return false;
      if (platformFilter && connection.platform !== platformFilter) return false;
      if (brandFilter && connection.brand_id !== brandFilter) return false;
      if (!query) return true;
      return [
        connection.account_name,
        connection.external_account_id,
        brandNames[connection.brand_id],
        PUBLISHING_PROVIDER_LABELS[connection.provider],
      ]
        .filter(Boolean)
        .some((value) => value!.toLocaleLowerCase("es").includes(query));
    });
  }, [
    brandFilter,
    brandNames,
    items,
    platformFilter,
    search,
    statusFilter,
  ]);

  const verify = async (connection: PublishingConnection) => {
    if (!currentOrgId) return;
    setBusyId(connection.id);
    setError(null);
    try {
      const updated = await api.verifyConnection(currentOrgId, connection.id);
      setSelected(updated);
      await load();
    } catch (verifyError) {
      setError(
        verifyError instanceof ApiError
          ? verifyError.detail
          : "No pudimos verificar la conexión.",
      );
    } finally {
      setBusyId(null);
    }
  };

  const applyConnectionAction = async () => {
    if (!currentOrgId || !confirmAction) return;
    const { connection, action } = confirmAction;
    setBusyId(connection.id);
    setError(null);
    try {
      if (action === "revoke") {
        await api.revokeConnection(currentOrgId, connection.id);
      } else {
        await api.disableConnection(currentOrgId, connection.id);
      }
      setConfirmAction(null);
      setSelected(null);
      await load();
    } catch (actionError) {
      setError(
        actionError instanceof ApiError
          ? actionError.detail
          : "No pudimos actualizar la conexión.",
      );
    } finally {
      setBusyId(null);
    }
  };

  const columns: DataTableColumn<PublishingConnection>[] = [
    {
      key: "account",
      label: "Cuenta",
      render: (connection) => (
        <div className="min-w-0">
          <p className="truncate font-semibold text-foreground">{connection.account_name}</p>
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {brandNames[connection.brand_id] ?? "Marca vinculada"}
          </p>
        </div>
      ),
      mobileClassName: "items-start",
    },
    {
      key: "channel",
      label: "Canal",
      render: (connection) => (
        <span className="text-sm text-muted-foreground">
          {OPERATIONS_PLATFORM_LABELS[connection.platform]}
        </span>
      ),
    },
    {
      key: "provider",
      label: "Proveedor",
      render: (connection) => (
        <span className="text-sm text-muted-foreground">
          {PUBLISHING_PROVIDER_LABELS[connection.provider]}
        </span>
      ),
    },
    {
      key: "status",
      label: "Estado",
      render: (connection) => (
        <StatusBadge
          label={CONNECTION_STATUS_LABELS[connection.status]}
          tone={CONNECTION_STATUS_TONES[connection.status]}
        />
      ),
    },
    {
      key: "verified",
      label: "Verificada",
      render: (connection) => (
        <span className="text-xs text-muted-foreground">
          {formatOperationsDate(connection.last_verified_at)}
        </span>
      ),
    },
    {
      key: "actions",
      label: "Acciones",
      render: (connection) => (
        <Button variant="ghost" size="sm" onClick={() => setSelected(connection)}>
          <Pencil className="h-3.5 w-3.5" />
          {canManage ? "Administrar" : "Ver detalle"}
        </Button>
      ),
      className: "w-32",
    },
  ];

  if (!currentOrgId) {
    return (
      <StatePanel
        icon={Link2}
        title="Selecciona una organización"
        description="Las conexiones aparecerán cuando elijas una organización."
      />
    );
  }

  if (isViewer) {
    return (
      <StatePanel
        icon={Unplug}
        title="Acceso restringido"
        description="Tu rol no tiene acceso a las conexiones de publicación."
      />
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Distribución"
        title="Conexiones de publicación"
        description="Administra las cuentas y proveedores que distribuyen contenido a cada canal."
        metadata={
          <>
            <StatusBadge label={`${items.length} conexiones`} />
            {!canManage && (
              <span className="text-xs text-muted-foreground">Configuración de solo lectura</span>
            )}
          </>
        }
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
            {canManage && brands.length > 0 && (
              <Button size="sm" onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" />
                Agregar cuenta
              </Button>
            )}
          </>
        }
      />

      {error && <InlineError>{error}</InlineError>}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Resumen de conexiones">
        <MetricCard
          label="Conexiones"
          value={items.length}
          helper="Cuentas configuradas"
          icon={Link2}
          loading={loading}
        />
        <MetricCard
          label="Activas"
          value={items.filter((connection) => connection.status === "ACTIVE").length}
          helper="Disponibles para publicar"
          icon={Wifi}
          tone="positive"
          loading={loading}
        />
        <MetricCard
          label="Requieren atención"
          value={items.filter((connection) => ["ERROR", "EXPIRED", "PENDING"].includes(connection.status)).length}
          helper="Errores, vencimientos o pendientes"
          icon={CircleAlert}
          tone="warning"
          loading={loading}
        />
        <MetricCard
          label="Verificadas"
          value={items.filter((connection) => Boolean(connection.last_verified_at)).length}
          helper="Comprobadas al menos una vez"
          icon={ShieldCheck}
          tone="info"
          loading={loading}
        />
      </section>

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchLabel="Buscar conexiones"
        searchPlaceholder="Buscar por cuenta, marca o proveedor…"
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
          onChange={(event) => setStatusFilter(event.target.value as ConnectionStatus | "")}
          aria-label="Filtrar conexiones por estado"
          className="lg:w-44"
        >
          <option value="">Todos los estados</option>
          {CONNECTION_STATUSES.map((status) => (
            <option key={status} value={status}>{CONNECTION_STATUS_LABELS[status]}</option>
          ))}
        </Select>
        <Select
          value={platformFilter}
          onChange={(event) => setPlatformFilter(event.target.value as Platform | "")}
          aria-label="Filtrar conexiones por canal"
          className="lg:w-40"
        >
          <option value="">Todos los canales</option>
          {PLATFORMS.map((platform) => (
            <option key={platform} value={platform}>{OPERATIONS_PLATFORM_LABELS[platform]}</option>
          ))}
        </Select>
        <Select
          value={brandFilter}
          onChange={(event) => setBrandFilter(event.target.value)}
          aria-label="Filtrar conexiones por marca"
          className="lg:w-44"
        >
          <option value="">Todas las marcas</option>
          {brands.map((brand) => (
            <option key={brand.id} value={brand.id}>{brand.name}</option>
          ))}
        </Select>
      </FilterBar>

      {!canManage && (
        <p className="rounded-xl border border-border bg-interactive/35 px-4 py-3 text-sm text-muted-foreground">
          Tu rol puede revisar el estado de las conexiones, pero solo propietarios y administradores pueden configurarlas.
        </p>
      )}

      <DataTable
        items={filteredItems}
        columns={columns}
        rowKey={(connection) => connection.id}
        loading={loading}
        emptyIcon={Link2}
        emptyTitle="No encontramos conexiones"
        emptyDescription="Ajusta los filtros o agrega la primera cuenta de publicación."
        emptyActionLabel={canManage && brands.length > 0 ? "Agregar cuenta" : undefined}
        onEmptyAction={canManage && brands.length > 0 ? () => setCreateOpen(true) : undefined}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
        ariaLabel="Listado de conexiones de publicación"
      />

      <CreateConnectionDrawer
        open={createOpen}
        onOpenChange={setCreateOpen}
        currentOrgId={currentOrgId}
        brands={brands}
        onCreated={async () => {
          setCreateOpen(false);
          await load();
        }}
      />

      <ConnectionDetailDrawer
        open={Boolean(selected)}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
        connection={selected}
        currentOrgId={currentOrgId}
        brandName={selected ? brandNames[selected.brand_id] : undefined}
        canManage={canManage}
        busy={Boolean(selected && busyId === selected.id)}
        onVerify={verify}
        onRequestAction={(connection, action) => setConfirmAction({ connection, action })}
        onSaved={async (updated) => {
          setSelected(updated);
          await load();
        }}
      />

      <ConfirmationDialog
        open={Boolean(confirmAction)}
        onOpenChange={(open) => {
          if (!open && !busyId) setConfirmAction(null);
        }}
        title={
          confirmAction?.action === "revoke"
            ? "¿Revocar esta conexión?"
            : "¿Deshabilitar esta conexión?"
        }
        description={
          confirmAction?.action === "revoke"
            ? "La credencial quedará revocada y será necesario configurar una nueva para volver a publicar."
            : "La cuenta dejará de estar disponible para nuevas publicaciones hasta que se configure nuevamente."
        }
        confirmLabel={confirmAction?.action === "revoke" ? "Revocar conexión" : "Deshabilitar conexión"}
        tone="danger"
        busy={Boolean(busyId)}
        onConfirm={applyConnectionAction}
      />
    </div>
  );
}

function CreateConnectionDrawer({
  open,
  onOpenChange,
  currentOrgId,
  brands,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentOrgId: string;
  brands: Brand[];
  onCreated: () => Promise<void>;
}) {
  const [brandId, setBrandId] = useState("");
  const [platform, setPlatform] = useState<Platform>("INSTAGRAM");
  const [provider, setProvider] = useState<PublishingProviderName>("MOCK");
  const [accountName, setAccountName] = useState("");
  const [externalAccountId, setExternalAccountId] = useState("");
  const [token, setToken] = useState("");
  const [useBaseToken, setUseBaseToken] = useState(false);
  const [pageId, setPageId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setBrandId(brands[0]?.id ?? "");
    setPlatform("INSTAGRAM");
    setProvider("MOCK");
    setAccountName("");
    setExternalAccountId("");
    setToken("");
    setUseBaseToken(false);
    setPageId("");
    setError(null);
  }, [brands, open]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!brandId) return;
    setBusy(true);
    setError(null);
    try {
      await api.createConnection(currentOrgId, {
        brand_id: brandId,
        platform,
        provider,
        account_name: accountName.trim(),
        external_account_id: externalAccountId.trim() || null,
        credentials:
          provider === "MANUAL" || provider === "MOCK" || !token
            ? null
            : useBaseToken && provider === "META"
              ? {
                  base_access_token: token,
                  ...(platform === "INSTAGRAM" && pageId ? { page_id: pageId } : {}),
                }
              : { access_token: token },
      });
      await onCreated();
    } catch (createError) {
      setError(
        createError instanceof ApiError
          ? createError.detail
          : "No pudimos guardar la cuenta.",
      );
    } finally {
      setBusy(false);
    }
  };

  const needsCredentials = provider !== "MANUAL" && provider !== "MOCK";

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title="Agregar cuenta"
      description="Vincula una cuenta o un flujo manual a la marca que publicará contenido."
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancelar
          </Button>
          <Button type="submit" form="connection-form" disabled={busy || !brandId}>
            {busy ? "Guardando…" : "Guardar cuenta"}
          </Button>
        </div>
      }
    >
      <form id="connection-form" onSubmit={submit} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Marca">
            <Select value={brandId} onChange={(event) => setBrandId(event.target.value)}>
              {brands.map((brand) => (
                <option key={brand.id} value={brand.id}>{brand.name}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Plataforma">
            <Select value={platform} onChange={(event) => setPlatform(event.target.value as Platform)}>
              {PLATFORMS.map((value) => (
                <option key={value} value={value}>{OPERATIONS_PLATFORM_LABELS[value]}</option>
              ))}
            </Select>
          </FormField>
        </div>
        <FormField label="Proveedor">
          <Select
            value={provider}
            onChange={(event) => {
              setProvider(event.target.value as PublishingProviderName);
              setToken("");
              setUseBaseToken(false);
            }}
          >
            {PUBLISHING_PROVIDERS.map((value) => (
              <option key={value} value={value}>{PUBLISHING_PROVIDER_LABELS[value]}</option>
            ))}
          </Select>
        </FormField>
        <FormField label="Nombre de la cuenta">
          <Input
            required
            value={accountName}
            onChange={(event) => setAccountName(event.target.value)}
            placeholder="Ejemplo: Instagram principal"
          />
        </FormField>
        {needsCredentials && (
          <>
            <FormField label="ID de cuenta externa" optional>
              <Input value={externalAccountId} onChange={(event) => setExternalAccountId(event.target.value)} />
            </FormField>
            <FormField label={provider === "META" && useBaseToken ? "Token base" : "Token de acceso"}>
              <Input
                required
                type="password"
                autoComplete="off"
                value={token}
                onChange={(event) => setToken(event.target.value)}
              />
            </FormField>
          </>
        )}
        {provider === "META" && (
          <label className="flex items-start gap-3 rounded-xl border border-border bg-interactive/35 p-4 text-sm">
            <input
              type="checkbox"
              checked={useBaseToken}
              onChange={(event) => setUseBaseToken(event.target.checked)}
              className="mt-0.5 rounded border-input"
            />
            <span>
              <span className="font-medium text-foreground">Token base de larga duración</span>
              <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                El servidor resolverá credenciales de página actualizadas en cada publicación.
              </span>
            </span>
          </label>
        )}
        {provider === "META" && platform === "INSTAGRAM" && useBaseToken && (
          <FormField label="ID de la página de Facebook vinculada">
            <Input required value={pageId} onChange={(event) => setPageId(event.target.value)} />
          </FormField>
        )}
        {error && <InlineError>{error}</InlineError>}
      </form>
    </Drawer>
  );
}

function ConnectionDetailDrawer({
  open,
  onOpenChange,
  connection,
  currentOrgId,
  brandName,
  canManage,
  busy,
  onVerify,
  onRequestAction,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  connection: PublishingConnection | null;
  currentOrgId: string;
  brandName?: string;
  canManage: boolean;
  busy: boolean;
  onVerify: (connection: PublishingConnection) => Promise<void>;
  onRequestAction: (connection: PublishingConnection, action: ConnectionAction) => void;
  onSaved: (connection: PublishingConnection) => Promise<void>;
}) {
  const [accountName, setAccountName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setAccountName(connection?.account_name ?? "");
    setError(null);
  }, [connection]);

  if (!connection) return null;

  const saveName = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateConnection(currentOrgId, connection.id, {
        account_name: accountName.trim(),
      });
      await onSaved(updated);
    } catch (saveError) {
      setError(
        saveError instanceof ApiError
          ? saveError.detail
          : "No pudimos actualizar la cuenta.",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={connection.account_name}
      description={`${OPERATIONS_PLATFORM_LABELS[connection.platform]} · ${PUBLISHING_PROVIDER_LABELS[connection.provider]}`}
      footer={
        <div className="flex justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cerrar</Button>
        </div>
      }
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            label={CONNECTION_STATUS_LABELS[connection.status]}
            tone={CONNECTION_STATUS_TONES[connection.status]}
          />
          <span className="text-xs text-muted-foreground">{brandName ?? "Marca vinculada"}</span>
        </div>
        <dl className="grid gap-4 rounded-xl border border-border bg-card p-4 text-sm sm:grid-cols-2">
          <Metadata label="Proveedor" value={PUBLISHING_PROVIDER_LABELS[connection.provider]} />
          <Metadata label="Cuenta externa" value={connection.external_account_id ?? "Sin identificador"} />
          <Metadata
            label="Credencial"
            value={connection.credentials_last_four ? `•••• ${connection.credentials_last_four}` : "No requerida"}
          />
          <Metadata label="Última verificación" value={formatOperationsDate(connection.last_verified_at)} />
          <Metadata label="Vencimiento" value={formatOperationsDate(connection.token_expires_at)} />
          <Metadata
            label="Capacidades"
            value={connection.capabilities.length ? connection.capabilities.join(", ") : "Predeterminadas"}
          />
        </dl>
        {canManage && (
          <>
            <FormField label="Nombre interno">
              <div className="flex gap-2">
                <Input value={accountName} onChange={(event) => setAccountName(event.target.value)} />
                <Button
                  variant="outline"
                  onClick={() => void saveName()}
                  disabled={saving || !accountName.trim() || accountName === connection.account_name}
                >
                  {saving ? "Guardando…" : "Guardar"}
                </Button>
              </div>
            </FormField>
            <div className="space-y-2 rounded-xl border border-border p-4">
              <p className="text-sm font-medium text-foreground">Acciones de conexión</p>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={busy}
                  onClick={() => void onVerify(connection)}
                >
                  <ShieldCheck className="h-3.5 w-3.5" />
                  Verificar
                </Button>
                {connection.status !== "REVOKED" && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy}
                    onClick={() => onRequestAction(connection, "revoke")}
                  >
                    Revocar
                  </Button>
                )}
                {connection.status !== "DISABLED" && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy}
                    onClick={() => onRequestAction(connection, "disable")}
                  >
                    Deshabilitar
                  </Button>
                )}
              </div>
            </div>
          </>
        )}
        {!canManage && (
          <p className="rounded-xl border border-border bg-interactive/35 p-4 text-sm text-muted-foreground">
            Solo propietarios y administradores pueden verificar o cambiar esta conexión.
          </p>
        )}
        {error && <InlineError>{error}</InlineError>}
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

function FormField({
  label,
  optional,
  children,
}: {
  label: string;
  optional?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5 text-sm">
      <span className="font-medium text-foreground">
        {label}
        {optional && <span className="ml-1 font-normal text-muted-foreground">(opcional)</span>}
      </span>
      {children}
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
