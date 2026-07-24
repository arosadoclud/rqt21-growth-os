"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Megaphone,
  FileText,
  Link2,
  MousePointerClick,
  ClipboardCheck,
  CalendarClock,
  CheckCircle2,
  Users,
  UserCheck,
  Trophy,
  TrendingUp,
  Sparkles,
} from "lucide-react";
import type {
  Asset,
  AutomationSummary,
  DashboardSummary,
  GenerationJob,
  Phase3Dashboard,
  PublishingSummary,
} from "@rqt21/contracts";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatDate } from "@/lib/ui";
import { cn } from "@/lib/utils";

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
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Bienvenido, {user?.full_name}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {currentOrg ? (
            <>
              Organización activa: <span className="font-medium text-foreground">{currentOrg.name}</span>{" "}
              · Rol <Badge variant="outline" className="ml-1">{currentOrg.role}</Badge>
            </>
          ) : (
            <>Sin organización seleccionada</>
          )}
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile icon={Megaphone} label="Campañas" value={summary?.campaigns_total} loading={loading} />
        <StatTile icon={FileText} label="Contenidos" value={summary?.contents_total} loading={loading} />
        <StatTile icon={Link2} label="Enlaces activos" value={summary?.active_links} loading={loading} />
        <StatTile icon={MousePointerClick} label="Clics totales" value={summary?.clicks_total} loading={loading} />
      </div>

      <Section title="Operación editorial">
        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard icon={ClipboardCheck} label="Pendientes de revisión" value={p3?.editorial.pending_review} />
          <StatCard icon={CalendarClock} label="Programados esta semana" value={p3?.editorial.scheduled_this_week} />
          <StatCard icon={CheckCircle2} label="Publicados este mes" value={p3?.editorial.published_this_month} />
        </div>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-foreground">Próximos contenidos</CardTitle>
          </CardHeader>
          <CardContent>
            {(!p3 || p3.editorial.upcoming.length === 0) && (
              <p className="text-sm text-muted-foreground">Sin próximos programados.</p>
            )}
            <ul className="divide-y divide-border">
              {p3?.editorial.upcoming.slice(0, 5).map((u) => (
                <li key={u.id} className="flex items-center justify-between py-2 text-sm">
                  <span className="flex items-center gap-2">
                    <Badge variant="secondary">{u.platform}</Badge>
                    <span className="text-xs text-muted-foreground">{u.status}</span>
                  </span>
                  <span className="text-muted-foreground">{formatDate(u.scheduled_for)}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </Section>

      <Section title="Conversión">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard icon={Users} label="Leads nuevos" value={p3?.leads.new_leads} />
          <StatCard icon={UserCheck} label="Calificados" value={p3?.leads.qualified_leads} />
          <StatCard icon={Trophy} label="Ganados" value={p3?.leads.won_leads} />
          <StatCard
            icon={TrendingUp}
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
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-foreground">Top campañas por leads</CardTitle>
            </CardHeader>
            <CardContent>
              {(!p3 || p3.leads.top_campaigns.length === 0) && (
                <p className="text-sm text-muted-foreground">Sin datos.</p>
              )}
              <ul className="divide-y divide-border">
                {p3?.leads.top_campaigns.slice(0, 5).map((c) => (
                  <li key={c.campaign_id} className="flex justify-between py-2 text-sm">
                    <span>{c.campaign_name}</span>
                    <span className="text-muted-foreground">{c.leads} leads</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-foreground">Top contenidos por leads</CardTitle>
            </CardHeader>
            <CardContent>
              {(!p3 || p3.leads.top_contents.length === 0) && (
                <p className="text-sm text-muted-foreground">Sin datos.</p>
              )}
              <ul className="divide-y divide-border">
                {p3?.leads.top_contents.slice(0, 5).map((c) => (
                  <li key={c.content_id} className="flex justify-between py-2 text-sm">
                    <span>{c.content_title}</span>
                    <span className="text-muted-foreground">{c.leads} leads</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      </Section>

      <Section title="Producción asistida">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            icon={Sparkles}
            label="Generados esta semana"
            value={aiJobs ? countThisWeek(aiJobs) : undefined}
          />
          <StatCard
            icon={FileText}
            label="Borradores creados"
            value={aiJobs ? aiJobs.filter((j) => j.content_item_id).length : undefined}
          />
          <StatCard
            icon={CheckCircle2}
            label="Completados"
            value={aiJobs ? aiJobs.filter((j) => j.status === "COMPLETED").length : undefined}
          />
          <StatCard
            icon={TrendingUp}
            label="Generación → contenido"
            value={aiJobs ? `${conversionRate(aiJobs)}%` : undefined}
          />
        </div>
      </Section>

      <Section title="Publicaciones y activos">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard icon={CalendarClock} label="Programadas" value={publishing?.scheduled} />
          <StatCard icon={CheckCircle2} label="Publicadas" value={publishing?.published} />
          <StatCard icon={ClipboardCheck} label="Fallidas" value={publishing?.failed} tone="destructive" />
          <StatCard
            icon={TrendingUp}
            label="Tasa de éxito"
            value={publishing ? `${publishing.success_rate}%` : undefined}
            tone="success"
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Activos totales" value={assets?.length} />
          <StatCard
            label="Activos listos"
            value={assets ? assets.filter((a) => a.status === "READY").length : undefined}
            tone="success"
          />
          <StatCard
            label="Activos rechazados"
            value={assets ? assets.filter((a) => a.status === "REJECTED").length : undefined}
            tone="destructive"
          />
          <StatCard
            label="Sin texto alternativo"
            value={
              assets
                ? assets.filter((a) => a.asset_type === "IMAGE" && !a.alt_text).length
                : undefined
            }
            tone="warning"
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard label="Automatizaciones activas" value={automation?.active_rules} />
          <StatCard label="Ejecuciones de automatización" value={automation?.total_executions} />
          <StatCard label="Bucles prevenidos" value={automation?.loop_preventions} />
        </div>
      </Section>
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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold tracking-tight">{title}</h2>
      {children}
    </section>
  );
}

const TONE_CLASSES: Record<string, string> = {
  default: "text-muted-foreground",
  success: "text-success",
  destructive: "text-destructive",
  warning: "text-warning",
};

function StatTile({
  icon: Icon,
  label,
  value,
  loading,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value?: number | string;
  loading?: boolean;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <div className="text-sm text-muted-foreground">{label}</div>
          <div className="text-2xl font-semibold tracking-tight">
            {loading ? "…" : value ?? "—"}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  tone = "default",
}: {
  icon?: React.ComponentType<{ className?: string }>;
  label: string;
  value?: number | string;
  tone?: "default" | "success" | "destructive" | "warning";
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
          {Icon && <Icon className="h-3.5 w-3.5" />}
          {label}
        </div>
        <div className={cn("mt-1 text-2xl font-semibold tracking-tight", TONE_CLASSES[tone])}>
          {value === undefined || value === null ? "—" : value}
        </div>
      </CardContent>
    </Card>
  );
}
