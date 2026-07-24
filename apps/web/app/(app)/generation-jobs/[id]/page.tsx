"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import type { CouncilDecisionResult, GenerationJob } from "@rqt21/contracts";
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

const DECISION_STYLES: Record<string, string> = {
  APPROVED: "bg-emerald-50 text-emerald-800 border-emerald-200",
  NEEDS_REVISION: "bg-amber-50 text-amber-800 border-amber-200",
  REJECTED: "bg-red-50 text-red-800 border-red-200",
  BLOCKED: "bg-red-100 text-red-900 border-red-300",
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

  const load = useCallback(async () => {
    if (!currentOrgId || !jobId) return;
    setLoading(true);
    setError(null);
    try {
      const j = await api.getGenerationJob(currentOrgId, jobId);
      setJob(j);
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

  if (!currentOrgId) return <p>Selecciona una organización.</p>;
  if (loading && !job) return <p className="text-sm text-slate-500">Cargando…</p>;
  if (!job) return <p className="text-sm text-slate-500">Generación no encontrada.</p>;

  const out = job.output_payload;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">
          {job.generation_type} · {STATUS_LABELS[job.status]}
        </h1>
        <p className="text-sm text-slate-500">
          Proveedor {job.provider} · Modelo {job.model} · {formatDate(job.created_at)}
        </p>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      {job.status === "FAILED" && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-800">
          <p>
            <strong>{job.error_code}</strong>: {job.error_message}
          </p>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-xs text-slate-500">Tokens entrada</div>
          <div className="text-lg font-semibold text-slate-900">{job.input_tokens ?? "—"}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-xs text-slate-500">Tokens salida</div>
          <div className="text-lg font-semibold text-slate-900">{job.output_tokens ?? "—"}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-xs text-slate-500">Costo estimado</div>
          <div className="text-lg font-semibold text-slate-900">
            {job.visibility === "restricted" ? "No autorizado" : job.estimated_cost ?? "—"}
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-xs text-slate-500">Versión de prompt</div>
          <div className="text-sm font-medium text-slate-900">{job.prompt_version}</div>
        </div>
      </div>

      {out && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2">
          <h2 className="text-lg font-medium text-slate-900">Resultado</h2>
          <p className="font-medium text-slate-900">{out.title}</p>
          {out.hook && <p className="text-sm text-slate-700">Hook: {out.hook}</p>}
          {out.script && <p className="text-sm text-slate-700 whitespace-pre-wrap">{out.script}</p>}
          {out.caption && <p className="text-sm text-slate-700">Caption: {out.caption}</p>}
          {out.cta && <p className="text-sm text-slate-700">CTA: {out.cta}</p>}
          {out.hashtags?.length > 0 && (
            <p className="text-xs text-slate-500">{out.hashtags.join(" ")}</p>
          )}
        </div>
      )}

      {canAct && (
        <div className="flex flex-wrap gap-2">
          {job.status === "FAILED" && (
            <button
              type="button"
              onClick={() => void retry()}
              disabled={busy}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-60"
            >
              Regenerar
            </button>
          )}
          {(job.status === "QUEUED" || job.status === "RUNNING") && (
            <button
              type="button"
              onClick={() => void cancel()}
              disabled={busy}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-60"
            >
              Cancelar
            </button>
          )}
          {job.status === "COMPLETED" && !council && (
            <button
              type="button"
              onClick={() => void runCouncil()}
              disabled={busy}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-60"
            >
              Ejecutar Consejo de revisión
            </button>
          )}
          {job.status === "COMPLETED" && !job.content_item_id && (
            <button
              type="button"
              onClick={() => void createContent()}
              disabled={busy}
              className="rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-fg disabled:opacity-60"
            >
              Crear contenido
            </button>
          )}
          {job.content_item_id && (
            <span className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm text-emerald-800">
              Ya convertido a contenido — envíalo a revisión desde /content
            </span>
          )}
        </div>
      )}

      {council && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-slate-900">Consejo de revisión</h2>
            <span
              className={`rounded-full border px-3 py-1 text-xs font-medium ${
                DECISION_STYLES[council.decision] ?? ""
              }`}
            >
              {council.decision} · {council.score}/100
            </span>
          </div>

          {council.blocking_issues.length > 0 && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
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
              <div key={r.id} className="rounded-md border border-slate-200 p-3 text-sm">
                <div className="flex justify-between">
                  <span className="font-medium text-slate-900">{r.reviewer_type}</span>
                  <span className="text-slate-500">{r.score}/100</span>
                </div>
                <p className="mt-1 text-xs text-slate-500">{r.summary}</p>
                {r.issues.length > 0 && (
                  <ul className="mt-1 list-disc pl-4 text-xs text-slate-700">
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
              <h3 className="text-sm font-medium text-slate-900">Recomendaciones</h3>
              <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
                {council.recommendations.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          <p className="text-xs text-slate-500">
            El Consejo recomienda; la aprobación final siempre requiere una acción
            humana explícita (OWNER o ADMIN) desde la bandeja de revisiones.
          </p>
        </div>
      )}
    </div>
  );
}
