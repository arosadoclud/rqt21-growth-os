"use client";

import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CalendarClock,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  ExternalLink,
  FilePenLine,
  FileText,
  Inbox,
  Info,
  MessageSquareText,
  Plus,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Trash2,
  XCircle,
} from "lucide-react";
import type {
  Brand,
  Campaign,
  ContentItem,
  ContentType,
  Platform,
  Review,
  ReviewStatus,
} from "@rqt21/contracts";
import {
  CONTENT_TYPES,
  PLATFORMS,
  REVIEW_STATUSES,
} from "@rqt21/contracts";

import { ConfirmationDialog } from "@/components/design-system/confirmation-dialog";
import { Drawer } from "@/components/design-system/drawer";
import { MetricCard } from "@/components/design-system/metric-card";
import { PageHeader } from "@/components/design-system/page-header";
import { StatusBadge } from "@/components/design-system/status-badge";
import { LoadingSkeleton, StatePanel } from "@/components/design-system/state-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";
import { cn } from "@/lib/utils";

import {
  CONTENT_STATUS_LABELS,
  CONTENT_STATUS_TONES,
  CONTENT_TYPE_LABELS,
  formatEditorialDate,
  friendlyReviewError,
  PLATFORM_LABELS,
  REVIEW_DECISION_LABELS,
  REVIEW_DECISION_TONES,
  REVIEW_STATUS_LABELS,
  REVIEW_STATUS_TONES,
  SOURCE_LABELS,
} from "./editorial-config";

type InboxMode = "content" | "reviews";
type ReviewAction = "submit" | "approve" | "changes" | "reject";

