"use client";

import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Activity,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  ShieldCheck,
  ToggleLeft,
  Zap,
} from "lucide-react";
import type {
  AutomationRule,
  AutomationSummary,
  AutomationTriggerType,
  Brand,
  PublishingConnection,
} from "@rqt21/contracts";
import { AUTOMATION_TRIGGER_TYPES } from "@rqt21/contracts";

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
  AUTOMATION_ACTION_LABELS,
  AUTOMATION_TEMPLATES,
  AUTOMATION_TRIGGER_LABELS,
  formatOperationsDate,
  PUBLISHING_PROVIDER_LABELS,
} from "./operations-config";

type ActivityFilter = "all" | "active" | "inactive";

export function AutomationManagement() {
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canManage = canAdmin(organization?.role);
  const [items, setItems] = useState<AutomationRule[]>([]);
  const [summary, setSummary] = useState<AutomationSummary | null>(null);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [connections, setConnections] = useState<PublishingConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [activityFilter, setActivityFilter] = useState<ActivityFilter>("all");
  const [triggerFilter, setTriggerFilter] = useState<AutomationTriggerType | "">("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<AutomationRule | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId || !canManage) return;
    setLoading(true);
    setError(null);
    try {
      const [ruleResult, summaryResult, brandResult, connectionResult] =
        await Promise.all([
          api.listAutomations(currentOrgId),
          api.automationSummary(currentOrgId).catch(() => null),
          api.listBrands(currentOrgId),
          api.listConnections(currentOrgId).catch(() => []),
        ]);
      setItems(ruleResult);
      setSummary(summaryResult);
      setBrands(brandResult);
      setConnections(connectionResult);
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar las automatizaciones.",
      );
    } finally {
      setLoading(false);
    }
  }, [canManage, currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => setPage(1), [activityFilter, pageSize, search, triggerFilter]);

  const brandNames = useMemo(
    () => Object.fromEntries(brands.map((brand) => [brand.id, brand.name])),
    [brands],
  );
  const filteredItems = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("es");
    return items.filter((rule) => {
      if (activityFilter === "active" && !rule.is_active) return false;
      if (activityFilter === "inactive" && rule.is_active) return false;
      if (triggerFilter && rule.trigger_type !== triggerFilter) return false;
      if (!query) return true;
      return [
        rule.name,
        AUTOMATION_TRIGGER_LABELS[rule.trigger_type],
        AUTOMATION_ACTION_LABELS[rule.action_type],
        rule.brand_id ? brandNames[rule.brand_id] : "todas las marcas",
      ].some((value) => value.toLocaleLowerCase("es").includes(query));
    });
  }, [
    activityFilter,
    brandNames,
    items,
    search,
    triggerFilter,
  ]);

  const toggle = async (rule: AutomationRule) => {
    if (!currentOrgId) return;
    setBusyId(rule.id);
    setError(null);
    try {
      await api.updateAutomation(currentOrgId, rule.id, {
        is_active: !rule.is_active,
      });
      await load();
    } catch (toggleError) {
      setError(
        toggleError instanceof ApiError
          ? toggleError.detail
          : "No pudimos cambiar el estado de la automatización.",
      );
    } finally {
      setBusyId(null);
    }
  };

  const columns: DataTableColumn<AutomationRule>[] = [
    {
      key: "name",
      label: "Automatización",
      render: (rule) => (
        <div className="min-w-0">
          <p className="truncate font-semibold text-foreground">{rule.name}</p>
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {rule.brand_id ? brandNames[rule.brand_id] ?? "Marca vinculada" : "Todas las marcas"}
          </p>
        </div>
      ),
      mobileClassName: "items-start",
    },
    {
      key: "flow",
      label: "Flujo",
      render: (rule) => (
        <div className="max-w-sm text-sm">
          <p className="text-foreground">
            {AUTOMATION_TRIGGER_LABELS[rule.trigger_type]}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            → {AUTOMATION_ACTION_LABELS[rule.action_type]}
          </p>
        </div>
      ),
    },
    {
      key: "executions",
      label: "Ejecuciones",
      render: (rule) => (
        <div>
          <p className="font-semibold tabular-nums text-foreground">{rule.execution_count}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {formatOperationsDate(rule.last_executed_at)}
          </p>
        </div>
      ),
    },
    {
      key: "status",
      label: "Estado",
      render: (rule) => (
        <StatusBadge
          label={rule.is_active ? "Activa" : "Inactiva"}
          tone={rule.is_active ? "success" : "neutral"}
        />
      ),
    },
    {
      key: "actions",
      label: "Acciones",
      render: (rule) => (
        <div className="flex flex-wrap gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setEditing(rule);
              setDrawerOpen(true);
            }}
          >
            <Pencil className="h-3.5 w-3.5" />
            Editar
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={busyId === rule.id}
            onClick={() => void toggle(rule)}
          >
            {rule.is_active ? "Desactivar" : "Activar"}
          </Button>
        </div>
      ),
      className: "min-w-52",
    },
  ];

  if (!currentOrgId) {
    return (
      <StatePanel
        icon={Zap}
        title="Selecciona una organización"
        description="Las automatizaciones aparecerán cuando elijas una organización."
      />
    );
  }

  if (!canManage) {
    return (
      <StatePanel
        icon={ShieldCheck}
        title="Acceso administrativo"
        description="Solo propietarios y administradores pueden consultar o modificar automatizaciones."
      />
    );
  }

  const openCreate = () => {
    setEditing(null);
    setDrawerOpen(true);
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Operación asistida"
        title="Automatizaciones"
        description="Activa flujos predefinidos y auditables. Ninguna regla publica contenido sin una revisión humana."
        metadata={
          <>
            <StatusBadge label={`${items.length} reglas`} />
            <span className="text-xs text-muted-foreground">
              Plantillas seguras, sin código personalizado
            </span>
          </>
        }
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
            <Button size="sm" onClick={openCreate}>
              <Plus className="h-4 w-4" />
              Nueva automatización
            </Button>
          </>
        }
      />

      {error && <InlineError>{error}</InlineError>}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Resumen de automatizaciones">
        <MetricCard
          label="Reglas activas"
          value={summary?.active_rules ?? items.filter((rule) => rule.is_active).length}
          helper="Flujos habilitados"
          icon={Play}
          tone="positive"
          loading={loading}
        />
        <MetricCard
          label="Ejecuciones"
          value={summary?.total_executions ?? items.reduce((total, rule) => total + rule.execution_count, 0)}
          helper="Acciones procesadas"
          icon={Activity}
          tone="info"
          loading={loading}
        />
        <MetricCard
          label="Bucles prevenidos"
          value={summary?.loop_preventions ?? 0}
          helper="Protecciones del sistema"
          icon={ShieldCheck}
          tone="warning"
          loading={loading}
        />
        <MetricCard
          label="Inactivas"
          value={items.filter((rule) => !rule.is_active).length}
          helper="Disponibles para reactivar"
          icon={ToggleLeft}
          loading={loading}
        />
      </section>

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchLabel="Buscar automatizaciones"
        searchPlaceholder="Buscar por nombre, evento o acción…"
        hasFilters={Boolean(search || triggerFilter || activityFilter !== "all")}
        onClear={() => {
          setSearch("");
          setTriggerFilter("");
          setActivityFilter("all");
        }}
      >
        <Select
          value={activityFilter}
          onChange={(event) => setActivityFilter(event.target.value as ActivityFilter)}
          aria-label="Filtrar automatizaciones por estado"
          className="lg:w-40"
        >
          <option value="all">Todos los estados</option>
          <option value="active">Activas</option>
          <option value="inactive">Inactivas</option>
        </Select>
        <Select
          value={triggerFilter}
          onChange={(event) => setTriggerFilter(event.target.value as AutomationTriggerType | "")}
          aria-label="Filtrar automatizaciones por evento"
          className="lg:w-56"
        >
          <option value="">Todos los eventos</option>
          {AUTOMATION_TRIGGER_TYPES.map((trigger) => (
            <option key={trigger} value={trigger}>
              {AUTOMATION_TRIGGER_LABELS[trigger]}
            </option>
          ))}
        </Select>
      </FilterBar>

      <DataTable
        items={filteredItems}
        columns={columns}
        rowKey={(rule) => rule.id}
        loading={loading}
        emptyIcon={Zap}
        emptyTitle="No encontramos automatizaciones"
        emptyDescription="Ajusta los filtros o activa el primer flujo operativo."
        emptyActionLabel="Crear automatización"
        onEmptyAction={openCreate}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
        ariaLabel="Listado de automatizaciones"
      />

      <AutomationDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        currentOrgId={currentOrgId}
        rule={editing}
        brands={brands}
        connections={connections}
        onSaved={async () => {
          setDrawerOpen(false);
          await load();
        }}
      />
    </div>
  );
}

