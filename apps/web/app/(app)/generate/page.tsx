"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Brand, Campaign, GenerationType, Product } from "@rqt21/contracts";
import { GENERATION_TYPES } from "@rqt21/contracts";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";

const PLATFORMS = ["INSTAGRAM", "FACEBOOK", "TIKTOK", "YOUTUBE", "EMAIL", "OTHER"];

export default function GeneratePage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canGenerate = canWriteGrowth(org?.role);
  const router = useRouter();

  const [brands, setBrands] = useState<Brand[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [brandId, setBrandId] = useState("");
  const [productId, setProductId] = useState("");
  const [campaignId, setCampaignId] = useState("");
  const [generationType, setGenerationType] = useState<GenerationType>("REEL_SCRIPT");
  const [platform, setPlatform] = useState("INSTAGRAM");
  const [objective, setObjective] = useState("engagement");
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("");
  const [cta, setCta] = useState("");
  const [notes, setNotes] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [bs, ps, cs] = await Promise.all([
        api.listBrands(currentOrgId),
        api.listProducts(currentOrgId),
        api.listCampaigns(currentOrgId),
      ]);
      setBrands(bs);
      setProducts(ps);
      setCampaigns(cs);
      if (!brandId && bs.length > 0) setBrandId(bs[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar datos");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, brandId]);

  useEffect(() => {
    void load();
  }, [load]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !brandId || submitting) return;
    setSubmitting(true);
    setFormError(null);
    try {
      const job = await api.createGenerationJob(currentOrgId, {
        brand_id: brandId,
        product_id: productId || null,
        campaign_id: campaignId || null,
        generation_type: generationType,
        input: {
          objective,
          platform,
          topic,
          audience: audience || null,
          cta: cta || null,
          notes: notes || null,
        },
      });
      router.push(`/generation-jobs/${job.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 402) {
        setFormError(`Límite de generación alcanzado: ${err.detail}`);
      } else {
        setFormError(err instanceof ApiError ? err.detail : "Error generando contenido");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;
  if (!canGenerate) {
    return (
      <p className="text-sm text-muted-foreground">
        Tu rol no permite generar contenido con IA.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Generar contenido</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Un borrador estructurado, nunca publicado automáticamente. Siempre requiere
          revisión y aprobación humana.
        </p>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading && <p className="text-sm text-muted-foreground">Cargando…</p>}

      {!loading && brands.length > 0 && (
        <Card>
          <CardContent className="p-4">
            <form onSubmit={onSubmit} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block text-sm">
                  <span className="text-muted-foreground">Marca</span>
                  <Select value={brandId} onChange={(e) => setBrandId(e.target.value)} required className="mt-1">
                    {brands.map((b) => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Producto (opcional)</span>
                  <Select value={productId} onChange={(e) => setProductId(e.target.value)} className="mt-1">
                    <option value="">—</option>
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Campaña (opcional)</span>
                  <Select value={campaignId} onChange={(e) => setCampaignId(e.target.value)} className="mt-1">
                    <option value="">—</option>
                    {campaigns.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Tipo de contenido</span>
                  <Select value={generationType} onChange={(e) => setGenerationType(e.target.value as GenerationType)} className="mt-1">
                    {GENERATION_TYPES.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Plataforma</span>
                  <Select value={platform} onChange={(e) => setPlatform(e.target.value)} className="mt-1">
                    {PLATFORMS.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Objetivo</span>
                  <Input value={objective} onChange={(e) => setObjective(e.target.value)} required maxLength={500} className="mt-1" />
                </label>
              </div>

              <label className="block text-sm">
                <span className="flex items-center justify-between text-muted-foreground">
                  <span>Tema</span>
                  <span className="text-xs">{topic.length}/1000</span>
                </span>
                <Textarea value={topic} onChange={(e) => setTopic(e.target.value)} required rows={2} maxLength={1000} className="mt-1" />
              </label>
              <label className="block text-sm">
                <span className="text-muted-foreground">Audiencia (opcional)</span>
                <Input value={audience} onChange={(e) => setAudience(e.target.value)} maxLength={1000} className="mt-1" />
              </label>
              <label className="block text-sm">
                <span className="text-muted-foreground">CTA (opcional)</span>
                <Input value={cta} onChange={(e) => setCta(e.target.value)} maxLength={500} className="mt-1" />
              </label>
              <label className="block text-sm">
                <span className="flex items-center justify-between text-muted-foreground">
                  <span>Notas (opcional)</span>
                  <span className="text-xs">{notes.length}/2000</span>
                </span>
                <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} maxLength={2000} className="mt-1" />
              </label>

              <p className="text-xs text-muted-foreground">
                Costo estimado: cero con el proveedor de desarrollo (MOCK); con un
                proveedor real dependerá de los tokens usados — visible en el detalle
                de la generación para roles autorizados.
              </p>

              {formError && (
                <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </div>
              )}

              <Button type="submit" disabled={submitting}>
                {submitting ? "Generando…" : "Generar"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
