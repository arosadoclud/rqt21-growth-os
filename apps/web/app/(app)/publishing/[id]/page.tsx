"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import type { Publication, PublicationAttempt } from "@rqt21/contracts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canAdmin, canWriteGrowth, formatDate } from "@/lib/ui";

const ATTEMPT_VARIANT: Record<string, "secondary" | "success" | "destructive" | "warning"> = {
  STARTED: "secondary",
  SUCCEEDED: "success",
  FAILED: "destructive",
  RATE_LIMITED: "warning",
  CANCELLED: "secondary",
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

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;
  if (loading && !pub) return <p className="text-sm text-muted-foreground">Cargando…</p>;
  if (!pub) return <p className="text-sm text-muted-foreground">Publicación no encontrada.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {pub.platform} · {pub.publication_type} · {pub.status}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">Creada {formatDate(pub.created_at)}</p>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {pub.status === "FAILED" && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-3 text-sm text-destructive">
          <strong>{pub.failure_code}</strong>: {pub.failure_message}
        </div>
      )}

      {validation && (
        <div
          className={`rounded-md border px-3 py-3 text-sm ${
            validation.ok
              ? "border-success/30 bg-success/10 text-success"
              : "border-destructive/30 bg-destructive/10 text-destructive"
          }`}
        >
          {validation.errors.map((e) => (<p key={e}>⚠ {e}</p>))}
          {validation.warnings.map((w) => (<p key={w}>ℹ {w}</p>))}
          {validation.ok && <p>Validación correcta — lista para programar o publicar.</p>}
        </div>
      )}

      <Card>
        <CardContent className="space-y-2 p-4 text-sm">
          <p className="whitespace-pre-wrap">{pub.caption}</p>
          {pub.cta && <p className="text-muted-foreground">CTA: {pub.cta}</p>}
          {pub.hashtags.length > 0 && <p className="text-xs text-muted-foreground">{pub.hashtags.join(" ")}</p>}
          <Button variant="outline" size="sm" onClick={() => void copyCaption()}>
            Copiar caption
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Programada para</div>
            <div className="text-sm font-medium">{formatDate(pub.scheduled_for)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Publicada</div>
            <div className="text-sm font-medium">{formatDate(pub.published_at)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">URL externa</div>
            <div className="truncate text-sm font-medium text-primary">
              {pub.external_url ? (
                <a href={pub.external_url} target="_blank" rel="noreferrer">{pub.external_url}</a>
              ) : "—"}
            </div>
          </CardContent>
        </Card>
      </div>

      {canPrepare && (
        <div className="flex flex-wrap gap-2">
          {(pub.status === "DRAFT" || pub.status === "READY") && (
            <Button variant="outline" onClick={() => void validate()} disabled={busy}>
              Validar
            </Button>
          )}
          {pub.status === "READY" && (
            <Button variant="outline" onClick={() => void schedule()} disabled={busy}>
              Programar
            </Button>
          )}
          {canAuthorize && (pub.status === "READY" || pub.status === "SCHEDULED") && (
            <Button onClick={() => void publish()} disabled={busy}>
              Publicar ahora (automático)
            </Button>
          )}
          {canAuthorize && (pub.status === "FAILED" || pub.status === "RETRY_SCHEDULED") && (
            <Button variant="outline" onClick={() => void retry()} disabled={busy}>
              Reintentar
            </Button>
          )}
          {(pub.status === "DRAFT" || pub.status === "READY" || pub.status === "SCHEDULED") && (
            <Button variant="outline" onClick={() => void markManual()} disabled={busy}>
              Marcar publicado manualmente
            </Button>
          )}
          {pub.status !== "PUBLISHED" && pub.status !== "PUBLISHING" && pub.status !== "CANCELLED" && (
            <Button variant="outline" onClick={() => void cancel()} disabled={busy}>
              Cancelar
            </Button>
          )}
        </div>
      )}

      <div className="space-y-3">
        <h2 className="text-base font-semibold tracking-tight">Historial de intentos</h2>
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Proveedor</TableHead>
                <TableHead>Error</TableHead>
                <TableHead>Inicio</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {attempts.length === 0 && (
                <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">Sin intentos</TableCell></TableRow>
              )}
              {attempts.map((a) => (
                <TableRow key={a.id}>
                  <TableCell className="text-muted-foreground">{a.attempt_number}</TableCell>
                  <TableCell>
                    <Badge variant={ATTEMPT_VARIANT[a.status] ?? "secondary"}>{a.status}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{a.provider}</TableCell>
                  <TableCell className="text-muted-foreground">{a.error_message ?? "—"}</TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(a.started_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>
    </div>
  );
}
