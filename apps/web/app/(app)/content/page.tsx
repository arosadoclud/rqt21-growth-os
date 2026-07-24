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
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Contenidos</h1>
      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Título</TableHead>
              <TableHead>Tipo</TableHead>
              <TableHead>Plataforma</TableHead>
              <TableHead>Estado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (<TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">Cargando…</TableCell></TableRow>)}
            {!loading && items.length === 0 && (<TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">Sin contenidos</TableCell></TableRow>)}
            {items.map((c) => (
              <TableRow key={c.id}>
                <TableCell className="font-medium">{c.title}</TableCell>
                <TableCell className="text-muted-foreground">{c.content_type}</TableCell>
                <TableCell className="text-muted-foreground">{c.platform}</TableCell>
                <TableCell className="text-muted-foreground">{c.status}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {canWrite && brands.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground text-lg">Nuevo contenido</CardTitle>
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
                  <span className="text-muted-foreground">Campaña (opcional)</span>
                  <Select value={campaignId} onChange={(e) => setCampaignId(e.target.value)} className="mt-1">
                    <option value="">— sin campaña —</option>
                    {campaigns.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
                  </Select>
                </label>
                <label className="block text-sm sm:col-span-2">
                  <span className="text-muted-foreground">Título</span>
                  <Input required value={title} onChange={(e) => setTitle(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm sm:col-span-2">
                  <span className="text-muted-foreground">Gancho</span>
                  <Input value={hook} onChange={(e) => setHook(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Tipo</span>
                  <Select value={contentType} onChange={(e) => setContentType(e.target.value as ContentType)} className="mt-1">
                    {CONTENT_TYPES.map((c) => (<option key={c} value={c}>{c}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Plataforma</span>
                  <Select value={platform} onChange={(e) => setPlatform(e.target.value as Platform)} className="mt-1">
                    {PLATFORMS.map((p) => (<option key={p} value={p}>{p}</option>))}
                  </Select>
                </label>
              </div>
              {formError && (
                <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </div>
              )}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Guardando…" : "Crear contenido"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
