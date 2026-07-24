"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import type { Publication, PublicationAttempt } from "@rqt21/contracts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canAdmin, canWriteGrowth, formatDate } from "@/lib/ui";

const ATTEMPT_STYLES: Record<string, string> = {
  STARTED: "bg-slate-100 text-slate-700 border-slate-200",
  SUCCEEDED: "bg-emerald-50 text-emerald-800 border-emerald-200",
  FAILED: "bg-red-50 text-red-800 border-red-200",
  RATE_LIMITED: "bg-amber-50 text-amber-800 border-amber-200",
  CANCELLED: "bg-slate-100 text-slate-500 border-slate-200",
};

export default function PublicationDetailPage() {
  const params = useParams<{ id: string }>();
  const pubId = params.id;
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canPrepare = canWriteGrowth(org?.role);
  const canAuthorize = canAdmin(org?.role);

  const [pub, setPub] = useState<Publication | null>(null);
  const [attempts, setAttempts] = useState<PublicationAttempt[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [validation, setValidation] = useState<{ ok: boolean; errors: string[]; warnings: string[] } | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId || !pubId) return;
    setLoading(true);
    setError(null);
    try {
      const [p, a] = await Promise.all([
        api.getPublication(currentOrgId, pubId),
        api.listPublicationAttempts(currentOrgId, pubId),
      ]);
      setPub(p);
      setAttempts(a);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar la publicación");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, pubId]);

  useEffect(() => {
    void load();
  }, [load]);

  const validate = async () => {
    if (!currentOrgId || !pubId) return;
    setBusy(true);
    setError(null);
    try {
      setValidation(await api.validatePublication(currentOrgId, pubId));
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al validar");
    } finally {
      setBusy(false);
    }
  };

  const schedule = async () => {
    if (!currentOrgId || !pubId) return;
    const when = window.prompt("Programar para (ISO, ej. 2026-08-01T15:00:00Z)");
    if (!when) return;
    setBusy(true);
    setError(null);
    try {
      await api.schedulePublication(currentOrgId, pubId, { scheduled_for: when });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al programar");
    } finally {
      setBusy(false);
    }
  };

  const publish = async () => {
    if (!currentOrgId || !pubId) return;
    setBusy(true);
    setError(null);
    try {
      await api.publishPublication(currentOrgId, pubId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al publicar");
    } finally {
      setBusy(false);
    }
  };

  const retry = async () => {
    if (!currentOrgId || !pubId) return;
    setBusy(true);
    setError(null);
    try {
      await api.retryPublication(currentOrgId, pubId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al reintentar");
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    if (!currentOrgId || !pubId) return;
    setBusy(true);
    setError(null);
    try {
      await api.cancelPublication(currentOrgId, pubId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cancelar");
    } finally {
      setBusy(false);
    }
  };

  const markManual = async () => {
    if (!currentOrgId || !pubId) return;
    const url = window.prompt("URL de la publicación (copiar/pegar tras publicar manualmente)");
    if (!url) return;
    setBusy(true);
    setError(null);
    try {
      await api.markPublicationPublished(currentOrgId, pubId, { external_url: url });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al registrar publicación manual");
    } finally {
      setBusy(false);
    }
  };

  const copyCaption = async () => {
    if (!pub) return;
    try {
      await navigator.clipboard.writeText(pub.caption);
    } catch {
      window.prompt("Copia el caption:", pub.caption);
    }
  };

  if (!currentOrgId) return <p>Selecciona una organización.</p>;
  if (loading && !pub) return <p className="text-sm text-slate-500">Cargando…</p>;
  if (!pub) return <p className="text-sm text-slate-500">Publicación no encontrada.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">
          {pub.platform} · {pub.publication_type} · {pub.status}
        </h1>
        <p className="text-sm text-slate-500">Creada {formatDate(pub.created_at)}</p>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      {pub.status === "FAILED" && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-800">
          <strong>{pub.failure_code}</strong>: {pub.failure_message}
        </div>
      )}

      {validation && (
        <div
          className={`rounded-md border px-3 py-3 text-sm ${
            validation.ok
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-red-200 bg-red-50 text-red-800"
          }`}
        >
          {validation.errors.map((e) => (<p key={e}>⚠ {e}</p>))}
          {validation.warnings.map((w) => (<p key={w}>ℹ {w}</p>))}
          {validation.ok && <p>Validación correcta — lista para programar o publicar.</p>}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 text-sm">
        <p className="whitespace-pre-wrap text-slate-800">{pub.caption}</p>
        {pub.cta && <p className="text-slate-600">CTA: {pub.cta}</p>}
        {pub.hashtags.length > 0 && <p className="text-xs text-slate-500">{pub.hashtags.join(" ")}</p>}
        <button type="button" onClick={() => void copyCaption()}
          className="rounded-md border border-slate-300 px-3 py-1 text-xs hover:bg-slate-50">
          Copiar caption
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-xs text-slate-500">Programada para</div>
          <div className="text-sm font-medium text-slate-900">{formatDate(pub.scheduled_for)}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-xs text-slate-500">Publicada</div>
          <div className="text-sm font-medium text-slate-900">{formatDate(pub.published_at)}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-xs text-slate-500">URL externa</div>
          <div className="truncate text-sm font-medium text-brand">
            {pub.external_url ? (
              <a href={pub.external_url} target="_blank" rel="noreferrer">{pub.external_url}</a>
            ) : "—"}
          </div>
        </div>
      </div>

      {canPrepare && (
        <div className="flex flex-wrap gap-2">
          {(pub.status === "DRAFT" || pub.status === "READY") && (
            <button type="button" onClick={() => void validate()} disabled={busy}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-60">
              Validar
            </button>
          )}
          {pub.status === "READY" && (
            <button type="button" onClick={() => void schedule()} disabled={busy}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-60">
              Programar
            </button>
          )}
          {canAuthorize && (pub.status === "READY" || pub.status === "SCHEDULED") && (
            <button type="button" onClick={() => void publish()} disabled={busy}
              className="rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-fg disabled:opacity-60">
              Publicar ahora (automático)
            </button>
          )}
          {canAuthorize && (pub.status === "FAILED" || pub.status === "RETRY_SCHEDULED") && (
            <button type="button" onClick={() => void retry()} disabled={busy}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-60">
              Reintentar
            </button>
          )}
          {(pub.status === "DRAFT" || pub.status === "READY" || pub.status === "SCHEDULED") && (
            <button type="button" onClick={() => void markManual()} disabled={busy}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-60">
              Marcar publicado manualmente
            </button>
          )}
          {pub.status !== "PUBLISHED" && pub.status !== "PUBLISHING" && pub.status !== "CANCELLED" && (
            <button type="button" onClick={() => void cancel()} disabled={busy}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-60">
              Cancelar
            </button>
          )}
        </div>
      )}

      <div className="space-y-3">
        <h2 className="text-lg font-medium text-slate-900">Historial de intentos</h2>
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-500">
              <tr>
                <th className="px-4 py-2 font-medium">#</th>
                <th className="px-4 py-2 font-medium">Estado</th>
                <th className="px-4 py-2 font-medium">Proveedor</th>
                <th className="px-4 py-2 font-medium">Error</th>
                <th className="px-4 py-2 font-medium">Inicio</th>
              </tr>
            </thead>
            <tbody>
              {attempts.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-4 text-center text-slate-400">Sin intentos</td></tr>
              )}
              {attempts.map((a) => (
                <tr key={a.id} className="border-t border-slate-100">
                  <td className="px-4 py-2 text-slate-500">{a.attempt_number}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full border px-2 py-0.5 text-xs ${ATTEMPT_STYLES[a.status] ?? ""}`}>
                      {a.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-600">{a.provider}</td>
                  <td className="px-4 py-2 text-slate-600">{a.error_message ?? "—"}</td>
                  <td className="px-4 py-2 text-slate-500">{formatDate(a.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
