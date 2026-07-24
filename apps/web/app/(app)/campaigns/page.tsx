"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type {
  Brand,
  Campaign,
  CampaignObjective,
  CampaignStatus,
  Platform,
} from "@rqt21/contracts";
import {
  CAMPAIGN_OBJECTIVES,
  CAMPAIGN_STATUSES,
  PLATFORMS,
} from "@rqt21/contracts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";

export default function CampaignsPage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);

  const [items, setItems] = useState<Campaign[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [brandId, setBrandId] = useState("");
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [platform, setPlatform] = useState<Platform>("INSTAGRAM");
  const [objective, setObjective] = useState<CampaignObjective>("SALES");
  const [status, setStatus] = useState<CampaignStatus>("ACTIVE");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [cs, bs] = await Promise.all([
        api.listCampaigns(currentOrgId),
        api.listBrands(currentOrgId),
      ]);
      setItems(cs);
      setBrands(bs);
      if (!brandId && bs.length > 0) setBrandId(bs[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar campañas");
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
      await api.createCampaign(currentOrgId, {
        brand_id: brandId,
        name,
        slug,
        platform,
        objective,
        status,
      });
      setName("");
      setSlug("");
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Error creando campaña");
    } finally {
      setSubmitting(false);
    }
  };

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Campañas</h1>
      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nombre</TableHead>
              <TableHead>Plataforma</TableHead>
              <TableHead>Objetivo</TableHead>
              <TableHead>Estado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (<TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">Cargando…</TableCell></TableRow>)}
            {!loading && items.length === 0 && (<TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">Sin campañas</TableCell></TableRow>)}
            {items.map((c) => (
              <TableRow key={c.id}>
                <TableCell className="font-medium">{c.name}</TableCell>
                <TableCell className="text-muted-foreground">{c.platform}</TableCell>
                <TableCell className="text-muted-foreground">{c.objective}</TableCell>
                <TableCell className="text-muted-foreground">{c.status}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {canWrite && brands.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground text-lg">Nueva campaña</CardTitle>
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
                  <span className="text-muted-foreground">Nombre</span>
                  <Input required value={name} onChange={(e) => setName(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Slug</span>
                  <Input required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={slug} onChange={(e) => setSlug(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Plataforma</span>
                  <Select value={platform} onChange={(e) => setPlatform(e.target.value as Platform)} className="mt-1">
                    {PLATFORMS.map((p) => (<option key={p} value={p}>{p}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Objetivo</span>
                  <Select value={objective} onChange={(e) => setObjective(e.target.value as CampaignObjective)} className="mt-1">
                    {CAMPAIGN_OBJECTIVES.map((o) => (<option key={o} value={o}>{o}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Estado</span>
                  <Select value={status} onChange={(e) => setStatus(e.target.value as CampaignStatus)} className="mt-1">
                    {CAMPAIGN_STATUSES.map((s) => (<option key={s} value={s}>{s}</option>))}
                  </Select>
                </label>
              </div>
              {formError && (
                <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </div>
              )}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Guardando…" : "Crear campaña"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
