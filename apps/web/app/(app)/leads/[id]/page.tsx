"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import type { Lead, LeadActivity, LeadStatus } from "@rqt21/contracts";
import { LEAD_STATUSES } from "@rqt21/contracts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
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

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;
  if (loading && !lead) return <p className="text-sm text-muted-foreground">Cargando…</p>;
  if (!lead) return <p className="text-sm text-muted-foreground">Lead no encontrado.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {lead.first_name}
          {lead.last_name ? ` ${lead.last_name}` : ""}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">Estado: {STATUS_LABELS[lead.status]} · Fuente: {lead.source}</p>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground text-lg">Contacto</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {!canSeePii && <p className="text-muted-foreground">Tu rol no permite ver datos personales.</p>}
            {canSeePii && (
              <>
                {lead.email && <p><strong>Email:</strong> <a href={`mailto:${lead.email}`} className="text-primary hover:underline">{lead.email}</a></p>}
                {lead.phone && <p><strong>Teléfono:</strong> {lead.phone}</p>}
                {lead.whatsapp && (
                  <p>
                    <strong>WhatsApp:</strong>{" "}
                    <a
                      href={`https://wa.me/${lead.whatsapp.replace(/[^\d]/g, "")}`}
                      className="text-primary hover:underline"
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
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-foreground text-lg">Atribución</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p><strong>Campaña:</strong> {lead.campaign_id || "—"}</p>
            <p><strong>Contenido:</strong> {lead.content_item_id || "—"}</p>
            <p><strong>Tracking link:</strong> {lead.tracking_link_id || "—"}</p>
            <p><strong>UTM source:</strong> {lead.utm_source || "—"}</p>
            <p><strong>UTM medium:</strong> {lead.utm_medium || "—"}</p>
            <p><strong>UTM campaign:</strong> {lead.utm_campaign || "—"}</p>
            <p><strong>UTM content:</strong> {lead.utm_content || "—"}</p>
          </CardContent>
        </Card>
      </div>

      {canWrite && (
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground text-lg">Cambiar estado</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {LEAD_STATUSES.map((s) => (
                <Button
                  key={s}
                  size="sm"
                  variant={lead.status === s ? "default" : "outline"}
                  onClick={() => void changeStatus(s)}
                  disabled={lead.status === s}
                >
                  {STATUS_LABELS[s]}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {canWrite && (
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground text-lg">Añadir nota</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} />
            <Button onClick={() => void addNote()} disabled={!note.trim()}>
              Añadir nota
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-foreground text-lg">Actividad</CardTitle>
        </CardHeader>
        <CardContent>
          {activities.length === 0 && <p className="text-sm text-muted-foreground">Sin actividad.</p>}
          <ol className="space-y-2">
            {activities.map((a) => (
              <li key={a.id} className="border-l-2 border-border pl-3 text-sm">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>{a.activity_type}</span>
                  <span>{formatDate(a.created_at)}</span>
                </div>
                {a.description && <p>{a.description}</p>}
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
