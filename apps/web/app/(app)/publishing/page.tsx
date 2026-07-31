"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type {
  Asset,
  Brand,
  ContentItem,
  Platform,
  Publication,
  PublicationStatus,
  PublicationType,
  PublishingConnection,
  PublishingSummary,
} from "@rqt21/contracts";
import { PLATFORMS, PUBLICATION_TYPES } from "@rqt21/contracts";
import { FileUp, Settings2, Trash2 } from "lucide-react";
import { ConfirmationDialog } from "@/components/design-system/confirmation-dialog";
import { PageHeader } from "@/components/design-system/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth, formatDate } from "@/lib/ui";

const STATUS_VARIANT: Record<PublicationStatus, "secondary" | "success" | "warning" | "destructive" | "outline"> = {
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

// Everything except ARCHIVED — archiving is how this page's "eliminar" works
// (a publication that already went out can't be hard-deleted), so archived
// rows disappear from the default view instead of piling up as clutter.
const VISIBLE_STATUSES: PublicationStatus[] = [
  "DRAFT",
  "READY",
  "SCHEDULED",
  "PUBLISHING",
  "PUBLISHED",
  "FAILED",
  "RETRY_SCHEDULED",
  "CANCELLED",
];

export default function PublishingPage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);

  const [items, setItems] = useState<Publication[]>([]);
  const [summary, setSummary] = useState<PublishingSummary | null>(null);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [contents, setContents] = useState<ContentItem[]>([]);
  const [connections, setConnections] = useState<PublishingConnection[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<PublicationStatus | "">("");
  const [showArchived, setShowArchived] = useState(false);

  const [brandId, setBrandId] = useState("");
  const [contentId, setContentId] = useState("");
  const [connectionId, setConnectionId] = useState("");
  const [assetId, setAssetId] = useState("");
  const [platform, setPlatform] = useState<Platform>("INSTAGRAM");
  const [pubType, setPubType] = useState<PublicationType>("POST");
  const [caption, setCaption] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [archiveTarget, setArchiveTarget] = useState<Publication | null>(null);
  const [archiving, setArchiving] = useState(false);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      const [pubs, sum, bs, cs, conns, as_] = await Promise.all([
        api.listPublications(currentOrgId, params),
        api.publishingSummary(currentOrgId).catch(() => null),
        api.listBrands(currentOrgId),
        api.listContent(currentOrgId),
        api.listConnections(currentOrgId).catch(() => []),
        api.listAssets(currentOrgId, { status: "READY" }).catch(() => []),
      ]);
      setItems(pubs);
      setSummary(sum);
      setBrands(bs);
      setContents(cs);
      setConnections(conns);
      setAssets(as_);
      if (!brandId && bs.length > 0) setBrandId(bs[0].id);
      if (!connectionId && conns.length > 0) setConnectionId(conns[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar publicaciones");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, statusFilter, brandId, connectionId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Only content that's actually ready to go out and doesn't already have a
  // publication tied to it — publishing a fresh idea belongs in "Nueva
  // publicación"; this form exists purely to send already-approved AI/editorial
  // content to a connected account.
  const publishableContent = contents.filter(
    (c) =>
      c.review_status === "APPROVED" &&
      !items.some((p) => p.content_item_id === c.id && p.status !== "ARCHIVED" && p.status !== "CANCELLED"),
  );

  useEffect(() => {
    if (!contentId && publishableContent.length > 0) setContentId(publishableContent[0].id);
  }, [contentId, publishableContent]);

  const visibleItems = items.filter((p) => showArchived || p.status !== "ARCHIVED");

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !brandId || !contentId || !connectionId) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await api.createPublication(currentOrgId, {
        content_item_id: contentId,
        brand_id: brandId,
        publishing_connection_id: connectionId,
        asset_id: assetId || null,
        platform,
        publication_type: pubType,
        caption,
      });
      setCaption("");
      setContentId("");
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Error creando publicación");
    } finally {
      setSubmitting(false);
    }
  };

  const confirmArchive = async () => {
    if (!currentOrgId || !archiveTarget) return;
    setArchiving(true);
    setError(null);
    try {
      await api.deletePublication(currentOrgId, archiveTarget.id);
      setArchiveTarget(null);
      await load();
    } catch (archiveError) {
      setError(
        archiveError instanceof ApiError
          ? archiveError.detail
          : "No pudimos eliminar la publicación.",
      );
    } finally {
      setArchiving(false);
    }
  };

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Distribución"
        title="Publicaciones"
        description="Prepara, programa y supervisa el contenido que sale a tus canales."
        actions={
          <>
            <Button asChild variant="outline">
              <Link href="/publishing/connections">
                <Settings2 />
                Conexiones
              </Link>
            </Button>
            {canWrite && (
              <Button asChild>
                <Link href="/publishing/upload-reel">
                  <FileUp />
                  Nueva publicación
                </Link>
              </Button>
            )}
          </>
        }
      />

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {summary && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <StatCard label="Programadas" value={summary.scheduled} />
          <StatCard label="Publicadas" value={summary.published} />
          <StatCard label="Fallidas" value={summary.failed} />
          <StatCard label="Tasa de éxito" value={`${summary.success_rate}%`} />
          <StatCard label="Próx. 7 días" value={summary.upcoming_7_days} />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as PublicationStatus | "")}
          className="w-56"
        >
          <option value="">Todos los estados</option>
          {VISIBLE_STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
          <option value="ARCHIVED">Archivadas</option>
        </Select>
        {!statusFilter && (
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
              className="size-4 rounded border-border"
            />
            Mostrar eliminadas
          </label>
        )}
      </div>

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Contenido</TableHead>
              <TableHead>Plataforma</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Programada</TableHead>
              <TableHead>Intentos</TableHead>
              {canWrite && <TableHead className="text-right">Acciones</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={canWrite ? 6 : 5} className="text-center text-muted-foreground">Cargando…</TableCell></TableRow>
            )}
            {!loading && visibleItems.length === 0 && (
              <TableRow><TableCell colSpan={canWrite ? 6 : 5} className="text-center text-muted-foreground">Sin publicaciones</TableCell></TableRow>
            )}
            {visibleItems.map((p) => {
              const content = contents.find((c) => c.id === p.content_item_id);
              const canArchive = p.status !== "PUBLISHED" && p.status !== "PUBLISHING" && p.status !== "ARCHIVED";
              return (
                <TableRow key={p.id}>
                  <TableCell>
                    <Link href={`/publishing/${p.id}`} className="text-primary hover:underline">
                      {content?.title ?? p.public_id}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{p.platform}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[p.status]}>{p.status}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(p.scheduled_for)}</TableCell>
                  <TableCell className="text-muted-foreground">{p.attempt_count}</TableCell>
                  {canWrite && (
                    <TableCell className="text-right">
                      {canArchive && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setArchiveTarget(p)}
                          className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                          title="Eliminar — útil para limpiar pruebas o errores"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>

      {canWrite && publishableContent.length > 0 && connections.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle id="prepare-publication-title" className="text-foreground text-lg">
              Enviar contenido ya aprobado a una cuenta
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Para contenido generado con IA o aprobado en Revisiones que todavía no está
              conectado a ninguna cuenta. Si es contenido nuevo, usa &ldquo;Nueva publicación&rdquo;.
            </p>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={onCreate}
              className="space-y-4"
              aria-labelledby="prepare-publication-title"
            >
              <span className="sr-only">Preparar publicación</span>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-sm">
                  <span className="text-muted-foreground">Marca</span>
                  <Select value={brandId} onChange={(e) => setBrandId(e.target.value)} className="mt-1">
                    {brands.map((b) => (<option key={b.id} value={b.id}>{b.name}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Contenido aprobado</span>
                  <Select value={contentId} onChange={(e) => setContentId(e.target.value)} className="mt-1">
                    {publishableContent.map((c) => (<option key={c.id} value={c.id}>{c.title}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Conexión</span>
                  <Select value={connectionId} onChange={(e) => setConnectionId(e.target.value)} className="mt-1">
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>{c.account_name} ({c.provider})</option>
                    ))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Activo (READY)</span>
                  <Select value={assetId} onChange={(e) => setAssetId(e.target.value)} className="mt-1">
                    <option value="">Sin activo</option>
                    {assets.map((a) => (<option key={a.id} value={a.id}>{a.original_filename}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Plataforma</span>
                  <Select value={platform} onChange={(e) => setPlatform(e.target.value as Platform)} className="mt-1">
                    {PLATFORMS.map((p) => (<option key={p} value={p}>{p}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Tipo</span>
                  <Select value={pubType} onChange={(e) => setPubType(e.target.value as PublicationType)} className="mt-1">
                    {PUBLICATION_TYPES.map((t) => (<option key={t} value={t}>{t}</option>))}
                  </Select>
                </label>
                <label className="block text-sm sm:col-span-2">
                  <span className="text-muted-foreground">Caption</span>
                  <Textarea value={caption} onChange={(e) => setCaption(e.target.value)} className="mt-1" />
                </label>
              </div>
              {formError && (
                <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </div>
              )}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Guardando…" : "Crear borrador"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <ConfirmationDialog
        open={archiveTarget !== null}
        onOpenChange={(open) => !open && setArchiveTarget(null)}
        title="Eliminar publicación"
        description="Se archivará y dejará de aparecer en la lista. Cualquier reintento programado se cancela. Esta acción no se puede deshacer."
        confirmLabel="Eliminar"
        tone="danger"
        busy={archiving}
        onConfirm={confirmArchive}
      />
    </div>
  );
}

function StatCard({ label, value }: { label: string; value?: number | string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-sm text-muted-foreground">{label}</div>
        <div className="mt-1 text-2xl font-semibold tracking-tight">
          {value === undefined || value === null ? "—" : value}
        </div>
      </CardContent>
    </Card>
  );
}
