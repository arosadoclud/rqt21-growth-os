"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type { Brand, BrandVoiceWrite } from "@rqt21/contracts";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";

const EMPTY: BrandVoiceWrite = {
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
};

function TermListEditor(props: {
  label: string;
  hint: string;
  values: string[];
  onChange: (v: string[]) => void;
  disabled: boolean;
}) {
  const { label, hint, values, onChange, disabled } = props;
  const [draft, setDraft] = useState("");

  const add = () => {
    const v = draft.trim();
    if (!v || values.includes(v)) return;
    onChange([...values, v]);
    setDraft("");
  };

  return (
    <div>
      <label className="block text-sm font-medium">{label}</label>
      <p className="text-xs text-muted-foreground">{hint}</p>
      <div className="mt-1 flex gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          disabled={disabled}
        />
        <Button type="button" variant="outline" onClick={add} disabled={disabled}>
          Añadir
        </Button>
      </div>
      <ul className="mt-2 flex flex-wrap gap-2">
        {values.map((v) => (
          <li
            key={v}
            className="flex items-center gap-1 rounded-full bg-secondary px-3 py-1 text-xs text-secondary-foreground"
          >
            {v}
            {!disabled && (
              <button
                type="button"
                onClick={() => onChange(values.filter((x) => x !== v))}
                className="text-muted-foreground hover:text-foreground"
                aria-label={`Quitar ${v}`}
              >
                ×
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function BrandVoicePage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);

  const [brands, setBrands] = useState<Brand[]>([]);
  const [brandId, setBrandId] = useState("");
  const [form, setForm] = useState<BrandVoiceWrite>(EMPTY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const loadBrands = useCallback(async () => {
    if (!currentOrgId) return;
    try {
      const bs = await api.listBrands(currentOrgId);
      setBrands(bs);
      if (!brandId && bs.length > 0) setBrandId(bs[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar marcas");
    }
  }, [currentOrgId, brandId]);

  const loadVoice = useCallback(async () => {
    if (!currentOrgId || !brandId) return;
    setLoading(true);
    setError(null);
    setSaved(false);
    try {
      const v = await api.getBrandVoice(currentOrgId, brandId);
      setForm({ ...v, brand_id: brandId });
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setForm({ ...EMPTY, brand_id: brandId });
      } else {
        setError(err instanceof ApiError ? err.detail : "Error al cargar voz de marca");
      }
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, brandId]);

  useEffect(() => {
    void loadBrands();
  }, [loadBrands]);

  useEffect(() => {
    void loadVoice();
  }, [loadVoice]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
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
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error guardando voz de marca");
    } finally {
      setSaving(false);
    }
  };

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Voz de marca</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Este perfil guía las generaciones asistidas por IA para esta marca: audiencia,
          tono, términos preferidos y prohibidos, y notas de cumplimiento.
        </p>
      </div>

      {brands.length > 0 && (
        <label className="block text-sm">
          <span className="text-muted-foreground">Marca</span>
          <Select value={brandId} onChange={(e) => setBrandId(e.target.value)} className="mt-1 max-w-xs">
            {brands.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </Select>
        </label>
      )}

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}
      {saved && (
        <div className="rounded-md border border-success/30 bg-success/10 px-3 py-2 text-sm text-success">
          Guardado.
        </div>
      )}

      {loading && <p className="text-sm text-muted-foreground">Cargando…</p>}

      {!loading && brandId && (
        <Card>
          <CardContent className="p-4">
            <form onSubmit={onSubmit} className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block text-sm sm:col-span-2">
                  <span className="text-muted-foreground">Audiencia</span>
                  <Textarea
                    value={form.audience}
                    onChange={(e) => setForm({ ...form, audience: e.target.value })}
                    disabled={!canWrite}
                    rows={2}
                    maxLength={2000}
                    className="mt-1"
                  />
                </label>
                <label className="block text-sm sm:col-span-2">
                  <span className="text-muted-foreground">Propuesta de valor</span>
                  <Textarea
                    value={form.value_proposition}
                    onChange={(e) => setForm({ ...form, value_proposition: e.target.value })}
                    disabled={!canWrite}
                    rows={2}
                    maxLength={2000}
                    className="mt-1"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Tono</span>
                  <Input
                    value={form.tone}
                    onChange={(e) => setForm({ ...form, tone: e.target.value })}
                    disabled={!canWrite}
                    maxLength={1000}
                    className="mt-1"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Estilo de CTA</span>
                  <Input
                    value={form.cta_style}
                    onChange={(e) => setForm({ ...form, cta_style: e.target.value })}
                    disabled={!canWrite}
                    maxLength={1000}
                    className="mt-1"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Idioma</span>
                  <Input
                    value={form.language}
                    onChange={(e) => setForm({ ...form, language: e.target.value })}
                    disabled={!canWrite}
                    maxLength={16}
                    className="mt-1"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">País</span>
                  <Input
                    value={form.country}
                    onChange={(e) => setForm({ ...form, country: e.target.value.toUpperCase() })}
                    disabled={!canWrite}
                    maxLength={2}
                    className="mt-1"
                  />
                </label>
              </div>

              <TermListEditor
                label="Términos preferidos"
                hint="Palabras o frases que el asistente debería usar cuando encajen."
                values={form.preferred_terms}
                onChange={(v) => setForm({ ...form, preferred_terms: v })}
                disabled={!canWrite}
              />
              <TermListEditor
                label="Términos prohibidos"
                hint="El Consejo de revisión bloqueará contenido que use estos términos."
                values={form.forbidden_terms}
                onChange={(v) => setForm({ ...form, forbidden_terms: v })}
                disabled={!canWrite}
              />
              <TermListEditor
                label="Ejemplos de tono"
                hint="Frases de ejemplo que ilustran el tono deseado."
                values={form.examples}
                onChange={(v) => setForm({ ...form, examples: v })}
                disabled={!canWrite}
              />

              <label className="block text-sm">
                <span className="text-muted-foreground">Notas de cumplimiento</span>
                <Textarea
                  value={form.compliance_notes}
                  onChange={(e) => setForm({ ...form, compliance_notes: e.target.value })}
                  disabled={!canWrite}
                  rows={3}
                  maxLength={3000}
                  placeholder="Ej: nunca presentar el producto como tratamiento médico."
                  className="mt-1"
                />
              </label>

              {canWrite && (
                <Button type="submit" disabled={saving}>
                  {saving ? "Guardando…" : "Guardar"}
                </Button>
              )}
              {!canWrite && (
                <p className="text-xs text-muted-foreground">Tu rol no permite editar la voz de marca.</p>
              )}
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
