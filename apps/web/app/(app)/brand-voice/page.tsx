"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type { Brand, BrandVoiceWrite } from "@rqt21/contracts";
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
      <label className="block text-sm font-medium text-slate-700">{label}</label>
      <p className="text-xs text-slate-500">{hint}</p>
      <div className="mt-1 flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          disabled={disabled}
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
        />
        <button
          type="button"
          onClick={add}
          disabled={disabled}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-60"
        >
          Añadir
        </button>
      </div>
      <ul className="mt-2 flex flex-wrap gap-2">
        {values.map((v) => (
          <li
            key={v}
            className="flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700"
          >
            {v}
            {!disabled && (
              <button
                type="button"
                onClick={() => onChange(values.filter((x) => x !== v))}
                className="text-slate-400 hover:text-slate-700"
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

  if (!currentOrgId) return <p>Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Voz de marca</h1>
      <p className="text-sm text-slate-500">
        Este perfil guía las generaciones asistidas por IA para esta marca: audiencia,
        tono, términos preferidos y prohibidos, y notas de cumplimiento.
      </p>

      {brands.length > 0 && (
        <label className="block text-sm">
          <span className="text-slate-700">Marca</span>
          <select
            value={brandId}
            onChange={(e) => setBrandId(e.target.value)}
            className="mt-1 w-full max-w-xs rounded-md border border-slate-300 bg-white px-3 py-2"
          >
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
      )}

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}
      {saved && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          Guardado.
        </div>
      )}

      {loading && <p className="text-sm text-slate-500">Cargando…</p>}

      {!loading && brandId && (
        <form onSubmit={onSubmit} className="space-y-5 rounded-xl border border-slate-200 bg-white p-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm sm:col-span-2">
              <span className="text-slate-700">Audiencia</span>
              <textarea
                value={form.audience}
                onChange={(e) => setForm({ ...form, audience: e.target.value })}
                disabled={!canWrite}
                rows={2}
                maxLength={2000}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
              />
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="text-slate-700">Propuesta de valor</span>
              <textarea
                value={form.value_proposition}
                onChange={(e) => setForm({ ...form, value_proposition: e.target.value })}
                disabled={!canWrite}
                rows={2}
                maxLength={2000}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
              />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Tono</span>
              <input
                value={form.tone}
                onChange={(e) => setForm({ ...form, tone: e.target.value })}
                disabled={!canWrite}
                maxLength={1000}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
              />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Estilo de CTA</span>
              <input
                value={form.cta_style}
                onChange={(e) => setForm({ ...form, cta_style: e.target.value })}
                disabled={!canWrite}
                maxLength={1000}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
              />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Idioma</span>
              <input
                value={form.language}
                onChange={(e) => setForm({ ...form, language: e.target.value })}
                disabled={!canWrite}
                maxLength={16}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
              />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">País</span>
              <input
                value={form.country}
                onChange={(e) => setForm({ ...form, country: e.target.value.toUpperCase() })}
                disabled={!canWrite}
                maxLength={2}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
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
            <span className="text-slate-700">Notas de cumplimiento</span>
            <textarea
              value={form.compliance_notes}
              onChange={(e) => setForm({ ...form, compliance_notes: e.target.value })}
              disabled={!canWrite}
              rows={3}
              maxLength={3000}
              placeholder="Ej: nunca presentar el producto como tratamiento médico."
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
            />
          </label>

          {canWrite && (
            <button
              type="submit"
              disabled={saving}
              className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-fg disabled:opacity-60"
            >
              {saving ? "Guardando…" : "Guardar"}
            </button>
          )}
          {!canWrite && (
            <p className="text-xs text-slate-500">Tu rol no permite editar la voz de marca.</p>
          )}
        </form>
      )}
    </div>
  );
}
