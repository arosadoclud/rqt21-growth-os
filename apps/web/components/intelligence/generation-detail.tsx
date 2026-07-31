"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  CheckCircle2,
  FileText,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  StopCircle,
} from "lucide-react";
import type { CouncilDecisionResult, GenerationJob } from "@rqt21/contracts";

import { ConfirmationDialog } from "@/components/design-system/confirmation-dialog";
import { MetricCard } from "@/components/design-system/metric-card";
import { PageHeader } from "@/components/design-system/page-header";
import { SectionHeader } from "@/components/design-system/section-header";
import { StatusBadge } from "@/components/design-system/status-badge";
import { LoadingSkeleton, StatePanel } from "@/components/design-system/state-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";
import { cn } from "@/lib/utils";

import {
  AI_PROVIDER_LABELS,
  COUNCIL_DECISION_LABELS,
  COUNCIL_DECISION_TONES,
  COUNCIL_REVIEWER_LABELS,
  formatCost,
  formatIntelligenceDate,
  GENERATION_STATUS_LABELS,
  GENERATION_STATUS_TONES,
  GENERATION_TYPE_LABELS,
} from "./intelligence-config";

// Single-post outputs go straight into the editorial pipeline the moment
// the job finishes — nothing left for a human to add before review. The
// exploratory/batch types (ideas, blog outline, CTA variations, email)
// stay manual since "convert this one idea from a list into a single
// publishable post" is a judgment call, not something to auto-decide.
const AUTO_CONVERT_TYPES = new Set(["SOCIAL_POST", "REEL_SCRIPT", "STORY"]);

