"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import type { Lead, LeadActivity, LeadStatus } from "@rqt21/contracts";
import { LEAD_STATUSES } from "@rqt21/contracts";
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

export default function LeadDetail() {
  const params = useParams<{ id: string }>();
  const leadId = params.id;
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite =
    org?.role === "OWNER" ||
    org?.role === "ADMIN" ||
    org?.role === "SALES" ||
    org?.role === "MARKETER";
  const canSeePii = canWrite;

  const [lead, setLead] = useState<Lead | null>(null);
  const [activities, setActivities] = useState<LeadActivity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    if (!currentOrgId || !leadId) return;
    setLoading(true);
    setError(null);
    try {
      const [l, acts] = await Promise.all([
        api.getLead(currentOrgId, leadId),
        api.listLeadActivities(currentOrgId, leadId),
      ]);
      setLead(l);
      setActivities(acts);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar lead");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, leadId]);

  useEffect(() => {
    void load();
  }, [load]);

  const changeStatus = async (s: LeadStatus) => {
    if (!currentOrgId || !leadId) return;
    try {
      await api.changeLeadStatus(currentOrgId, leadId, s);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error");
    }
  };

  const addNote = async () => {
    if (!currentOrgId || !leadId || !note.trim()) return;
    try {
      await api.createLeadActivity(currentOrgId, leadId, {
        activity_type: "NOTE_ADDED",
        description: note.trim(),
      });
      setNote("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error");
    }
  };

  if (!currentOrgId) return <p>Selecciona una organización.</p>;
  if (loading && !lead) return <p className="text-sm text-slate-500">Cargando…</p>;
  if (!lead) return <p className="text-sm text-slate-500">Lead no encontrado.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">
          {lead.first_name}
          {lead.last_name ? ` ${lead.last_name}` : ""}
        </h1>
        <p className="text-sm text-slate-500">Estado: {STATUS_LABELS[lead.status]} · Fuente: {lead.source}</p>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 text-sm">
          <h2 className="text-lg font-medium text-slate-900">Contacto</h2>
          {!canSeePii && <p className="text-slate-500">Tu rol no permite ver datos personales.</p>}
          {canSeePii && (
            <>
              {lead.email && <p><strong>Email:</strong> <a href={`mailto:${lead.email}`} className="text-brand">{lead.email}</a></p>}
              {lead.phone && <p><strong>Teléfono:</strong> {lead.phone}</p>}
              {lead.whatsapp && (
                <p>
                  <strong>WhatsApp:</strong>{" "}
                  <a
                    href={`https://wa.me/${lead.whatsapp.replace(/[^\d]/g, "")}`}
                    className="text-brand"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {lead.whatsapp}
                  </a>
                </p>
              )}
              {lead.country && <p><strong>País:</strong> {lead.country}</p>}
              {lead.city && <p><strong>Ciudad:</strong> {lead.city}</p>}
            </>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 text-sm">
          <h2 className="text-lg font-medium text-slate-900">Atribución</h2>
          <p><strong>Campaña:</strong> {lead.campaign_id || "—"}</p>
          <p><strong>Contenido:</strong> {lead.content_item_id || "—"}</p>
          <p><strong>Tracking link:</strong> {lead.tracking_link_id || "—"}</p>
          <p><strong>UTM source:</strong> {lead.utm_source || "—"}</p>
          <p><strong>UTM medium:</strong> {lead.utm_medium || "—"}</p>
          <p><strong>UTM campaign:</strong> {lead.utm_campaign || "—"}</p>
          <p><strong>UTM content:</strong> {lead.utm_content || "—"}</p>
        </div>
      </div>

      {canWrite && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
          <h2 className="text-lg font-medium text-slate-900">Cambiar estado</h2>
          <div className="flex flex-wrap gap-2">
            {LEAD_STATUSES.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => void changeStatus(s)}
                disabled={lead.status === s}
                className={
                  lead.status === s
                    ? "rounded-md bg-brand px-3 py-1 text-xs text-white"
                    : "rounded-md border border-slate-300 px-3 py-1 text-xs hover:bg-slate-50"
                }
              >
                {STATUS_LABELS[s]}
              </button>
            ))}
          </div>
        </div>
      )}

      {canWrite && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2">
          <h2 className="text-lg font-medium text-slate-900">Añadir nota</h2>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={() => void addNote()}
            className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-fg disabled:opacity-60"
            disabled={!note.trim()}
          >
            Añadir nota
          </button>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-lg font-medium text-slate-900">Actividad</h2>
        {activities.length === 0 && <p className="text-sm text-slate-500">Sin actividad.</p>}
        <ol className="space-y-2">
          {activities.map((a) => (
            <li key={a.id} className="border-l-2 border-slate-200 pl-3 text-sm">
              <div className="flex justify-between text-xs text-slate-500">
                <span>{a.activity_type}</span>
                <span>{formatDate(a.created_at)}</span>
              </div>
              {a.description && <p className="text-slate-700">{a.description}</p>}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
