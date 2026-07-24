"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type { Brand, Product, ProductStatus } from "@rqt21/contracts";
import { PRODUCT_STATUSES } from "@rqt21/contracts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";

export default function ProductsPage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);

  const [items, setItems] = useState<Product[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [brandId, setBrandId] = useState("");
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [price, setPrice] = useState("");
  const [status, setStatus] = useState<ProductStatus>("DRAFT");
  const [checkout, setCheckout] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [ps, bs] = await Promise.all([
        api.listProducts(currentOrgId),
        api.listBrands(currentOrgId),
      ]);
      setItems(ps);
      setBrands(bs);
      if (!brandId && bs.length > 0) setBrandId(bs[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar productos");
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
      await api.createProduct(currentOrgId, {
        brand_id: brandId,
        name,
        slug,
        price: price || null,
        status,
        checkout_url: checkout || null,
      });
      setName("");
      setSlug("");
      setPrice("");
      setCheckout("");
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Error creando producto");
    } finally {
      setSubmitting(false);
    }
  };

  if (!currentOrgId) return <p>Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Productos</h1>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Nombre</th>
              <th className="px-4 py-2 font-medium">Precio</th>
              <th className="px-4 py-2 font-medium">Estado</th>
              <th className="px-4 py-2 font-medium">Checkout</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-400">Cargando…</td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-400">Sin productos</td>
              </tr>
            )}
            {items.map((p) => (
              <tr key={p.id} className="border-t border-slate-100">
                <td className="px-4 py-2 text-slate-900">{p.name}</td>
                <td className="px-4 py-2 text-slate-600">
                  {p.price ? `${p.price} ${p.currency}` : "—"}
                </td>
                <td className="px-4 py-2 text-slate-600">{p.status}</td>
                <td className="px-4 py-2 text-slate-500 truncate max-w-xs">
                  {p.checkout_url || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {canWrite && brands.length > 0 && (
        <form onSubmit={onCreate} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-medium text-slate-900">Nuevo producto</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-slate-700">Marca</span>
              <select
                value={brandId}
                onChange={(e) => setBrandId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2"
              >
                {brands.map((b) => (
                  <option key={b.id} value={b.id}>{b.name}</option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Nombre</span>
              <input required value={name} onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Slug</span>
              <input required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={slug} onChange={(e) => setSlug(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Precio (USD)</span>
              <input type="number" step="0.01" min="0" value={price} onChange={(e) => setPrice(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Estado</span>
              <select value={status} onChange={(e) => setStatus(e.target.value as ProductStatus)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {PRODUCT_STATUSES.map((s) => (<option key={s} value={s}>{s}</option>))}
              </select>
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="text-slate-700">Checkout URL</span>
              <input type="url" value={checkout} onChange={(e) => setCheckout(e.target.value)}
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
            {submitting ? "Guardando…" : "Crear producto"}
          </button>
        </form>
      )}
    </div>
  );
}