export function GenerationDetail() {
  const params = useParams<{ id: string }>();
  const jobId = params.id;
  const router = useRouter();
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canAct = canWriteGrowth(organization?.role);
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [council, setCouncil] = useState<CouncilDecisionResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [mediaUrl, setMediaUrl] = useState<string | null>(null);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [autoSubmitted, setAutoSubmitted] = useState(false);
  const autoConvertAttempted = useRef(false);

  const load = useCallback(async () => {
    if (!currentOrgId || !jobId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.getGenerationJob(currentOrgId, jobId);
      setJob(result);
      setMediaUrl(null);
      if (
        ["IMAGE_ASSET", "VIDEO_ASSET", "VOICE_OVER"].includes(result.generation_type) &&
        result.output_payload?.asset_id
      ) {
        try {
          const signed = await api.assetDownloadUrl(
            currentOrgId,
            result.output_payload.asset_id,
          );
          setMediaUrl(signed.url);
        } catch {
          setMediaUrl(null);
        }
      }
      try {
        setCouncil(await api.getCouncil(currentOrgId, jobId));
      } catch (councilError) {
        if (councilError instanceof ApiError && councilError.status === 404) {
          setCouncil(null);
        } else {
          throw councilError;
        }
      }
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar esta generación.",
      );
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!job || !(job.status === "QUEUED" || job.status === "RUNNING")) {
      return;
    }

    const interval = window.setInterval(() => {
      void load();
    }, 3000);

    return () => window.clearInterval(interval);
  }, [job, load]);

  useEffect(() => {
    if (
      !currentOrgId ||
      !job ||
      autoConvertAttempted.current ||
      job.status !== "COMPLETED" ||
      job.content_item_id ||
      !AUTO_CONVERT_TYPES.has(job.generation_type) ||
      !canWriteGrowth(organization?.role)
    ) {
      return;
    }
    autoConvertAttempted.current = true;
    void (async () => {
      try {
        await api.createContentFromJob(currentOrgId, jobId, {});
        setAutoSubmitted(true);
        await load();
      } catch {
        // Leave the manual "Crear contenido" button as a fallback if the
        // automatic conversion fails for any reason (e.g. a transient
        // network error) — the user isn't blocked either way.
      }
    })();
  }, [currentOrgId, job, jobId, load, organization?.role]);

  const runCouncil = async () => {
    if (!currentOrgId) return;
    setBusy(true);
    setError(null);
    try {
      setCouncil(await api.runCouncil(currentOrgId, jobId));
    } catch (actionError) {
      setError(
        actionError instanceof ApiError
          ? actionError.detail
          : "No pudimos ejecutar el Consejo de revisión.",
      );
    } finally {
      setBusy(false);
    }
  };

  const retry = async () => {
    if (!currentOrgId) return;
    setBusy(true);
    setError(null);
    try {
      const retried = await api.retryGenerationJob(currentOrgId, jobId);
      router.push(`/generation-jobs/${retried.id}`);
    } catch (actionError) {
      setError(
        actionError instanceof ApiError
          ? actionError.detail
          : "No pudimos reintentar la generación.",
      );
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    if (!currentOrgId) return;
    setBusy(true);
    setError(null);
    try {
      await api.cancelGenerationJob(currentOrgId, jobId);
      setConfirmCancel(false);
      await load();
    } catch (actionError) {
      setError(
        actionError instanceof ApiError
          ? actionError.detail
          : "No pudimos cancelar la generación.",
      );
    } finally {
      setBusy(false);
    }
  };

  const createContent = async () => {
    if (!currentOrgId) return;
    setBusy(true);
    setError(null);
    try {
      await api.createContentFromJob(currentOrgId, jobId, {});
      router.push("/content");
    } catch (actionError) {
      setError(
        actionError instanceof ApiError
          ? actionError.detail
          : "No pudimos crear el contenido.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (!currentOrgId) {
    return (
      <StatePanel
        icon={Bot}
        title="Selecciona una organización"
        description="El resultado aparecerá cuando elijas una organización."
      />
    );
  }

  if (loading && !job) return <LoadingSkeleton rows={7} />;

  if (!job) {
    return (
      <StatePanel
        icon={Bot}
        title="Generación no encontrada"
        description={error ?? "Este resultado no existe o no está disponible para tu organización."}
        actionLabel="Volver al historial"
        onAction={() => router.push("/generation-jobs")}
      />
    );
  }

  const totalTokens = (job.input_tokens ?? 0) + (job.output_tokens ?? 0);
  const output = job.output_payload;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Resultado asistido"
        title={GENERATION_TYPE_LABELS[job.generation_type]}
        description={`Creada ${formatIntelligenceDate(job.created_at)} con ${AI_PROVIDER_LABELS[job.provider]}. Revisa el resultado antes de convertirlo en contenido.`}
        metadata={
          <>
            <StatusBadge
              label={GENERATION_STATUS_LABELS[job.status]}
              tone={GENERATION_STATUS_TONES[job.status]}
            />
            <span className="text-xs text-muted-foreground">
              Modelo {job.model} · prompt {job.prompt_version}
            </span>
          </>
        }
        actions={
          <>
            <Button asChild variant="outline" size="sm">
              <Link href="/generation-jobs">
                <ArrowLeft className="h-4 w-4" />
                Historial
              </Link>
            </Button>
            <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
          </>
        }
      />

      {error && <InlineError>{error}</InlineError>}
      {job.status === "FAILED" && (
        <div className="rounded-xl border border-destructive/25 bg-destructive/5 p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
            <div>
              <p className="text-sm font-semibold text-destructive">La generación no terminó</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {job.error_message || "El proveedor devolvió un error sin descripción."}
              </p>
              {job.error_code && (
                <p className="mt-2 font-mono text-xs text-muted-foreground">
                  Referencia técnica: {job.error_code}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Consumo de la generación">
        <MetricCard
          label="Tokens procesados"
          value={totalTokens || "Sin datos"}
          helper={`${job.input_tokens ?? 0} entrada · ${job.output_tokens ?? 0} salida`}
          icon={Sparkles}
          tone="info"
        />
        <MetricCard
          label="Costo estimado"
          value={
            job.visibility === "restricted"
              ? "Restringido"
              : formatCost(job.estimated_cost)
          }
          helper={
            job.visibility === "restricted"
              ? "Visible solo para administración"
              : "Estimación del proveedor"
          }
          icon={Bot}
        />
        <MetricCard
          label="Revisión automática"
          value={council ? `${council.score}/100` : "Pendiente"}
          helper={
            council
              ? COUNCIL_DECISION_LABELS[council.decision]
              : "Consejo aún no ejecutado"
          }
          icon={ShieldCheck}
          tone={council?.decision === "APPROVED" ? "positive" : council ? "warning" : "neutral"}
        />
        <MetricCard
          label="Destino editorial"
          value={job.content_item_id ? "Creado" : "Pendiente"}
          helper={
            job.content_item_id
              ? "Disponible en la bandeja editorial"
              : "Aún no convertido en contenido"
          }
          icon={FileText}
          tone={job.content_item_id ? "positive" : "neutral"}
        />
      </section>

      {output ? (
        <ResultCard job={job} mediaUrl={mediaUrl} />
      ) : (
        <StatePanel
          compact
          icon={job.status === "FAILED" ? AlertTriangle : Sparkles}
          title={
            job.status === "FAILED"
              ? "No se produjo un resultado"
              : "La generación todavía está en proceso"
          }
          description={
            job.stage ||
            "Actualiza la página dentro de unos momentos para consultar el resultado."
          }
        />
      )}

      {canAct && (
        <Card className="bg-card/80 shadow-none">
          <CardContent className="p-5 sm:p-6">
            <SectionHeader
              title="Próxima acción"
              description={
                AUTO_CONVERT_TYPES.has(job.generation_type)
                  ? "Este tipo de contenido se envía a revisión automáticamente al terminar de generarse."
                  : "Estas acciones siempre requieren una decisión humana explícita."
              }
            />
            <div className="mt-5 flex flex-wrap gap-2">
              {job.status === "FAILED" && (
                <Button variant="outline" onClick={() => void retry()} disabled={busy}>
                  <RotateCcw className="h-4 w-4" />
                  Regenerar
                </Button>
              )}
              {(job.status === "QUEUED" || job.status === "RUNNING") && (
                <Button
                  variant="outline"
                  onClick={() => setConfirmCancel(true)}
                  disabled={busy}
                >
                  <StopCircle className="h-4 w-4" />
                  Cancelar generación
                </Button>
              )}
              {job.status === "COMPLETED" && !council && (
                <Button variant="outline" onClick={() => void runCouncil()} disabled={busy}>
                  <ShieldCheck className="h-4 w-4" />
                  Ejecutar Consejo de revisión
                </Button>
              )}
              {job.status === "COMPLETED" &&
                !job.content_item_id &&
                !AUTO_CONVERT_TYPES.has(job.generation_type) && (
                  <Button onClick={() => void createContent()} disabled={busy}>
                    <FileText className="h-4 w-4" />
                    Crear contenido
                  </Button>
                )}
              {job.status === "COMPLETED" &&
                !job.content_item_id &&
                AUTO_CONVERT_TYPES.has(job.generation_type) && (
                  <div className="flex items-center gap-2 rounded-lg border border-border bg-interactive/30 px-3 py-2 text-sm text-muted-foreground">
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    Enviando a revisión automáticamente…
                  </div>
                )}
              {job.content_item_id && (
                <div className="flex items-center gap-2 rounded-lg border border-success/20 bg-success/5 px-3 py-2 text-sm text-success">
                  <CheckCircle2 className="h-4 w-4" />
                  {autoSubmitted
                    ? "Enviado a revisión automáticamente — disponible en la bandeja editorial."
                    : "Ya está disponible en la bandeja editorial."}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {council && <CouncilPanel council={council} />}

      <ConfirmationDialog
        open={confirmCancel}
        onOpenChange={setConfirmCancel}
        title="¿Cancelar esta generación?"
        description="El proceso se detendrá y el resultado no podrá recuperarse. Podrás iniciar una nueva generación más adelante."
        confirmLabel="Cancelar generación"
        tone="danger"
        busy={busy}
        onConfirm={() => void cancel()}
      />
    </div>
  );
}

function ResultCard({
  job,
  mediaUrl,
}: {
  job: GenerationJob;
  mediaUrl: string | null;
}) {
  const output = job.output_payload;
  if (!output) return null;
  const isMedia = ["IMAGE_ASSET", "VIDEO_ASSET", "VOICE_OVER"].includes(
    job.generation_type,
  );
  return (
    <Card className="overflow-hidden bg-card/80 shadow-none">
      <CardContent className="p-5 sm:p-6">
        <SectionHeader
          title="Resultado"
          description={
            isMedia
              ? "Vista previa del recurso y su contenido asociado."
              : "Borrador generado para revisión editorial."
          }
          action={
            isMedia ? (
              <Button asChild variant="outline" size="sm">
                <Link href="/assets">Abrir biblioteca</Link>
              </Button>
            ) : undefined
          }
        />
        <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.7fr)]">
          <div className="space-y-4">
            {job.generation_type === "IMAGE_ASSET" && (
              mediaUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={mediaUrl}
                  alt={String(output.prompt ?? output.title ?? "Imagen generada")}
                  className="max-h-[34rem] w-full rounded-xl border border-border object-contain"
                />
              ) : (
                <MediaPlaceholder label="Preparando vista previa de la imagen…" />
              )
            )}
            {job.generation_type === "VIDEO_ASSET" && (
              mediaUrl ? (
                // eslint-disable-next-line jsx-a11y/media-has-caption
                <video
                  src={mediaUrl}
                  controls
                  className="max-h-[34rem] w-full rounded-xl border border-border bg-black"
                />
              ) : (
                <MediaPlaceholder label="Preparando vista previa del video…" />
              )
            )}
            {job.generation_type === "VOICE_OVER" && (
              mediaUrl ? (
                // eslint-disable-next-line jsx-a11y/media-has-caption
                <audio src={mediaUrl} controls className="w-full" />
              ) : (
                <MediaPlaceholder label="Preparando el audio…" />
              )
            )}
            {!isMedia && output.script && (
              <div className="whitespace-pre-wrap rounded-xl border border-border bg-elevated p-5 text-sm leading-7 text-foreground">
                {output.script}
              </div>
            )}
            {!isMedia && !output.script && output.caption && (
              <div className="whitespace-pre-wrap rounded-xl border border-border bg-elevated p-5 text-sm leading-7 text-foreground">
                {output.caption}
              </div>
            )}
          </div>
          <dl className="space-y-4">
            <ResultField label="Título" value={output.title} />
            <ResultField label="Gancho" value={output.hook} />
            {isMedia && <ResultField label="Guion" value={output.script} multiline />}
            <ResultField label="Texto de publicación" value={output.caption} multiline />
            <ResultField label="Llamada a la acción" value={output.cta} />
            {output.prompt && <ResultField label="Instrucción visual" value={output.prompt} multiline />}
            {typeof output.scene_count === "number" && (
              <ResultField label="Escenas generadas" value={String(output.scene_count)} />
            )}
            {output.hashtags && output.hashtags.length > 0 && (
              <div>
                <dt className="text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
                  Etiquetas
                </dt>
                <dd className="mt-2 flex flex-wrap gap-2">
                  {output.hashtags.map((hashtag) => (
                    <span key={hashtag} className="rounded-full bg-interactive px-2.5 py-1 text-xs">
                      {hashtag}
                    </span>
                  ))}
                </dd>
              </div>
            )}
          </dl>
        </div>
      </CardContent>
    </Card>
  );
}

function CouncilPanel({ council }: { council: CouncilDecisionResult }) {
  return (
    <Card className="bg-card/80 shadow-none">
      <CardContent className="p-5 sm:p-6">
        <SectionHeader
          title="Consejo de revisión"
          description="Evaluación asistida para apoyar la decisión editorial; no sustituye la aprobación humana."
          action={
            <StatusBadge
              label={`${COUNCIL_DECISION_LABELS[council.decision]} · ${council.score}/100`}
              tone={COUNCIL_DECISION_TONES[council.decision]}
            />
          }
        />
        {council.blocking_issues.length > 0 && (
          <div className="mt-5 rounded-xl border border-destructive/25 bg-destructive/5 p-4">
            <p className="text-sm font-semibold text-destructive">Bloqueos detectados</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {council.blocking_issues.map((issue) => <li key={issue}>{issue}</li>)}
            </ul>
          </div>
        )}
        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {council.reviews.map((review) => (
            <div key={review.id} className="rounded-xl border border-border bg-elevated p-4">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-semibold text-foreground">
                  {COUNCIL_REVIEWER_LABELS[review.reviewer_type]}
                </p>
                <span className="text-sm font-semibold tabular-nums">{review.score}/100</span>
              </div>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">{review.summary}</p>
              {review.issues.length > 0 && (
                <ul className="mt-3 list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                  {review.issues.map((issue) => <li key={issue}>{issue}</li>)}
                </ul>
              )}
            </div>
          ))}
        </div>
        {council.recommendations.length > 0 && (
          <div className="mt-6">
            <p className="text-sm font-semibold text-foreground">Recomendaciones</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {council.recommendations.map((recommendation) => (
                <li key={recommendation}>{recommendation}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MediaPlaceholder({ label }: { label: string }) {
  return (
    <div className="flex min-h-56 items-center justify-center rounded-xl border border-dashed border-border bg-interactive/25 text-sm text-muted-foreground">
      {label}
    </div>
  );
}

function ResultField({
  label,
  value,
  multiline = false,
}: {
  label: string;
  value?: string | null;
  multiline?: boolean;
}) {
  if (!value) return null;
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </dt>
      <dd className={cn("mt-1.5 text-sm leading-6 text-foreground", multiline && "whitespace-pre-wrap")}>
        {value}
      </dd>
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
