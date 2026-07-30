"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  CircleDashed,
  Clock3,
  LayoutGrid,
  List,
  Plus,
  RefreshCw,
  Rows3,
  Search,
  Send,
  SlidersHorizontal,
} from "lucide-react";
import type {
  Brand,
  ContentItem,
  EditorialItem,
  EditorialPlatform,
  EditorialStatus,
  Publication,
} from "@rqt21/contracts";
import { EDITORIAL_PLATFORMS, EDITORIAL_STATUSES } from "@rqt21/contracts";

import {
  CalendarEditorDrawer,
  type EditorialFormValues,
} from "@/components/calendar/calendar-editor-drawer";
import { ListView, MonthView, WeekView } from "@/components/calendar/calendar-views";
import { MetricCard } from "@/components/design-system/metric-card";
import { PageHeader } from "@/components/design-system/page-header";
import { StatusBadge } from "@/components/design-system/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api, request } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";
import { cn } from "@/lib/utils";

import {
  type CalendarEntry,
  type CalendarView,
  friendlyEditorialError,
  PLATFORM_LABELS,
  startOfWeek,
  STATUS_LABELS,
} from "./calendar-config";

export function EditorialCalendar() {
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canWrite = canWriteGrowth(organization?.role);

  const [items, setItems] = useState<EditorialItem[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [contents, setContents] = useState<ContentItem[]>([]);
  const [publications, setPublications] = useState<Publication[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawerError, setDrawerError] = useState<string | null>(null);

  const [view, setView] = useState<CalendarView>("month");
  const [cursorDate, setCursorDate] = useState(() => new Date());
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<EditorialStatus | "">("");
  const [platformFilter, setPlatformFilter] = useState<EditorialPlatform | "">("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<EditorialItem | null>(null);
  const [initialDate, setInitialDate] = useState<Date | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [editorialRows, brandRows, contentRows, publicationRows] = await Promise.all([
        api.listEditorial(currentOrgId),
        api.listBrands(currentOrgId),
        api.listContent(currentOrgId),
        api.listPublications(currentOrgId).catch(() => []),
      ]);
      setItems(editorialRows);
      setBrands(brandRows);
      setContents(contentRows);
      setPublications(publicationRows);
    } catch (loadError) {
      setError(friendlyEditorialError(loadError, "No pudimos cargar el calendario editorial."));
    } finally {
      setLoading(false);
    }
  }, [currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  const entries = useMemo<CalendarEntry[]>(
    () =>
      items.map((item) => ({
        item,
        content: contents.find((content) => content.id === item.content_item_id),
        publication: publications.find(
          (publication) =>
            publication.editorial_calendar_item_id === item.id ||
            publication.content_item_id === item.content_item_id,
        ),
      })),
    [contents, items, publications],
  );

  const filteredEntries = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("es");
    return entries.filter(
      (entry) =>
        (!statusFilter || entry.item.status === statusFilter) &&
        (!platformFilter || entry.item.platform === platformFilter) &&
        (!query ||
          entry.content?.title.toLocaleLowerCase("es").includes(query) ||
          entry.item.notes?.toLocaleLowerCase("es").includes(query) ||
          entry.item.public_id.toLocaleLowerCase("es").includes(query)),
    );
  }, [entries, platformFilter, search, statusFilter]);

  const now = new Date();
  const inSevenDays = new Date(now);
  inSevenDays.setDate(inSevenDays.getDate() + 7);
  const scheduledNextWeek = items.filter((item) => {
    if (!item.scheduled_for || item.status === "CANCELLED" || item.status === "ARCHIVED") return false;
    const date = new Date(item.scheduled_for);
    return date >= now && date <= inSevenDays;
  }).length;
  const pendingReview = items.filter((item) =>
    ["IN_REVIEW", "NEEDS_REVISION"].includes(item.status),
  ).length;
  const publishedThisMonth = items.filter((item) => {
    if (!item.published_at) return false;
    const date = new Date(item.published_at);
    return date.getMonth() === now.getMonth() && date.getFullYear() === now.getFullYear();
  }).length;
  const unscheduled = items.filter(
    (item) => !item.scheduled_for && !["PUBLISHED", "CANCELLED", "ARCHIVED"].includes(item.status),
  ).length;

  const openCreate = (date?: Date) => {
    setSelectedItem(null);
    setInitialDate(date ?? null);
    setDrawerError(null);
    setDrawerOpen(true);
  };

  const openEntry = (entry: CalendarEntry) => {
    setSelectedItem(entry.item);
    setInitialDate(null);
    setDrawerError(null);
    setDrawerOpen(true);
  };

  const finishMutation = async () => {
    await load();
    setDrawerOpen(false);
    setSelectedItem(null);
    setInitialDate(null);
  };

  const saveItem = async (values: EditorialFormValues) => {
    if (!currentOrgId) return;
    setBusy(true);
    setDrawerError(null);
    try {
      if (selectedItem) {
        await request<EditorialItem>(
          `/api/v1/editorial-calendar/${selectedItem.id}`,
          {
            method: "PATCH",
            body: JSON.stringify({
              platform: values.platform,
              content_format: values.format,
              scheduled_for: values.scheduledFor,
              timezone: values.timezone,
              status: values.status,
              priority: values.priority,
              notes: values.notes,
            }),
          },
          currentOrgId,
        );
      } else {
        await api.createEditorial(currentOrgId, {
          brand_id: values.brandId,
          content_item_id: values.contentId,
          platform: values.platform,
          content_format: values.format,
          status: values.status,
          priority: values.priority,
          scheduled_for: values.scheduledFor,
          timezone: values.timezone,
          notes: values.notes,
        });
      }
      await finishMutation();
    } catch (mutationError) {
      setDrawerError(friendlyEditorialError(mutationError, "No pudimos guardar los cambios."));
    } finally {
      setBusy(false);
    }
  };

  const scheduleItem = async (item: EditorialItem, scheduledFor: string) => {
    if (!currentOrgId) return;
    setBusy(true);
    setDrawerError(null);
    try {
      await api.scheduleEditorial(currentOrgId, item.id, {
        scheduled_for: scheduledFor,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      });
      await finishMutation();
    } catch (mutationError) {
      setDrawerError(friendlyEditorialError(mutationError, "No pudimos programar el contenido."));
    } finally {
      setBusy(false);
    }
  };

  const publishItem = async (item: EditorialItem, publicationUrl: string) => {
    if (!currentOrgId) return;
    setBusy(true);
    setDrawerError(null);
    try {
      await api.markPublished(currentOrgId, item.id, { publication_url: publicationUrl });
      await finishMutation();
    } catch (mutationError) {
      setDrawerError(
        friendlyEditorialError(mutationError, "No pudimos confirmar la publicación."),
      );
    } finally {
      setBusy(false);
    }
  };

  const cancelItem = async (item: EditorialItem) => {
    if (!currentOrgId) return;
    setBusy(true);
    setDrawerError(null);
    try {
      await api.cancelEditorial(currentOrgId, item.id);
      await finishMutation();
    } catch (mutationError) {
      setDrawerError(friendlyEditorialError(mutationError, "No pudimos cancelar el elemento."));
    } finally {
      setBusy(false);
    }
  };

  const selectedPublication = selectedItem
    ? publications.find(
        (publication) =>
          publication.editorial_calendar_item_id === selectedItem.id ||
          publication.content_item_id === selectedItem.content_item_id,
      )
    : undefined;

  if (!currentOrgId) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          Selecciona una organización para consultar su calendario.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Operación editorial"
        title="Calendario editorial"
        description="Organiza el contenido por fecha, canal y estado. Abre cualquier elemento para editarlo, programarlo o confirmar su publicación."
        metadata={
          <>
            <StatusBadge
              label={`${filteredEntries.length} elementos visibles`}
              tone="neutral"
            />
            {!canWrite && <span className="text-xs text-muted-foreground">Modo de solo lectura</span>}
          </>
        }
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void load()}
              disabled={loading}
              aria-label="Actualizar calendario"
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
            {canWrite && (
              <Button
                size="sm"
                onClick={() => openCreate()}
                disabled={brands.length === 0 || contents.length === 0}
                title={
                  brands.length === 0 || contents.length === 0
                    ? "Necesitas al menos una marca y un contenido"
                    : undefined
                }
              >
                <Plus className="h-4 w-4" />
                Nuevo elemento
              </Button>
            )}
          </>
        }
      />

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-destructive/25 bg-destructive/8 px-4 py-3 text-sm text-destructive"
        >
          {error}
        </div>
      )}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Resumen editorial">
        <MetricCard
          label="Próximos 7 días"
          value={scheduledNextWeek}
          helper="Contenidos con fecha confirmada"
          icon={CalendarClock}
          tone="info"
          loading={loading}
        />
        <MetricCard
          label="En revisión"
          value={pendingReview}
          helper="Pendientes de decisión editorial"
          icon={CircleDashed}
          tone="warning"
          loading={loading}
        />
        <MetricCard
          label="Publicados este mes"
          value={publishedThisMonth}
          helper="Con publicación confirmada"
          icon={Send}
          tone="positive"
          loading={loading}
        />
        <MetricCard
          label="Sin fecha"
          value={unscheduled}
          helper="Ideas y borradores por programar"
          icon={Clock3}
          tone="neutral"
          loading={loading}
        />
      </section>

      <section className="space-y-4">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            {view !== "list" && (
              <>
                <Button
                  variant="outline"
                  size="icon"
                  aria-label={view === "month" ? "Mes anterior" : "Semana anterior"}
                  onClick={() => setCursorDate(changePeriod(cursorDate, view, -1))}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="sm" onClick={() => setCursorDate(new Date())}>
                  Hoy
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  aria-label={view === "month" ? "Mes siguiente" : "Semana siguiente"}
                  onClick={() => setCursorDate(changePeriod(cursorDate, view, 1))}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <h2 className="ml-1 min-w-48 text-base font-semibold capitalize text-foreground">
                  {periodLabel(cursorDate, view)}
                </h2>
              </>
            )}
            {view === "list" && (
              <h2 className="text-base font-semibold text-foreground">Todos los elementos</h2>
            )}
          </div>
          <div
            className="inline-flex w-fit rounded-lg border border-border bg-interactive/45 p-1"
            role="group"
            aria-label="Vista del calendario"
          >
            <ViewButton
              active={view === "month"}
              label="Mes"
              icon={LayoutGrid}
              onClick={() => setView("month")}
            />
            <ViewButton
              active={view === "week"}
              label="Semana"
              icon={Rows3}
              onClick={() => setView("week")}
            />
            <ViewButton
              active={view === "list"}
              label="Lista"
              icon={List}
              onClick={() => setView("list")}
            />
          </div>
        </div>

        <Card className="bg-card/75 shadow-none">
          <CardContent className="p-4">
            <div className="grid gap-3 lg:grid-cols-[minmax(14rem,1fr)_12rem_12rem_auto]">
              <label className="relative">
                <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Buscar contenido o notas…"
                  className="pl-9"
                  aria-label="Buscar en el calendario"
                />
              </label>
              <Select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as EditorialStatus | "")}
                aria-label="Filtrar por estado"
              >
                <option value="">Todos los estados</option>
                {EDITORIAL_STATUSES.map((value) => (
                  <option key={value} value={value}>{STATUS_LABELS[value]}</option>
                ))}
              </Select>
              <Select
                value={platformFilter}
                onChange={(event) => setPlatformFilter(event.target.value as EditorialPlatform | "")}
                aria-label="Filtrar por plataforma"
              >
                <option value="">Todas las plataformas</option>
                {EDITORIAL_PLATFORMS.map((value) => (
                  <option key={value} value={value}>{PLATFORM_LABELS[value]}</option>
                ))}
              </Select>
              {(search || statusFilter || platformFilter) && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSearch("");
                    setStatusFilter("");
                    setPlatformFilter("");
                  }}
                >
                  Limpiar filtros
                </Button>
              )}
              {!search && !statusFilter && !platformFilter && (
                <span className="flex items-center justify-end gap-2 text-xs text-muted-foreground">
                  <SlidersHorizontal className="h-3.5 w-3.5" />
                  Sin filtros activos
                </span>
              )}
            </div>
          </CardContent>
        </Card>

        {view === "month" && (
          <MonthView
            entries={filteredEntries}
            cursorDate={cursorDate}
            loading={loading}
            onSelect={openEntry}
            onCreateForDate={openCreate}
            canWrite={canWrite}
          />
        )}
        {view === "week" && (
          <WeekView
            entries={filteredEntries}
            cursorDate={cursorDate}
            loading={loading}
            onSelect={openEntry}
            onCreateForDate={openCreate}
            canWrite={canWrite}
          />
        )}
        {view === "list" && (
          <ListView entries={filteredEntries} loading={loading} onSelect={openEntry} />
        )}
      </section>

      <CalendarEditorDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        item={selectedItem}
        initialDate={initialDate}
        brands={brands}
        contents={contents}
        publication={selectedPublication}
        canWrite={canWrite}
        busy={busy}
        error={drawerError}
        onSave={saveItem}
        onSchedule={scheduleItem}
        onPublish={publishItem}
        onCancel={cancelItem}
      />
    </div>
  );
}

function ViewButton({
  active,
  label,
  icon: Icon,
  onClick,
}: {
  active: boolean;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-medium transition-colors",
        active
          ? "bg-elevated text-foreground shadow-sm"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

function changePeriod(date: Date, view: CalendarView, direction: -1 | 1) {
  const next = new Date(date);
  if (view === "week") {
    next.setDate(next.getDate() + direction * 7);
  } else {
    next.setMonth(next.getMonth() + direction);
  }
  return next;
}

function periodLabel(date: Date, view: CalendarView) {
  if (view === "week") {
    const start = startOfWeek(date);
    const end = new Date(start);
    end.setDate(end.getDate() + 6);
    if (start.getMonth() === end.getMonth()) {
      return `${start.getDate()}–${end.getDate()} de ${end.toLocaleDateString("es", {
        month: "long",
        year: "numeric",
      })}`;
    }
    return `${start.toLocaleDateString("es", {
      day: "numeric",
      month: "short",
    })} – ${end.toLocaleDateString("es", {
      day: "numeric",
      month: "short",
      year: "numeric",
    })}`;
  }
  return date.toLocaleDateString("es", { month: "long", year: "numeric" });
}
