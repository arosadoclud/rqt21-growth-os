"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import type { CouncilDecisionResult, GenerationJob } from "@rqt21/contracts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth, formatDate } from "@/lib/ui";

const STATUS_LABELS: Record<string, string> = {
  QUEUED: "En cola",
  RUNNING: "Ejecutando",
  COMPLETED: "Completado",
  FAILED: "Fallido",
  CANCELLED: "Cancelado",
};

const DECISION_VARIANT: Record<string, "success" | "warning" | "destructive"> = {
  APPROVED: "success",
  NEEDS_REVISION: "warning",
  REJECTED: "destructive",
  BLOCKED: "destructive",
};

export default function GenerationJobDetail() {
  const params = useParams<{ id: string }>();
  const jobId = params.id;
  const router = useRouter();
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canAct = canWriteGrowth(org?.role);

  const [job, setJob] = useState<GenerationJob | null>(null);
  const [council, setCouncil] = useState<CouncilDecisionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [imageUrl, setImageUrl] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId || !jobId) return;
    setLoading(true);
    setError(null);
    try {
      const j = await api.getGenerationJob(currentOrgId, jobId);
      setJob(j);
      if (
        (j.generation_type === "IMAGE_ASSET" || j.generation_type === "VIDEO_ASSET") &&
        j.output_payload?.asset_id
      ) {
        try {
          const signed = await api.assetDownloadUrl(currentOrgId, j.output_payload.asset_id as string);
          setImageUrl(signed.url);
        } catch {
          setImageUrl(null);
        }
      }
      try {
        setCouncil(await api.getCouncil(currentOrgId, jobId));
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setCouncil(null);
        } else {
          throw err;
        }
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar la generación");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  const runCouncil = async () => {
    if (!currentOrgId || !jobId) return;
    setBusy(true);
    setError(null);
    try {
      setCouncil(await api.runCouncil(currentOrgId, jobId));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error ejecutando el consejo");
    } finally {
      setBusy(false);
    }
  };

  const retry = async () => {
    if (!currentOrgId || !jobId) return;
    setBusy(true);
    setError(null);
    try {
      const retried = await api.retryGenerationJob(currentOrgId, jobId);
      router.push(`/generation-jobs/${retried.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al reintentar");
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    if (!currentOrgId || !jobId) return;
    setBusy(true);
    setError(null);
    try {
      await api.cancelGenerationJob(currentOrgId, jobId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cancelar");
    } finally {
      setBusy(false);
    }
  };

  const createContent = async () => {
    if (!currentOrgId || !jobId) return;
    setBusy(true);
    setError(null);
    try {
      const content = await api.createContentFromJob(currentOrgId, jobId, {});
      router.push(`/content`);
      void content;
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al crear el contenido");
    } finally {
      setBusy(false);
    }
  };

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;
  if (loading && !job) return <p className="text-sm text-muted-foreground">Cargando…</p>;
  if (!job) return <p className="text-sm text-muted-foreground">Generación no encontrada.</p>;

  const out = job.output_payload;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {job.generation_type} · {STATUS_LABELS[job.status]}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Proveedor {job.provider} · Modelo {job.model} · {formatDate(job.created_at)}
        </p>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {job.status === "FAILED" && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-3 text-sm text-destructive">
          <p>
            <strong>{job.error_code}</strong>: {job.error_message}
          </p>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Tokens entrada</div>
            <div className="text-lg font-semibold">{job.input_tokens ?? "—"}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Tokens salida</div>
            <div className="text-lg font-semibold">{job.output_tokens ?? "—"}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Costo estimado</div>
            <div className="text-lg font-semibold">
              {job.visibility === "restricted" ? "No autorizado" : job.estimated_cost ?? "—"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Versión de prompt</div>
            <div className="text-sm font-medium">{job.prompt_version}</div>
          </CardContent>
        </Card>
      </div>

      {out && job.generation_type === "IMAGE_ASSET" && (
        <Card>
          <CardContent className="space-y-2 p-4">
            <h2 className="text-base font-semibold tracking-tight">Imagen generada</h2>
            {imageUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={imageUrl} alt={String(out.prompt ?? "")} className="max-w-md rounded-lg border border-border" />
            ) : (
              <p className="text-sm text-muted-foreground">Cargando vista previa…</p>
            )}
            <p className="text-sm text-muted-foreground">{String(out.prompt ?? "")}</p>
            <a href={`/assets`} className="inline-block text-sm font-medium text-primary hover:underline">
              Ver en Activos →
            </a>
          </CardContent>
        </Card>
      )}

      {out && job.generation_type === "VIDEO_ASSET" && (
        <Card>
          <CardContent className="space-y-2 p-4">
            <h2 className="text-base font-semibold tracking-tight">Video generado</h2>
            {imageUrl ? (
              // eslint-disable-next-line jsx-a11y/media-has-caption
              <video
                src={imageUrl}
                controls
                className="max-w-xs rounded-lg border border-border"
              />
            ) : (
              <p className="text-sm text-muted-foreground">Cargando vista previa…</p>
            )}
            {out.title && <p className="font-medium">{String(out.title)}</p>}
            {out.script && (
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                Guion / narración: {String(out.script)}
              </p>
            )}
            {out.caption && <p className="text-sm text-muted-foreground">Caption: {String(out.caption)}</p>}
            {out.cta && <p className="text-sm text-muted-foreground">CTA: {String(out.cta)}</p>}
            {Array.isArray(out.hashtags) && out.hashtags.length > 0 && (
              <p className="text-xs text-muted-foreground">{(out.hashtags as string[]).join(" ")}</p>
            )}
            {typeof out.scene_count === "number" && (
              <p className="text-xs text-muted-foreground">{out.scene_count} escenas generadas</p>
            )}
            <a href={`/assets`} className="inline-block text-sm font-medium text-primary hover:underline">
              Ver en Activos →
            </a>
          </CardContent>
        </Card>
      )}

      {out && job.generation_type !== "IMAGE_ASSET" && job.generation_type !== "VIDEO_ASSET" && (
        <Card>
          <CardContent className="space-y-2 p-4">
            <h2 className="text-base font-semibold tracking-tight">Resultado</h2>
            <p className="font-medium">{out.title}</p>
            {out.hook && <p className="text-sm text-muted-foreground">Hook: {out.hook}</p>}
            {out.script && <p className="text-sm text-muted-foreground whitespace-pre-wrap">{out.script}</p>}
            {out.caption && <p className="text-sm text-muted-foreground">Caption: {out.caption}</p>}
            {out.cta && <p className="text-sm text-muted-foreground">CTA: {out.cta}</p>}
            {out.hashtags && out.hashtags.length > 0 && (
              <p className="text-xs text-muted-foreground">{out.hashtags.join(" ")}</p>
            )}
          </CardContent>
        </Card>
      )}

      {canAct && (
        <div className="flex flex-wrap items-center gap-2">
          {job.status === "FAILED" && (
            <Button variant="outline" onClick={() => void retry()} disabled={busy}>
              Regenerar
            </Button>
          )}
          {(job.status === "QUEUED" || job.status === "RUNNING") && (
            <Button variant="outline" onClick={() => void cancel()} disabled={busy}>
              Cancelar
            </Button>
          )}
          {job.status === "COMPLETED" && !council && (
            <Button variant="outline" onClick={() => void runCouncil()} disabled={busy}>
              Ejecutar Consejo de revisión
            </Button>
          )}
          {job.status === "COMPLETED" && !job.content_item_id && (
            <Button onClick={() => void createContent()} disabled={busy}>
              Crear contenido
            </Button>
          )}
          {job.content_item_id && (
            <Badge variant="success" className="px-3 py-1.5">
              Ya convertido a contenido — envíalo a revisión desde /content
            </Badge>
          )}
        </div>
      )}

      {council && (
        <Card>
          <CardContent className="space-y-4 p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold tracking-tight">Consejo de revisión</h2>
              <Badge variant={DECISION_VARIANT[council.decision] ?? "secondary"}>
                {council.decision} · {council.score}/100
              </Badge>
            </div>

            {council.blocking_issues.length > 0 && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                <strong>Bloqueos:</strong>
                <ul className="mt-1 list-disc pl-5">
                  {council.blocking_issues.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="grid gap-3 sm:grid-cols-2">
              {council.reviews.map((r) => (
                <div key={r.id} className="rounded-md border border-border p-3 text-sm">
                  <div className="flex justify-between">
                    <span className="font-medium">{r.reviewer_type}</span>
                    <span className="text-muted-foreground">{r.score}/100</span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{r.summary}</p>
                  {r.issues.length > 0 && (
                    <ul className="mt-1 list-disc pl-4 text-xs text-muted-foreground">
                      {r.issues.map((i) => (
                        <li key={i}>{i}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>

            {council.recommendations.length > 0 && (
              <div>
                <h3 className="text-sm font-medium">Recomendaciones</h3>
                <ul className="mt-1 list-disc pl-5 text-sm text-muted-foreground">
                  {council.recommendations.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              </div>
            )}

            <p className="text-xs text-muted-foreground">
              El Consejo recomienda; la aprobación final siempre requiere una acción
              humana explícita (OWNER o ADMIN) desde la bandeja de revisiones.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
