"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { Lead, LeadSource, LeadStatus } from "@rqt21/contracts";
import { LEAD_SOURCES, LEAD_STATUSES } from "@rqt21/contracts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Leads</h1>
        {canExport && (
          <Button variant="outline" size="sm" asChild>
            <a href={api.exportLeadsUrl(currentOrgId)}>Exportar CSV</a>
          </Button>
        )}
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar…"
          className="w-56"
        />
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as LeadStatus | "")} className="w-48">
          <option value="">Todos los estados</option>
          {LEAD_STATUSES.map((s) => (
            <option key={s} value={s}>{STATUS_LABELS[s]}</option>
          ))}
        </Select>
        <Select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value as LeadSource | "")} className="w-48">
          <option value="">Todas las fuentes</option>
          {LEAD_SOURCES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </Select>
      </div>

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nombre</TableHead>
              <TableHead>Contacto</TableHead>
              <TableHead>Fuente</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Creado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">Cargando…</TableCell></TableRow>
            )}
            {!loading && items.length === 0 && (
              <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">Sin leads</TableCell></TableRow>
            )}
            {items.map((l) => (
              <TableRow key={l.id}>
                <TableCell>
                  <Link href={`/leads/${l.id}`} className="text-primary hover:underline">
                    {l.first_name}{l.last_name ? ` ${l.last_name}` : ""}
                  </Link>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {canSeePii ? (
                    <>
                      {l.email && <div>{l.email}</div>}
                      {l.phone && <div className="text-xs">{l.phone}</div>}
                      {l.whatsapp && <div className="text-xs">WA: {l.whatsapp}</div>}
                    </>
                  ) : (
                    <span>— oculto —</span>
                  )}
                </TableCell>
                <TableCell className="text-muted-foreground">{l.source}</TableCell>
                <TableCell className="text-muted-foreground">{STATUS_LABELS[l.status]}</TableCell>
                <TableCell className="text-muted-foreground">{formatDate(l.created_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {canWrite && (
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground text-lg">Nuevo lead</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onCreate} className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-sm">
                  <span className="text-muted-foreground">Nombre</span>
                  <Input required value={firstName} onChange={(e) => setFirstName(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Correo</span>
                  <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Teléfono</span>
                  <Input value={phone} onChange={(e) => setPhone(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Fuente</span>
                  <Select value={source} onChange={(e) => setSource(e.target.value as LeadSource)} className="mt-1">
                    {LEAD_SOURCES.map((s) => (<option key={s} value={s}>{s}</option>))}
                  </Select>
                </label>
              </div>
              {formError && (
                <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </div>
              )}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Guardando…" : "Crear lead"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
