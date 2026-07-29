"use client";

import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowDownAZ,
  ArrowUpDown,
  Download,
  Filter,
  Plus,
  RefreshCw,
  Search,
  Trophy,
  UserCheck,
  UserPlus,
  Users,
} from "lucide-react";
import type { Lead, LeadSource, LeadStatus } from "@rqt21/contracts";
import { LEAD_SOURCES, LEAD_STATUSES } from "@rqt21/contracts";

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
import { cn } from "@/lib/utils";

import {
  formatLeadDate,
  leadName,
  LEAD_SOURCE_LABELS,
  LEAD_STATUS_LABELS,
  LEAD_STATUS_TONES,
} from "./lead-config";

type SortKey = "created" | "name" | "status" | "source";
type SortDirection = "asc" | "desc";

export function LeadsCrm() {
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canWrite = ["OWNER", "ADMIN", "SALES", "MARKETER"].includes(organization?.role ?? "");
  const canExport = ["OWNER", "ADMIN", "SALES"].includes(organization?.role ?? "");
  const canSeePii = canWrite || canExport;

  const [items, setItems] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<LeadStatus | "">("");
  const [sourceFilter, setSourceFilter] = useState<LeadSource | "">("");
  const [sortKey, setSortKey] = useState<SortKey>("created");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [createOpen, setCreateOpen] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = { limit: "1000" };
      if (query) params.q = query;
      if (statusFilter) params.status = statusFilter;
      if (sourceFilter) params.source = sourceFilter;
      setItems(await api.listLeads(currentOrgId, params));
    } catch (loadError) {
      setError(
        loadError instanceof ApiError ? loadError.detail : "No pudimos cargar los leads.",
      );
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, query, sourceFilter, statusFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => setPage(1), [query, sourceFilter, statusFilter, pageSize]);

  const sortedItems = useMemo(() => {
    const direction = sortDirection === "asc" ? 1 : -1;
    return [...items].sort((first, second) => {
      if (sortKey === "name") return leadName(first).localeCompare(leadName(second), "es") * direction;
      if (sortKey === "status") {
        return (
          (LEAD_STATUSES.indexOf(first.status) - LEAD_STATUSES.indexOf(second.status)) *
          direction
        );
      }
      if (sortKey === "source") return first.source.localeCompare(second.source) * direction;
      return (new Date(first.created_at).getTime() - new Date(second.created_at).getTime()) * direction;
    });
  }, [items, sortDirection, sortKey]);

  const pageItems = sortedItems.slice((page - 1) * pageSize, page * pageSize);
  const newCount = items.filter((lead) => lead.status === "NEW").length;
  const qualifiedCount = items.filter((lead) => lead.status === "QUALIFIED").length;
  const wonCount = items.filter((lead) => lead.status === "WON").length;

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDirection((current) => current === "asc" ? "desc" : "asc");
    else {
      setSortKey(key);
      setSortDirection(key === "created" ? "desc" : "asc");
    }
    setPage(1);
  };

  if (!currentOrgId) {
    return (
      <StatePanel
        icon={Users}
        title="Selecciona una organización"
        description="El CRM aparecerá cuando elijas una organización."
      />
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Relaciones comerciales"
        title="Leads y CRM"
        description="Encuentra oportunidades, prioriza el seguimiento y abre cada lead para consultar su historial completo."
        metadata={
          <>
            <StatusBadge label={`${items.length} resultados`} />
            {!canSeePii && <span className="text-xs text-muted-foreground">Datos personales protegidos</span>}
          </>
        }
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
            {canExport && (
              <Button variant="outline" size="sm" asChild>
                <a href={api.exportLeadsUrl(currentOrgId)}>
                  <Download className="h-4 w-4" />
                  Exportar CSV
                </a>
              </Button>
            )}
            {canWrite && (
              <Button size="sm" onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" />
                Nuevo lead
              </Button>
            )}
          </>
        }
      />

      {error && (
        <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/8 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Resumen de leads">
        <MetricCard label="Resultados" value={items.length} helper="Con los filtros actuales" icon={Users} tone="neutral" loading={loading} />
        <MetricCard label="Nuevos" value={newCount} helper="Pendientes de primer contacto" icon={UserPlus} tone="info" loading={loading} />
        <MetricCard label="Calificados" value={qualifiedCount} helper="Oportunidades priorizadas" icon={UserCheck} tone="warning" loading={loading} />
        <MetricCard label="Ganados" value={wonCount} helper="Conversiones confirmadas" icon={Trophy} tone="positive" loading={loading} />
      </section>

      <Card className="bg-card/80 shadow-none">
        <CardContent className="p-4">
          <div className="grid gap-3 lg:grid-cols-[minmax(15rem,1fr)_13rem_13rem_auto]">
            <label className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Buscar…"
                className="pl-9"
                aria-label="Buscar leads"
              />
            </label>
            <Select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as LeadStatus | "")}
              aria-label="Filtrar por estado"
            >
              <option value="">Todos los estados</option>
              {LEAD_STATUSES.map((status) => (
                <option key={status} value={status}>{LEAD_STATUS_LABELS[status]}</option>
              ))}
            </Select>
            <Select
              value={sourceFilter}
              onChange={(event) => setSourceFilter(event.target.value as LeadSource | "")}
              aria-label="Filtrar por fuente"
            >
              <option value="">Todas las fuentes</option>
              {LEAD_SOURCES.map((source) => (
                <option key={source} value={source}>{LEAD_SOURCE_LABELS[source]}</option>
              ))}
            </Select>
            {search || statusFilter || sourceFilter ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSearch("");
                  setQuery("");
                  setStatusFilter("");
                  setSourceFilter("");
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

      {loading ? (
        <Card className="bg-card/80 shadow-none"><CardContent className="p-5"><LoadingSkeleton rows={7} /></CardContent></Card>
      ) : items.length === 0 ? (
        <StatePanel
          icon={Users}
          title="No encontramos leads"
          description="Ajusta los filtros o añade el primer lead a esta organización."
          actionLabel={canWrite ? "Crear lead" : undefined}
          onAction={canWrite ? () => setCreateOpen(true) : undefined}
        />
      ) : (
        <Card className="overflow-hidden bg-card/85 shadow-none">
          <div className="hidden grid-cols-[minmax(12rem,1.3fr)_minmax(12rem,1fr)_0.8fr_0.8fr_0.7fr_auto] gap-4 border-b border-border bg-interactive/35 px-5 py-3 md:grid">
            <SortHeader label="Lead" sortKey="name" activeKey={sortKey} direction={sortDirection} onSort={toggleSort} />
            <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Contacto</span>
            <SortHeader label="Fuente" sortKey="source" activeKey={sortKey} direction={sortDirection} onSort={toggleSort} />
            <SortHeader label="Estado" sortKey="status" activeKey={sortKey} direction={sortDirection} onSort={toggleSort} />
            <SortHeader label="Creado" sortKey="created" activeKey={sortKey} direction={sortDirection} onSort={toggleSort} />
            <span className="sr-only">Abrir</span>
          </div>
          <ul className="divide-y divide-border">
            {pageItems.map((lead) => (
              <li key={lead.id}>
                <Link
                  href={`/leads/${lead.id}`}
                  className="grid gap-3 px-4 py-4 transition-colors hover:bg-interactive/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring md:grid-cols-[minmax(12rem,1.3fr)_minmax(12rem,1fr)_0.8fr_0.8fr_0.7fr_auto] md:items-center md:gap-4 md:px-5"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold text-foreground">{leadName(lead)}</span>
                    <span className="mt-1 block text-xs text-muted-foreground">{lead.public_id}</span>
                  </span>
                  <span className="min-w-0 text-sm text-muted-foreground">
                    {canSeePii ? (
                      <>
                        {lead.email && <span className="block truncate">{lead.email}</span>}
                        {(lead.phone || lead.whatsapp) && <span className="mt-1 block text-xs">{lead.phone ?? lead.whatsapp}</span>}
                        {!lead.email && !lead.phone && !lead.whatsapp && "Sin contacto"}
                      </>
                    ) : (
                      "Información protegida"
                    )}
                  </span>
                  <span className="text-sm text-muted-foreground">{LEAD_SOURCE_LABELS[lead.source]}</span>
                  <StatusBadge label={LEAD_STATUS_LABELS[lead.status]} tone={LEAD_STATUS_TONES[lead.status]} className="w-fit" />
                  <span className="text-xs text-muted-foreground">{formatLeadDate(lead.created_at)}</span>
                  <span className="text-xs font-medium text-primary">Ver detalle</span>
                </Link>
              </li>
            ))}
          </ul>
          <Pagination
            page={page}
            pageSize={pageSize}
            totalItems={sortedItems.length}
            onPageChange={setPage}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(1);
            }}
          />
        </Card>
      )}

      <CreateLeadDrawer
        open={createOpen}
        onOpenChange={setCreateOpen}
        currentOrgId={currentOrgId}
        onCreated={async () => {
          setCreateOpen(false);
          await load();
        }}
      />
    </div>
  );
}

