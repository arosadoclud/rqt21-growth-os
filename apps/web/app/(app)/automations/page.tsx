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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;
  if (!canManage) {
    return (
      <p className="text-sm text-muted-foreground">
        Solo OWNER/ADMIN pueden administrar automatizaciones.
      </p>
    );
  }

  const selectedCombo = ALLOWED_COMBINATIONS[comboIndex];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Automatizaciones</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Solo plantillas predefinidas — sin editor de reglas libres, sin ejecución de código de usuario.
          Ninguna automatización publica contenido automáticamente; como máximo crea un borrador para revisión humana.
        </p>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
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

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nombre</TableHead>
              <TableHead>Disparador → Acción</TableHead>
              <TableHead>Ejecuciones</TableHead>
              <TableHead>Activa</TableHead>
              <TableHead>Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">Cargando…</TableCell></TableRow>
            )}
            {!loading && items.length === 0 && (
              <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">Sin automatizaciones</TableCell></TableRow>
            )}
            {items.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell className="text-muted-foreground">{r.trigger_type} → {r.action_type}</TableCell>
                <TableCell className="text-muted-foreground">{r.execution_count}</TableCell>
                <TableCell>
                  <Badge variant={r.is_active ? "success" : "secondary"}>
                    {r.is_active ? "Activa" : "Inactiva"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Button variant="outline" size="sm" disabled={busyId === r.id} onClick={() => void toggle(r)}>
                    {r.is_active ? "Desactivar" : "Activar"}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-foreground text-lg">Nueva automatización</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onCreate} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm sm:col-span-2">
                <span className="text-muted-foreground">Plantilla</span>
                <Select value={comboIndex} onChange={(e) => setComboIndex(Number(e.target.value))} className="mt-1">
                  {ALLOWED_COMBINATIONS.map((c, i) => (
                    <option key={c.label} value={i}>{c.label}</option>
                  ))}
                </Select>
              </label>
              <label className="block text-sm">
                <span className="text-muted-foreground">Nombre</span>
                <Input value={name} onChange={(e) => setName(e.target.value)} required className="mt-1" />
              </label>
              <label className="block text-sm">
                <span className="text-muted-foreground">Marca (opcional)</span>
                <Select value={brandId} onChange={(e) => setBrandId(e.target.value)} className="mt-1">
                  <option value="">Todas las marcas</option>
                  {brands.map((b) => (<option key={b.id} value={b.id}>{b.name}</option>))}
                </Select>
              </label>
              {selectedCombo.action === "CREATE_PUBLICATION_DRAFT" && (
                <label className="block text-sm sm:col-span-2">
                  <span className="text-muted-foreground">Conexión de publicación destino</span>
                  <Select value={connectionId} onChange={(e) => setConnectionId(e.target.value)} required className="mt-1">
                    <option value="">Selecciona una conexión</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>{c.account_name} ({c.provider})</option>
                    ))}
                  </Select>
                </label>
              )}
            </div>
            {formError && (
              <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {formError}
              </div>
            )}
            <Button type="submit" disabled={submitting}>
              {submitting ? "Creando…" : "Crear automatización"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value?: number | string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-sm text-muted-foreground">{label}</div>
        <div className="mt-1 text-2xl font-semibold tracking-tight">
          {value === undefined || value === null ? "—" : value}
        </div>
      </CardContent>
    </Card>
  );
}
