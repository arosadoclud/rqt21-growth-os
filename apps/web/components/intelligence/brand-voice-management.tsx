"use client";

import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Check,
  Languages,
  Palette,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import type { Brand, BrandVoiceWrite } from "@rqt21/contracts";

import { MetricCard } from "@/components/design-system/metric-card";
import { PageHeader } from "@/components/design-system/page-header";
import { SectionHeader } from "@/components/design-system/section-header";
import { StatusBadge } from "@/components/design-system/status-badge";
import { LoadingSkeleton, StatePanel } from "@/components/design-system/state-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";
import { cn } from "@/lib/utils";

const EMPTY_VOICE: BrandVoiceWrite = {
  brand_id: "",
  audience: "",
  value_proposition: "",
  tone: "",
  preferred_terms: [],
  forbidden_terms: [],
  cta_style: "",
  compliance_notes: "",
  language: "es",
  country: "DO",
  examples: [],
  visual_style: "",
};

export function BrandVoiceManagement() {
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canWrite = canWriteGrowth(organization?.role);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [brandId, setBrandId] = useState("");
  const [form, setForm] = useState<BrandVoiceWrite>(EMPTY_VOICE);
  const [loadingBrands, setLoadingBrands] = useState(true);
  const [loadingVoice, setLoadingVoice] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const loadBrands = useCallback(async () => {
    if (!currentOrgId) return;
    setLoadingBrands(true);
    setError(null);
    try {
      const result = await api.listBrands(currentOrgId);
      setBrands(result);
      setBrandId((current) => current || result[0]?.id || "");
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar las marcas.",
      );
    } finally {
      setLoadingBrands(false);
    }
  }, [currentOrgId]);

  const loadVoice = useCallback(async () => {
    if (!currentOrgId || !brandId) return;
    setLoadingVoice(true);
    setError(null);
    setSaved(false);
    try {
      const result = await api.getBrandVoice(currentOrgId, brandId);
      setForm({ ...result, brand_id: brandId });
    } catch (loadError) {
      if (loadError instanceof ApiError && loadError.status === 404) {
        setForm({ ...EMPTY_VOICE, brand_id: brandId });
      } else {
        setError(
          loadError instanceof ApiError
            ? loadError.detail
            : "No pudimos cargar la voz de marca.",
        );
      }
    } finally {
      setLoadingVoice(false);
    }
  }, [brandId, currentOrgId]);

  useEffect(() => {
    void loadBrands();
  }, [loadBrands]);

  useEffect(() => {
    void loadVoice();
  }, [loadVoice]);

  const completion = useMemo(() => {
    const fields = [
      form.audience,
      form.value_proposition,
      form.tone,
      form.cta_style,
      form.visual_style,
      form.compliance_notes,
      form.preferred_terms.length ? "complete" : "",
      form.examples.length ? "complete" : "",
    ];
    return Math.round((fields.filter(Boolean).length / fields.length) * 100);
  }, [form]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!currentOrgId || !brandId) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await api.upsertBrandVoice(currentOrgId, brandId, {
        ...form,
        brand_id: brandId,
      });
      setForm({ ...updated, brand_id: brandId });
      setSaved(true);
    } catch (saveError) {
      setError(
        saveError instanceof ApiError
          ? saveError.detail
          : "No pudimos guardar la voz de marca.",
      );
    } finally {
      setSaving(false);
    }
  };

  if (!currentOrgId) {
    return (
      <StatePanel
        icon={Sparkles}
        title="Selecciona una organización"
        description="Las guías de marca aparecerán cuando elijas una organización."
      />
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Dirección creativa"
        title="Voz de marca"
        description="Define el contexto que guía cada generación: audiencia, tono, vocabulario, identidad visual y límites de cumplimiento."
        metadata={
          <>
            <StatusBadge
              label={canWrite ? "Edición habilitada" : "Solo lectura"}
              tone={canWrite ? "success" : "neutral"}
            />
            {brandId && <span className="text-xs text-muted-foreground">{completion}% configurado</span>}
          </>
        }
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadVoice()}
            disabled={loadingVoice || !brandId}
          >
            <RefreshCw className={cn("h-4 w-4", loadingVoice && "animate-spin")} />
            Actualizar
          </Button>
        }
      />

      {error && <InlineError>{error}</InlineError>}
      {saved && (
        <div role="status" className="flex items-center gap-2 rounded-xl border border-success/25 bg-success/5 px-4 py-3 text-sm text-success">
          <Check className="h-4 w-4" />
          Guardado.
        </div>
      )}

      {loadingBrands ? (
        <LoadingSkeleton rows={4} />
      ) : brands.length === 0 ? (
        <StatePanel
          icon={Sparkles}
          title="Primero crea una marca"
          description="Cada guía de voz pertenece a una marca y se aplica automáticamente a sus generaciones."
          actionLabel="Ir a marcas"
          onAction={() => window.location.assign("/brands")}
        />
      ) : (
        <>
          <Card className="bg-card/80 shadow-none">
            <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-end sm:justify-between">
              <label className="block w-full max-w-md space-y-1.5 text-sm">
                <span className="font-medium text-foreground">Marca activa</span>
                <Select value={brandId} onChange={(event) => setBrandId(event.target.value)}>
                  {brands.map((brand) => (
                    <option key={brand.id} value={brand.id}>{brand.name}</option>
                  ))}
                </Select>
              </label>
              {!canWrite && (
                <p className="flex max-w-md items-start gap-2 text-xs leading-5 text-muted-foreground">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
                  Tu rol puede consultar esta guía, pero no modificarla.
                </p>
              )}
            </CardContent>
          </Card>

          {loadingVoice ? (
            <LoadingSkeleton rows={6} />
          ) : (
            <>
              <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Resumen de voz de marca">
                <MetricCard
                  label="Configuración"
                  value={`${completion}%`}
                  helper="Campos estratégicos completados"
                  icon={Target}
                  tone={completion >= 75 ? "positive" : "warning"}
                />
                <MetricCard
                  label="Términos preferidos"
                  value={form.preferred_terms.length}
                  helper="Vocabulario recomendado"
                  icon={Sparkles}
                />
                <MetricCard
                  label="Términos restringidos"
                  value={form.forbidden_terms.length}
                  helper="Expresiones que deben evitarse"
                  icon={ShieldCheck}
                  tone={form.forbidden_terms.length ? "warning" : "neutral"}
                />
                <MetricCard
                  label="Idioma"
                  value={form.language.toUpperCase()}
                  helper={`Mercado ${form.country || "sin definir"}`}
                  icon={Languages}
                  tone="info"
                />
              </section>

              <form onSubmit={submit} className="space-y-6">
                <VoiceSection
                  title="Posicionamiento"
                  description="Contexto esencial para que el contenido hable a la audiencia correcta."
                >
                  <div className="grid gap-4 md:grid-cols-2">
                    <FormField label="Audiencia" className="md:col-span-2">
                      <Textarea
                        value={form.audience}
                        onChange={(event) => setForm({ ...form, audience: event.target.value })}
                        disabled={!canWrite}
                        rows={3}
                        maxLength={2000}
                        placeholder="Describe a quién ayuda la marca, sus necesidades y nivel de conocimiento."
                      />
                    </FormField>
                    <FormField label="Propuesta de valor" className="md:col-span-2">
                      <Textarea
                        value={form.value_proposition}
                        onChange={(event) =>
                          setForm({ ...form, value_proposition: event.target.value })
                        }
                        disabled={!canWrite}
                        rows={3}
                        maxLength={2000}
                        placeholder="Explica el cambio concreto que ofrece la marca."
                      />
                    </FormField>
                    <FormField label="Tono">
                      <Input
                        value={form.tone}
                        onChange={(event) => setForm({ ...form, tone: event.target.value })}
                        disabled={!canWrite}
                        maxLength={1000}
                        placeholder="Cercano, claro y motivador"
                      />
                    </FormField>
                    <FormField label="Estilo de CTA">
                      <Input
                        value={form.cta_style}
                        onChange={(event) => setForm({ ...form, cta_style: event.target.value })}
                        disabled={!canWrite}
                        maxLength={1000}
                        placeholder="Invitación directa y útil"
                      />
                    </FormField>
                    <FormField label="Idioma">
                      <Input
                        value={form.language}
                        onChange={(event) => setForm({ ...form, language: event.target.value })}
                        disabled={!canWrite}
                        maxLength={16}
                      />
                    </FormField>
                    <FormField label="País">
                      <Input
                        value={form.country}
                        onChange={(event) =>
                          setForm({ ...form, country: event.target.value.toUpperCase() })
                        }
                        disabled={!canWrite}
                        maxLength={2}
                      />
                    </FormField>
                  </div>
                </VoiceSection>

                <VoiceSection
                  title="Lenguaje y ejemplos"
                  description="Expresiones que ayudan al modelo a sonar consistente y reconocible."
                >
                  <div className="grid gap-6 lg:grid-cols-2">
                    <TermListEditor
                      label="Términos preferidos"
                      hint="Palabras o frases que conviene utilizar."
                      values={form.preferred_terms}
                      onChange={(values) => setForm({ ...form, preferred_terms: values })}
                      disabled={!canWrite}
                    />
                    <TermListEditor
                      label="Términos prohibidos"
                      hint="El consejo señalará contenido que los utilice."
                      values={form.forbidden_terms}
                      onChange={(values) => setForm({ ...form, forbidden_terms: values })}
                      disabled={!canWrite}
                      danger
                    />
                    <div className="lg:col-span-2">
                      <TermListEditor
                        label="Ejemplos de tono"
                        hint="Frases breves que representan la voz deseada."
                        values={form.examples}
                        onChange={(values) => setForm({ ...form, examples: values })}
                        disabled={!canWrite}
                      />
                    </div>
                  </div>
                </VoiceSection>

                <VoiceSection
                  title="Identidad visual y cumplimiento"
                  description="Instrucciones para imágenes coherentes y contenido seguro."
                  icon={Palette}
                >
                  <div className="grid gap-4 lg:grid-cols-2">
                    <FormField
                      label="Identidad visual"
                      helper="Paleta, fondos, tipografía, logo y estilo fotográfico."
                    >
                      <Textarea
                        value={form.visual_style}
                        onChange={(event) =>
                          setForm({ ...form, visual_style: event.target.value })
                        }
                        disabled={!canWrite}
                        rows={7}
                        maxLength={4000}
                        placeholder="Fondo negro mate, fotografía gastronómica natural, acentos lima…"
                      />
                    </FormField>
                    <FormField
                      label="Notas de cumplimiento"
                      helper="Afirmaciones, promesas o enfoques que deben evitarse."
                    >
                      <Textarea
                        value={form.compliance_notes}
                        onChange={(event) =>
                          setForm({ ...form, compliance_notes: event.target.value })
                        }
                        disabled={!canWrite}
                        rows={7}
                        maxLength={3000}
                        placeholder="Nunca presentar el producto como tratamiento médico."
                      />
                    </FormField>
                  </div>
                </VoiceSection>

                {canWrite && (
                  <div className="sticky bottom-4 flex justify-end rounded-xl border border-border bg-elevated/95 p-3 shadow-premium backdrop-blur">
                    <Button type="submit" disabled={saving}>
                      {saving ? "Guardando…" : "Guardar"}
                    </Button>
                  </div>
                )}
              </form>
            </>
          )}
        </>
      )}
    </div>
  );
}

