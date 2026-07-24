"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type { Brand } from "@rqt21/contracts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth, formatDate } from "@/lib/ui";

export default function BrandsPage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);

  const [items, setItems] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [website, setWebsite] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      setItems(await api.listBrands(currentOrgId));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar marcas");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await api.createBrand(currentOrgId, {
        name,
        slug,
        website_url: website || null,
      });
      setName("");
      setSlug("");
      setWebsite("");
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Error creando marca");
    } finally {
      setSubmitting(false);
    }
  };

  if (!currentOrgId) return <p>Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Marcas</h1>

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
              <th className="px-4 py-2 font-medium">Slug</th>
              <th className="px-4 py-2 font-medium">Estado</th>
              <th className="px-4 py-2 font-medium">Creada</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                  Cargando…
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                  Sin marcas
                </td>
              </tr>
            )}
            {items.map((b) => (
              <tr key={b.id} className="border-t border-slate-100">
                <td className="px-4 py-2 text-slate-900">{b.name}</td>
                <td className="px-4 py-2 text-slate-600">{b.slug}</td>
                <td className="px-4 py-2">
                  <span
                    className={
                      b.is_active
                        ? "rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-800"
                        : "rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                    }
                  >
                    {b.is_active ? "activa" : "inactiva"}
                  </span>
                </td>
                <td className="px-4 py-2 text-slate-500">{formatDate(b.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {canWrite ? (
        <form
          onSubmit={onCreate}
          className="space-y-3 rounded-xl border border-slate-200 bg-white p-4"
        >
          <h2 className="text-lg font-medium text-slate-900">Nueva marca</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-slate-700">Nombre</span>
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Slug</span>
              <input
                required
                pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="text-slate-700">Sitio web</span>
              <input
                type="url"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                placeholder="https://…"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
          </div>
          {formError && (
            <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {formError}
            </div>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-fg disabled:opacity-60"
          >
            {submitting ? "Guardando…" : "Crear marca"}
          </button>
        </form>
      ) : (
        <p className="text-sm text-slate-500">
          Tu rol no permite crear marcas.
        </p>
      )}
    </div>
  );
}
