import { CalendarDays, Clock3, ExternalLink } from "lucide-react";

import { StatusBadge } from "@/components/design-system/status-badge";
import { LoadingSkeleton, StatePanel } from "@/components/design-system/state-panel";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import {
  addDays,
  type CalendarEntry,
  dateKey,
  formatShortDate,
  isSameDay,
  PLATFORM_LABELS,
  PRIORITY_LABELS,
  startOfWeek,
  STATUS_LABELS,
  STATUS_TONES,
} from "./calendar-config";

interface ViewProps {
  entries: CalendarEntry[];
  cursorDate: Date;
  loading: boolean;
  onSelect: (entry: CalendarEntry) => void;
  onCreateForDate: (date: Date) => void;
  canWrite: boolean;
}

const WEEKDAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

export function MonthView({
  entries,
  cursorDate,
  loading,
  onSelect,
  onCreateForDate,
  canWrite,
}: ViewProps) {
  const firstOfMonth = new Date(cursorDate.getFullYear(), cursorDate.getMonth(), 1);
  const gridStart = startOfWeek(firstOfMonth);
  const days = Array.from({ length: 42 }, (_, index) => addDays(gridStart, index));
  const entriesByDay = groupByDay(entries);

  if (loading) return <CalendarLoading />;

  return (
    <Card className="overflow-hidden bg-card/85 shadow-none">
      <CardContent className="p-0">
        <div className="grid grid-cols-7 border-b border-border bg-interactive/40">
          {WEEKDAYS.map((day) => (
            <div
              key={day}
              className="px-2 py-3 text-center text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground"
            >
              {day}
            </div>
          ))}
        </div>
        <div className="overflow-x-auto">
          <div className="grid min-w-[760px] grid-cols-7">
          {days.map((day) => {
            const dayEntries = entriesByDay.get(dateKey(day)) ?? [];
            const isCurrentMonth = day.getMonth() === cursorDate.getMonth();
            const isToday = isSameDay(day, new Date());
            return (
              <div
                key={dateKey(day)}
                className={cn(
                  "group min-h-32 border-b border-r border-border/70 p-2",
                  !isCurrentMonth && "bg-interactive/25 text-muted-foreground",
                )}
              >
                <button
                  type="button"
                  onClick={() => canWrite && onCreateForDate(day)}
                  className={cn(
                    "mb-2 flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium",
                    isToday
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-interactive hover:text-foreground",
                    !canWrite && "cursor-default",
                  )}
                  aria-label={
                    canWrite
                      ? `Crear contenido para ${day.toLocaleDateString("es")}`
                      : day.toLocaleDateString("es")
                  }
                >
                  {day.getDate()}
                </button>
                <div className="space-y-1">
                  {dayEntries.slice(0, 3).map((entry) => (
                    <CalendarChip key={entry.item.id} entry={entry} onSelect={onSelect} />
                  ))}
                  {dayEntries.length > 3 && (
                    <p className="px-1 text-[11px] font-medium text-muted-foreground">
                      +{dayEntries.length - 3} más
                    </p>
                  )}
                </div>
              </div>
            );
          })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function WeekView({
  entries,
  cursorDate,
  loading,
  onSelect,
  onCreateForDate,
  canWrite,
}: ViewProps) {
  const start = startOfWeek(cursorDate);
  const days = Array.from({ length: 7 }, (_, index) => addDays(start, index));
  const entriesByDay = groupByDay(entries);

  if (loading) return <CalendarLoading />;

  return (
    <Card className="overflow-x-auto bg-card/85 shadow-none">
      <CardContent className="min-w-[880px] p-0">
        <div className="grid grid-cols-7 divide-x divide-border">
          {days.map((day) => {
            const dayEntries = entriesByDay.get(dateKey(day)) ?? [];
            const isToday = isSameDay(day, new Date());
            return (
              <section key={dateKey(day)} className="min-h-[31rem]">
                <header className="border-b border-border bg-interactive/30 px-3 py-3 text-center">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                    {day.toLocaleDateString("es", { weekday: "short" })}
                  </p>
                  <button
                    type="button"
                    onClick={() => canWrite && onCreateForDate(day)}
                    className={cn(
                      "mx-auto mt-1 flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold",
                      isToday ? "bg-primary text-primary-foreground" : "hover:bg-interactive",
                      !canWrite && "cursor-default",
                    )}
                    aria-label={
                      canWrite
                        ? `Crear contenido para ${day.toLocaleDateString("es")}`
                        : day.toLocaleDateString("es")
                    }
                  >
                    {day.getDate()}
                  </button>
                </header>
                <div className="space-y-2 p-2">
                  {dayEntries.length === 0 ? (
                    <p className="rounded-lg border border-dashed border-border px-2 py-5 text-center text-xs text-muted-foreground">
                      Sin contenido
                    </p>
                  ) : (
                    dayEntries.map((entry) => (
                      <button
                        key={entry.item.id}
                        type="button"
                        onClick={() => onSelect(entry)}
                        className="w-full rounded-lg border border-border bg-elevated p-3 text-left transition-colors hover:border-primary/35 hover:bg-accent/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <p className="line-clamp-2 text-xs font-semibold leading-5 text-foreground">
                          {entry.content?.title ?? "Contenido sin título"}
                        </p>
                        <p className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground">
                          <Clock3 className="h-3 w-3" />
                          {entry.item.scheduled_for
                            ? new Date(entry.item.scheduled_for).toLocaleTimeString("es", {
                                hour: "2-digit",
                                minute: "2-digit",
                              })
                            : "Sin hora"}
                        </p>
                        <StatusBadge
                          label={STATUS_LABELS[entry.item.status]}
                          tone={STATUS_TONES[entry.item.status]}
                          className="mt-2 max-w-full"
                        />
                      </button>
                    ))
                  )}
                </div>
              </section>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

export function ListView({
  entries,
  loading,
  onSelect,
}: Pick<ViewProps, "entries" | "loading" | "onSelect">) {
  if (loading) return <CalendarLoading />;
  if (entries.length === 0) {
    return (
      <StatePanel
        icon={CalendarDays}
        title="No hay elementos con estos filtros"
        description="Ajusta los filtros o crea un nuevo elemento editorial."
      />
    );
  }

  const sorted = [...entries].sort((first, second) => {
    if (!first.item.scheduled_for) return 1;
    if (!second.item.scheduled_for) return -1;
    return new Date(first.item.scheduled_for).getTime() - new Date(second.item.scheduled_for).getTime();
  });

  return (
    <Card className="overflow-hidden bg-card/85 shadow-none">
      <CardContent className="p-0">
        <div className="hidden grid-cols-[minmax(0,1.6fr)_0.8fr_0.85fr_0.75fr_auto] gap-4 border-b border-border bg-interactive/40 px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground md:grid">
          <span>Contenido</span>
          <span>Canal</span>
          <span>Programación</span>
          <span>Estado</span>
          <span className="sr-only">Abrir</span>
        </div>
        <ul className="divide-y divide-border">
          {sorted.map((entry) => (
            <li key={entry.item.id}>
              <button
                type="button"
                onClick={() => onSelect(entry)}
                className="grid w-full gap-3 px-4 py-4 text-left transition-colors hover:bg-interactive/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring md:grid-cols-[minmax(0,1.6fr)_0.8fr_0.85fr_0.75fr_auto] md:items-center md:gap-4 md:px-5"
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-foreground">
                    {entry.content?.title ?? "Contenido sin título"}
                  </span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {entry.item.public_id} · {PRIORITY_LABELS[entry.item.priority]}
                  </span>
                </span>
                <span className="text-sm text-muted-foreground">
                  {PLATFORM_LABELS[entry.item.platform]}
                </span>
                <span className="text-sm text-muted-foreground">
                  {formatShortDate(entry.item.scheduled_for)}
                </span>
                <StatusBadge
                  label={STATUS_LABELS[entry.item.status]}
                  tone={STATUS_TONES[entry.item.status]}
                  className="w-fit"
                />
                <span className="flex items-center gap-2 text-xs font-medium text-primary">
                  Ver detalle
                  <ExternalLink className="h-3.5 w-3.5" />
                </span>
              </button>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function CalendarChip({
  entry,
  onSelect,
}: {
  entry: CalendarEntry;
  onSelect: (entry: CalendarEntry) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(entry)}
      title={entry.content?.title ?? "Contenido sin título"}
      className={cn(
        "block w-full truncate rounded-md border px-2 py-1.5 text-left text-[11px] font-medium transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        STATUS_TONES[entry.item.status] === "success" && "border-success/20 bg-success/10 text-success",
        STATUS_TONES[entry.item.status] === "info" && "border-info/20 bg-info/10 text-info",
        STATUS_TONES[entry.item.status] === "warning" && "border-warning/20 bg-warning/10 text-warning",
        STATUS_TONES[entry.item.status] === "danger" &&
          "border-destructive/20 bg-destructive/10 text-destructive",
        STATUS_TONES[entry.item.status] === "accent" && "border-lime/25 bg-lime/10 text-foreground",
        STATUS_TONES[entry.item.status] === "neutral" &&
          "border-border bg-interactive text-muted-foreground",
      )}
    >
      {entry.content?.title ?? "Contenido sin título"}
    </button>
  );
}

function groupByDay(entries: CalendarEntry[]) {
  const grouped = new Map<string, CalendarEntry[]>();
  for (const entry of entries) {
    if (!entry.item.scheduled_for) continue;
    const key = dateKey(new Date(entry.item.scheduled_for));
    grouped.set(key, [...(grouped.get(key) ?? []), entry]);
  }
  for (const rows of grouped.values()) {
    rows.sort(
      (first, second) =>
        new Date(first.item.scheduled_for ?? 0).getTime() -
        new Date(second.item.scheduled_for ?? 0).getTime(),
    );
  }
  return grouped;
}

function CalendarLoading() {
  return (
    <Card className="bg-card/85 shadow-none">
      <CardContent className="p-5">
        <LoadingSkeleton rows={6} />
      </CardContent>
    </Card>
  );
}
