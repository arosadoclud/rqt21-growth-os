"use client";

import { useCallback, useEffect, useState } from "react";
import type { ContentItem, Review, ReviewStatus } from "@rqt21/contracts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth, formatDate } from "@/lib/ui";

const REVIEW_STATUS_LABEL: Record<ReviewStatus, string> = {
  NOT_SUBMITTED: "Sin enviar",
  IN_REVIEW: "En revisión",
  APPROVED: "Aprobado",
  CHANGES_REQUESTED: "Cambios solicitados",
  REJECTED: "Rechazado",
};

const REVIEW_STATUS_VARIANT: Record<ReviewStatus, "secondary" | "warning" | "success" | "destructive"> = {
  NOT_SUBMITTED: "secondary",
  IN_REVIEW: "warning",
  APPROVED: "success",
  CHANGES_REQUESTED: "warning",
  REJECTED: "destructive",
};

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
      if (err instanceof ApiError && err.status === 409) {
        // Backstop for the exact bug this screen used to have: nothing
        // stopped double-clicking "Enviar a revisión" (or reopening this
        // tab and clicking again) from piling up duplicate submissions.
        // The button itself is now disabled once review_status is
        // IN_REVIEW, but a stale UI (another tab, a slow refresh) could
        // still hit this — refresh so the real state shows immediately.
        setError("Este contenido ya se envió a revisión y está esperando que un OWNER/ADMIN lo revise.");
        await load();
      } else {
        setError(err instanceof ApiError ? err.detail : "Error");
      }
    } finally {
      setBusy(false);
    }
  };

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Bandeja de revisiones</h1>
      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground text-lg">Contenidos</CardTitle>
          </CardHeader>
          <CardContent>
            {loading && <p className="text-sm text-muted-foreground">Cargando…</p>}
            {!loading && contents.length === 0 && (
              <p className="text-sm text-muted-foreground">Sin contenidos</p>
            )}
            <ul className="divide-y divide-border">
              {contents.map((c) => {
                const reviews = reviewsBy[c.id] || [];
                return (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => setSelected(c.id)}
                      className={cn(
                        "flex w-full items-center justify-between py-2 text-left text-sm",
                        selected === c.id ? "font-medium text-primary" : "text-foreground hover:text-primary"
                      )}
                    >
                      <span>{c.title}</span>
                      <span className="text-xs text-muted-foreground">
                        {reviews.length} revisiones · {c.status}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-foreground text-lg">Detalle</CardTitle>
          </CardHeader>
          <CardContent>
            {!selected && (
              <p className="text-sm text-muted-foreground">Selecciona un contenido de la izquierda.</p>
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
          </CardContent>
        </Card>
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

  const alreadyInReview = content.review_status === "IN_REVIEW";

  return (
    <div className="space-y-4">
      <div>
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span>{content.content_type} · {content.platform} · {content.status}</span>
          <Badge variant={REVIEW_STATUS_VARIANT[content.review_status]}>
            {REVIEW_STATUS_LABEL[content.review_status]}
          </Badge>
        </div>
        <h3 className="mt-1 text-base font-semibold">{content.title}</h3>
        {content.hook && <p className="mt-1 text-sm text-muted-foreground">{content.hook}</p>}
        {content.cta && (
          <p className="mt-1 text-xs text-muted-foreground">
            CTA: <span>{content.cta}</span>
          </p>
        )}
      </div>

      {alreadyInReview && (
        <p className="rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
          Ya se envió a revisión y está esperando que un OWNER/ADMIN lo apruebe, pida
          cambios o lo rechace — no hace falta (ni se puede) volver a enviarlo hasta
          entonces. No tenemos un tiempo estimado de respuesta: depende de cuándo lo
          revise esa persona.
        </p>
      )}

      {canWrite && (
        <div>
          <label className="block text-sm text-muted-foreground">Comentario</label>
          <Textarea value={comment} onChange={(e) => setComment(e.target.value)} className="mt-1" />
          <div className="mt-2 flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={busy || alreadyInReview}
              onClick={() => handle("submit")}
              title={alreadyInReview ? "Ya está en revisión — esperá la decisión antes de reenviar" : undefined}
            >
              {alreadyInReview ? "Ya enviado a revisión" : "Enviar a revisión"}
            </Button>
            {canApprove && (
              <>
                <Button
                  size="sm"
                  disabled={busy}
                  onClick={() => handle("approve")}
                  className="bg-success text-success-foreground hover:bg-success/90"
                >
                  Aprobar
                </Button>
                <Button
                  size="sm"
                  disabled={busy}
                  onClick={() => handle("changes")}
                  className="bg-warning text-warning-foreground hover:bg-warning/90"
                >
                  Solicitar cambios
                </Button>
                <Button variant="destructive" size="sm" disabled={busy} onClick={() => handle("reject")}>
                  Rechazar
                </Button>
              </>
            )}
          </div>
          {!canApprove && (
            <p className="mt-2 text-xs text-muted-foreground">
              Tu rol permite enviar a revisión pero no aprobar.
            </p>
          )}
        </div>
      )}

      <div>
        <h4 className="mb-2 text-sm font-medium">Historial ({reviews.length})</h4>
        {reviews.length === 0 && (
          <p className="text-sm text-muted-foreground">Sin revisiones todavía.</p>
        )}
        <ol className="space-y-2">
          {reviews.map((r) => (
            <li key={r.id} className="rounded-md border border-border bg-muted p-2 text-xs">
              <div className="flex justify-between text-muted-foreground">
                <span>{r.review_type} · <strong>{r.decision}</strong></span>
                <span>{formatDate(r.created_at)}</span>
              </div>
              {r.score !== null && <p>Score: {r.score}</p>}
              {r.comment && <p className="mt-1">{r.comment}</p>}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
