"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link2, Plus, ShieldCheck } from "lucide-react";
import type { Brand, ConnectionStatus, Platform, PublishingConnection, PublishingProviderName } from "@rqt21/contracts";
import { PLATFORMS, PUBLISHING_PROVIDERS } from "@rqt21/contracts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canAdmin, formatDate } from "@/lib/ui";

const STATUS_VARIANT: Record<ConnectionStatus, "secondary" | "success" | "warning" | "destructive"> = {
  PENDING: "secondary",
  ACTIVE: "success",
  EXPIRED: "warning",
  REVOKED: "destructive",
  ERROR: "destructive",
  DISABLED: "secondary",
};

const STATUS_LABEL: Record<ConnectionStatus, string> = {
  PENDING: "Pendiente de verificar",
  ACTIVE: "Activa",
  EXPIRED: "Token expirado",
  REVOKED: "Revocada",
  ERROR: "Error",
  DISABLED: "Deshabilitada",
};

const PLATFORM_META: Record<string, { label: string; glyph: string; accent: string }> = {
  FACEBOOK: { label: "Facebook", glyph: "f", accent: "text-blue-500 bg-blue-500/10" },
  INSTAGRAM: { label: "Instagram", glyph: "IG", accent: "text-fuchsia-500 bg-fuchsia-500/10" },
};

