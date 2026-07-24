"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type {
  AutomationActionType,
  AutomationRule,
  AutomationSummary,
  AutomationTriggerType,
  Brand,
  PublishingConnection,
} from "@rqt21/contracts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canAdmin } from "@/lib/ui";

// Only these combinations are executable server-side — see
// app/automation/engine.py::_ALLOWED_COMBINATIONS. The UI mirrors that
// closed list so users never submit a combination the backend will reject.
const ALLOWED_COMBINATIONS: Array<{ trigger: AutomationTriggerType; action: AutomationActionType; label: string }> = [
  { trigger: "CONTENT_APPROVED", action: "CREATE_PUBLICATION_DRAFT", label: "Contenido aprobado → crear borrador de publicación" },
  { trigger: "CONTENT_APPROVED", action: "GENERATE_TRACKING_LINK", label: "Contenido aprobado → generar enlace de seguimiento" },
  { trigger: "PUBLICATION_FAILED", action: "SCHEDULE_RETRY", label: "Publicación fallida → programar reintento" },
  { trigger: "PUBLICATION_FAILED", action: "SEND_INTERNAL_NOTIFICATION", label: "Publicación fallida → notificar" },
  { trigger: "LEAD_CREATED", action: "CREATE_LEAD_ACTIVITY", label: "Lead creado → registrar actividad" },
  { trigger: "LEAD_STATUS_CHANGED", action: "CREATE_LEAD_ACTIVITY", label: "Cambio de estado de lead → registrar actividad" },
  { trigger: "LEAD_STATUS_CHANGED", action: "SEND_INTERNAL_NOTIFICATION", label: "Cambio de estado de lead → notificar" },
  { trigger: "CALENDAR_ITEM_DUE", action: "SEND_INTERNAL_NOTIFICATION", label: "Ítem de calendario vence → notificar" },
];

export default function AutomationsPage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canManage = canAdmin(org?.role);

  const [items, setItems] = useState<AutomationRule[]>([]);
  const [summary, setSummary] = useState<AutomationSummary | null>(null);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [connections, setConnections] = useState<PublishingConnection[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [comboIndex, setComboIndex] = useState(0);
  const [name, setName] = useState("");
  const [brandId, setBrandId] = useState("");
  const [connectionId, setConnectionId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId || !canManage) return;
    setLoading(true);
    setError(null);
    try {
      const [a, s, bs, cs] = await Promise.all([
        api.listAutomations(currentOrgId),
        api.automationSummary(currentOrgId).catch(() => null),
        api.listBrands(currentOrgId),
        api.listConnections(currentOrgId).catch(() => []),
      ]);
      setItems(a);
      setSummary(s);
      setBrands(bs);
      setConnections(cs);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar automatizaciones");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, canManage]);

  useEffect(() => {
    void load();
  }, [load]);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !name) return;
    const combo = ALLOWED_COMBINATIONS[comboIndex];
    setSubmitting(true);
    setFormError(null);
    try {
      const action_config: Record<string, unknown> =
        combo.action === "CREATE_PUBLICATION_DRAFT"
          ? { publishing_connection_id: connectionId, publication_type: "POST", default_caption: "" }
          : {};
      await api.createAutomation(currentOrgId, {
        name,
        brand_id: brandId || null,
        trigger_type: combo.trigger,
        action_type: combo.action,
        conditions: {},
        action_config,
        is_active: true,
      });
      setName("");
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Error creando automatización");
    } finally {
      setSubmitting(false);
    }
  };

  const toggle = async (rule: AutomationRule) => {
    if (!currentOrgId) return;
    setBusyId(rule.id);
    try {
      await api.updateAutomation(currentOrgId, rule.id, { is_active: !rule.is_active });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error");
    } finally {
      setBusyId(null);
    }
  };

  if (!currentOrgId) return <p>Selecciona una organización.</p>;
  if (!canManage) {
    return (
      <p className="text-sm text-slate-500">
        Solo OWNER/ADMIN pueden administrar automatizaciones.
      </p>
    );
  }

  const selectedCombo = ALLOWED_COMBINATIONS[comboIndex];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Automatizaciones</h1>
      <p className="text-sm text-slate-500">
        Solo plantillas predefinidas — sin editor de reglas libres, sin ejecución de código de usuario.
        Ninguna automatización publica contenido automáticamente; como máximo crea un borrador para revisión humana.
      </p>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      {summary && (
        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard label="Reglas activas" value={summary.active_rules} />
          <StatCard label="Ejecuciones totales" value={summary.total_executions} />
          <StatCard label="Bucles prevenidos" value={summary.loop_preventions} />
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Nombre</th>
              <th className="px-4 py-2 font-medium">Disparador → Acción</th>
              <th className="px-4 py-2 font-medium">Ejecuciones</th>
              <th className="px-4 py-2 font-medium">Activa</th>
              <th className="px-4 py-2 font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">Cargando…</td></tr>
            )}
            {!loading && items.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">Sin automatizaciones</td></tr>
            )}
            {items.map((r) => (
              <tr key={r.id} className="border-t border-slate-100">
                <td className="px-4 py-2 text-slate-900">{r.name}</td>
                <td className="px-4 py-2 text-slate-600">{r.trigger_type} → {r.action_type}</td>
                <td className="px-4 py-2 text-slate-500">{r.execution_count}</td>
                <td className="px-4 py-2">
                  <span className={`rounded-full border px-2 py-0.5 text-xs ${
                    r.is_active
                      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                      : "border-slate-200 bg-slate-100 text-slate-500"
                  }`}>
                    {r.is_active ? "Activa" : "Inactiva"}
                  </span>
                </td>
                <td className="px-4 py-2">
                  <button type="button" disabled={busyId === r.id}
                    onClick={() => void toggle(r)}
                    className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-60">
                    {r.is_active ? "Desactivar" : "Activar"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <form onSubmit={onCreate} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-lg font-medium text-slate-900">Nueva automatización</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm sm:col-span-2">
            <span className="text-slate-700">Plantilla</span>
            <select value={comboIndex} onChange={(e) => setComboIndex(Number(e.target.value))}
              className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
              {ALLOWED_COMBINATIONS.map((c, i) => (
                <option key={c.label} value={i}>{c.label}</option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-slate-700">Nombre</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
          </label>
          <label className="block text-sm">
            <span className="text-slate-700">Marca (opcional)</span>
            <select value={brandId} onChange={(e) => setBrandId(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
              <option value="">Todas las marcas</option>
              {brands.map((b) => (<option key={b.id} value={b.id}>{b.name}</option>))}
            </select>
          </label>
          {selectedCombo.action === "CREATE_PUBLICATION_DRAFT" && (
            <label className="block text-sm sm:col-span-2">
              <span className="text-slate-700">Conexión de publicación destino</span>
              <select value={connectionId} onChange={(e) => setConnectionId(e.target.value)} required
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                <option value="">Selecciona una conexión</option>
                {connections.map((c) => (
                  <option key={c.id} value={c.id}>{c.account_name} ({c.provider})</option>
                ))}
              </select>
            </label>
          )}
        </div>
        {formError && (
          <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {formError}
          </div>
        )}
        <button type="submit" disabled={submitting}
          className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-fg disabled:opacity-60">
          {submitting ? "Creando…" : "Crear automatización"}
        </button>
      </form>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value?: number | string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">
        {value === undefined || value === null ? "—" : value}
      </div>
    </div>
  );
}
