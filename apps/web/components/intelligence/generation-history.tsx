"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock3,
  Plus,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import type {
  GenerationJob,
  GenerationStatus,
  GenerationType,
} from "@rqt21/contracts";
import { GENERATION_STATUSES, GENERATION_TYPES } from "@rqt21/contracts";

import {
  DataTable,
  type DataTableColumn,
} from "@/components/design-system/data-table";
import { FilterBar } from "@/components/design-system/filter-bar";
import { MetricCard } from "@/components/design-system/metric-card";
import { PageHeader } from "@/components/design-system/page-header";
import { StatusBadge } from "@/components/design-system/status-badge";
import { StatePanel } from "@/components/design-system/state-panel";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

import {
  AI_PROVIDER_LABELS,
  formatCost,
  formatIntelligenceDate,
  GENERATION_STATUS_LABELS,
  GENERATION_STATUS_TONES,
  GENERATION_TYPE_LABELS,
} from "./intelligence-config";

export function GenerationHistory() {
  const { currentOrgId } = useAuth();
  const [items, setItems] = useState<GenerationJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<GenerationStatus | "">("");
  const [typeFilter, setTypeFilter] = useState<GenerationType | "">("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      setItems(await api.listGenerationJobs(currentOrgId));
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar el historial de IA.",
      );
    } finally {
      setLoading(false);
    }
  }, [currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => setPage(1), [pageSize, search, statusFilter, typeFilter]);

  const filteredItems = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("es");
    return items.filter((job) => {
      if (statusFilter && job.status !== statusFilter) return false;
      if (typeFilter && job.generation_type !== typeFilter) return false;
      if (!query) return true;
      const input = job.input_payload ?? {};
      return [
        GENERATION_TYPE_LABELS[job.generation_type],
        GENERATION_STATUS_LABELS[job.status],
        AI_PROVIDER_LABELS[job.provider],
        String(input.topic ?? ""),
        String(input.platform ?? ""),
        job.model,
      ].some((value) => value.toLocaleLowerCase("es").includes(query));
    });
  }, [items, search, statusFilter, typeFilter]);

  const columns: DataTableColumn<GenerationJob>[] = [
    {
      key: "generation",
      label: "Generación",
      render: (job) => (
        <div className="min-w-0">
          <Link
            href={`/generation-jobs/${job.id}`}
            className="font-semibold text-foreground hover:text-primary"
          >
            {GENERATION_TYPE_LABELS[job.generation_type]}
          </Link>
          <p className="mt-1 max-w-xs truncate text-xs text-muted-foreground">
            {String(job.input_payload?.topic ?? "Sin tema registrado")}
          </p>
        </div>
      ),
      mobileClassName: "items-start",
    },
    {
      key: "status",
      label: "Estado",
      render: (job) => (
        <div>
          <StatusBadge
            label={GENERATION_STATUS_LABELS[job.status]}
            tone={GENERATION_STATUS_TONES[job.status]}
          />
          {job.stage && job.status === "RUNNING" && (
            <p className="mt-1 max-w-48 truncate text-xs text-muted-foreground">{job.stage}</p>
          )}
        </div>
      ),
    },
    {
      key: "provider",
      label: "Motor",
      render: (job) => (
        <div>
          <p className="text-sm text-foreground">{AI_PROVIDER_LABELS[job.provider]}</p>
          <p className="mt-1 text-xs text-muted-foreground">{job.model}</p>
        </div>
      ),
    },
    {
      key: "cost",
      label: "Consumo",
      render: (job) =>
        job.visibility === "restricted" ? (
          <span className="text-xs text-muted-foreground">Restringido por rol</span>
        ) : (
          <div>
            <p className="font-medium tabular-nums">{formatCost(job.estimated_cost)}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {(job.input_tokens ?? 0) + (job.output_tokens ?? 0)} tokens
            </p>
          </div>
        ),
    },
    {
      key: "created",
      label: "Fecha",
      render: (job) => (
        <span className="text-xs text-muted-foreground">
          {formatIntelligenceDate(job.created_at)}
        </span>
      ),
    },
    {
      key: "action",
      label: "Acción",
      render: (job) => (
        <Button asChild variant="ghost" size="sm">
          <Link href={`/generation-jobs/${job.id}`}>Ver resultado</Link>
        </Button>
      ),
    },
  ];

  if (!currentOrgId) {
    return (
      <StatePanel
        icon={Bot}
        title="Selecciona una organización"
        description="El historial aparecerá cuando elijas una organización."
      />
    );
  }

  const completed = items.filter((job) => job.status === "COMPLETED").length;
  const failed = items.filter((job) => job.status === "FAILED").length;
  const inProgress = items.filter(
    (job) => job.status === "QUEUED" || job.status === "RUNNING",
  ).length;
  const successRate = items.length ? Math.round((completed / items.length) * 100) : 0;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Inteligencia creativa"
        title="Historial de IA"
        description="Consulta resultados, consumo y errores con estados claros antes de convertir una generación en contenido."
        metadata={
          <>
            <StatusBadge label={`${items.length} generaciones`} />
            <span className="text-xs text-muted-foreground">
              Los resultados nunca se publican automáticamente
            </span>
          </>
        }
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
            <Button asChild size="sm">
              <Link href="/generate">
                <Plus className="h-4 w-4" />
                Nueva generación
              </Link>
            </Button>
          </>
        }
      />

      {error && <InlineError>{error}</InlineError>}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Resumen de generaciones">
        <MetricCard
          label="Completadas"
          value={completed}
          helper={`${successRate}% del historial`}
          icon={CheckCircle2}
          tone="positive"
          loading={loading}
        />
        <MetricCard
          label="En proceso"
          value={inProgress}
          helper="En espera o generándose"
          icon={Clock3}
          tone="info"
          loading={loading}
        />
        <MetricCard
          label="Con error"
          value={failed}
          helper="Disponibles para reintentar"
          icon={AlertTriangle}
          tone={failed ? "critical" : "neutral"}
          loading={loading}
        />
        <MetricCard
          label="Tipos utilizados"
          value={new Set(items.map((job) => job.generation_type)).size}
          helper="Formatos creativos distintos"
          icon={Sparkles}
          loading={loading}
        />
      </section>

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchLabel="Buscar generaciones"
        searchPlaceholder="Buscar por tema, formato, motor o modelo…"
        hasFilters={Boolean(search || statusFilter || typeFilter)}
        onClear={() => {
          setSearch("");
          setStatusFilter("");
          setTypeFilter("");
        }}
      >
        <Select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as GenerationStatus | "")}
          aria-label="Filtrar generaciones por estado"
          className="lg:w-48"
        >
          <option value="">Todos los estados</option>
          {GENERATION_STATUSES.map((status) => (
            <option key={status} value={status}>{GENERATION_STATUS_LABELS[status]}</option>
          ))}
        </Select>
        <Select
          value={typeFilter}
          onChange={(event) => setTypeFilter(event.target.value as GenerationType | "")}
          aria-label="Filtrar generaciones por formato"
          className="lg:w-56"
        >
          <option value="">Todos los formatos</option>
          {GENERATION_TYPES.map((type) => (
            <option key={type} value={type}>{GENERATION_TYPE_LABELS[type]}</option>
          ))}
        </Select>
      </FilterBar>

      <DataTable
        items={filteredItems}
        columns={columns}
        rowKey={(job) => job.id}
        loading={loading}
        emptyIcon={Bot}
        emptyTitle="No encontramos generaciones"
        emptyDescription="Ajusta los filtros o crea el primer borrador asistido."
        emptyActionLabel="Crear generación"
        onEmptyAction={() => window.location.assign("/generate")}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        ariaLabel="Historial de generaciones de IA"
      />
    </div>
  );
}

function InlineError({ children }: { children: React.ReactNode }) {
  return (
    <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive">
      {children}
    </div>
  );
}
