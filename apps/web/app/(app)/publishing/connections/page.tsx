"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type { Brand, ConnectionStatus, Platform, PublishingConnection, PublishingProviderName } from "@rqt21/contracts";
import { PLATFORMS, PUBLISHING_PROVIDERS } from "@rqt21/contracts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canAdmin, formatDate } from "@/lib/ui";

const STATUS_STYLES: Record<ConnectionStatus, string> = {
  PENDING: "bg-slate-100 text-slate-700 border-slate-200",
  ACTIVE: "bg-emerald-50 text-emerald-800 border-emerald-200",
  EXPIRED: "bg-amber-50 text-amber-800 border-amber-200",
  REVOKED: "bg-red-50 text-red-800 border-red-200",
  ERROR: "bg-red-50 text-red-800 border-red-200",
  DISABLED: "bg-slate-100 text-slate-500 border-slate-200",
};

export default function ConnectionsPage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canManage = canAdmin(org?.role);
  const isViewer = org?.role === "VIEWER";

  const [items, setItems] = useState<PublishingConnection[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [brandId, setBrandId] = useState("");
  const [platform, setPlatform] = useState<Platform>("INSTAGRAM");
  const [provider, setProvider] = useState<PublishingProviderName>("MOCK");
  const [accountName, setAccountName] = useState("");
  const [externalAccountId, setExternalAccountId] = useState("");
  const [token, setToken] = useState("");
  const [useBaseToken, setUseBaseToken] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId || isViewer) return;
    setLoading(true);
    setError(null);
    try {
      const [c, bs] = await Promise.all([
        api.listConnections(currentOrgId),
        api.listBrands(currentOrgId),
      ]);
      setItems(c);
      setBrands(bs);
      if (!brandId && bs.length > 0) setBrandId(bs[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar conexiones");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, isViewer, brandId]);

  useEffect(() => {
    void load();
  }, [load]);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !brandId) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await api.createConnection(currentOrgId, {
        brand_id: brandId,
        platform,
        provider,
        account_name: accountName,
        external_account_id: externalAccountId || null,
        credentials:
          provider === "MANUAL" || !token
            ? null
            : useBaseToken && provider === "META"
              ? { base_access_token: token }
              : { access_token: token },
      });
      setAccountName("");
      setExternalAccountId("");
      setToken("");
      setUseBaseToken(false);
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Error creando conexión");
    } finally {
      setSubmitting(false);
    }
  };

  const act = async (id: string, action: "verify" | "revoke" | "disable") => {
    if (!currentOrgId) return;
    setBusyId(id);
    setError(null);
    try {
      if (action === "verify") await api.verifyConnection(currentOrgId, id);
      if (action === "revoke") await api.revokeConnection(currentOrgId, id);
      if (action === "disable") await api.disableConnection(currentOrgId, id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error");
    } finally {
      setBusyId(null);
    }
  };

  if (!currentOrgId) return <p>Selecciona una organización.</p>;
  if (isViewer) {
    return (
      <p className="text-sm text-slate-500">
        Tu rol (VIEWER) no tiene acceso a las conexiones de publicación.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Conexiones de publicación</h1>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Cuenta</th>
              <th className="px-4 py-2 font-medium">Plataforma</th>
              <th className="px-4 py-2 font-medium">Proveedor</th>
              <th className="px-4 py-2 font-medium">Estado</th>
              <th className="px-4 py-2 font-medium">Últimos 4 (solo OWNER/ADMIN)</th>
              <th className="px-4 py-2 font-medium">Verificado</th>
              {canManage && <th className="px-4 py-2 font-medium">Acciones</th>}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-400">Cargando…</td></tr>
            )}
            {!loading && items.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-400">Sin conexiones</td></tr>
            )}
            {items.map((c) => (
              <tr key={c.id} className="border-t border-slate-100">
                <td className="px-4 py-2 text-slate-900">{c.account_name}</td>
                <td className="px-4 py-2 text-slate-600">{c.platform}</td>
                <td className="px-4 py-2 text-slate-600">{c.provider}</td>
                <td className="px-4 py-2">
                  <span className={`rounded-full border px-2 py-0.5 text-xs ${STATUS_STYLES[c.status]}`}>
                    {c.status}
                  </span>
                </td>
                <td className="px-4 py-2 font-mono text-xs text-slate-500">
                  {c.credentials_last_four ? `••••${c.credentials_last_four}` : "—"}
                </td>
                <td className="px-4 py-2 text-slate-500">{formatDate(c.last_verified_at)}</td>
                {canManage && (
                  <td className="px-4 py-2 space-x-2">
                    <button type="button" disabled={busyId === c.id}
                      onClick={() => void act(c.id, "verify")}
                      className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-60">
                      Verificar
                    </button>
                    {c.status !== "REVOKED" && (
                      <button type="button" disabled={busyId === c.id}
                        onClick={() => void act(c.id, "revoke")}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-60">
                        Revocar
                      </button>
                    )}
                    {c.status !== "DISABLED" && (
                      <button type="button" disabled={busyId === c.id}
                        onClick={() => void act(c.id, "disable")}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-60">
                        Deshabilitar
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {canManage && brands.length > 0 && (
        <form onSubmit={onCreate} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-medium text-slate-900">Nueva conexión</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-slate-700">Marca</span>
              <select value={brandId} onChange={(e) => setBrandId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {brands.map((b) => (<option key={b.id} value={b.id}>{b.name}</option>))}
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
              <span className="text-slate-700">Proveedor</span>
              <select value={provider} onChange={(e) => setProvider(e.target.value as PublishingProviderName)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {PUBLISHING_PROVIDERS.map((p) => (<option key={p} value={p}>{p}</option>))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Nombre de cuenta</span>
              <input value={accountName} onChange={(e) => setAccountName(e.target.value)} required
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            {provider !== "MANUAL" && provider !== "MOCK" && (
              <label className="block text-sm">
                <span className="text-slate-700">
                  ID de cuenta externa {provider === "META" && "(ID de página de Facebook o de cuenta de Instagram)"}
                </span>
                <input value={externalAccountId} onChange={(e) => setExternalAccountId(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
              </label>
            )}
            {provider !== "MANUAL" && (
              <label className="block text-sm sm:col-span-2">
                <span className="text-slate-700">
                  {provider === "META" && useBaseToken
                    ? "Token base (System User de Business Manager, se cifra en el servidor)"
                    : "Token de acceso (se cifra en el servidor)"}
                </span>
                <input value={token} onChange={(e) => setToken(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
              </label>
            )}
            {provider === "META" && (
              <label className="flex items-center gap-2 text-sm sm:col-span-2">
                <input type="checkbox" checked={useBaseToken}
                  onChange={(e) => setUseBaseToken(e.target.checked)}
                  className="rounded border-slate-300" />
                <span className="text-slate-700">
                  Es un token base de larga duración (System User) — RQT21 resolverá un token
                  de página fresco automáticamente en cada publicación, en vez de depender de un
                  token de página estático.
                </span>
              </label>
            )}
          </div>
          {formError && (
            <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {formError}
            </div>
          )}
          <button type="submit" disabled={submitting}
            className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-fg disabled:opacity-60">
            {submitting ? "Creando…" : "Crear conexión"}
          </button>
        </form>
      )}
    </div>
  );
}
