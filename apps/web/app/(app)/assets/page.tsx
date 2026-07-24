"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { Asset, AssetStatus, AssetType, Brand } from "@rqt21/contracts";
import { ASSET_STATUSES, ASSET_TYPES } from "@rqt21/contracts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth, formatDate } from "@/lib/ui";

const STATUS_STYLES: Record<AssetStatus, string> = {
  UPLOADING: "bg-slate-100 text-slate-700 border-slate-200",
  PROCESSING: "bg-amber-50 text-amber-800 border-amber-200",
  READY: "bg-emerald-50 text-emerald-800 border-emerald-200",
  REJECTED: "bg-red-50 text-red-800 border-red-200",
  FAILED: "bg-red-50 text-red-800 border-red-200",
  ARCHIVED: "bg-slate-100 text-slate-500 border-slate-200",
};

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(",")[1] ?? "");
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export default function AssetsPage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);

  const [items, setItems] = useState<Asset[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [typeFilter, setTypeFilter] = useState<AssetType | "">("");
  const [statusFilter, setStatusFilter] = useState<AssetStatus | "">("");

  const [file, setFile] = useState<File | null>(null);
  const [brandId, setBrandId] = useState("");
  const [altText, setAltText] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (typeFilter) params.asset_type = typeFilter;
      if (statusFilter) params.status = statusFilter;
      const [a, bs] = await Promise.all([
        api.listAssets(currentOrgId, params),
        api.listBrands(currentOrgId),
      ]);
      setItems(a);
      setBrands(bs);
      if (!brandId && bs.length > 0) setBrandId(bs[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar activos");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, typeFilter, statusFilter, brandId]);

  useEffect(() => {
    void load();
  }, [load]);

  const detectType = (f: File): AssetType => {
    if (f.type.startsWith("image/")) return "IMAGE";
    if (f.type.startsWith("video/")) return "VIDEO";
    if (f.type.startsWith("audio/")) return "AUDIO";
    if (f.type === "application/pdf") return "DOCUMENT";
    return "OTHER";
  };

  const onUpload = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const init = await api.initUpload(currentOrgId, {
        filename: file.name,
        mime_type: file.type || "application/octet-stream",
        size_bytes: file.size,
        asset_type: detectType(file),
        brand_id: brandId || null,
        alt_text: altText || null,
      });
      const content_base64 = await fileToBase64(file);
      await api.completeUpload(currentOrgId, { asset_id: init.asset_id, content_base64 });
      setFile(null);
      setAltText("");
      await load();
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.detail : "Error al subir el activo");
    } finally {
      setUploading(false);
    }
  };

  if (!currentOrgId) return <p>Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Biblioteca de activos</h1>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-3 text-sm">
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as AssetType | "")}
          className="rounded-md border border-slate-300 bg-white px-2 py-1"
        >
          <option value="">Todos los tipos</option>
          {ASSET_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as AssetStatus | "")}
          className="rounded-md border border-slate-300 bg-white px-2 py-1"
        >
          <option value="">Todos los estados</option>
          {ASSET_STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Archivo</th>
              <th className="px-4 py-2 font-medium">Tipo</th>
              <th className="px-4 py-2 font-medium">Estado</th>
              <th className="px-4 py-2 font-medium">Tamaño</th>
              <th className="px-4 py-2 font-medium">Subido</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">Cargando…</td></tr>
            )}
            {!loading && items.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">Sin activos</td></tr>
            )}
            {items.map((a) => (
              <tr key={a.id} className="border-t border-slate-100">
                <td className="px-4 py-2">
                  <Link href={`/assets/${a.id}`} className="text-brand hover:underline">
                    {a.original_filename}
                  </Link>
                  {!a.alt_text && a.asset_type === "IMAGE" && (
                    <span className="ml-2 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-800">
                      sin alt text
                    </span>
                  )}
                </td>
                <td className="px-4 py-2 text-slate-600">{a.asset_type}</td>
                <td className="px-4 py-2">
                  <span className={`rounded-full border px-2 py-0.5 text-xs ${STATUS_STYLES[a.status]}`}>
                    {a.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-slate-500">{(a.size_bytes / 1024).toFixed(0)} KB</td>
                <td className="px-4 py-2 text-slate-500">{formatDate(a.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {canWrite && (
        <form onSubmit={onUpload} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-medium text-slate-900">Subir activo (simulado, MOCK)</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-slate-700">Marca</span>
              <select
                value={brandId}
                onChange={(e) => setBrandId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2"
              >
                <option value="">Sin marca</option>
                {brands.map((b) => (
                  <option key={b.id} value={b.id}>{b.name}</option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Archivo</span>
              <input
                type="file"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="mt-1 w-full text-sm"
              />
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="text-slate-700">Texto alternativo (obligatorio para imágenes en publicaciones)</span>
              <input
                value={altText}
                onChange={(e) => setAltText(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
          </div>
          {uploadError && (
            <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {uploadError}
            </div>
          )}
          <button
            type="submit"
            disabled={uploading || !file}
            className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-fg disabled:opacity-60"
          >
            {uploading ? "Subiendo…" : "Subir"}
          </button>
        </form>
      )}
    </div>
  );
}
