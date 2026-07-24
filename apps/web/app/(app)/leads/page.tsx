"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { Lead, LeadSource, LeadStatus } from "@rqt21/contracts";
import { LEAD_SOURCES, LEAD_STATUSES } from "@rqt21/contracts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatDate } from "@/lib/ui";

const STATUS_LABELS: Record<LeadStatus, string> = {
  NEW: "Nuevo",
  CONTACTED: "Contactado",
  QUALIFIED: "Calificado",
  PROPOSAL: "Propuesta",
  WON: "Ganado",
  LOST: "Perdido",
  ARCHIVED: "Archivado",
};

export default function LeadsPage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite =
    org?.role === "OWNER" ||
    org?.role === "ADMIN" ||
    org?.role === "SALES" ||
    org?.role === "MARKETER";
  const canExport =
    org?.role === "OWNER" || org?.role === "ADMIN" || org?.role === "SALES";
  const canSeePii = canWrite || canExport;

  const [items, setItems] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState<LeadStatus | "">("");
  const [sourceFilter, setSourceFilter] = useState<LeadSource | "">("");

  const [firstName, setFirstName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [source, setSource] = useState<LeadSource>("MANUAL");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (q) params.q = q;
      if (statusFilter) params.status = statusFilter;
      if (sourceFilter) params.source = sourceFilter;
      setItems(await api.listLeads(currentOrgId, params));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar leads");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, q, statusFilter, sourceFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await api.createLead(currentOrgId, {
        first_name: firstName,
        email: email || null,
        phone: phone || null,
        source,
      });
      setFirstName("");
      setEmail("");
      setPhone("");
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Error creando lead");
    } finally {
      setSubmitting(false);
    }
  };

  if (!currentOrgId) return <p>Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Leads</h1>
        {canExport && (
          <a
            href={api.exportLeadsUrl(currentOrgId)}
            className="rounded-md border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50"
          >
            Exportar CSV
          </a>
        )}
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-3 text-sm">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar…"
          className="rounded-md border border-slate-300 px-3 py-1"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as LeadStatus | "")}
          className="rounded-md border border-slate-300 bg-white px-2 py-1"
        >
          <option value="">Todos los estados</option>
          {LEAD_STATUSES.map((s) => (
            <option key={s} value={s}>{STATUS_LABELS[s]}</option>
          ))}
        </select>
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value as LeadSource | "")}
          className="rounded-md border border-slate-300 bg-white px-2 py-1"
        >
          <option value="">Todas las fuentes</option>
          {LEAD_SOURCES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Nombre</th>
              <th className="px-4 py-2 font-medium">Contacto</th>
              <th className="px-4 py-2 font-medium">Fuente</th>
              <th className="px-4 py-2 font-medium">Estado</th>
              <th className="px-4 py-2 font-medium">Creado</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">Cargando…</td></tr>
            )}
            {!loading && items.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">Sin leads</td></tr>
            )}
            {items.map((l) => (
              <tr key={l.id} className="border-t border-slate-100">
                <td className="px-4 py-2">
                  <Link href={`/leads/${l.id}`} className="text-brand hover:underline">
                    {l.first_name}{l.last_name ? ` ${l.last_name}` : ""}
                  </Link>
                </td>
                <td className="px-4 py-2 text-slate-600">
                  {canSeePii ? (
                    <>
                      {l.email && <div>{l.email}</div>}
                      {l.phone && <div className="text-xs">{l.phone}</div>}
                      {l.whatsapp && <div className="text-xs">WA: {l.whatsapp}</div>}
                    </>
                  ) : (
                    <span className="text-slate-400">— oculto —</span>
                  )}
                </td>
                <td className="px-4 py-2 text-slate-600">{l.source}</td>
                <td className="px-4 py-2 text-slate-600">{STATUS_LABELS[l.status]}</td>
                <td className="px-4 py-2 text-slate-500">{formatDate(l.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {canWrite && (
        <form onSubmit={onCreate} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-medium text-slate-900">Nuevo lead</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-slate-700">Nombre</span>
              <input required value={firstName} onChange={(e) => setFirstName(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Correo</span>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Teléfono</span>
              <input value={phone} onChange={(e) => setPhone(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Fuente</span>
              <select value={source} onChange={(e) => setSource(e.target.value as LeadSource)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">
                {LEAD_SOURCES.map((s) => (<option key={s} value={s}>{s}</option>))}
              </select>
            </label>
          </div>
          {formError && (
            <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {formError}
            </div>
          )}
          <button type="submit" disabled={submitting}
            className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-fg disabled:opacity-60">
            {submitting ? "Guardando…" : "Crear lead"}
          </button>
        </form>
      )}
    </div>
  );
}