function platformMeta(platform: string) {
  return PLATFORM_META[platform] ?? { label: platform, glyph: "•", accent: "text-muted-foreground bg-muted" };
}

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
  const [showForm, setShowForm] = useState(false);

  const [brandId, setBrandId] = useState("");
  const [platform, setPlatform] = useState<Platform>("INSTAGRAM");
  const [provider, setProvider] = useState<PublishingProviderName>("MOCK");
  const [accountName, setAccountName] = useState("");
  const [externalAccountId, setExternalAccountId] = useState("");
  const [token, setToken] = useState("");
  const [useBaseToken, setUseBaseToken] = useState(false);
  const [pageId, setPageId] = useState("");
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

  const brandName = (id: string) => brands.find((b) => b.id === id)?.name ?? "—";

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
              ? {
                  base_access_token: token,
                  ...(platform === "INSTAGRAM" && pageId ? { page_id: pageId } : {}),
                }
              : { access_token: token },
      });
      setAccountName("");
      setExternalAccountId("");
      setToken("");
      setUseBaseToken(false);
      setPageId("");
      setShowForm(false);
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

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;
  if (isViewer) {
    return (
      <p className="text-sm text-muted-foreground">
        Tu rol (VIEWER) no tiene acceso a las conexiones de publicación.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Cuentas de Facebook e Instagram</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Todas las cuentas conectadas a esta licencia. Cada marca puede tener su propia
            página de Facebook y su propia cuenta de Instagram — agrégalas aquí para poder
            publicar y generar contenido dirigido a ellas.
          </p>
        </div>
        {canManage && brands.length > 0 && (
          <Button onClick={() => setShowForm((v) => !v)} className="gap-1.5">
            <Plus className="h-4 w-4" />
            {showForm ? "Cerrar" : "Agregar cuenta"}
          </Button>
        )}
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {canManage && showForm && brands.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground text-lg">Agregar cuenta</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onCreate} className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-sm">
                  <span className="text-muted-foreground">Marca</span>
                  <Select value={brandId} onChange={(e) => setBrandId(e.target.value)} className="mt-1">
                    {brands.map((b) => (<option key={b.id} value={b.id}>{b.name}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Plataforma</span>
                  <Select value={platform} onChange={(e) => setPlatform(e.target.value as Platform)} className="mt-1">
                    {PLATFORMS.map((p) => (<option key={p} value={p}>{platformMeta(p).label}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Proveedor</span>
                  <Select value={provider} onChange={(e) => setProvider(e.target.value as PublishingProviderName)} className="mt-1">
                    {PUBLISHING_PROVIDERS.map((p) => (<option key={p} value={p}>{p}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">
                    Nombre de la cuenta (para identificarla en la lista)
                  </span>
                  <Input
                    value={accountName}
                    onChange={(e) => setAccountName(e.target.value)}
                    placeholder="Ej: Recetasquetransforman21 (Facebook)"
                    required
                    className="mt-1"
                  />
                </label>
                {provider !== "MANUAL" && provider !== "MOCK" && (
                  <label className="block text-sm">
                    <span className="text-muted-foreground">
                      ID de cuenta externa {provider === "META" && "(ID de página de Facebook o de cuenta de Instagram)"}
                    </span>
                    <Input value={externalAccountId} onChange={(e) => setExternalAccountId(e.target.value)} className="mt-1" />
                  </label>
                )}
                {provider !== "MANUAL" && (
                  <label className="block text-sm sm:col-span-2">
                    <span className="text-muted-foreground">
                      {provider === "META" && useBaseToken
                        ? "Token base (System User de Business Manager, se cifra en el servidor)"
                        : "Token de acceso (se cifra en el servidor)"}
                    </span>
                    <Input value={token} onChange={(e) => setToken(e.target.value)} className="mt-1" />
                  </label>
                )}
                {provider === "META" && (
                  <label className="flex items-center gap-2 text-sm sm:col-span-2">
                    <input type="checkbox" checked={useBaseToken}
                      onChange={(e) => setUseBaseToken(e.target.checked)}
                      className="rounded border-input" />
                    <span className="text-muted-foreground">
                      Es un token base de larga duración (System User) — RQT21 resolverá un token
                      de página fresco automáticamente en cada publicación, en vez de depender de un
                      token de página estático.
                    </span>
                  </label>
                )}
                {provider === "META" && platform === "INSTAGRAM" && useBaseToken && (
                  <label className="block text-sm sm:col-span-2">
                    <span className="text-muted-foreground">
                      ID de la página de Facebook vinculada (requerido para resolver el token
                      de esta cuenta de Instagram — ver el{" "}
                      <a href="/manual#meta" className="text-primary hover:underline">manual</a>)
                    </span>
                    <Input value={pageId} onChange={(e) => setPageId(e.target.value)} className="mt-1" />
                  </label>
                )}
              </div>
              {formError && (
                <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </div>
              )}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Creando…" : "Guardar cuenta"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {loading && <p className="text-sm text-muted-foreground">Cargando…</p>}

      {!loading && items.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <Link2 className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Todavía no hay cuentas conectadas. Agrega la página de Facebook o la cuenta de
              Instagram de cada marca para poder generar y publicar contenido dirigido a ellas.
            </p>
          </CardContent>
        </Card>
      )}

      {!loading && items.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((c) => {
            const meta = platformMeta(c.platform);
            return (
              <Card key={c.id}>
                <CardContent className="space-y-3 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className={`flex h-9 w-9 items-center justify-center rounded-full text-xs font-bold ${meta.accent}`}>
                        {meta.glyph}
                      </span>
                      <div>
                        <p className="text-sm font-semibold leading-tight">{c.account_name}</p>
                        <p className="text-xs text-muted-foreground">{brandName(c.brand_id)}</p>
                      </div>
                    </div>
                    <Badge variant={STATUS_VARIANT[c.status]}>{STATUS_LABEL[c.status]}</Badge>
                  </div>

                  <dl className="space-y-1 text-xs text-muted-foreground">
                    <div className="flex justify-between">
                      <dt>Proveedor</dt>
                      <dd className="text-foreground">{c.provider}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt>Credencial</dt>
                      <dd className="font-mono text-foreground">
                        {c.credentials_last_four ? `••••${c.credentials_last_four}` : "—"}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt>Última verificación</dt>
                      <dd className="text-foreground">{formatDate(c.last_verified_at)}</dd>
                    </div>
                  </dl>

                  {canManage && (
                    <div className="flex flex-wrap gap-2 border-t border-border pt-3">
                      <Button variant="outline" size="sm" disabled={busyId === c.id} className="gap-1.5"
                        onClick={() => void act(c.id, "verify")}>
                        <ShieldCheck className="h-3.5 w-3.5" />
                        Verificar
                      </Button>
                      {c.status !== "REVOKED" && (
                        <Button variant="outline" size="sm" disabled={busyId === c.id}
                          onClick={() => void act(c.id, "revoke")}>
                          Revocar
                        </Button>
                      )}
                      {c.status !== "DISABLED" && (
                        <Button variant="outline" size="sm" disabled={busyId === c.id}
                          onClick={() => void act(c.id, "disable")}>
                          Deshabilitar
                        </Button>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
