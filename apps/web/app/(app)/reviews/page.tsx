"use client";

import { useCallback, useEffect, useState } from "react";
import type { ContentItem, Review } from "@rqt21/contracts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth, formatDate } from "@/lib/ui";

export default function ReviewsPage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);
  const canApprove = org?.role === "OWNER" || org?.role === "ADMIN";

  const [contents, setContents] = useState<ContentItem[]>([]);
  const [reviewsBy, setReviewsBy] = useState<Record<string, Review[]>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const cs = await api.listContent(currentOrgId);
      setContents(cs);
      const map: Record<string, Review[]> = {};
      await Promise.all(
        cs.slice(0, 30).map(async (c) => {
          try {
            map[c.id] = await api.listReviews(currentOrgId, c.id);
          } catch {
            map[c.id] = [];
          }
        }),
      );
      setReviewsBy(map);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  const act = async (
    contentId: string,
    action: "submit" | "approve" | "changes" | "reject",
    comment?: string,
  ) => {
    if (!currentOrgId) return;
    setBusy(true);
    setError(null);
    try {
      if (action === "submit") await api.submitForReview(currentOrgId, contentId, comment);
      if (action === "approve") await api.approveContent(currentOrgId, contentId, { comment });
      if (action === "changes") await api.requestChanges(currentOrgId, contentId, { comment });
      if (action === "reject") await api.rejectContent(currentOrgId, contentId, { comment });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error");
    } finally {
      setBusy(false);
    }
  };

  if (!currentOrgId) return <p>Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Bandeja de revisiones</h1>
      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-lg font-medium text-slate-900">Contenidos</h2>
          {loading && <p className="text-sm text-slate-400">Cargando…</p>}
          {!loading && contents.length === 0 && (
            <p className="text-sm text-slate-500">Sin contenidos</p>
          )}
          <ul className="divide-y divide-slate-100">
            {contents.map((c) => {
              const reviews = reviewsBy[c.id] || [];
              return (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(c.id)}
                    className={
                      selected === c.id
                        ? "flex w-full items-center justify-between py-2 text-left text-sm font-medium text-brand"
                        : "flex w-full items-center justify-between py-2 text-left text-sm text-slate-700 hover:text-slate-900"
                    }
                  >
                    <span>{c.title}</span>
                    <span className="text-xs text-slate-400">
                      {reviews.length} revisiones · {c.status}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-lg font-medium text-slate-900">Detalle</h2>
          {!selected && (
            <p className="text-sm text-slate-500">Selecciona un contenido de la izquierda.</p>
          )}
          {selected && (
            <ContentDetail
              content={contents.find((c) => c.id === selected)!}
              reviews={reviewsBy[selected] || []}
              canWrite={canWrite}
              canApprove={canApprove}
              busy={busy}
              onAct={(a, comment) => void act(selected, a, comment)}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function ContentDetail(props: {
  content: ContentItem;
  reviews: Review[];
  canWrite: boolean;
  canApprove: boolean;
  busy: boolean;
  onAct: (a: "submit" | "approve" | "changes" | "reject", comment?: string) => void;
}) {
  const { content, reviews, canWrite, canApprove, busy, onAct } = props;
  const [comment, setComment] = useState("");

  const handle = (a: "submit" | "approve" | "changes" | "reject") => {
    onAct(a, comment.trim() || undefined);
    setComment("");
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm text-slate-500">
          {content.content_type} · {content.platform} · {content.status}
        </p>
        <h3 className="mt-1 text-base font-semibold text-slate-900">{content.title}</h3>
        {content.hook && <p className="mt-1 text-sm text-slate-700">{content.hook}</p>}
        {content.cta && (
          <p className="mt-1 text-xs text-slate-500">
            CTA: <span className="text-slate-700">{content.cta}</span>
          </p>
        )}
      </div>

      {canWrite && (
        <div>
          <label className="block text-sm text-slate-700">Comentario</label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => handle("submit")}
              className="rounded-md border border-slate-300 px-3 py-1 text-xs hover:bg-slate-50 disabled:opacity-60"
            >
              Enviar a revisión
            </button>
            {canApprove && (
              <>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => handle("approve")}
                  className="rounded-md bg-emerald-600 px-3 py-1 text-xs text-white hover:bg-emerald-700 disabled:opacity-60"
                >
                  Aprobar
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => handle("changes")}
                  className="rounded-md bg-amber-500 px-3 py-1 text-xs text-white hover:bg-amber-600 disabled:opacity-60"
                >
                  Solicitar cambios
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => handle("reject")}
                  className="rounded-md bg-red-600 px-3 py-1 text-xs text-white hover:bg-red-700 disabled:opacity-60"
                >
                  Rechazar
                </button>
              </>
            )}
          </div>
          {!canApprove && (
            <p className="mt-2 text-xs text-slate-500">
              Tu rol permite enviar a revisión pero no aprobar.
            </p>
          )}
        </div>
      )}

      <div>
        <h4 className="mb-2 text-sm font-medium text-slate-900">Historial ({reviews.length})</h4>
        {reviews.length === 0 && (
          <p className="text-sm text-slate-500">Sin revisiones todavía.</p>
        )}
        <ol className="space-y-2">
          {reviews.map((r) => (
            <li key={r.id} className="rounded-md border border-slate-200 bg-slate-50 p-2 text-xs">
              <div className="flex justify-between text-slate-500">
                <span>{r.review_type} · <strong>{r.decision}</strong></span>
                <span>{formatDate(r.created_at)}</span>
              </div>
              {r.score !== null && <p>Score: {r.score}</p>}
              {r.comment && <p className="mt-1 text-slate-700">{r.comment}</p>}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
