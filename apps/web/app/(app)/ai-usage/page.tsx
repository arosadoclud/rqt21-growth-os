"use client";

import { useCallback, useEffect, useState } from "react";
import type { AIUsageSummary } from "@rqt21/contracts";
import { Card, CardContent } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function AiUsagePage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canView = org?.role === "OWNER" || org?.role === "ADMIN";

  const [summary, setSummary] = useState<AIUsageSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId || !canView) return;
    setLoading(true);
    setError(null);
    try {
      setSummary(await api.aiUsageSummary(currentOrgId));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar el uso de IA");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, canView]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;
  if (!canView) {
    return (
      <p className="text-sm text-muted-foreground">
        Tu rol no permite ver el consumo y costos de IA.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Uso de IA</h1>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}
      {loading && <p className="text-sm text-muted-foreground">Cargando…</p>}

      {summary && (
        <>
          <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <Stat label="Jobs totales" value={summary.jobs_total} />
            <Stat label="Completados" value={summary.jobs_completed} />
            <Stat label="Fallidos" value={summary.jobs_failed} />
            <Stat label="Tokens entrada" value={summary.input_tokens} />
            <Stat label="Tokens salida" value={summary.output_tokens} />
            <Stat label="Costo estimado" value={`$${summary.estimated_cost}`} />
          </div>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between text-sm">
                <span>Presupuesto mensual</span>
                <span className="text-muted-foreground">
                  ${summary.estimated_cost} / ${summary.monthly_budget}
                </span>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full bg-primary"
                  style={{
                    width: `${Math.min(
                      100,
                      (Number(summary.estimated_cost) / Math.max(1, Number(summary.monthly_budget))) *
                        100,
                    )}%`,
                  }}
                />
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-3">
            <Breakdown title="Por proveedor" data={summary.by_provider} />
            <Breakdown title="Por tipo" data={summary.by_type} />
            <Breakdown title="Por marca" data={summary.by_brand} />
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 text-xl font-semibold tracking-tight">{value}</div>
      </CardContent>
    </Card>
  );
}

function Breakdown({ title, data }: { title: string; data: Record<string, number> }) {
  const entries = Object.entries(data);
  return (
    <Card>
      <CardContent className="p-4">
        <h2 className="text-sm font-medium">{title}</h2>
        {entries.length === 0 && <p className="mt-2 text-sm text-muted-foreground">Sin datos.</p>}
        <ul className="mt-2 divide-y divide-border text-sm">
          {entries.map(([k, v]) => (
            <li key={k} className="flex justify-between py-1.5">
              <span>{k}</span>
              <span className="text-muted-foreground">{v}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
