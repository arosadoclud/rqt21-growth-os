"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type {
  Brand,
  Campaign,
  ContentItem,
  ContentType,
  Platform,
} from "@rqt21/contracts";
import { CONTENT_TYPES, PLATFORMS } from "@rqt21/contracts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";

export default function ContentPage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);

  const [items, setItems] = useState<ContentItem[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [brandId, setBrandId] = useState("");
  const [campaignId, setCampaignId] = useState("");
  const [title, setTitle] = useState("");
  const [hook, setHook] = useState("");
  const [contentType, setContentType] = useState<ContentType>("REEL");
  const [platform, setPlatform] = useState<Platform>("INSTAGRAM");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [cs, bs, camps] = await Promise.all([
        api.listContent(currentOrgId),
        api.listBrands(currentOrgId),
        api.listCampaigns(currentOrgId),
      ]);
      setItems(cs);
      setBrands(bs);
      setCampaigns(camps);
      if (!brandId && bs.length > 0) setBrandId(bs[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar contenidos");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, brandId]);

  useEffect(() => {
    void load();
  }, [load]);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !brandId) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await api.createContent(currentOrgId, {
        brand_id: brandId,
        campaign_id: campaignId || null,
        title,
        hook: hook || null,
        content_type: contentType,
        platform,
      });
      setTitle("");
      setHook("");
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Error creando contenido");
    } finally {
      setSubmitting(false);
    }
  };

  if (!currentOrgId) return <p>Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Contenidos</h1>
      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Título</th>
              <th className="px-4 py-2 font-medium">Tipo</th>
              <th className="px-4 py-2 font-medium">Plataforma</th>
              <th className="px-4 py-2 font-medium">Estado</th>
            </tr>
          </thead>
          <tbody>
            {loading && (<tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">Cargando…</td></tr>)}
            {!loading && items.length === 0 && (<tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">Sin contenidos</td></tr>)}
            {items.map((c) => (
              <tr key={c.id} className="border-t border-slate-100">
                <td className="px-4 py-2 text-slate-900">{c.title}</td>
                <td className="px-4 py-2 text-slate-600">{c.content_type}</td>
                <td className="px-4 py-2 text-slate-600">{c.platform}</td>
                <td className="px-4 py-2 text-slate-600">{c.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {canWrite && brands.length > 0 && (
        <form onSubmit={onCreate} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-medium text-slate-900">Nuevo contenido</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-slate-700">Marca</span>
              <select value={brandId} onChange={(e) => setBrandId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {brands.map((b) => (<option key={b.id} value={b.id}>{b.name}</option>))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Campaña (opcional)</span>
              <select value={campaignId} onChange={(e) => setCampaignId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                <option value="">— sin campaña —</option>
                {campaigns.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
              </select>
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="text-slate-700">Título</span>
              <input required value={title} onChange={(e) => setTitle(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="text-slate-700">Gancho</span>
              <input value={hook} onChange={(e) => setHook(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Tipo</span>
              <select value={contentType} onChange={(e) => setContentType(e.target.value as ContentType)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {CONTENT_TYPES.map((c) => (<option key={c} value={c}>{c}</option>))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Plataforma</span>
              <select value={platform} onChange={(e) => setPlatform(e.target.value as Platform)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {PLATFORMS.map((p) => (<option key={p} value={p}>{p}</option>))}
              </select>
            </label>
          </div>
          {formError && (
            <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {formError}
            </div>
          )}
          <button type="submit" disabled={submitting}
            className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-fg disabled:opacity-60">
            {submitting ? "Guardando…" : "Crear contenido"}
          </button>
        </form>
      )}
    </div>
  );
}
