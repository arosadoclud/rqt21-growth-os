"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import type { Publication, PublicationAttempt } from "@rqt21/contracts";
import {
  ArrowLeft,
  CalendarClock,
  Check,
  Copy,
  ExternalLink,
  Loader2,
  Send,
  Trash2,
} from "lucide-react";
import { ConfirmationDialog } from "@/components/design-system/confirmation-dialog";
import { PageHeader } from "@/components/design-system/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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

const STATUS_LABEL: Record<string, string> = {
  DRAFT: "Borrador",
  READY: "Lista para publicar",
  SCHEDULED: "Programada",
  PUBLISHING: "Publicando",
  PUBLISHED: "Publicada",
  FAILED: "Fallida",
  RETRY_SCHEDULED: "Reintento programado",
  CANCELLED: "Cancelada",
  ARCHIVED: "Archivada",
};

const STATUS_VARIANT: Record<
  string,
  "secondary" | "success" | "destructive" | "warning" | "outline"
> = {
  DRAFT: "secondary",
  READY: "outline",
  SCHEDULED: "outline",
  PUBLISHING: "warning",
  PUBLISHED: "success",
  FAILED: "destructive",
  RETRY_SCHEDULED: "warning",
  CANCELLED: "secondary",
  ARCHIVED: "secondary",
};

function toLocalDateTimeValue(date: Date) {
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return localDate.toISOString().slice(0, 19);
}

