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

  if (!currentOrgId) return <p>Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Calendario editorial</h1>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-3 text-sm">
        <label>
          <span className="text-slate-600">Estado</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as EditorialStatus | "")}
            className="ml-2 rounded-md border border-slate-300 bg-white px-2 py-1"
          >
            <option value="">Todos</option>
            {EDITORIAL_STATUSES.map((s) => (
              <option key={s} value={s}>{STATUS_LABELS[s]}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="text-slate-600">Plataforma</span>
          <select
            value={platformFilter}
            onChange={(e) => setPlatformFilter(e.target.value as EditorialPlatform | "")}
            className="ml-2 rounded-md border border-slate-300 bg-white px-2 py-1"
          >
            <option value="">Todas</option>
            {EDITORIAL_PLATFORMS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Contenido</th>
              <th className="px-4 py-2 font-medium">Plataforma</th>
              <th className="px-4 py-2 font-medium">Programado</th>
              <th className="px-4 py-2 font-medium">Estado</th>
              <th className="px-4 py-2 font-medium">Prioridad</th>
              <th className="px-4 py-2 font-medium">Publicación</th>
              <th className="px-4 py-2 font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-400">Cargando…</td></tr>
            )}
            {!loading && filtered.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-400">Sin elementos</td></tr>
            )}
            {filtered.map((i) => {
              const content = contents.find((c) => c.id === i.content_item_id);
              const pub = publications.find((p) => p.content_item_id === i.content_item_id);
              return (
                <tr key={i.id} className="border-t border-slate-100">
                  <td className="px-4 py-2 text-slate-900">{content?.title ?? i.content_item_id}</td>
                  <td className="px-4 py-2 text-slate-600">{i.platform}</td>
                  <td className="px-4 py-2 text-slate-500">{formatDate(i.scheduled_for)}</td>
                  <td className="px-4 py-2">
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-700">
                      {STATUS_LABELS[i.status]}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-600">{i.priority}</td>
                  <td className="px-4 py-2">
                    {pub ? (
                      <Link href={`/publishing/${pub.id}`} className="text-brand hover:underline text-xs">
                        {pub.platform} · {pub.status}
                      </Link>
                    ) : (
                      <Link href="/publishing" className="text-xs text-slate-400 hover:text-brand hover:underline">
                        Preparar publicación
                      </Link>
                    )}
                  </td>
                  <td className="px-4 py-2 space-x-2">
                    {canWrite && i.status !== "PUBLISHED" && (
                      <>
                        <button
                          type="button"
                          onClick={() => {
                            const v = window.prompt(
                              "Programar para (ISO, ej. 2026-08-01T15:00:00Z)",
                              i.scheduled_for || "",
                            );
                            if (v) void schedule(i, v);
                          }}
                          className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"
                        >
                          Programar
                        </button>
                        <button
                          type="button"
                          onClick={() => void publish(i)}
                          className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"
                        >
                          Marcar publicado
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {canWrite && brands.length > 0 && contents.length > 0 && (
        <form onSubmit={onCreate} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-medium text-slate-900">Nuevo elemento</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-slate-700">Marca</span>
              <select value={brandId} onChange={(e) => setBrandId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {brands.map((b) => (<option key={b.id} value={b.id}>{b.name}</option>))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Contenido</span>
              <select value={contentId} onChange={(e) => setContentId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {contents.map((c) => (<option key={c.id} value={c.id}>{c.title}</option>))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Plataforma</span>
              <select value={platform} onChange={(e) => setPlatform(e.target.value as EditorialPlatform)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {EDITORIAL_PLATFORMS.map((p) => (<option key={p} value={p}>{p}</option>))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Formato</span>
              <select value={format} onChange={(e) => setFormat(e.target.value as ContentFormat)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {CONTENT_FORMATS.map((f) => (<option key={f} value={f}>{f}</option>))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Estado</span>
              <select value={status} onChange={(e) => setStatus(e.target.value as EditorialStatus)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {EDITORIAL_STATUSES.filter((s) => s !== "ARCHIVED").map((s) => (
                  <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Prioridad</span>
              <select value={priority} onChange={(e) => setPriority(e.target.value as Priority)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {PRIORITIES.map((p) => (<option key={p} value={p}>{p}</option>))}
              </select>
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="text-slate-700">Fecha programada (ISO opcional)</span>
              <input value={scheduledFor} onChange={(e) => setScheduledFor(e.target.value)}
                placeholder="2026-08-01T15:00:00Z"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 font-mono" />
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="text-slate-700">Notas</span>
              <textarea value={notes} onChange={(e) => setNotes(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
          </div>
          {formError && (
            <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {formError}
            </div>
          )}
          <button type="submit" disabled={submitting}
            className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-fg disabled:opacity-60">
            {submitting ? "Guardando…" : "Añadir al calendario"}
          </button>
        </form>
      )}
    </div>
  );
}