export function EditorialInbox({ mode }: { mode: InboxMode }) {
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canWrite = canWriteGrowth(organization?.role);
  const canApprove = organization?.role === "OWNER" || organization?.role === "ADMIN";

  const [contents, setContents] = useState<ContentItem[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [reviewsByContent, setReviewsByContent] = useState<Record<string, Review[]>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [reviewFilter, setReviewFilter] = useState<ReviewStatus | "">("");
  const [platformFilter, setPlatformFilter] = useState<Platform | "">("");
  const [comment, setComment] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ContentItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [contentRows, brandRows, campaignRows] = await Promise.all([
        api.listContent(currentOrgId),
        api.listBrands(currentOrgId),
        api.listCampaigns(currentOrgId),
      ]);
      const reviewMap: Record<string, Review[]> = {};
      await Promise.all(
        contentRows.slice(0, 50).map(async (content) => {
          reviewMap[content.id] = await api.listReviews(currentOrgId, content.id).catch(() => []);
        }),
      );
      setContents(contentRows);
      setBrands(brandRows);
      setCampaigns(campaignRows);
      setReviewsByContent(reviewMap);
      setSelectedId((current) =>
        current && contentRows.some((content) => content.id === current)
          ? current
          : contentRows[0]?.id ?? null,
      );
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar la bandeja editorial.",
      );
    } finally {
      setLoading(false);
    }
  }, [currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredContents = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("es");
    const priority: Record<ReviewStatus, number> = {
      IN_REVIEW: 0,
      CHANGES_REQUESTED: 1,
      NOT_SUBMITTED: 2,
      REJECTED: 3,
      APPROVED: 4,
    };
    return contents
      .filter(
        (content) =>
          (!reviewFilter || content.review_status === reviewFilter) &&
          (!platformFilter || content.platform === platformFilter) &&
          (!query ||
            content.title.toLocaleLowerCase("es").includes(query) ||
            content.hook?.toLocaleLowerCase("es").includes(query) ||
            content.caption?.toLocaleLowerCase("es").includes(query)),
      )
      .sort((first, second) => {
        if (mode === "reviews") {
          const statusOrder = priority[first.review_status] - priority[second.review_status];
          if (statusOrder !== 0) return statusOrder;
        }
        return new Date(second.updated_at).getTime() - new Date(first.updated_at).getTime();
      });
  }, [contents, mode, platformFilter, reviewFilter, search]);

  useEffect(() => {
    if (
      selectedId &&
      filteredContents.some((content) => content.id === selectedId)
    ) {
      return;
    }
    setSelectedId(filteredContents[0]?.id ?? null);
  }, [filteredContents, selectedId]);

  const selected = contents.find((content) => content.id === selectedId) ?? null;
  const selectedReviews = selected ? reviewsByContent[selected.id] ?? [] : [];

  const act = async (action: ReviewAction) => {
    if (!currentOrgId || !selected) return;
    setBusy(true);
    setError(null);
    setSuccess(null);
    const note = comment.trim() || undefined;
    try {
      if (action === "submit") {
        const review = await api.submitForReview(currentOrgId, selected.id, note);
        setSuccess(
          review.comment?.startsWith("Auto-aprobado") ||
            review.comment?.startsWith("Auto-rechazado") ||
            review.comment?.startsWith("Cambios solicitados automáticamente")
            ? review.comment
            : "Contenido enviado a revisión.",
        );
      }
      if (action === "approve") {
        await api.approveContent(currentOrgId, selected.id, { comment: note });
        setSuccess("Contenido aprobado.");
      }
      if (action === "changes") {
        await api.requestChanges(currentOrgId, selected.id, { comment: note });
        setSuccess("Cambios solicitados al equipo editorial.");
      }
      if (action === "reject") {
        await api.rejectContent(currentOrgId, selected.id, { comment: note });
        setSuccess("Contenido rechazado.");
      }
      setComment("");
      await load();
    } catch (actionError) {
      setError(friendlyReviewError(actionError, "No pudimos completar la acción."));
      if (actionError instanceof ApiError && actionError.status === 409) {
        await load();
      }
    } finally {
      setBusy(false);
    }
  };

  const confirmDelete = async () => {
    if (!currentOrgId || !deleteTarget) return;
    setDeleting(true);
    setError(null);
    try {
      await api.deleteContent(currentOrgId, deleteTarget.id);
      setDeleteTarget(null);
      setSuccess("Contenido eliminado.");
      if (selectedId === deleteTarget.id) setSelectedId(null);
      await load();
    } catch (deleteError) {
      setError(
        deleteError instanceof ApiError && deleteError.status === 409
          ? "No se puede eliminar: ya tiene una publicación enviada o publicándose. Archívala primero."
          : friendlyReviewError(deleteError, "No pudimos eliminar el contenido."),
      );
    } finally {
      setDeleting(false);
    }
  };

  const created = async () => {
    setCreateOpen(false);
    setSuccess("Contenido creado y añadido a la bandeja.");
    await load();
  };

  const inReview = contents.filter((content) => content.review_status === "IN_REVIEW").length;
  const changesRequested = contents.filter(
    (content) => content.review_status === "CHANGES_REQUESTED",
  ).length;
  const approved = contents.filter((content) => content.review_status === "APPROVED").length;

  if (!currentOrgId) {
    return (
      <StatePanel
        icon={Inbox}
        title="Selecciona una organización"
        description="La bandeja editorial se mostrará cuando elijas una organización."
      />
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Flujo editorial"
        title={mode === "reviews" ? "Bandeja de revisiones" : "Contenido editorial"}
        description={
          mode === "reviews"
            ? "Revisa el contenido, deja contexto y toma decisiones editoriales desde una sola bandeja."
            : "Explora borradores, revisa su estado y prepara cada pieza antes de enviarla a aprobación."
        }
        metadata={
          <>
            <StatusBadge label={`${contents.length} contenidos`} />
            {!canWrite && <span className="text-xs text-muted-foreground">Modo de solo lectura</span>}
          </>
        }
        actions={
          <>
            <div className="inline-flex rounded-lg border border-border bg-interactive/45 p-1">
              <InboxLink href="/content" active={mode === "content"} label="Contenido" />
              <InboxLink href="/reviews" active={mode === "reviews"} label="Revisiones" />
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void load()}
              disabled={loading}
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
            {mode === "content" && canWrite && (
              <Button
                size="sm"
                onClick={() => setCreateOpen(true)}
                disabled={brands.length === 0}
                title={brands.length === 0 ? "Crea una marca antes de añadir contenido" : undefined}
              >
                <Plus className="h-4 w-4" />
                Nuevo contenido
              </Button>
            )}
          </>
        }
      />

      {(error || success) && (
        <div
          role={error ? "alert" : "status"}
          className={cn(
            "flex items-start gap-3 rounded-xl border px-4 py-3 text-sm",
            error
              ? "border-destructive/25 bg-destructive/8 text-destructive"
              : "border-success/25 bg-success/8 text-success",
          )}
        >
          {error ? (
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          ) : (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          )}
          <span>{error ?? success}</span>
        </div>
      )}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Resumen editorial">
        <MetricCard
          label="Contenido total"
          value={contents.length}
          helper="Piezas disponibles en la bandeja"
          icon={FileText}
          tone="neutral"
          loading={loading}
        />
        <MetricCard
          label="Esperando revisión"
          value={inReview}
          helper="Requieren una decisión"
          icon={Clock3}
          tone="warning"
          loading={loading}
        />
        <MetricCard
          label="Cambios solicitados"
          value={changesRequested}
          helper="Deben volver al equipo"
          icon={FilePenLine}
          tone="warning"
          loading={loading}
        />
        <MetricCard
          label="Aprobados"
          value={approved}
          helper="Listos para programar"
          icon={ShieldCheck}
          tone="positive"
          loading={loading}
        />
      </section>

      <Card className="bg-card/80 shadow-none">
        <CardContent className="p-4">
          <div className="grid gap-3 lg:grid-cols-[minmax(14rem,1fr)_12rem_12rem_auto]">
            <label className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Buscar por título, gancho o texto…"
                className="pl-9"
                aria-label="Buscar contenido"
              />
            </label>
            <Select
              value={reviewFilter}
              onChange={(event) => setReviewFilter(event.target.value as ReviewStatus | "")}
              aria-label="Filtrar por estado de revisión"
            >
              <option value="">Todas las revisiones</option>
              {REVIEW_STATUSES.map((status) => (
                <option key={status} value={status}>{REVIEW_STATUS_LABELS[status]}</option>
              ))}
            </Select>
            <Select
              value={platformFilter}
              onChange={(event) => setPlatformFilter(event.target.value as Platform | "")}
              aria-label="Filtrar por plataforma"
            >
              <option value="">Todas las plataformas</option>
              {PLATFORMS.map((platform) => (
                <option key={platform} value={platform}>{PLATFORM_LABELS[platform]}</option>
              ))}
            </Select>
            {(search || reviewFilter || platformFilter) ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSearch("");
                  setReviewFilter("");
                  setPlatformFilter("");
                }}
              >
                Limpiar filtros
              </Button>
            ) : (
              <span className="flex items-center justify-end text-xs text-muted-foreground">
                {filteredContents.length} visibles
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <Card className="bg-card/80 shadow-none">
          <CardContent className="p-5"><LoadingSkeleton rows={6} /></CardContent>
        </Card>
      ) : filteredContents.length === 0 ? (
        <StatePanel
          icon={Inbox}
          title="No hay contenido con estos filtros"
          description="Prueba otros filtros o crea una nueva pieza editorial."
          actionLabel={search || reviewFilter || platformFilter ? "Limpiar filtros" : undefined}
          onAction={
            search || reviewFilter || platformFilter
              ? () => {
                  setSearch("");
                  setReviewFilter("");
                  setPlatformFilter("");
                }
              : undefined
          }
        />
      ) : (
        <div className="grid min-h-[42rem] overflow-hidden rounded-xl border border-border bg-card/80 xl:grid-cols-[minmax(18rem,0.82fr)_minmax(24rem,1.35fr)_minmax(17rem,0.78fr)]">
          <ContentList
            contents={filteredContents}
            selectedId={selectedId}
            reviewsByContent={reviewsByContent}
            onSelect={setSelectedId}
          />
          <ContentPreview
            content={selected}
            reviews={selectedReviews}
            comment={comment}
            onCommentChange={setComment}
            canWrite={canWrite}
            canApprove={canApprove}
            busy={busy}
            onAction={(action) => void act(action)}
            onDelete={() => setDeleteTarget(selected)}
          />
          <ContentInfo
            content={selected}
            brand={brands.find((brand) => brand.id === selected?.brand_id)}
            campaign={campaigns.find((campaign) => campaign.id === selected?.campaign_id)}
          />
        </div>
      )}

      <CreateContentDrawer
        open={createOpen}
        onOpenChange={setCreateOpen}
        currentOrgId={currentOrgId}
        brands={brands}
        campaigns={campaigns}
        onCreated={created}
      />

      <ConfirmationDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Eliminar contenido"
        description={
          deleteTarget
            ? `"${deleteTarget.title}" se eliminará junto con cualquier borrador de publicación asociado. Esta acción no se puede deshacer.`
            : ""
        }
        confirmLabel="Eliminar"
        tone="danger"
        busy={deleting}
        onConfirm={confirmDelete}
      />
    </div>
  );
}