function SortHeader({
  label,
  sortKey,
  activeKey,
  direction,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  activeKey: SortKey;
  direction: SortDirection;
  onSort: (key: SortKey) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      className="flex items-center gap-1.5 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground hover:text-foreground"
    >
      {label}
      {activeKey === sortKey ? (
        <ArrowDownAZ className={cn("h-3.5 w-3.5", direction === "desc" && "rotate-180")} />
      ) : (
        <ArrowUpDown className="h-3.5 w-3.5 opacity-50" />
      )}
    </button>
  );
}

function CreateLeadDrawer({
  open,
  onOpenChange,
  currentOrgId,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentOrgId: string;
  onCreated: () => Promise<void>;
}) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [source, setSource] = useState<LeadSource>("MANUAL");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setFirstName("");
    setLastName("");
    setEmail("");
    setPhone("");
    setWhatsapp("");
    setSource("MANUAL");
    setNotes("");
    setError(null);
  }, [open]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!email.trim() && !phone.trim() && !whatsapp.trim()) {
      setError("Añade al menos un correo, teléfono o WhatsApp.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.createLead(currentOrgId, {
        first_name: firstName.trim(),
        last_name: lastName.trim() || null,
        email: email.trim() || null,
        phone: phone.trim() || null,
        whatsapp: whatsapp.trim() || null,
        source,
        notes: notes.trim() || null,
      });
      await onCreated();
    } catch (createError) {
      setError(createError instanceof ApiError ? createError.detail : "No pudimos crear el lead.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title="Nuevo lead"
      description="Registra la información de contacto disponible. Podrás completar su seguimiento desde el detalle."
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button type="submit" form="create-lead-form" disabled={busy}>
            {busy ? "Guardando…" : "Crear lead"}
          </Button>
        </div>
      }
    >
      <form id="create-lead-form" onSubmit={submit} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Nombre"><Input required value={firstName} onChange={(event) => setFirstName(event.target.value)} /></FormField>
          <FormField label="Apellido" optional><Input value={lastName} onChange={(event) => setLastName(event.target.value)} /></FormField>
        </div>
        <FormField label="Correo" optional><Input type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></FormField>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Teléfono" optional><Input value={phone} onChange={(event) => setPhone(event.target.value)} /></FormField>
          <FormField label="WhatsApp" optional><Input value={whatsapp} onChange={(event) => setWhatsapp(event.target.value)} /></FormField>
        </div>
        <FormField label="Fuente">
          <Select value={source} onChange={(event) => setSource(event.target.value as LeadSource)}>
            {LEAD_SOURCES.map((value) => <option key={value} value={value}>{LEAD_SOURCE_LABELS[value]}</option>)}
          </Select>
        </FormField>
        <FormField label="Notas" optional>
          <Textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={4} />
        </FormField>
        <p className="text-xs text-muted-foreground">Se requiere al menos un medio de contacto.</p>
        {error && <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/8 px-4 py-3 text-sm text-destructive">{error}</div>}
      </form>
    </Drawer>
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
        {label}{optional && <span className="ml-1 font-normal text-muted-foreground">(opcional)</span>}
      </span>
      {children}
    </label>
  );
}
