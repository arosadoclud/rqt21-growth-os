"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CircleDollarSign,
  Gauge,
  Hash,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type { AIUsageSummary, Brand, GenerationType } from "@rqt21/contracts";

import { MetricCard } from "@/components/design-system/metric-card";
import { PageHeader } from "@/components/design-system/page-header";
import { SectionHeader } from "@/components/design-system/section-header";
import { StatusBadge } from "@/components/design-system/status-badge";
import { LoadingSkeleton, StatePanel } from "@/components/design-system/state-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

import {
  AI_PROVIDER_LABELS,
  formatCompactNumber,
  formatCost,
  GENERATION_TYPE_LABELS,
} from "./intelligence-config";

export function AIUsageDashboard() {
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canView = organization?.role === "OWNER" || organization?.role === "ADMIN";
  const [summary, setSummary] = useState<AIUsageSummary | null>(null);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId || !canView) return;
    setLoading(true);
    setError(null);
    try {
      const [usageResult, brandResult] = await Promise.all([
        api.aiUsageSummary(currentOrgId),
        api.listBrands(currentOrgId),
      ]);
      setSummary(usageResult);
      setBrands(brandResult);
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar el consumo de IA.",
      );
    } finally {
      setLoading(false);
    }
  }, [canView, currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  const brandNames = useMemo(
    () => Object.fromEntries(brands.map((brand) => [brand.id, brand.name])),
    [brands],
  );

  if (!currentOrgId) {
    return (
      <StatePanel
        icon={Bot}
        title="Selecciona una organización"
        description="El consumo aparecerá cuando elijas una organización."
      />
    );
  }

  if (!canView) {
    return (
      <StatePanel
        icon={ShieldCheck}
        title="Información financiera restringida"
        description="Solo propietarios y administradores pueden consultar tokens, costos y presupuesto de IA."
      />
    );
  }

  const totalTokens = (summary?.input_tokens ?? 0) + (summary?.output_tokens ?? 0);
  const cost = Number(summary?.estimated_cost ?? 0);
  const budget = Number(summary?.monthly_budget ?? 0);
  const budgetPercent = budget > 0 ? Math.min(100, (cost / budget) * 100) : 0;
  const remaining = Math.max(0, budget - cost);
  const successRate = summary?.jobs_total
    ? Math.round((summary.jobs_completed / summary.jobs_total) * 100)
    : 0;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Control de consumo"
        title="Uso de IA"
        description="Supervisa volumen, costos estimados y distribución del trabajo asistido sin exponer datos financieros a roles no autorizados."
        metadata={
          <>
            <StatusBadge
              label={`${budgetPercent.toFixed(0)}% del presupuesto`}
              tone={budgetPercent >= 90 ? "danger" : budgetPercent >= 70 ? "warning" : "success"}
            />
            <span className="text-xs text-muted-foreground">Estimación del periodo actual</span>
          </>
        }
        actions={
          <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            Actualizar
          </Button>
        }
      />

      {error && <InlineError>{error}</InlineError>}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Resumen de consumo de IA">
        <MetricCard
          label="Generaciones"
          value={summary?.jobs_total ?? 0}
          helper={`${successRate}% completadas correctamente`}
          icon={Sparkles}
          tone="info"
          loading={loading}
        />
        <MetricCard
          label="Tokens procesados"
          value={formatCompactNumber(totalTokens)}
          helper={`${formatCompactNumber(summary?.input_tokens ?? 0)} entrada · ${formatCompactNumber(summary?.output_tokens ?? 0)} salida`}
          icon={Hash}
          loading={loading}
        />
        <MetricCard
          label="Costo estimado"
          value={formatCost(summary?.estimated_cost)}
          helper={`${formatCost(String(remaining))} disponibles`}
          icon={CircleDollarSign}
          tone={budgetPercent >= 90 ? "critical" : "positive"}
          loading={loading}
        />
        <MetricCard
          label="Generaciones con error"
          value={summary?.jobs_failed ?? 0}
          helper="No generan consumo publicable"
          icon={AlertTriangle}
          tone={summary?.jobs_failed ? "warning" : "neutral"}
          loading={loading}
        />
      </section>

      {loading && !summary ? (
        <LoadingSkeleton rows={4} />
      ) : (
        <>
          <Card className="overflow-hidden bg-card/80 shadow-none">
            <CardContent className="p-5 sm:p-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="text-sm font-medium text-foreground">Presupuesto mensual</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    El costo es estimado según tokens y proveedor; no reemplaza la factura del servicio.
                  </p>
                </div>
                <p className="metric-numbers text-xl font-semibold">
                  {formatCost(summary?.estimated_cost)}{" "}
                  <span className="text-sm font-normal text-muted-foreground">
                    de {formatCost(summary?.monthly_budget)}
                  </span>
                </p>
              </div>
              <div
                className="mt-5 h-3 overflow-hidden rounded-full bg-interactive"
                role="progressbar"
                aria-label="Presupuesto mensual utilizado"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(budgetPercent)}
              >
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    budgetPercent >= 90
                      ? "bg-destructive"
                      : budgetPercent >= 70
                        ? "bg-warning"
                        : "bg-success",
                  )}
                  style={{ width: `${budgetPercent}%` }}
                />
              </div>
              <div className="mt-2 flex justify-between text-xs text-muted-foreground">
                <span>{budgetPercent.toFixed(1)}% utilizado</span>
                <span>{formatCost(String(remaining))} restante</span>
              </div>
            </CardContent>
          </Card>

          <section>
            <SectionHeader
              title="Distribución del consumo"
              description="Cantidad de generaciones por motor, formato y marca."
            />
            <div className="mt-4 grid gap-4 lg:grid-cols-3">
              <BreakdownCard
                icon={Bot}
                title="Por motor"
                data={summary?.by_provider ?? {}}
                labelFor={(key) =>
                  AI_PROVIDER_LABELS[key as keyof typeof AI_PROVIDER_LABELS] ?? key
                }
              />
              <BreakdownCard
                icon={Gauge}
                title="Por formato"
                data={summary?.by_type ?? {}}
                labelFor={(key) =>
                  GENERATION_TYPE_LABELS[key as GenerationType] ?? key
                }
              />
              <BreakdownCard
                icon={Sparkles}
                title="Por marca"
                data={summary?.by_brand ?? {}}
                labelFor={(key) => brandNames[key] ?? "Marca sin nombre"}
              />
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function BreakdownCard({
  icon: Icon,
  title,
  data,
  labelFor,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  data: Record<string, number>;
  labelFor: (key: string) => string;
}) {
  const entries = Object.entries(data).sort((left, right) => right[1] - left[1]);
  const max = Math.max(1, ...entries.map(([, value]) => value));
  return (
    <Card className="bg-card/80 shadow-none">
      <CardContent className="p-5">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-interactive text-muted-foreground">
            <Icon className="h-4 w-4" />
          </span>
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        </div>
        {entries.length === 0 ? (
          <p className="mt-5 text-sm text-muted-foreground">Todavía no hay datos.</p>
        ) : (
          <ul className="mt-5 space-y-4">
            {entries.map(([key, value]) => (
              <li key={key}>
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="truncate text-foreground">{labelFor(key)}</span>
                  <span className="font-medium tabular-nums">{value}</span>
                </div>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-interactive">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${(value / max) * 100}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function InlineError({ children }: { children: React.ReactNode }) {
  return (
    <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive">
      {children}
    </div>
  );
}