function VoiceSection({
  title,
  description,
  icon: Icon,
  children,
}: {
  title: string;
  description: string;
  icon?: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <Card className="bg-card/80 shadow-none">
      <CardContent className="p-5 sm:p-6">
        <SectionHeader
          title={
            <span className="flex items-center gap-2">
              {Icon && <Icon className="h-4 w-4 text-primary" />}
              {title}
            </span>
          }
          description={description}
        />
        <div className="mt-5">{children}</div>
      </CardContent>
    </Card>
  );
}

function FormField({
  label,
  helper,
  className,
  children,
}: {
  label: string;
  helper?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <label className={cn("block space-y-1.5 text-sm", className)}>
      <span className="font-medium text-foreground">{label}</span>
      {children}
      {helper && <span className="block text-xs leading-5 text-muted-foreground">{helper}</span>}
    </label>
  );
}

function TermListEditor({
  label,
  hint,
  values,
  onChange,
  disabled,
  danger = false,
}: {
  label: string;
  hint: string;
  values: string[];
  onChange: (values: string[]) => void;
  disabled: boolean;
  danger?: boolean;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const value = draft.trim();
    if (!value || values.includes(value)) return;
    onChange([...values, value]);
    setDraft("");
  };
  return (
    <div>
      <p className="text-sm font-medium text-foreground">{label}</p>
      <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      <div className="mt-3 flex gap-2">
        <Input
          value={draft}
          aria-label={`Añadir a ${label}`}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              add();
            }
          }}
          disabled={disabled}
        />
        <Button type="button" variant="outline" onClick={add} disabled={disabled}>
          <Plus className="h-4 w-4" />
          Añadir
        </Button>
      </div>
      {values.length === 0 ? (
        <p className="mt-3 text-xs text-muted-foreground">Sin términos configurados.</p>
      ) : (
        <ul className="mt-3 flex flex-wrap gap-2">
          {values.map((value) => (
            <li
              key={value}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs",
                danger
                  ? "border-destructive/20 bg-destructive/5 text-destructive"
                  : "border-border bg-interactive text-foreground",
              )}
            >
              {value}
              {!disabled && (
                <button
                  type="button"
                  onClick={() => onChange(values.filter((candidate) => candidate !== value))}
                  aria-label={`Quitar ${value}`}
                  className="rounded-full p-0.5 hover:bg-background"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function InlineError({ children }: { children: React.ReactNode }) {
  return (
    <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive">
      {children}
    </div>
  );
}
