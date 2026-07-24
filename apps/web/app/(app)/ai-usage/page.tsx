"use client";

import { useCallback, useEffect, useState } from "react";
import type { AIUsageSummary } from "@rqt21/contracts";
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

  if (!currentOrgId) return <p>Selecciona una organización.</p>;
  if (!canView) {
    return (
      <p className="text-sm text-slate-500">
        Tu rol no permite ver el consumo y costos de IA.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Uso de IA</h1>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}
      {loading && <p className="text-sm text-slate-500">Cargando…</p>}

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

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-700">Presupuesto mensual</span>
              <span className="text-slate-500">
                ${summary.estimated_cost} / ${summary.monthly_budget}
              </span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full bg-brand"
                style={{
                  width: `${Math.min(
                    100,
                    (Number(summary.estimated_cost) / Math.max(1, Number(summary.monthly_budget))) *
                      100,
                  )}%`,
                }}
              />
            </div>
          </div>

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
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function Breakdown({ title, data }: { title: string; data: Record<string, number> }) {
  const entries = Object.entries(data);
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-medium text-slate-900">{title}</h2>
      {entries.length === 0 && <p className="mt-2 text-sm text-slate-500">Sin datos.</p>}
      <ul className="mt-2 space-y-1 text-sm">
        {entries.map(([k, v]) => (
          <li key={k} className="flex justify-between text-slate-700">
            <span>{k}</span>
            <span className="text-slate-500">{v}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
