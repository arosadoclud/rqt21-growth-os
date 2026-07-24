"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type {
  Brand,
  Campaign,
  ContentItem,
  Product,
  TrackingLink,
} from "@rqt21/contracts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";

export default function TrackingLinksPage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);

  const [items, setItems] = useState<TrackingLink[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [contents, setContents] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [brandId, setBrandId] = useState("");
  const [productId, setProductId] = useState("");
  const [campaignId, setCampaignId] = useState("");
  const [contentId, setContentId] = useState("");
  const [destination, setDestination] = useState("");
  const [utmSource, setUtmSource] = useState("");
  const [utmMedium, setUtmMedium] = useState("social");
  const [utmCampaign, setUtmCampaign] = useState("");
  const [utmContent, setUtmContent] = useState("");
  const [utmTerm, setUtmTerm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [links, bs, ps, camps, cs] = await Promise.all([
        api.listTrackingLinks(currentOrgId),
        api.listBrands(currentOrgId),
        api.listProducts(currentOrgId),
        api.listCampaigns(currentOrgId),
        api.listContent(currentOrgId),
      ]);
      setItems(links);
      setBrands(bs);
      setProducts(ps);
      setCampaigns(camps);
      setContents(cs);
      if (!brandId && bs.length > 0) setBrandId(bs[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar enlaces");
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
      await api.createTrackingLink(currentOrgId, {
        brand_id: brandId,
        product_id: productId || null,
        campaign_id: campaignId || null,
        content_id: contentId || null,
        destination_url: destination,
        utm_source: utmSource || null,
        utm_medium: utmMedium || null,
        utm_campaign: utmCampaign || null,
        utm_content: utmContent || null,
        utm_term: utmTerm || null,
      });
      setDestination("");
      setUtmSource("");
      setUtmCampaign("");
      setUtmContent("");
      setUtmTerm("");
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Error creando enlace");
    } finally {
      setSubmitting(false);
    }
  };

  const copy = (text: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      void navigator.clipboard.writeText(text);
    }
  };

  const toggleActive = async (link: TrackingLink) => {
    if (!currentOrgId) return;
    try {
      await api.updateTrackingLink(currentOrgId, link.id, {
        is_active: !link.is_active,
      });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error");
    }
  };

  if (!currentOrgId) return <p>Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Enlaces rastreables</h1>
      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Código</th>
              <th className="px-4 py-2 font-medium">URL corta</th>
              <th className="px-4 py-2 font-medium">Estado</th>
              <th className="px-4 py-2 font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {loading && (<tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">Cargando…</td></tr>)}
            {!loading && items.length === 0 && (<tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">Sin enlaces</td></tr>)}
            {items.map((l) => (
              <tr key={l.id} className="border-t border-slate-100 align-top">
                <td className="px-4 py-2 font-mono text-slate-900">{l.short_code}</td>
                <td className="px-4 py-2 text-slate-600">
                  <div className="truncate max-w-md">{l.short_url}</div>
                  <div className="mt-1 truncate max-w-md text-xs text-slate-400">{l.final_url}</div>
                </td>
                <td className="px-4 py-2 text-slate-600">
                  {l.is_active ? "activo" : "inactivo"}
                </td>
                <td className="px-4 py-2 space-x-2">
                  <button type="button" onClick={() => copy(l.short_url)}
                    className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50">
                    Copiar
                  </button>
                  {canWrite && (
                    <button type="button" onClick={() => void toggleActive(l)}
                      className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50">
                      {l.is_active ? "Desactivar" : "Reactivar"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {canWrite && brands.length > 0 && (
        <form onSubmit={onCreate} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-medium text-slate-900">Nuevo enlace</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-slate-700">Marca</span>
              <select value={brandId} onChange={(e) => setBrandId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {brands.map((b) => (<option key={b.id} value={b.id}>{b.name}</option>))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Producto</span>
              <select value={productId} onChange={(e) => setProductId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                <option value="">—</option>
                {products.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Campaña</span>
              <select value={campaignId} onChange={(e) => setCampaignId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                <option value="">—</option>
                {campaigns.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Contenido</span>
              <select value={contentId} onChange={(e) => setContentId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                <option value="">—</option>
                {contents.map((c) => (<option key={c.id} value={c.id}>{c.title}</option>))}
              </select>
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="text-slate-700">URL destino</span>
              <input required type="url" value={destination} onChange={(e) => setDestination(e.target.value)}
                placeholder="https://checkout.example.com/…"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">utm_source</span>
              <input value={utmSource} onChange={(e) => setUtmSource(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">utm_medium</span>
              <input value={utmMedium} onChange={(e) => setUtmMedium(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">utm_campaign</span>
              <input value={utmCampaign} onChange={(e) => setUtmCampaign(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">utm_content</span>
              <input value={utmContent} onChange={(e) => setUtmContent(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="text-slate-700">utm_term</span>
              <input value={utmTerm} onChange={(e) => setUtmTerm(e.target.value)}
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
            {submitting ? "Guardando…" : "Generar enlace"}
          </button>
        </form>
      )}
    </div>
  );
}
