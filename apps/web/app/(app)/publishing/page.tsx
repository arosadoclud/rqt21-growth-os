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
import { PLATFORMS, PUBLICATION_STATUSES, PUBLICATION_TYPES } from "@rqt21/contracts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth, formatDate } from "@/lib/ui";

const STATUS_STYLES: Record<PublicationStatus, string> = {
  DRAFT: "bg-slate-100 text-slate-700 border-slate-200",
  READY: "bg-blue-50 text-blue-800 border-blue-200",
  SCHEDULED: "bg-indigo-50 text-indigo-800 border-indigo-200",
  PUBLISHING: "bg-amber-50 text-amber-800 border-amber-200",
  PUBLISHED: "bg-emerald-50 text-emerald-800 border-emerald-200",
  FAILED: "bg-red-50 text-red-800 border-red-200",
  RETRY_SCHEDULED: "bg-amber-50 text-amber-800 border-amber-200",
  CANCELLED: "bg-slate-100 text-slate-500 border-slate-200",
  ARCHIVED: "bg-slate-100 text-slate-500 border-slate-200",
};

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

  const [brandId, setBrandId] = useState("");
  const [contentId, setContentId] = useState("");
  const [connectionId, setConnectionId] = useState("");
  const [assetId, setAssetId] = useState("");
  const [platform, setPlatform] = useState<Platform>("INSTAGRAM");
  const [pubType, setPubType] = useState<PublicationType>("POST");
  const [caption, setCaption] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

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
      if (!contentId && cs.length > 0) setContentId(cs[0].id);
      if (!connectionId && conns.length > 0) setConnectionId(conns[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar publicaciones");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, statusFilter, brandId, contentId, connectionId]);

  useEffect(() => {
    void load();
  }, [load]);

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
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Error creando publicación");
    } finally {
      setSubmitting(false);
    }
  };

  if (!currentOrgId) return <p>Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Publicaciones</h1>
        <Link href="/publishing/connections" className="text-sm text-brand hover:underline">
          Gestionar conexiones →
        </Link>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
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

      <div className="flex flex-wrap gap-3 text-sm">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as PublicationStatus | "")}
          className="rounded-md border border-slate-300 bg-white px-2 py-1"
        >
          <option value="">Todos los estados</option>
          {PUBLICATION_STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Contenido</th>
              <th className="px-4 py-2 font-medium">Plataforma</th>
              <th className="px-4 py-2 font-medium">Estado</th>
              <th className="px-4 py-2 font-medium">Programada</th>
              <th className="px-4 py-2 font-medium">Intentos</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">Cargando…</td></tr>
            )}
            {!loading && items.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">Sin publicaciones</td></tr>
            )}
            {items.map((p) => {
              const content = contents.find((c) => c.id === p.content_item_id);
              return (
                <tr key={p.id} className="border-t border-slate-100">
                  <td className="px-4 py-2">
                    <Link href={`/publishing/${p.id}`} className="text-brand hover:underline">
                      {content?.title ?? p.public_id}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-slate-600">{p.platform}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full border px-2 py-0.5 text-xs ${STATUS_STYLES[p.status]}`}>
                      {p.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-500">{formatDate(p.scheduled_for)}</td>
                  <td className="px-4 py-2 text-slate-500">{p.attempt_count}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {canWrite && brands.length > 0 && contents.length > 0 && connections.length > 0 && (
        <form onSubmit={onCreate} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-medium text-slate-900">Preparar publicación</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-slate-700">Marca</span>
              <select value={brandId} onChange={(e) => setBrandId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {brands.map((b) => (<option key={b.id} value={b.id}>{b.name}</option>))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Contenido aprobado</span>
              <select value={contentId} onChange={(e) => setContentId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {contents.map((c) => (<option key={c.id} value={c.id}>{c.title}</option>))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Conexión</span>
              <select value={connectionId} onChange={(e) => setConnectionId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {connections.map((c) => (
                  <option key={c.id} value={c.id}>{c.account_name} ({c.provider})</option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Activo (READY)</span>
              <select value={assetId} onChange={(e) => setAssetId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                <option value="">Sin activo</option>
                {assets.map((a) => (<option key={a.id} value={a.id}>{a.original_filename}</option>))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Plataforma</span>
              <select value={platform} onChange={(e) => setPlatform(e.target.value as Platform)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {PLATFORMS.map((p) => (<option key={p} value={p}>{p}</option>))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Tipo</span>
              <select value={pubType} onChange={(e) => setPubType(e.target.value as PublicationType)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {PUBLICATION_TYPES.map((t) => (<option key={t} value={t}>{t}</option>))}
              </select>
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="text-slate-700">Caption</span>
              <textarea value={caption} onChange={(e) => setCaption(e.target.value)}
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
            {submitting ? "Guardando…" : "Crear borrador"}
          </button>
        </form>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value?: number | string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">
        {value === undefined || value === null ? "—" : value}
      </div>
    </div>
  );
}
