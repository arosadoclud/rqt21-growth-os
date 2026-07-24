"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { GenerationJob, GenerationStatus, GenerationType } from "@rqt21/contracts";
import { GENERATION_STATUSES, GENERATION_TYPES } from "@rqt21/contracts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatDate } from "@/lib/ui";

const STATUS_LABELS: Record<GenerationStatus, string> = {
  QUEUED: "En cola",
  RUNNING: "Ejecutando",
  COMPLETED: "Completado",
  FAILED: "Fallido",
  CANCELLED: "Cancelado",
};

export default function GenerationJobsPage() {
  const { currentOrgId } = useAuth();
  const [items, setItems] = useState<GenerationJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<GenerationStatus | "">("");
  const [typeFilter, setTypeFilter] = useState<GenerationType | "">("");

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      if (typeFilter) params.generation_type = typeFilter;
      setItems(await api.listGenerationJobs(currentOrgId, params));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar generaciones");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, statusFilter, typeFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!currentOrgId) return <p>Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Historial de generaciones</h1>
        <Link
          href="/generate"
          className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-fg"
        >
          Nueva generación
        </Link>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-3 text-sm">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as GenerationStatus | "")}
          className="rounded-md border border-slate-300 bg-white px-2 py-1"
        >
          <option value="">Todos los estados</option>
          {GENERATION_STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as GenerationType | "")}
          className="rounded-md border border-slate-300 bg-white px-2 py-1"
        >
          <option value="">Todos los tipos</option>
          {GENERATION_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Fecha</th>
              <th className="px-4 py-2 font-medium">Tipo</th>
              <th className="px-4 py-2 font-medium">Estado</th>
              <th className="px-4 py-2 font-medium">Proveedor</th>
              <th className="px-4 py-2 font-medium">Costo</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                  Cargando…
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                  Sin generaciones
                </td>
              </tr>
            )}
            {items.map((j) => (
              <tr key={j.id} className="border-t border-slate-100">
                <td className="px-4 py-2 text-slate-500">{formatDate(j.created_at)}</td>
                <td className="px-4 py-2 text-slate-700">{j.generation_type}</td>
                <td className="px-4 py-2">
                  <Link href={`/generation-jobs/${j.id}`} className="text-brand hover:underline">
                    {STATUS_LABELS[j.status]}
                  </Link>
                </td>
                <td className="px-4 py-2 text-slate-600">{j.provider}</td>
                <td className="px-4 py-2 text-slate-600">
                  {j.visibility === "restricted" ? "—" : j.estimated_cost ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
