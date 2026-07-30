"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  FileText,
  Info,
  Send,
  Trash2,
} from "lucide-react";
import type {
  Brand,
  ContentFormat,
  ContentItem,
  EditorialItem,
  EditorialPlatform,
  EditorialStatus,
  Priority,
  Publication,
} from "@rqt21/contracts";
import {
  CONTENT_FORMATS,
  EDITORIAL_PLATFORMS,
  EDITORIAL_STATUSES,
  PRIORITIES,
} from "@rqt21/contracts";

import { Drawer } from "@/components/design-system/drawer";
import { StatusBadge } from "@/components/design-system/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

import {
  FORMAT_LABELS,
  PLATFORM_LABELS,
  PRIORITY_LABELS,
  STATUS_LABELS,
  STATUS_TONES,
  toDateTimeLocal,
  toISOString,
} from "./calendar-config";

export interface EditorialFormValues {
  brandId: string;
  contentId: string;
  platform: EditorialPlatform;
  format: ContentFormat;
  status: EditorialStatus;
  priority: Priority;
  scheduledFor: string | null;
  timezone: string;
  notes: string | null;
}

interface CalendarEditorDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: EditorialItem | null;
  initialDate: Date | null;
  brands: Brand[];
  contents: ContentItem[];
  publication?: Publication;
  canWrite: boolean;
  busy: boolean;
  error: string | null;
  onSave: (values: EditorialFormValues) => Promise<void>;
  onSchedule: (item: EditorialItem, scheduledFor: string) => Promise<void>;
  onPublish: (item: EditorialItem, publicationUrl: string) => Promise<void>;
  onCancel: (item: EditorialItem) => Promise<void>;
}