export default function PublicationDetailPage() {
  const params = useParams<{ id: string }>();
  const pubId = params.id;
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((organization) => organization.id === currentOrgId);
  const canPrepare = canWriteGrowth(org?.role);
  const canAuthorize = canAdmin(org?.role);

  const [publication, setPublication] = useState<Publication | null>(null);
  const [attempts, setAttempts] = useState<PublicationAttempt[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [validation, setValidation] = useState<{
    ok: boolean;
    errors: string[];
    warnings: string[];
  } | null>(null);
  const [showSchedule, setShowSchedule] = useState(false);
  const [scheduledFor, setScheduledFor] = useState("");
  const [showManual, setShowManual] = useState(false);
  const [externalUrl, setExternalUrl] = useState("");
  const [captionCopied, setCaptionCopied] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    if (!currentOrgId || !pubId) return;
    setLoading(true);
    setError(null);
    try {
      const [loadedPublication, loadedAttempts] = await Promise.all([
        api.getPublication(currentOrgId, pubId),
        api.listPublicationAttempts(currentOrgId, pubId),
      ]);
      setPublication(loadedPublication);
      setAttempts(loadedAttempts);
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar la publicación.",
      );
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, pubId]);

  useEffect(() => {
    void load();
  }, [load]);

  const router = useRouter();

  const deletePublication = async () => {
    if (!currentOrgId || !pubId) return;
    setDeleting(true);
    setError(null);
    try {
      await api.deletePublication(currentOrgId, pubId);
      // navigate back to publications list
      router.push("/publishing");
    } catch (delError) {
      setError(delError instanceof ApiError ? delError.detail : "No pudimos eliminar la publicación.");
    } finally {
      setDeleting(false);
      setDeleteOpen(false);
    }
  };

  const validate = async () => {
    if (!currentOrgId || !pubId) return;
    setBusy(true);
    setError(null);
    try {
      setValidation(await api.validatePublication(currentOrgId, pubId));
      await load();
    } catch (validationError) {
      setError(
        validationError instanceof ApiError ? validationError.detail : "No pudimos validar.",
      );
    } finally {
      setBusy(false);
    }
  };

  const schedule = async (event: FormEvent) => {
    event.preventDefault();
    if (!currentOrgId || !pubId || !scheduledFor) return;
    setBusy(true);
    setError(null);
    try {
      await api.schedulePublication(currentOrgId, pubId, {
        scheduled_for: new Date(scheduledFor).toISOString(),
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      });
      setShowSchedule(false);
      await load();
    } catch (scheduleError) {
      setError(
        scheduleError instanceof ApiError ? scheduleError.detail : "No pudimos programar.",
      );
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
    } catch (publishError) {
      setError(
        publishError instanceof ApiError ? publishError.detail : "No pudimos publicar.",
      );
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
    } catch (retryError) {
      setError(
        retryError instanceof ApiError ? retryError.detail : "No pudimos reintentar.",
      );
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
    } catch (cancelError) {
      setError(
        cancelError instanceof ApiError ? cancelError.detail : "No pudimos cancelar.",
      );
    } finally {
      setBusy(false);
    }
  };

  const markManual = async (event: FormEvent) => {
    event.preventDefault();
    if (!currentOrgId || !pubId || !externalUrl.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.markPublicationPublished(currentOrgId, pubId, {
        external_url: externalUrl.trim(),
      });
      setShowManual(false);
      await load();
    } catch (manualError) {
      setError(
        manualError instanceof ApiError
          ? manualError.detail
          : "No pudimos registrar la publicación manual.",
      );
    } finally {
      setBusy(false);
    }
  };

  const copyCaption = async () => {
    if (!publication) return;
    try {
      await navigator.clipboard.writeText(publication.caption);
      setCaptionCopied(true);
      window.setTimeout(() => setCaptionCopied(false), 2000);
    } catch {
      window.prompt("Copia el caption:", publication.caption);
    }
  };

  if (!currentOrgId) {
    return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;
  }

  if (loading && !publication) {
    return (
      <div className="flex min-h-56 items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 size-4 animate-spin" />
        Cargando publicación…
      </div>
    );
  }

  if (!publication) {
    return <p className="text-sm text-muted-foreground">Publicación no encontrada.</p>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Publicación"
        title={`${publication.platform} · ${publication.publication_type} · ${
          STATUS_LABEL[publication.status] ?? publication.status
        } (${publication.status})`}
        description={`Creada ${formatDate(publication.created_at)}`}
        metadata={
          <Badge variant={STATUS_VARIANT[publication.status] ?? "secondary"}>
            {STATUS_LABEL[publication.status] ?? publication.status}
          </Badge>
        }
        actions={
          <Button asChild variant="outline">
            <Link href="/publishing">
              <ArrowLeft />
              Volver
            </Link>
          </Button>
        }
      />

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error}
        </div>
      )}

      {publication.status === "FAILED" && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <strong>{publication.failure_code}</strong>: {publication.failure_message}
        </div>
      )}

      {validation && (
        <div
          className={`rounded-lg border px-4 py-3 text-sm ${
            validation.ok
              ? "border-success/30 bg-success/10 text-success"
              : "border-destructive/30 bg-destructive/10 text-destructive"
          }`}
        >
          {validation.errors.map((validationError) => (
            <p key={validationError}>⚠ {validationError}</p>
          ))}
          {validation.warnings.map((warning) => (
            <p key={warning}>ℹ {warning}</p>
          ))}
          {validation.ok && <p>Validación correcta. Ya puedes programar o publicar.</p>}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Card>
          <CardContent className="space-y-4 p-5">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Caption
              </p>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-foreground">
                {publication.caption || "Esta publicación no tiene caption."}
              </p>
            </div>
            {publication.cta && (
              <p className="text-sm text-muted-foreground">
                <span className="font-medium text-foreground">CTA:</span> {publication.cta}
              </p>
            )}
            {publication.hashtags.length > 0 && (
              <p className="text-sm text-primary">{publication.hashtags.join(" ")}</p>
            )}
            <Button variant="outline" size="sm" onClick={() => void copyCaption()}>
              {captionCopied ? <Check /> : <Copy />}
              {captionCopied ? "Caption copiado" : "Copiar caption"}
            </Button>
          </CardContent>
        </Card>

        <div className="grid gap-3">
          <InfoCard label="Programada para" value={formatDate(publication.scheduled_for)} />
          <InfoCard label="Publicada" value={formatDate(publication.published_at)} />
          <Card>
            <CardContent className="p-4">
              <div className="text-xs text-muted-foreground">URL externa</div>
              <div className="mt-1 truncate text-sm font-medium text-primary">
                {publication.external_url ? (
                  <a href={publication.external_url} target="_blank" rel="noreferrer">
                    {publication.external_url}
                  </a>
                ) : (
                  "—"
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {canPrepare && (
        <Card>
          <CardContent className="space-y-4 p-5">
            <div>
              <h2 className="font-semibold text-foreground">Siguiente acción</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Elige qué hacer con esta publicación según su estado actual.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {(publication.status === "DRAFT" || publication.status === "READY") && (
                <Button variant="outline" onClick={() => void validate()} disabled={busy}>
                  {busy ? <Loader2 className="animate-spin" /> : <Check />}
                  Validar
                </Button>
              )}
              {publication.status === "READY" && (
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowSchedule((current) => !current);
                    setShowManual(false);
                  }}
                  disabled={busy}
                >
                  <CalendarClock />
                  Programar
                </Button>
              )}
              {canAuthorize &&
                (publication.status === "READY" || publication.status === "SCHEDULED") && (
                  <Button onClick={() => void publish()} disabled={busy}>
                    {busy ? <Loader2 className="animate-spin" /> : <Send />}
                    Publicar ahora (automático)
                  </Button>
                )}
              {canAuthorize &&
                (publication.status === "FAILED" ||
                  publication.status === "RETRY_SCHEDULED") && (
                  <Button variant="outline" onClick={() => void retry()} disabled={busy}>
                    Reintentar
                  </Button>
                )}
              {(publication.status === "DRAFT" ||
                publication.status === "READY" ||
                publication.status === "SCHEDULED") && (
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowManual((current) => !current);
                    setShowSchedule(false);
                  }}
                  disabled={busy}
                >
                  <ExternalLink />
                  Marcar publicado manualmente
                </Button>
              )}
              {publication.status !== "PUBLISHED" &&
                publication.status !== "PUBLISHING" &&
                publication.status !== "CANCELLED" && (
                  <>
                    <Button variant="outline" onClick={() => void cancel()} disabled={busy}>
                      Cancelar
                    </Button>
                    {canPrepare && publication.status !== "ARCHIVED" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                        onClick={() => setDeleteOpen(true)}
                        disabled={busy}
                      >
                        <Trash2 className="h-4 w-4" />
                        Eliminar
                      </Button>
                    )}
                  </>
                )}
            </div>

            {showSchedule && (
              <form
                onSubmit={schedule}
                className="rounded-lg border border-primary/20 bg-primary/5 p-4"
              >
                <label className="block text-sm">
                  <span className="font-medium text-foreground">Fecha y hora</span>
                  <Input
                    type="datetime-local"
                    step={1}
                    value={scheduledFor}
                    min={toLocalDateTimeValue(new Date())}
                    onChange={(event) => setScheduledFor(event.target.value)}
                    className="mt-2 max-w-sm"
                    required
                  />
                  <span className="mt-2 block text-xs text-muted-foreground">
                    Zona horaria: {Intl.DateTimeFormat().resolvedOptions().timeZone}
                  </span>
                </label>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button type="submit" disabled={busy || !scheduledFor}>
                    {busy ? <Loader2 className="animate-spin" /> : <CalendarClock />}
                    Confirmar programación
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setShowSchedule(false)}>
                    Cerrar
                  </Button>
                </div>
              </form>
            )}

            {showManual && (
              <form
                onSubmit={markManual}
                className="rounded-lg border border-border bg-muted/20 p-4"
              >
                <label className="block text-sm">
                  <span className="font-medium text-foreground">
                    URL de la publicación externa
                  </span>
                  <Input
                    type="url"
                    value={externalUrl}
                    onChange={(event) => setExternalUrl(event.target.value)}
                    placeholder="https://instagram.com/p/..."
                    className="mt-2"
                    required
                  />
                  <span className="mt-2 block text-xs text-muted-foreground">
                    Publica primero en la red social, pega aquí el enlace y RQT21 registrará el
                    resultado.
                  </span>
                </label>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button type="submit" disabled={busy || !externalUrl.trim()}>
                    {busy ? <Loader2 className="animate-spin" /> : <Check />}
                    Confirmar publicación manual
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setShowManual(false)}>
                    Cerrar
                  </Button>
                </div>
              </form>
            )}
          </CardContent>
        </Card>
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
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    Sin intentos
                  </TableCell>
                </TableRow>
              )}
              {attempts.map((attempt) => (
                <TableRow key={attempt.id}>
                  <TableCell className="text-muted-foreground">
                    {attempt.attempt_number}
                  </TableCell>
                  <TableCell>
                    <Badge variant={ATTEMPT_VARIANT[attempt.status] ?? "secondary"}>
                      {attempt.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{attempt.provider}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {attempt.error_message ?? "—"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(attempt.started_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>
      <ConfirmationDialog
        open={deleteOpen}
        onOpenChange={(open) => {
          if (!open && !deleting) setDeleteOpen(false);
        }}
        title="¿Eliminar esta publicación?"
        description={`Esta acción archivará la publicación y la quitará de la lista activa. Se conservará el historial para auditoría.`}
        confirmLabel="Eliminar publicación"
        tone="danger"
        busy={deleting}
        onConfirm={deletePublication}
      />
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 text-sm font-medium text-foreground">{value}</div>
      </CardContent>
    </Card>
  );
}
