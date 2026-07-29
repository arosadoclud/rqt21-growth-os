"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  FileWarning,
  ImageOff,
  MousePointerClick,
  RefreshCw,
  Send,
  Sparkles,
  Target,
  TrendingUp,
  UserCheck,
  Users,
  Zap,
} from "lucide-react";
import type {
  Asset,
  AutomationSummary,
  DashboardSummary,
  GenerationJob,
  Phase3Dashboard,
  PublishingSummary,
} from "@rqt21/contracts";

import { MetricCard } from "@/components/design-system/metric-card";
import { PageHeader } from "@/components/design-system/page-header";
import { SectionHeader } from "@/components/design-system/section-header";
import { LoadingSkeleton, StatePanel } from "@/components/design-system/state-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

type ActionTone = "warning" | "critical" | "info";

interface ActionItem {
  label: string;
  description: string;
  count: number;
  href: string;
  cta: string;
  tone: ActionTone;
  icon: React.ComponentType<{ className?: string }>;
}

const ACTION_TONES: Record<ActionTone, string> = {
  warning: "bg-warning/12 text-warning",
  critical: "bg-destructive/12 text-destructive",
  info: "bg-info/12 text-info",
};

export function PremiumDashboard() {
  const { user, organizations, currentOrgId } = useAuth();
  const currentOrg = organizations.find((organization) => organization.id === currentOrgId);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [phase3, setPhase3] = useState<Phase3Dashboard | null>(null);
  const [aiJobs, setAiJobs] = useState<GenerationJob[]>([]);
  const [publishing, setPublishing] = useState<PublishingSummary | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [automation, setAutomation] = useState<AutomationSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [dashboard, conversion, jobs, publishingData, assetData, automationData] =
        await Promise.all([
          api.dashboardSummary(currentOrgId),
          api.phase3Dashboard(currentOrgId),
          api.listGenerationJobs(currentOrgId).catch(() => []),
          api.publishingSummary(currentOrgId).catch(() => null),
          api.listAssets(currentOrgId).catch(() => []),
          api.automationSummary(currentOrgId).catch(() => null),
        ]);
      setSummary(dashboard);
      setPhase3(conversion);
      setAiJobs(jobs);
      setPublishing(publishingData);
      setAssets(assetData);
      setAutomation(automationData);
      setUpdatedAt(new Date());
    } catch (loadError) {
      setError(loadError instanceof ApiError ? loadError.detail : "No pudimos cargar el resumen.");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  const actions = useMemo<ActionItem[]>(() => {
    const missingAltText = assets.filter(
      (asset) => asset.asset_type === "IMAGE" && !asset.alt_text,
    ).length;

    return [
      {
        label: "Contenidos pendientes de revisión",
        description: "Esperan una decisión editorial antes de avanzar.",
        count: phase3?.editorial.pending_review ?? 0,
        href: "/reviews",
        cta: "Abrir revisiones",
        tone: "warning",
        icon: ClipboardCheck,
      },
      {
        label: "Publicaciones fallidas",
        description: "Requieren diagnóstico o un nuevo intento.",
        count: publishing?.failed ?? 0,
        href: "/publishing",
        cta: "Revisar publicaciones",
        tone: "critical",
        icon: FileWarning,
      },
      {
        label: "Conexiones con errores",
        description: "Pueden bloquear próximas publicaciones.",
        count: publishing?.connections_with_error ?? 0,
        href: "/publishing/connections",
        cta: "Ver conexiones",
        tone: "critical",
        icon: AlertTriangle,
      },
      {
        label: "Imágenes sin texto alternativo",
        description: "Completa la accesibilidad antes de publicar.",
        count: missingAltText,
        href: "/assets",
        cta: "Completar recursos",
        tone: "info",
        icon: ImageOff,
      },
    ].filter((item) => item.count > 0) as ActionItem[];
  }, [assets, phase3, publishing]);

  const firstName = user?.full_name?.trim().split(/\s+/)[0] || "equipo";
  const hasPrimaryData = Boolean(summary && phase3);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Resumen ejecutivo"
        title={`Bienvenido, ${firstName}`}
        description={
          <>
            Controla el rendimiento, las prioridades y la operación de{" "}
            <span className="font-medium text-foreground">
              {currentOrg?.name ?? "tu organización"}
            </span>{" "}
            desde un solo lugar.
          </>
        }
        metadata={
          <>
            {currentOrg && <Badge variant="outline">{currentOrg.role}</Badge>}
            <span className="text-xs text-muted-foreground">
              {updatedAt
                ? `Actualizado ${updatedAt.toLocaleTimeString("es", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}`
                : "Sincronizando datos"}
            </span>
          </>
        }
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void load()}
              disabled={loading}
              aria-label="Actualizar dashboard"
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
            <Button asChild size="sm">
              <Link href="/generate">
                <Sparkles className="h-4 w-4" />
                Crear contenido
              </Link>
            </Button>
          </>
        }
      />

      {error && !hasPrimaryData ? (
        <StatePanel
          tone="error"
          title="No pudimos cargar el centro de crecimiento"
          description={error}
          actionLabel="Intentar de nuevo"
          onAction={() => void load()}
        />
      ) : (
        <>
          {error && (
            <div
              role="alert"
              className="flex items-start gap-3 rounded-xl border border-warning/25 bg-warning/8 px-4 py-3 text-sm text-warning"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}. Algunos módulos pueden mostrar información anterior.</span>
            </div>
          )}

          <section className="space-y-4" aria-labelledby="kpi-title">
            <SectionHeader
              title="Indicadores clave"
              description="Estado actual con los datos disponibles; no se muestran comparaciones sin histórico."
            />
            <h2 id="kpi-title" className="sr-only">
              Indicadores clave
            </h2>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
              <MetricCard
                label="Leads nuevos"
                value={phase3?.leads.new_leads ?? "—"}
                helper={`${phase3?.leads.total_leads ?? 0} leads totales`}
                icon={Users}
                tone="info"
                loading={loading}
              />
              <MetricCard
                label="Conversión a calificado"
                value={
                  phase3 ? `${formatPercent(phase3.leads.conversion_qualified_rate)}%` : "—"
                }
                helper={`${phase3?.leads.qualified_leads ?? 0} leads calificados`}
                icon={UserCheck}
                tone="positive"
                loading={loading}
              />
              <MetricCard
                label="Publicados este mes"
                value={phase3?.editorial.published_this_month ?? "—"}
                helper={`${phase3?.editorial.scheduled_this_week ?? 0} programados esta semana`}
                icon={Send}
                tone="neutral"
                loading={loading}
              />
              <MetricCard
                label="Éxito de publicación"
                value={publishing ? `${formatPercent(publishing.success_rate)}%` : "—"}
                helper={`${publishing?.failed ?? 0} publicaciones fallidas`}
                icon={TrendingUp}
                tone={publishing?.failed ? "warning" : "positive"}
                loading={loading}
              />
              <MetricCard
                label="Clics totales"
                value={summary?.clicks_total ?? "—"}
                helper={`${summary?.active_links ?? 0} enlaces activos`}
                icon={MousePointerClick}
                tone="neutral"
                loading={loading}
              />
            </div>
          </section>

          <section className="space-y-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              Operación editorial
            </p>
            <SectionHeader
              title="Centro de acción"
              description="Prioridades operativas que requieren una decisión o corrección."
            />
            <Card className="overflow-hidden bg-card/85 shadow-none">
              <CardContent className="p-0">
                {loading ? (
                  <div className="p-5">
                    <LoadingSkeleton rows={3} />
                  </div>
                ) : actions.length === 0 ? (
                  <StatePanel
                    compact
                    icon={CheckCircle2}
                    title="Todo bajo control"
                    description="No hay revisiones, fallos de publicación ni alertas de recursos pendientes."
                    className="m-4"
                  />
                ) : (
                  <ul className="divide-y divide-border">
                    {actions.map((action) => {
                      const Icon = action.icon;
                      return (
                        <li
                          key={action.label}
                          className="group flex flex-col gap-4 p-4 transition-colors hover:bg-interactive/45 sm:flex-row sm:items-center"
                        >
                          <div className="flex min-w-0 flex-1 items-start gap-3">
                            <span
                              className={cn(
                                "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                                ACTION_TONES[action.tone],
                              )}
                            >
                              <Icon className="h-4 w-4" />
                            </span>
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <p className="font-medium text-foreground">{action.label}</p>
                                <Badge
                                  variant={action.tone === "critical" ? "destructive" : "warning"}
                                >
                                  {action.count}
                                </Badge>
                              </div>
                              <p className="mt-1 text-sm text-muted-foreground">
                                {action.description}
                              </p>
                            </div>
                          </div>
                          <Button asChild variant="ghost" size="sm" className="self-start sm:self-auto">
                            <Link href={action.href}>
                              {action.cta}
                              <ArrowRight className="h-4 w-4" />
                            </Link>
                          </Button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </CardContent>
            </Card>
          </section>

          <section className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
            <Card className="bg-card/85 shadow-none">
              <CardHeader className="flex-row items-start justify-between space-y-0">
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    Conversión
                  </p>
                  <CardTitle className="text-base font-semibold text-foreground">
                    Funnel de conversión
                  </CardTitle>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Del tráfico capturado a leads ganados.
                  </p>
                </div>
                <Target className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                {loading ? (
                  <LoadingSkeleton rows={4} />
                ) : (
                  <Funnel
                    clicks={summary?.clicks_total ?? 0}
                    leads={phase3?.leads.total_leads ?? 0}
                    qualified={phase3?.leads.qualified_leads ?? 0}
                    won={phase3?.leads.won_leads ?? 0}
                  />
                )}
              </CardContent>
            </Card>

            <Card className="bg-card/85 shadow-none">
              <CardHeader className="flex-row items-start justify-between space-y-0">
                <div>
                  <CardTitle className="text-base font-semibold text-foreground">
                    Distribución por plataforma
                  </CardTitle>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Publicaciones registradas por canal.
                  </p>
                </div>
                <Send className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                {loading ? (
                  <LoadingSkeleton rows={4} />
                ) : (
                  <PlatformBreakdown data={publishing?.by_platform ?? {}} />
                )}
              </CardContent>
            </Card>
          </section>

          <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <Card className="bg-card/85 shadow-none">
              <CardHeader className="flex-row items-end justify-between space-y-0">
                <div>
                  <CardTitle className="text-base font-semibold text-foreground">
                    Próximas publicaciones
                  </CardTitle>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Contenidos que ya tienen fecha en el calendario.
                  </p>
                </div>
                <Button asChild variant="ghost" size="sm">
                  <Link href="/calendar">
                    Ver calendario
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <LoadingSkeleton rows={4} />
                ) : !phase3?.editorial.upcoming.length ? (
                  <StatePanel
                    compact
                    icon={CalendarClock}
                    title="Sin contenidos programados"
                    description="Crea o programa contenido para verlo aquí."
                  />
                ) : (
                  <ul className="divide-y divide-border">
                    {phase3.editorial.upcoming.slice(0, 5).map((item) => (
                      <li
                        key={item.id}
                        className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div className="flex min-w-0 items-center gap-3">
                          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-interactive text-muted-foreground">
                            <CalendarClock className="h-4 w-4" />
                          </span>
                          <div>
                            <p className="text-sm font-medium text-foreground">
                              {humanize(item.platform)}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {item.scheduled_for
                                ? new Date(item.scheduled_for).toLocaleString("es", {
                                    dateStyle: "medium",
                                    timeStyle: "short",
                                  })
                                : "Sin fecha confirmada"}
                            </p>
                          </div>
                        </div>
                        <Badge variant="secondary">{humanize(item.status)}</Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card className="bg-card/85 shadow-none">
              <CardHeader>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Producción asistida
                </p>
                <CardTitle className="text-base font-semibold text-foreground">
                  Salud de producción
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  IA, recursos y automatización en el periodo disponible.
                </p>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                <HealthStat
                  icon={Bot}
                  label="Generados esta semana"
                  value={countThisWeek(aiJobs)}
                />
                <HealthStat
                  icon={Sparkles}
                  label="IA convertida a contenido"
                  value={`${generationConversion(aiJobs)}%`}
                />
                <HealthStat
                  icon={CheckCircle2}
                  label="Recursos listos"
                  value={assets.filter((asset) => asset.status === "READY").length}
                />
                <HealthStat
                  icon={Zap}
                  label="Automatizaciones activas"
                  value={automation?.active_rules ?? 0}
                />
              </CardContent>
            </Card>
          </section>

          <section className="space-y-4">
            <SectionHeader
              title="Rendimiento destacado"
              description="Entidades con mayor captación de leads en los datos actuales."
              action={
                <Button asChild variant="ghost" size="sm">
                  <Link href="/campaigns">
                    Ver campañas
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              }
            />
            <div className="grid gap-4 lg:grid-cols-2">
              <RankingCard
                title="Campañas por leads"
                rows={(phase3?.leads.top_campaigns ?? []).slice(0, 5).map((campaign) => ({
                  id: campaign.campaign_id,
                  label: campaign.campaign_name,
                  value: campaign.leads,
                }))}
              />
              <RankingCard
                title="Contenidos por leads"
                rows={(phase3?.leads.top_contents ?? []).slice(0, 5).map((content) => ({
                  id: content.content_id,
                  label: content.content_title,
                  value: content.leads,
                }))}
              />
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Funnel({
  clicks,
  leads,
  qualified,
  won,
}: {
  clicks: number;
  leads: number;
  qualified: number;
  won: number;
}) {
  const steps = [
    { label: "Clics", value: clicks, color: "bg-info" },
    { label: "Leads", value: leads, color: "bg-primary" },
    { label: "Calificados", value: qualified, color: "bg-success" },
    { label: "Ganados", value: won, color: "bg-lime" },
  ];
  const max = Math.max(clicks, leads, qualified, won, 1);

  return (
    <ol className="space-y-4">
      {steps.map((step, index) => (
        <li key={step.label}>
          <div className="mb-2 flex items-center justify-between gap-4 text-sm">
            <span className="text-muted-foreground">
              <span className="mr-2 text-xs tabular-nums text-muted-foreground/60">0{index + 1}</span>
              {step.label}
            </span>
            <span className="metric-numbers font-semibold text-foreground">{step.value}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-interactive">
            <div
              className={cn("h-full min-w-0 rounded-full transition-[width] duration-500", step.color)}
              style={{ width: `${safePercent(step.value, max)}%` }}
            />
          </div>
        </li>
      ))}
    </ol>
  );
}

function PlatformBreakdown({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).sort(([, a], [, b]) => b - a);
  const max = Math.max(...entries.map(([, value]) => value), 1);

  if (entries.length === 0) {
    return (
      <StatePanel
        compact
        icon={Send}
        title="Sin publicaciones registradas"
        description="La distribución aparecerá cuando existan publicaciones."
      />
    );
  }

  return (
    <ul className="space-y-4">
      {entries.slice(0, 6).map(([platform, value]) => (
        <li key={platform}>
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{humanize(platform)}</span>
            <span className="metric-numbers font-medium text-foreground">{value}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-interactive">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${safePercent(value, max)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

function HealthStat({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number | string;
}) {
  return (
    <div className="rounded-xl border border-border bg-interactive/35 p-4">
      <Icon className="h-4 w-4 text-primary" />
      <p className="mt-4 text-xs leading-5 text-muted-foreground">{label}</p>
      <p className="metric-numbers mt-1 text-xl font-semibold tracking-[-0.03em] text-foreground">
        {value}
      </p>
    </div>
  );
}

function RankingCard({
  title,
  rows,
}: {
  title: string;
  rows: Array<{ id: string; label: string; value: number }>;
}) {
  return (
    <Card className="bg-card/85 shadow-none">
      <CardHeader>
        <CardTitle className="text-sm font-semibold text-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <StatePanel
            compact
            icon={Target}
            title="Todavía no hay datos"
            description="Los resultados aparecerán cuando se atribuyan leads."
          />
        ) : (
          <ol className="divide-y divide-border">
            {rows.map((row, index) => (
              <li key={row.id} className="flex items-center gap-3 py-3">
                <span className="metric-numbers flex h-7 w-7 items-center justify-center rounded-lg bg-interactive text-xs text-muted-foreground">
                  {index + 1}
                </span>
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
                  {row.label}
                </span>
                <span className="metric-numbers text-sm text-muted-foreground">
                  {row.value} leads
                </span>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}

function safePercent(value: number, total: number) {
  if (total <= 0) return 0;
  return Math.min(100, Math.max(0, (value / total) * 100));
}

function formatPercent(value: number) {
  return new Intl.NumberFormat("es", { maximumFractionDigits: 1 }).format(value);
}

function humanize(value: string) {
  return value
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^\p{L}/u, (letter) => letter.toUpperCase());
}

function countThisWeek(jobs: GenerationJob[]) {
  const now = new Date();
  const start = new Date(now);
  start.setDate(now.getDate() - now.getDay());
  start.setHours(0, 0, 0, 0);
  return jobs.filter((job) => new Date(job.created_at) >= start).length;
}

function generationConversion(jobs: GenerationJob[]) {
  const completed = jobs.filter((job) => job.status === "COMPLETED");
  if (completed.length === 0) return "0.0";
  const converted = completed.filter((job) => job.content_item_id).length;
  return ((converted / completed.length) * 100).toFixed(1);
}
