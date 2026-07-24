"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import type { Asset, AssetVariant, VariantType } from "@rqt21/contracts";
import { VARIANT_TYPES } from "@rqt21/contracts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth, formatDate } from "@/lib/ui";

export default function AssetDetailPage() {
  const params = useParams<{ id: string }>();
  const assetId = params.id;
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);
  const canDownload = org?.role !== "ANALYST" && org?.role !== "VIEWER";

  const [asset, setAsset] = useState<Asset | null>(null);
  const [variants, setVariants] = useState<AssetVariant[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [signedUrl, setSignedUrl] = useState<string | null>(null);

  const [platform, setPlatform] = useState("INSTAGRAM");
  const [variantType, setVariantType] = useState<VariantType>("STORY");
  const [width, setWidth] = useState("1080");
  const [height, setHeight] = useState("1920");

  const load = useCallback(async () => {
    if (!currentOrgId || !assetId) return;
    setLoading(true);
    setError(null);
    try {
      const [a, v] = await Promise.all([
        api.getAsset(currentOrgId, assetId),
        api.listAssetVariants(currentOrgId, assetId),
      ]);
      setAsset(a);
      setVariants(v);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar el activo");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, assetId]);

  useEffect(() => {
    void load();
  }, [load]);

  const archive = async () => {
    if (!currentOrgId || !assetId) return;
    setBusy(true);
    try {
      await api.archiveAsset(currentOrgId, assetId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al archivar");
    } finally {
      setBusy(false);
    }
  };

  const getDownloadUrl = async () => {
    if (!currentOrgId || !assetId) return;
    setBusy(true);
    setSignedUrl(null);
    try {
      const res = await api.assetDownloadUrl(currentOrgId, assetId);
      setSignedUrl(res.url);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al generar URL firmada");
    } finally {
      setBusy(false);
    }
  };

  const createVariant = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !assetId) return;
    setBusy(true);
    setError(null);
    try {
      await api.createAssetVariant(currentOrgId, assetId, {
        platform,
        variant_type: variantType,
        width: Number(width) || null,
        height: Number(height) || null,
      });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al crear variante");
    } finally {
      setBusy(false);
    }
  };

  if (!currentOrgId) return <p>Selecciona una organización.</p>;
  if (loading && !asset) return <p className="text-sm text-slate-500">Cargando…</p>;
  if (!asset) return <p className="text-sm text-slate-500">Activo no encontrado.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{asset.original_filename}</h1>
        <p className="text-sm text-slate-500">
          {asset.asset_type} · {asset.status} · {(asset.size_bytes / 1024).toFixed(0)} KB · {formatDate(asset.created_at)}
        </p>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-xs text-slate-500">Dimensiones</div>
          <div className="text-sm font-medium text-slate-900">
            {asset.width && asset.height ? `${asset.width}x${asset.height}` : "—"}
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-xs text-slate-500">Duración</div>
          <div className="text-sm font-medium text-slate-900">{asset.duration_seconds ?? "—"}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-xs text-slate-500">Checksum SHA-256</div>
          <div className="truncate text-xs font-mono text-slate-700">{asset.checksum_sha256 || "—"}</div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 text-sm">
        <p><strong>Texto alternativo:</strong> {asset.alt_text || "— (requerido para publicar en Instagram)"}</p>
        <p><strong>Caption:</strong> {asset.caption || "—"}</p>
        {typeof asset.metadata?.duplicate_of === "string" && (
          <p className="text-amber-700">Duplicado de otro activo: {asset.metadata.duplicate_of as string}</p>
        )}
      </div>

      {canWrite && asset.status !== "ARCHIVED" && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void archive()}
            disabled={busy}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-60"
          >
            Archivar
          </button>
          {canDownload && asset.status === "READY" && (
            <button
              type="button"
              onClick={() => void getDownloadUrl()}
              disabled={busy}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-60"
            >
              Generar URL firmada
            </button>
          )}
        </div>
      )}

      {signedUrl && (
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-mono break-all text-slate-700">
          {signedUrl}
        </div>
      )}

      <div className="space-y-3">
        <h2 className="text-lg font-medium text-slate-900">Variantes</h2>
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-500">
              <tr>
                <th className="px-4 py-2 font-medium">Plataforma</th>
                <th className="px-4 py-2 font-medium">Tipo</th>
                <th className="px-4 py-2 font-medium">Dimensiones</th>
                <th className="px-4 py-2 font-medium">Estado</th>
              </tr>
            </thead>
            <tbody>
              {variants.length === 0 && (
                <tr><td colSpan={4} className="px-4 py-4 text-center text-slate-400">Sin variantes</td></tr>
              )}
              {variants.map((v) => (
                <tr key={v.id} className="border-t border-slate-100">
                  <td className="px-4 py-2 text-slate-700">{v.platform}</td>
                  <td className="px-4 py-2 text-slate-600">{v.variant_type}</td>
                  <td className="px-4 py-2 text-slate-500">
                    {v.width && v.height ? `${v.width}x${v.height}` : "—"}
                  </td>
                  <td className="px-4 py-2 text-slate-600">{v.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {canWrite && asset.status === "READY" && (
          <form onSubmit={createVariant} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-medium text-slate-900">Nueva variante (MOCK)</h3>
            <div className="grid gap-3 sm:grid-cols-4">
              <label className="block text-sm">
                <span className="text-slate-700">Plataforma</span>
                <input value={platform} onChange={(e) => setPlatform(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
              </label>
              <label className="block text-sm">
                <span className="text-slate-700">Tipo</span>
                <select value={variantType} onChange={(e) => setVariantType(e.target.value as VariantType)}
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                  {VARIANT_TYPES.map((t) => (<option key={t} value={t}>{t}</option>))}
                </select>
              </label>
              <label className="block text-sm">
                <span className="text-slate-700">Ancho</span>
                <input value={width} onChange={(e) => setWidth(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
              </label>
              <label className="block text-sm">
                <span className="text-slate-700">Alto</span>
                <input value={height} onChange={(e) => setHeight(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
              </label>
            </div>
            <button type="submit" disabled={busy}
              className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-fg disabled:opacity-60">
              Crear variante
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