function AutomationDrawer({
  open,
  onOpenChange,
  currentOrgId,
  rule,
  brands,
  connections,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentOrgId: string;
  rule: AutomationRule | null;
  brands: Brand[];
  connections: PublishingConnection[];
  onSaved: () => Promise<void>;
}) {
  const [templateIndex, setTemplateIndex] = useState(0);
  const [name, setName] = useState("");
  const [brandId, setBrandId] = useState("");
  const [connectionId, setConnectionId] = useState("");
  const [active, setActive] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const matchingIndex = rule
      ? AUTOMATION_TEMPLATES.findIndex(
          (template) =>
            template.trigger === rule.trigger_type &&
            template.action === rule.action_type,
        )
      : 0;
    setTemplateIndex(Math.max(0, matchingIndex));
    setName(rule?.name ?? "");
    setBrandId(rule?.brand_id ?? "");
    setConnectionId(
      typeof rule?.action_config.publishing_connection_id === "string"
        ? rule.action_config.publishing_connection_id
        : "",
    );
    setActive(rule?.is_active ?? true);
    setError(null);
  }, [open, rule]);

  const selectedTemplate = AUTOMATION_TEMPLATES[templateIndex];
  const requiresConnection =
    selectedTemplate.action === "CREATE_PUBLICATION_DRAFT";

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (requiresConnection && !connectionId) {
      setError("Selecciona la conexión que recibirá el borrador.");
      return;
    }
    setBusy(true);
    setError(null);
    const actionConfig: Record<string, unknown> = requiresConnection
      ? {
          publishing_connection_id: connectionId,
          publication_type: "POST",
          default_caption: "",
        }
      : {};
    try {
      if (rule) {
        await api.updateAutomation(currentOrgId, rule.id, {
          name: name.trim(),
          action_config: actionConfig,
          is_active: active,
        });
      } else {
        await api.createAutomation(currentOrgId, {
          name: name.trim(),
          brand_id: brandId || null,
          trigger_type: selectedTemplate.trigger,
          action_type: selectedTemplate.action,
          conditions: {},
          action_config: actionConfig,
          is_active: active,
        });
      }
      await onSaved();
    } catch (saveError) {
      setError(
        saveError instanceof ApiError
          ? saveError.detail
          : "No pudimos guardar la automatización.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={rule ? "Editar automatización" : "Nueva automatización"}
      description={
        rule
          ? "Actualiza el nombre, destino y disponibilidad de la regla."
          : "Elige una plantilla segura y define dónde debe aplicarse."
      }
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancelar
          </Button>
          <Button type="submit" form="automation-form" disabled={busy}>
            {busy ? "Guardando…" : rule ? "Guardar cambios" : "Crear automatización"}
          </Button>
        </div>
      }
    >
      <form id="automation-form" onSubmit={submit} className="space-y-5">
        <span className="sr-only">Nueva automatización</span>
        <FormField label="Plantilla" helper={selectedTemplate.description}>
          <Select
            value={templateIndex}
            disabled={Boolean(rule)}
            className={rule ? "bg-muted" : undefined}
            onChange={(event) => {
              setTemplateIndex(Number(event.target.value));
              setConnectionId("");
            }}
          >
            {AUTOMATION_TEMPLATES.map((template, index) => (
              <option key={template.label} value={index}>{template.label}</option>
            ))}
          </Select>
        </FormField>
        <FormField label="Nombre">
          <Input required value={name} onChange={(event) => setName(event.target.value)} />
        </FormField>
        <FormField label="Marca" optional helper={rule ? "La marca no cambia después de crear la regla." : "Déjalo vacío para aplicar a todas las marcas."}>
          <Select
            value={brandId}
            disabled={Boolean(rule)}
            className={rule ? "bg-muted" : undefined}
            onChange={(event) => setBrandId(event.target.value)}
          >
            <option value="">Todas las marcas</option>
            {brands.map((brand) => (
              <option key={brand.id} value={brand.id}>{brand.name}</option>
            ))}
          </Select>
        </FormField>
        {requiresConnection && (
          <FormField label="Conexión de publicación destino">
            <Select
              required
              value={connectionId}
              onChange={(event) => setConnectionId(event.target.value)}
            >
              <option value="">Selecciona una conexión</option>
              {connections.map((connection) => (
                <option key={connection.id} value={connection.id}>
                  {connection.account_name} · {PUBLISHING_PROVIDER_LABELS[connection.provider]}
                </option>
              ))}
            </Select>
          </FormField>
        )}
        <FormField label="Estado">
          <Select value={active ? "active" : "inactive"} onChange={(event) => setActive(event.target.value === "active")}>
            <option value="active">Activa</option>
            <option value="inactive">Inactiva</option>
          </Select>
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