function ContentList({
  contents,
  selectedId,
  reviewsByContent,
  onSelect,
}: {
  contents: ContentItem[];
  selectedId: string | null;
  reviewsByContent: Record<string, Review[]>;
  onSelect: (id: string) => void;
}) {
  return (
    <aside className="border-b border-border xl:border-b-0 xl:border-r" aria-label="Lista editorial">
      <div className="border-b border-border bg-interactive/30 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          Bandeja
        </p>
      </div>
      <ul className="max-h-[38rem] divide-y divide-border overflow-y-auto xl:max-h-none">
        {contents.map((content) => (
          <li key={content.id}>
            <button
              type="button"
              onClick={() => onSelect(content.id)}
              className={cn(
                "group flex w-full items-start gap-3 px-4 py-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                selectedId === content.id ? "bg-accent/60" : "hover:bg-interactive/45",
              )}
            >
              <span
                className={cn(
                  "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                  selectedId === content.id
                    ? "bg-primary text-primary-foreground"
                    : "bg-interactive text-muted-foreground",
                )}
              >
                <FileText className="h-4 w-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-foreground">
                  {content.title}
                </span>
                <span className="mt-1 flex flex-wrap items-center gap-1.5">
                  <StatusBadge
                    label={REVIEW_STATUS_LABELS[content.review_status]}
                    tone={REVIEW_STATUS_TONES[content.review_status]}
                  />
                  <span className="text-[11px] text-muted-foreground">
                    {reviewsByContent[content.id]?.length ?? 0} eventos
                  </span>
                </span>
              </span>
              <ChevronRight
                className={cn(
                  "mt-2 h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                  selectedId === content.id && "translate-x-0.5 text-primary",
                )}
              />
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}

function ContentPreview({
  content,
  reviews,
  comment,
  onCommentChange,
  canWrite,
  canApprove,
  busy,
  onAction,
  onDelete,
}: {
  content: ContentItem | null;
  reviews: Review[];
  comment: string;
  onCommentChange: (value: string) => void;
  canWrite: boolean;
  canApprove: boolean;
  busy: boolean;
  onAction: (action: ReviewAction) => void;
  onDelete: () => void;
}) {
  if (!content) {
    return (
      <div className="flex items-center justify-center border-b border-border p-6 xl:border-b-0 xl:border-r">
        <StatePanel
          compact
          title="Selecciona un contenido"
          description="La vista previa y sus acciones aparecerán aquí."
        />
      </div>
    );
  }

  const alreadyInReview = content.review_status === "IN_REVIEW";

  return (
    <main className="min-w-0 border-b border-border xl:border-b-0 xl:border-r">
      <div className="border-b border-border px-5 py-5 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge
              label={REVIEW_STATUS_LABELS[content.review_status]}
              tone={REVIEW_STATUS_TONES[content.review_status]}
            />
            <span className="text-xs text-muted-foreground">
              {CONTENT_TYPE_LABELS[content.content_type]} · {PLATFORM_LABELS[content.platform]}
            </span>
          </div>
          {canApprove && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onDelete}
              className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
              title="Eliminar este contenido — útil para limpiar pruebas o errores"
            >
              <Trash2 className="h-4 w-4" />
              Eliminar
            </Button>
          )}
        </div>
        <h2 className="mt-3 text-xl font-semibold tracking-[-0.025em] text-foreground">
          {content.title}
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">{content.public_id}</p>
      </div>

      <div className="space-y-6 px-5 py-6 sm:px-6">
        <PreviewSection label="Gancho" value={content.hook} empty="Sin gancho definido." />
        <PreviewSection
          label="Texto principal"
          value={content.caption}
          empty="Este contenido todavía no tiene texto principal."
          spacious
        />
        <PreviewSection label="Llamado a la acción" value={content.cta} empty="Sin CTA definido." />

        {content.media_url && (
          <Button asChild variant="outline" size="sm">
            <a href={content.media_url} target="_blank" rel="noreferrer">
              <ExternalLink className="h-4 w-4" />
              Abrir recurso multimedia
            </a>
          </Button>
        )}

        <section className="space-y-3 border-t border-border pt-6" aria-labelledby="review-actions-title">
          <div>
            <h3 id="review-actions-title" className="text-sm font-semibold text-foreground">
              Decisión editorial
            </h3>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              Añade contexto para que la siguiente persona entienda la decisión. Si el
              consejo de revisión automático está activo, el contenido se aprueba,
              rechaza o marca para cambios al instante, sin esperar un clic manual.
            </p>
          </div>

          {canWrite ? (
            <>
              <label className="block space-y-1.5 text-sm">
                <span className="font-medium text-foreground">Comentario</span>
                <Textarea
                  value={comment}
                  onChange={(event) => onCommentChange(event.target.value)}
                  rows={4}
                  placeholder="Qué funciona, qué debe cambiar o por qué se aprueba…"
                />
              </label>
              <div className="grid gap-2 sm:grid-cols-2">
                <Button
                  variant="outline"
                  disabled={busy || alreadyInReview}
                  onClick={() => onAction("submit")}
                  title={
                    alreadyInReview
                      ? "Ya está esperando una decisión de Owner o Admin"
                      : undefined
                  }
                >
                  <Send className="h-4 w-4" />
                  {alreadyInReview ? "Ya enviado a revisión" : "Enviar a revisión"}
                </Button>
                {canApprove && (
                  <Button
                    disabled={busy}
                    onClick={() => onAction("approve")}
                    className="bg-success text-success-foreground hover:bg-success/90"
                  >
                    <Check className="h-4 w-4" />
                    Aprobar
                  </Button>
                )}
                {canApprove && (
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() => onAction("changes")}
                    className="border-warning/35 text-warning hover:bg-warning/10 hover:text-warning"
                  >
                    <FilePenLine className="h-4 w-4" />
                    Solicitar cambios
                  </Button>
                )}
                {canApprove && (
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() => onAction("reject")}
                    className="border-destructive/35 text-destructive hover:bg-destructive/10 hover:text-destructive"
                  >
                    <XCircle className="h-4 w-4" />
                    Rechazar
                  </Button>
                )}
              </div>
              {!canApprove && (
                <PermissionNote>
                  Tu rol permite enviar a revisión pero no aprobar. Solo Owner o Admin puede
                  aprobar, solicitar cambios o rechazar.
                </PermissionNote>
              )}
              {alreadyInReview && (
                <PermissionNote tone="warning">
                  Ya se envió a revisión. No puede volver a enviarse hasta que Owner o Admin
                  tome una decisión.
                </PermissionNote>
              )}
            </>
          ) : (
            <PermissionNote>
              Tu rol es de consulta. Solicita acceso de Marketing, Administración o Owner para
              participar en el flujo editorial.
            </PermissionNote>
          )}
        </section>

        <section className="space-y-3 border-t border-border pt-6">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-foreground">Historial de revisión</h3>
            <span className="text-xs text-muted-foreground">{reviews.length} eventos</span>
          </div>
          {reviews.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border p-5 text-center">
              <MessageSquareText className="mx-auto h-5 w-5 text-muted-foreground" />
              <p className="mt-2 text-sm text-muted-foreground">Todavía no hay revisiones.</p>
            </div>
          ) : (
            <ol className="space-y-3">
              {reviews.map((review) => (
                <li key={review.id} className="rounded-xl border border-border bg-interactive/25 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <StatusBadge
                      label={REVIEW_DECISION_LABELS[review.decision]}
                      tone={REVIEW_DECISION_TONES[review.decision]}
                    />
                    <time className="text-xs text-muted-foreground">
                      {formatEditorialDate(review.created_at)}
                    </time>
                  </div>
                  {review.comment && (
                    <p className="mt-3 text-sm leading-6 text-foreground">{review.comment}</p>
                  )}
                  <p className="mt-2 text-xs text-muted-foreground">
                    Revisión {review.review_type.toLocaleLowerCase("es").replaceAll("_", " ")}
                    {review.score !== null ? ` · Puntaje ${review.score}` : ""}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </main>
  );
}

function ContentInfo({
  content,
  brand,
  campaign,
}: {
  content: ContentItem | null;
  brand?: Brand;
  campaign?: Campaign;
}) {
  return (
    <aside aria-label="Información del contenido" className="bg-interactive/18">
      <div className="border-b border-border bg-interactive/30 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          Información
        </p>
      </div>
      {!content ? (
        <div className="p-5 text-sm text-muted-foreground">Sin contenido seleccionado.</div>
      ) : (
        <div className="space-y-6 p-5">
          <InfoGroup
            title="Estado"
            rows={[
              {
                label: "Revisión",
                value: (
                  <StatusBadge
                    label={REVIEW_STATUS_LABELS[content.review_status]}
                    tone={REVIEW_STATUS_TONES[content.review_status]}
                  />
                ),
              },
              {
                label: "Publicación",
                value: (
                  <StatusBadge
                    label={CONTENT_STATUS_LABELS[content.status]}
                    tone={CONTENT_STATUS_TONES[content.status]}
                  />
                ),
              },
            ]}
          />
          <InfoGroup
            title="Clasificación"
            rows={[
              { label: "Marca", value: brand?.name ?? "Marca no disponible" },
              { label: "Campaña", value: campaign?.name ?? "Sin campaña" },
              { label: "Plataforma", value: PLATFORM_LABELS[content.platform] },
              { label: "Formato", value: CONTENT_TYPE_LABELS[content.content_type] },
              { label: "Origen", value: SOURCE_LABELS[content.source_system] },
            ]}
          />
          <InfoGroup
            title="Actividad"
            rows={[
              { label: "Creado", value: formatEditorialDate(content.created_at) },
              { label: "Actualizado", value: formatEditorialDate(content.updated_at) },
              {
                label: "Publicado",
                value: content.published_at
                  ? formatEditorialDate(content.published_at)
                  : "Aún no publicado",
              },
            ]}
          />
          {content.publication_url && (
            <Button asChild variant="outline" size="sm" className="w-full">
              <a href={content.publication_url} target="_blank" rel="noreferrer">
                Ver publicación
                <ExternalLink className="ml-auto h-4 w-4" />
              </a>
            </Button>
          )}
          {content.review_status === "APPROVED" && (
            <Button asChild size="sm" className="w-full">
              <Link href="/calendar">
                <CalendarClock className="h-4 w-4" />
                Programar contenido
              </Link>
            </Button>
          )}
        </div>
      )}
    </aside>
  );
}

function CreateContentDrawer({
  open,
  onOpenChange,
  currentOrgId,
  brands,
  campaigns,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentOrgId: string;
  brands: Brand[];
  campaigns: Campaign[];
  onCreated: () => Promise<void>;
}) {
  const [brandId, setBrandId] = useState("");
  const [campaignId, setCampaignId] = useState("");
  const [title, setTitle] = useState("");
  const [hook, setHook] = useState("");
  const [contentType, setContentType] = useState<ContentType>("REEL");
  const [platform, setPlatform] = useState<Platform>("INSTAGRAM");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setBrandId(brands[0]?.id ?? "");
    setCampaignId("");
    setTitle("");
    setHook("");
    setContentType("REEL");
    setPlatform("INSTAGRAM");
    setError(null);
  }, [brands, open]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!brandId || !title.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.createContent(currentOrgId, {
        brand_id: brandId,
        campaign_id: campaignId || null,
        title: title.trim(),
        hook: hook.trim() || null,
        content_type: contentType,
        platform,
      });
      await onCreated();
    } catch (createError) {
      setError(
        createError instanceof ApiError
          ? createError.detail
          : "No pudimos crear el contenido.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title="Nuevo contenido"
      description="Crea la ficha editorial; podrás completar y revisar el contenido desde la bandeja."
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button type="submit" form="create-content-form" disabled={busy}>
            {busy ? "Guardando…" : "Crear contenido"}
          </Button>
        </div>
      }
    >
      <form id="create-content-form" onSubmit={submit} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Marca">
            <Select value={brandId} onChange={(event) => setBrandId(event.target.value)}>
              {brands.map((brand) => (
                <option key={brand.id} value={brand.id}>{brand.name}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Campaña" hint="Opcional">
            <Select value={campaignId} onChange={(event) => setCampaignId(event.target.value)}>
              <option value="">Sin campaña</option>
              {campaigns
                .filter((campaign) => !brandId || campaign.brand_id === brandId)
                .map((campaign) => (
                  <option key={campaign.id} value={campaign.id}>{campaign.name}</option>
                ))}
            </Select>
          </FormField>
        </div>
        <FormField label="Título">
          <Input
            required
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Nombre interno de la pieza"
          />
        </FormField>
        <FormField label="Gancho">
          <Textarea
            value={hook}
            onChange={(event) => setHook(event.target.value)}
            rows={3}
            placeholder="La primera idea que debe captar la atención"
          />
        </FormField>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Formato">
            <Select
              value={contentType}
              onChange={(event) => setContentType(event.target.value as ContentType)}
            >
              {CONTENT_TYPES.map((value) => (
                <option key={value} value={value}>{CONTENT_TYPE_LABELS[value]}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Plataforma">
            <Select
              value={platform}
              onChange={(event) => setPlatform(event.target.value as Platform)}
            >
              {PLATFORMS.map((value) => (
                <option key={value} value={value}>{PLATFORM_LABELS[value]}</option>
              ))}
            </Select>
          </FormField>
        </div>
        {error && (
          <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/8 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}
      </form>
    </Drawer>
  );
}

function InboxLink({ href, active, label }: { href: string; active: boolean; label: string }) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
        active ? "bg-elevated text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {label}
    </Link>
  );
}

function PreviewSection({
  label,
  value,
  empty,
  spacious,
}: {
  label: string;
  value: string | null;
  empty: string;
  spacious?: boolean;
}) {
  return (
    <section>
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </p>
      <p
        className={cn(
          "mt-2 whitespace-pre-wrap text-sm leading-6",
          value ? "text-foreground" : "italic text-muted-foreground",
          spacious && "min-h-24 rounded-xl border border-border bg-interactive/20 p-4",
        )}
      >
        {value || empty}
      </p>
    </section>
  );
}

function PermissionNote({
  children,
  tone = "info",
}: {
  children: React.ReactNode;
  tone?: "info" | "warning";
}) {
  return (
    <div
      className={cn(
        "flex gap-3 rounded-xl border p-3 text-sm leading-6",
        tone === "warning"
          ? "border-warning/25 bg-warning/8 text-warning"
          : "border-info/20 bg-info/8 text-muted-foreground",
      )}
    >
      <Info className={cn("mt-1 h-4 w-4 shrink-0", tone === "info" && "text-info")} />
      <p>{children}</p>
    </div>
  );
}

function InfoGroup({
  title,
  rows,
}: {
  title: string;
  rows: Array<{ label: string; value: React.ReactNode }>;
}) {
  return (
    <section>
      <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        {title}
      </h3>
      <dl className="mt-3 space-y-3">
        {rows.map((row) => (
          <div key={row.label} className="flex flex-col gap-1">
            <dt className="text-xs text-muted-foreground">{row.label}</dt>
            <dd className="text-sm font-medium text-foreground">{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function FormField({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5 text-sm">
      <span className="font-medium text-foreground">
        {label}
        {hint && <span className="ml-1 font-normal text-muted-foreground">({hint})</span>}
      </span>
      {children}
    </label>
  );
}
