"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Video, ImageIcon, Type, CircleDashed, Check, Clapperboard } from "lucide-react";
import type { Brand, Campaign, GenerationType, Product } from "@rqt21/contracts";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";

const OTHER_PLATFORMS = ["TIKTOK", "YOUTUBE", "EMAIL", "OTHER"];

const PLATFORM_OPTIONS: Array<{
  value: string;
  label: string;
  hint: string;
  accent: string;
}> = [
  {
    value: "FACEBOOK",
    label: "Facebook",
    hint: "Página Recetasquetransforman21",
    accent: "border-blue-500/40 hover:border-blue-500 data-[active=true]:border-blue-500 data-[active=true]:bg-blue-500/10",
  },
  {
    value: "INSTAGRAM",
    label: "Instagram",
    hint: "Cuenta profesional vinculada",
    accent: "border-fuchsia-500/40 hover:border-fuchsia-500 data-[active=true]:border-fuchsia-500 data-[active=true]:bg-fuchsia-500/10",
  },
];

const CONTENT_TYPE_OPTIONS: Array<{
  generationType: GenerationType;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  hint: string;
}> = [
  {
    generationType: "REEL_SCRIPT",
    icon: Video,
    label: "Reel",
    hint: "Guion con hook, tomas y CTA",
  },
  {
    generationType: "STORY",
    icon: CircleDashed,
    label: "Historia",
    hint: "Texto corto para historia",
  },
  {
    generationType: "IMAGE_ASSET",
    icon: ImageIcon,
    label: "Publicación con foto",
    hint: "Genera la imagen de marca",
  },
  {
    generationType: "SOCIAL_POST",
    icon: Type,
    label: "Publicación solo texto",
    hint: "Caption + hashtags, sin imagen",
  },
  {
    generationType: "VIDEO_ASSET",
    icon: Clapperboard,
    label: "Video",
    hint: "Guion + voz + imágenes, ensamblado automático",
  },
];

type Step = "platform" | "type" | "details";

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

  const [step, setStep] = useState<Step>("platform");
  const [showOtherPlatforms, setShowOtherPlatforms] = useState(false);

  const [brandId, setBrandId] = useState("");
  const [productId, setProductId] = useState("");
  const [campaignId, setCampaignId] = useState("");
  const [generationType, setGenerationType] = useState<GenerationType | null>(null);
  const [platform, setPlatform] = useState("");
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

  const choosePlatform = (value: string) => {
    setPlatform(value);
    setStep("type");
  };

  const chooseType = (value: GenerationType) => {
    setGenerationType(value);
    setStep("details");
  };

  const resetWizard = () => {
    setPlatform("");
    setGenerationType(null);
    setStep("platform");
  };

  const contentTypeLabel = CONTENT_TYPE_OPTIONS.find((o) => o.generationType === generationType)?.label;
  const platformLabel = PLATFORM_OPTIONS.find((o) => o.value === platform)?.label ?? platform;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !brandId || !generationType || submitting) return;
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

      {(platform || generationType) && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {platform && (
            <button
              type="button"
              onClick={resetWizard}
              className="flex items-center gap-1.5 rounded-full border border-border bg-accent/50 px-3 py-1 hover:bg-accent"
            >
              <Check className="h-3.5 w-3.5 text-primary" />
              {platformLabel}
            </button>
          )}
          {generationType && (
            <button
              type="button"
              onClick={() => setStep("type")}
              className="flex items-center gap-1.5 rounded-full border border-border bg-accent/50 px-3 py-1 hover:bg-accent"
            >
              <Check className="h-3.5 w-3.5 text-primary" />
              {contentTypeLabel}
            </button>
          )}
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading && <p className="text-sm text-muted-foreground">Cargando…</p>}

      {!loading && brands.length === 0 && (
        <div className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
          <p>Todavía no hay ninguna marca en esta organización.</p>
          <p className="mt-1">Creá una marca primero para poder generar contenido.</p>
          <Link
            href="/brands"
            className="mt-4 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Ir a Marcas
          </Link>
        </div>
      )}

      {!loading && brands.length > 0 && step === "platform" && (
        <div className="space-y-3">
          <p className="text-sm font-medium">¿Dónde vas a publicar?</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {PLATFORM_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                data-active={platform === opt.value}
                onClick={() => choosePlatform(opt.value)}
                className={cn(
                  "flex flex-col items-start gap-1 rounded-xl border-2 bg-card p-5 text-left transition-all",
                  opt.accent
                )}
              >
                <span className="text-lg font-semibold">{opt.label}</span>
                <span className="text-xs text-muted-foreground">{opt.hint}</span>
              </button>
            ))}
          </div>
          {!showOtherPlatforms && (
            <button
              type="button"
              onClick={() => setShowOtherPlatforms(true)}
              className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
            >
              Otra plataforma (TikTok, YouTube, Email…)
            </button>
          )}
          {showOtherPlatforms && (
            <Select
              value=""
              onChange={(e) => e.target.value && choosePlatform(e.target.value)}
              className="max-w-xs"
            >
              <option value="">Selecciona una plataforma…</option>
              {OTHER_PLATFORMS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </Select>
          )}
        </div>
      )}

      {!loading && brands.length > 0 && step === "type" && (
        <div className="space-y-3">
          <p className="text-sm font-medium">¿Qué quieres crear en {platformLabel}?</p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {CONTENT_TYPE_OPTIONS.map((opt) => {
              const Icon = opt.icon;
              return (
                <button
                  key={opt.generationType}
                  type="button"
                  onClick={() => chooseType(opt.generationType)}
                  className="flex flex-col items-start gap-2 rounded-xl border-2 border-border bg-card p-4 text-left transition-all hover:border-primary/50 hover:bg-accent/50"
                >
                  <Icon className="h-6 w-6 text-muted-foreground" />
                  <span className="text-sm font-medium">{opt.label}</span>
                  <span className="text-xs text-muted-foreground">{opt.hint}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {!loading && brands.length > 0 && step === "details" && generationType && (
        <Card>
          <CardContent className="space-y-4 p-4">
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
                <label className="block text-sm sm:col-span-2">
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

              <div className="flex gap-2">
                <Button type="submit" disabled={submitting}>
                  {submitting ? "Generando…" : "Generar"}
                </Button>
                <Button type="button" variant="outline" onClick={() => setStep("type")}>
                  Atrás
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
