"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type {
  Brand,
  Campaign,
  ContentItem,
  Product,
  TrackingLink,
} from "@rqt21/contracts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Enlaces rastreables</h1>
      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Código</TableHead>
              <TableHead>URL corta</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (<TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">Cargando…</TableCell></TableRow>)}
            {!loading && items.length === 0 && (<TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">Sin enlaces</TableCell></TableRow>)}
            {items.map((l) => (
              <TableRow key={l.id} className="align-top">
                <TableCell className="font-mono">{l.short_code}</TableCell>
                <TableCell className="text-muted-foreground">
                  <div className="max-w-md truncate">{l.short_url}</div>
                  <div className="mt-1 max-w-md truncate text-xs">{l.final_url}</div>
                </TableCell>
                <TableCell>
                  <Badge variant={l.is_active ? "success" : "secondary"}>
                    {l.is_active ? "activo" : "inactivo"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => copy(l.short_url)}>
                      Copiar
                    </Button>
                    {canWrite && (
                      <Button variant="outline" size="sm" onClick={() => void toggleActive(l)}>
                        {l.is_active ? "Desactivar" : "Reactivar"}
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {canWrite && brands.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground text-lg">Nuevo enlace</CardTitle>
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
                  <span className="text-muted-foreground">Producto</span>
                  <Select value={productId} onChange={(e) => setProductId(e.target.value)} className="mt-1">
                    <option value="">—</option>
                    {products.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Campaña</span>
                  <Select value={campaignId} onChange={(e) => setCampaignId(e.target.value)} className="mt-1">
                    <option value="">—</option>
                    {campaigns.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Contenido</span>
                  <Select value={contentId} onChange={(e) => setContentId(e.target.value)} className="mt-1">
                    <option value="">—</option>
                    {contents.map((c) => (<option key={c.id} value={c.id}>{c.title}</option>))}
                  </Select>
                </label>
                <label className="block text-sm sm:col-span-2">
                  <span className="text-muted-foreground">URL destino</span>
                  <Input required type="url" value={destination} onChange={(e) => setDestination(e.target.value)}
                    placeholder="https://checkout.example.com/…" className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">utm_source</span>
                  <Input value={utmSource} onChange={(e) => setUtmSource(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">utm_medium</span>
                  <Input value={utmMedium} onChange={(e) => setUtmMedium(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">utm_campaign</span>
                  <Input value={utmCampaign} onChange={(e) => setUtmCampaign(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">utm_content</span>
                  <Input value={utmContent} onChange={(e) => setUtmContent(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm sm:col-span-2">
                  <span className="text-muted-foreground">utm_term</span>
                  <Input value={utmTerm} onChange={(e) => setUtmTerm(e.target.value)} className="mt-1" />
                </label>
              </div>
              {formError && (
                <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </div>
              )}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Guardando…" : "Generar enlace"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
