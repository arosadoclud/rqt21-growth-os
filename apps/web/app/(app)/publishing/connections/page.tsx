"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type { Brand, ConnectionStatus, Platform, PublishingConnection, PublishingProviderName } from "@rqt21/contracts";
import { PLATFORMS, PUBLISHING_PROVIDERS } from "@rqt21/contracts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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
      <h1 className="text-2xl font-semibold tracking-tight">Conexiones de publicación</h1>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Cuenta</TableHead>
              <TableHead>Plataforma</TableHead>
              <TableHead>Proveedor</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Últimos 4 (solo OWNER/ADMIN)</TableHead>
              <TableHead>Verificado</TableHead>
              {canManage && <TableHead>Acciones</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground">Cargando…</TableCell></TableRow>
            )}
            {!loading && items.length === 0 && (
              <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground">Sin conexiones</TableCell></TableRow>
            )}
            {items.map((c) => (
              <TableRow key={c.id}>
                <TableCell className="font-medium">{c.account_name}</TableCell>
                <TableCell className="text-muted-foreground">{c.platform}</TableCell>
                <TableCell className="text-muted-foreground">{c.provider}</TableCell>
                <TableCell>
                  <Badge variant={STATUS_VARIANT[c.status]}>{c.status}</Badge>
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {c.credentials_last_four ? `••••${c.credentials_last_four}` : "—"}
                </TableCell>
                <TableCell className="text-muted-foreground">{formatDate(c.last_verified_at)}</TableCell>
                {canManage && (
                  <TableCell>
                    <div className="flex flex-wrap gap-2">
                      <Button variant="outline" size="sm" disabled={busyId === c.id}
                        onClick={() => void act(c.id, "verify")}>
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
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {canManage && brands.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground text-lg">Nueva conexión</CardTitle>
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
                    {PLATFORMS.map((p) => (<option key={p} value={p}>{p}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Proveedor</span>
                  <Select value={provider} onChange={(e) => setProvider(e.target.value as PublishingProviderName)} className="mt-1">
                    {PUBLISHING_PROVIDERS.map((p) => (<option key={p} value={p}>{p}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Nombre de cuenta</span>
                  <Input value={accountName} onChange={(e) => setAccountName(e.target.value)} required className="mt-1" />
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
              </div>
              {formError && (
                <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </div>
              )}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Creando…" : "Crear conexión"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
