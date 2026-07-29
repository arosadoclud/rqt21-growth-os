"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth, formatDate } from "@/lib/ui";

const STATUS_LABELS: Record<EditorialStatus, string> = {
  IDEA: "Idea",
  DRAFT: "Borrador",
  IN_REVIEW: "En revisión",
  NEEDS_REVISION: "Requiere cambios",
  APPROVED: "Aprobado",
  SCHEDULED: "Programado",
  PUBLISHED: "Publicado",
  CANCELLED: "Cancelado",
  ARCHIVED: "Archivado",
};

export default function CalendarPage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);

  const [items, setItems] = useState<EditorialItem[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [contents, setContents] = useState<ContentItem[]>([]);
  const [publications, setPublications] = useState<Publication[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<EditorialStatus | "">("");
  const [platformFilter, setPlatformFilter] = useState<EditorialPlatform | "">("");

  const [brandId, setBrandId] = useState("");
  const [contentId, setContentId] = useState("");
  const [platform, setPlatform] = useState<EditorialPlatform>("INSTAGRAM");
  const [format, setFormat] = useState<ContentFormat>("REEL");
  const [status, setStatus] = useState<EditorialStatus>("IDEA");
  const [priority, setPriority] = useState<Priority>("MEDIUM");
  const [scheduledFor, setScheduledFor] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [it, bs, cs, pubs] = await Promise.all([
        api.listEditorial(currentOrgId),
        api.listBrands(currentOrgId),
        api.listContent(currentOrgId),
        api.listPublications(currentOrgId).catch(() => []),
      ]);
      setItems(it);
      setBrands(bs);
      setContents(cs);
      setPublications(pubs);
      if (!brandId && bs.length > 0) setBrandId(bs[0].id);
      if (!contentId && cs.length > 0) setContentId(cs[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, brandId, contentId]);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(
    () =>
      items.filter(
        (i) =>
          (!statusFilter || i.status === statusFilter) &&
          (!platformFilter || i.platform === platformFilter),
      ),
    [items, statusFilter, platformFilter],
  );

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !brandId || !contentId) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await api.createEditorial(currentOrgId, {
        brand_id: brandId,
        content_item_id: contentId,
        platform,
        content_format: format,
        status,
        priority,
        scheduled_for: scheduledFor || null,
        notes: notes || null,
      });
      setScheduledFor("");
      setNotes("");
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Error creando ítem");
    } finally {
      setSubmitting(false);
    }
  };

  const schedule = async (item: EditorialItem, whenISO: string) => {
    if (!currentOrgId) return;
    try {
      await api.scheduleEditorial(currentOrgId, item.id, {
        scheduled_for: whenISO,
      });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error");
    }
  };

  const publish = async (item: EditorialItem) => {
    if (!currentOrgId) return;
    const url = window.prompt("URL de publicación");
    if (!url) return;
    try {
      await api.markPublished(currentOrgId, item.id, { publication_url: url });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error");
    }
  };

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Calendario editorial</h1>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Estado</span>
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as EditorialStatus | "")}
            className="w-44"
          >
            <option value="">Todos</option>
            {EDITORIAL_STATUSES.map((s) => (
              <option key={s} value={s}>{STATUS_LABELS[s]}</option>
            ))}
          </Select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Plataforma</span>
          <Select
            value={platformFilter}
            onChange={(e) => setPlatformFilter(e.target.value as EditorialPlatform | "")}
            className="w-44"
          >
            <option value="">Todas</option>
            {EDITORIAL_PLATFORMS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </Select>
        </label>
      </div>

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Contenido</TableHead>
              <TableHead>Plataforma</TableHead>
              <TableHead>Programado</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Prioridad</TableHead>
              <TableHead>Publicación</TableHead>
              <TableHead>Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground">Cargando…</TableCell></TableRow>
            )}
            {!loading && filtered.length === 0 && (
              <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground">Sin elementos</TableCell></TableRow>
            )}
            {filtered.map((i) => {
              const content = contents.find((c) => c.id === i.content_item_id);
              const pub = publications.find((p) => p.content_item_id === i.content_item_id);
              return (
                <TableRow key={i.id}>
                  <TableCell className="font-medium">{content?.title ?? i.content_item_id}</TableCell>
                  <TableCell className="text-muted-foreground">{i.platform}</TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(i.scheduled_for)}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{STATUS_LABELS[i.status]}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{i.priority}</TableCell>
                  <TableCell>
                    {pub ? (
                      <Link href={`/publishing/${pub.id}`} className="text-xs text-primary hover:underline">
                        {pub.platform} · {pub.status}
                      </Link>
                    ) : (
                      <Link href="/publishing" className="text-xs text-muted-foreground hover:text-primary hover:underline">
                        Preparar publicación
                      </Link>
                    )}
                  </TableCell>
                  <TableCell>
                    {canWrite && i.status !== "PUBLISHED" && (
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            const v = window.prompt(
                              "Programar para (ISO, ej. 2026-08-01T15:00:00Z)",
                              i.scheduled_for || "",
                            );
                            if (v) void schedule(i, v);
                          }}
                        >
                          Programar
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => void publish(i)}>
                          Marcar publicado
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>

      {canWrite && brands.length > 0 && contents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle id="new-calendar-item-title" className="text-foreground text-lg">
              Nuevo elemento
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={onCreate}
              className="space-y-4"
              aria-labelledby="new-calendar-item-title"
            >
              <span className="sr-only">Nuevo elemento</span>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-sm">
                  <span className="text-muted-foreground">Marca</span>
                  <Select value={brandId} onChange={(e) => setBrandId(e.target.value)} className="mt-1">
                    {brands.map((b) => (<option key={b.id} value={b.id}>{b.name}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Contenido</span>
                  <Select value={contentId} onChange={(e) => setContentId(e.target.value)} className="mt-1">
                    {contents.map((c) => (<option key={c.id} value={c.id}>{c.title}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Plataforma</span>
                  <Select value={platform} onChange={(e) => setPlatform(e.target.value as EditorialPlatform)} className="mt-1">
                    {EDITORIAL_PLATFORMS.map((p) => (<option key={p} value={p}>{p}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Formato</span>
                  <Select value={format} onChange={(e) => setFormat(e.target.value as ContentFormat)} className="mt-1">
                    {CONTENT_FORMATS.map((f) => (<option key={f} value={f}>{f}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Estado</span>
                  <Select value={status} onChange={(e) => setStatus(e.target.value as EditorialStatus)} className="mt-1">
                    {EDITORIAL_STATUSES.filter((s) => s !== "ARCHIVED").map((s) => (
                      <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                    ))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Prioridad</span>
                  <Select value={priority} onChange={(e) => setPriority(e.target.value as Priority)} className="mt-1">
                    {PRIORITIES.map((p) => (<option key={p} value={p}>{p}</option>))}
                  </Select>
                </label>
                <label className="block text-sm sm:col-span-2">
                  <span className="text-muted-foreground">Fecha programada (ISO opcional)</span>
                  <Input value={scheduledFor} onChange={(e) => setScheduledFor(e.target.value)}
                    placeholder="2026-08-01T15:00:00Z" className="mt-1 font-mono" />
                </label>
                <label className="block text-sm sm:col-span-2">
                  <span className="text-muted-foreground">Notas</span>
                  <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} className="mt-1" />
                </label>
              </div>
              {formError && (
                <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </div>
              )}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Guardando…" : "Añadir al calendario"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