export function CalendarEditorDrawer({
  open,
  onOpenChange,
  item,
  initialDate,
  brands,
  contents,
  publication,
  canWrite,
  busy,
  error,
  onSave,
  onSchedule,
  onPublish,
  onCancel,
}: CalendarEditorDrawerProps) {
  const isEditing = Boolean(item);
  const [brandId, setBrandId] = useState("");
  const [contentId, setContentId] = useState("");
  const [platform, setPlatform] = useState<EditorialPlatform>("INSTAGRAM");
  const [format, setFormat] = useState<ContentFormat>("REEL");
  const [status, setStatus] = useState<EditorialStatus>("IDEA");
  const [priority, setPriority] = useState<Priority>("MEDIUM");
  const [scheduledFor, setScheduledFor] = useState("");
  const [notes, setNotes] = useState("");
  const [publicationUrl, setPublicationUrl] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const content = useMemo(
    () => contents.find((candidate) => candidate.id === (item?.content_item_id ?? contentId)),
    [contentId, contents, item?.content_item_id],
  );
  const brand = useMemo(
    () => brands.find((candidate) => candidate.id === (item?.brand_id ?? brandId)),
    [brandId, brands, item?.brand_id],
  );

  useEffect(() => {
    if (!open) return;
    setBrandId(item?.brand_id ?? brands[0]?.id ?? "");
    setContentId(item?.content_item_id ?? contents[0]?.id ?? "");
    setPlatform(item?.platform ?? "INSTAGRAM");
    setFormat(item?.content_format ?? "REEL");
    setStatus(item?.status ?? (initialDate ? "SCHEDULED" : "IDEA"));
    setPriority(item?.priority ?? "MEDIUM");
    setScheduledFor(
      item?.scheduled_for
        ? toDateTimeLocal(item.scheduled_for)
        : initialDate
          ? toDateTimeLocal(initialDate.toISOString())
          : "",
    );
    setNotes(item?.notes ?? "");
    setPublicationUrl(item?.publication_url ?? "");
    setValidationError(null);
  }, [brands, contents, initialDate, item, open]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setValidationError(null);
    if (!brandId || !contentId) {
      setValidationError("Selecciona una marca y un contenido.");
      return;
    }
    if (status === "SCHEDULED" && !scheduledFor) {
      setValidationError("Selecciona una fecha y hora para programar.");
      return;
    }
    await onSave({
      brandId,
      contentId,
      platform,
      format,
      status,
      priority,
      scheduledFor: toISOString(scheduledFor),
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      notes: notes.trim() || null,
    });
  };

  const unavailableReason = !canWrite
    ? "Tu rol permite consultar el calendario, pero no modificarlo. Solicita acceso de Marketing o Administración."
    : item?.status === "ARCHIVED"
      ? "Este elemento está archivado y se conserva como historial."
      : null;
  const formDisabled = busy || Boolean(unavailableReason);

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={isEditing ? content?.title ?? "Detalle editorial" : "Nuevo elemento editorial"}
      description={
        isEditing
          ? `${item?.public_id} · ${brand?.name ?? "Marca sin identificar"}`
          : "Añade contenido al plan y define cuándo debe publicarse."
      }
      footer={
        canWrite && item?.status !== "ARCHIVED" ? (
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cerrar
            </Button>
            <Button type="submit" form="editorial-item-form" disabled={busy}>
              {busy ? "Guardando…" : isEditing ? "Guardar cambios" : "Añadir al calendario"}
            </Button>
          </div>
        ) : (
          <Button type="button" variant="outline" className="w-full" onClick={() => onOpenChange(false)}>
            Cerrar
          </Button>
        )
      }
    >
      <div className="space-y-6">
        {item && (
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge label={STATUS_LABELS[item.status]} tone={STATUS_TONES[item.status]} />
            <StatusBadge label={`Prioridad ${PRIORITY_LABELS[item.priority].toLowerCase()}`} />
            <span className="text-xs text-muted-foreground">
              {PLATFORM_LABELS[item.platform]} · {FORMAT_LABELS[item.content_format]}
            </span>
          </div>
        )}

        {unavailableReason && (
          <div className="flex gap-3 rounded-xl border border-info/20 bg-info/8 p-4 text-sm text-muted-foreground">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
            <p>{unavailableReason}</p>
          </div>
        )}

        <form id="editorial-item-form" onSubmit={submit} className="space-y-5">
          <fieldset disabled={formDisabled} className="space-y-5 disabled:opacity-70">
            {!isEditing ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Marca">
                  <Select value={brandId} onChange={(event) => setBrandId(event.target.value)}>
                    {brands.map((row) => (
                      <option key={row.id} value={row.id}>{row.name}</option>
                    ))}
                  </Select>
                </Field>
                <Field label="Contenido">
                  <Select value={contentId} onChange={(event) => setContentId(event.target.value)}>
                    {contents.map((row) => (
                      <option key={row.id} value={row.id}>{row.title}</option>
                    ))}
                  </Select>
                </Field>
              </div>
            ) : (
              <div className="rounded-xl border border-border bg-interactive/35 p-4">
                <div className="flex items-start gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-elevated text-primary">
                    <FileText className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="font-medium text-foreground">{content?.title ?? "Contenido"}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{brand?.name}</p>
                  </div>
                </div>
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Plataforma">
                <Select value={platform} onChange={(event) => setPlatform(event.target.value as EditorialPlatform)}>
                  {EDITORIAL_PLATFORMS.map((value) => (
                    <option key={value} value={value}>{PLATFORM_LABELS[value]}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Formato">
                <Select value={format} onChange={(event) => setFormat(event.target.value as ContentFormat)}>
                  {CONTENT_FORMATS.map((value) => (
                    <option key={value} value={value}>{FORMAT_LABELS[value]}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Estado">
                <Select value={status} onChange={(event) => setStatus(event.target.value as EditorialStatus)}>
                  {EDITORIAL_STATUSES.filter(
                    (value) => !["PUBLISHED", "ARCHIVED"].includes(value),
                  ).map((value) => (
                    <option key={value} value={value}>{STATUS_LABELS[value]}</option>
                  ))}
                  {item?.status === "PUBLISHED" && <option value="PUBLISHED">Publicado</option>}
                  {item?.status === "ARCHIVED" && <option value="ARCHIVED">Archivado</option>}
                </Select>
              </Field>
              <Field label="Prioridad">
                <Select value={priority} onChange={(event) => setPriority(event.target.value as Priority)}>
                  {PRIORITIES.map((value) => (
                    <option key={value} value={value}>{PRIORITY_LABELS[value]}</option>
                  ))}
                </Select>
              </Field>
            </div>

            <Field
              label="Fecha y hora"
              hint="Usaremos la zona horaria de este dispositivo."
            >
              <Input
                type="datetime-local"
                value={scheduledFor}
                onChange={(event) => setScheduledFor(event.target.value)}
              />
            </Field>

            <Field label="Notas editoriales">
              <Textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                rows={5}
                placeholder="Contexto, enfoque, recursos pendientes o instrucciones para el equipo…"
              />
            </Field>
          </fieldset>

          {(validationError || error) && (
            <div
              role="alert"
              className="rounded-xl border border-destructive/25 bg-destructive/8 px-4 py-3 text-sm text-destructive"
            >
              {validationError ?? error}
            </div>
          )}
        </form>

        {item && canWrite && item.status !== "PUBLISHED" && item.status !== "ARCHIVED" && (
          <section className="space-y-3 border-t border-border pt-5">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Acciones de programación</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Guarda primero los cambios generales o programa directamente con la fecha seleccionada.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              className="w-full"
              disabled={busy || !scheduledFor}
              onClick={() => scheduledFor && onSchedule(item, new Date(scheduledFor).toISOString())}
            >
              <CalendarClock className="h-4 w-4" />
              Guardar y programar
            </Button>
          </section>
        )}

        {item && canWrite && item.status !== "PUBLISHED" && item.status !== "ARCHIVED" && (
          <section className="space-y-3 border-t border-border pt-5">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Confirmar publicación manual</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Usa esta acción cuando el contenido ya esté publicado y tengas su enlace público.
              </p>
            </div>
            <Field label="URL de la publicación">
              <Input
                type="url"
                value={publicationUrl}
                onChange={(event) => setPublicationUrl(event.target.value)}
                placeholder="https://…"
              />
            </Field>
            <Button
              type="button"
              variant="outline"
              className="w-full"
              disabled={busy || !publicationUrl}
              onClick={() => onPublish(item, publicationUrl)}
            >
              <CheckCircle2 className="h-4 w-4" />
              Marcar como publicado
            </Button>
          </section>
        )}

        {item && (
          <section className="space-y-3 border-t border-border pt-5">
            <h3 className="text-sm font-semibold text-foreground">Publicación relacionada</h3>
            {publication ? (
              <Button asChild variant="outline" className="w-full">
                <Link href={`/publishing/${publication.id}`}>
                  <Send className="h-4 w-4" />
                  Abrir publicación
                  <ExternalLink className="ml-auto h-4 w-4" />
                </Link>
              </Button>
            ) : item.publication_url ? (
              <Button asChild variant="outline" className="w-full">
                <a href={item.publication_url} target="_blank" rel="noreferrer">
                  Ver publicación externa
                  <ExternalLink className="ml-auto h-4 w-4" />
                </a>
              </Button>
            ) : (
              <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
                Todavía no existe una publicación vinculada.
              </p>
            )}
          </section>
        )}

        {item && canWrite && item.status !== "PUBLISHED" && item.status !== "ARCHIVED" && (
          <section className="border-t border-border pt-5">
            <Button
              type="button"
              variant="ghost"
              className="w-full text-destructive hover:bg-destructive/10 hover:text-destructive"
              disabled={busy}
              onClick={() => onCancel(item)}
            >
              <Trash2 className="h-4 w-4" />
              Cancelar elemento
            </Button>
          </section>
        )}
      </div>
    </Drawer>
  );
}

function Field({
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
      <span className="font-medium text-foreground">{label}</span>
      {children}
      {hint && <span className="block text-xs text-muted-foreground">{hint}</span>}
    </label>
  );
}
