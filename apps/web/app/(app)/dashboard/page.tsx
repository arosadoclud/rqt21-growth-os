"use client";

import { useCallback, useEffect, useState } from "react";
import type {
  Asset,
  AutomationSummary,
  DashboardSummary,
  GenerationJob,
  Phase3Dashboard,
  PublishingSummary,
} from "@rqt21/contracts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatDate } from "@/lib/ui";

export default function DashboardPage() {
  const { user, organizations, currentOrgId } = useAuth();
  const currentOrg = organizations.find((o) => o.id === currentOrgId);

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [p3, setP3] = useState<Phase3Dashboard | null>(null);
  const [aiJobs, setAiJobs] = useState<GenerationJob[] | null>(null);
  const [publishing, setPublishing] = useState<PublishingSummary | null>(null);
  const [assets, setAssets] = useState<Asset[] | null>(null);
  const [automation, setAutomation] = useState<AutomationSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [s, three, jobs, pub, as_, auto] = await Promise.all([
        api.dashboardSummary(currentOrgId),
        api.phase3Dashboard(currentOrgId),
        api.listGenerationJobs(currentOrgId).catch(() => []),
        api.publishingSummary(currentOrgId).catch(() => null),
        api.listAssets(currentOrgId).catch(() => []),
        api.automationSummary(currentOrgId).catch(() => null),
      ]);
      setSummary(s);
      setP3(three);
      setAiJobs(jobs);
      setPublishing(pub);
      setAssets(as_);
      setAutomation(auto);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar métricas");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">
          Bienvenido, {user?.full_name}
        </h1>
        <p className="text-sm text-slate-500">
          {currentOrg ? (
            <>Organización activa: <strong>{currentOrg.name}</strong> · Rol <strong>{currentOrg.role}</strong></>
          ) : (
            <>Sin organización seleccionada</>
          )}
        </p>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Campañas", value: summary?.campaigns_total },
          { label: "Contenidos", value: summary?.contents_total },
          { label: "Enlaces activos", value: summary?.active_links },
          { label: "Clics totales", value: summary?.clicks_total },
        ].map((k) => (
          <div key={k.label} className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="text-sm text-slate-500">{k.label}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-900">
              {loading ? "…" : k.value ?? "—"}
            </div>
          </div>
        ))}
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-medium text-slate-900">Operación editorial</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard label="Pendientes de revisión" value={p3?.editorial.pending_review} />
          <StatCard label="Programados esta semana" value={p3?.editorial.scheduled_this_week} />
          <StatCard label="Publicados este mes" value={p3?.editorial.published_this_month} />
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="text-sm font-medium text-slate-900">Próximos contenidos</h3>
          {(!p3 || p3.editorial.upcoming.length === 0) && (
            <p className="mt-2 text-sm text-slate-500">Sin próximos programados.</p>
          )}
          <ul className="mt-2 space-y-1 text-sm">
            {p3?.editorial.upcoming.slice(0, 5).map((u) => (
              <li key={u.id} className="flex justify-between text-slate-700">
                <span>
                  {u.platform} · <span className="text-xs text-slate-400">{u.status}</span>
                </span>
                <span className="text-slate-500">{formatDate(u.scheduled_for)}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-medium text-slate-900">Conversión</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Leads nuevos" value={p3?.leads.new_leads} />
          <StatCard label="Calificados" value={p3?.leads.qualified_leads} />
          <StatCard label="Ganados" value={p3?.leads.won_leads} />
          <StatCard
            label="Clic → lead"
            value={
              p3
                ? `${(summary && summary.clicks_total
                    ? ((p3.leads.total_leads / summary.clicks_total) * 100).toFixed(1)
                    : "0.0")}%`
                : undefined
            }
          />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-medium text-slate-900">Top campañas por leads</h3>
            {(!p3 || p3.leads.top_campaigns.length === 0) && (
              <p className="mt-2 text-sm text-slate-500">Sin datos.</p>
            )}
            <ul className="mt-2 space-y-1 text-sm">
              {p3?.leads.top_campaigns.slice(0, 5).map((c) => (
                <li key={c.campaign_id} className="flex justify-between text-slate-700">
                  <span>{c.campaign_name}</span>
                  <span className="text-slate-500">{c.leads} leads</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-medium text-slate-900">Top contenidos por leads</h3>
            {(!p3 || p3.leads.top_contents.length === 0) && (
              <p className="mt-2 text-sm text-slate-500">Sin datos.</p>
            )}
            <ul className="mt-2 space-y-1 text-sm">
              {p3?.leads.top_contents.slice(0, 5).map((c) => (
                <li key={c.content_id} className="flex justify-between text-slate-700">
                  <span>{c.content_title}</span>
                  <span className="text-slate-500">{c.leads} leads</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-medium text-slate-900">Producción asistida</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Generados esta semana"
            value={aiJobs ? countThisWeek(aiJobs) : undefined}
          />
          <StatCard
            label="Borradores creados"
            value={aiJobs ? aiJobs.filter((j) => j.content_item_id).length : undefined}
          />
          <StatCard
            label="Completados"
            value={aiJobs ? aiJobs.filter((j) => j.status === "COMPLETED").length : undefined}
          />
          <StatCard
            label="Generación → contenido"
            value={aiJobs ? `${conversionRate(aiJobs)}%` : undefined}
          />
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-medium text-slate-900">Publicaciones y activos</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Programadas" value={publishing?.scheduled} />
          <StatCard label="Publicadas" value={publishing?.published} />
          <StatCard label="Fallidas" value={publishing?.failed} />
          <StatCard label="Tasa de éxito" value={publishing ? `${publishing.success_rate}%` : undefined} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Activos totales" value={assets?.length} />
          <StatCard
            label="Activos listos"
            value={assets ? assets.filter((a) => a.status === "READY").length : undefined}
          />
          <StatCard
            label="Activos rechazados"
            value={assets ? assets.filter((a) => a.status === "REJECTED").length : undefined}
          />
          <StatCard
            label="Sin texto alternativo"
            value={
              assets
                ? assets.filter((a) => a.asset_type === "IMAGE" && !a.alt_text).length
                : undefined
            }
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard label="Automatizaciones activas" value={automation?.active_rules} />
          <StatCard label="Ejecuciones de automatización" value={automation?.total_executions} />
          <StatCard label="Bucles prevenidos" value={automation?.loop_preventions} />
        </div>
      </section>
    </div>
  );
}

function countThisWeek(jobs: GenerationJob[]): number {
  const now = new Date();
  const start = new Date(now);
  start.setDate(now.getDate() - now.getDay());
  start.setHours(0, 0, 0, 0);
  return jobs.filter((j) => new Date(j.created_at) >= start).length;
}

function conversionRate(jobs: GenerationJob[]): string {
  const completed = jobs.filter((j) => j.status === "COMPLETED");
  if (completed.length === 0) return "0.0";
  const converted = completed.filter((j) => j.content_item_id).length;
  return ((converted / completed.length) * 100).toFixed(1);
}

function StatCard({ label, value }: { label: string; value?: number | string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">
        {value === undefined || value === null ? "—" : value}
      </div>
    </div>
  );
}
