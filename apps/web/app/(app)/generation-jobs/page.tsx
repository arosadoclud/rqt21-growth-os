"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { GenerationJob, GenerationStatus, GenerationType } from "@rqt21/contracts";
import { GENERATION_STATUSES, GENERATION_TYPES } from "@rqt21/contracts";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatDate } from "@/lib/ui";

const STATUS_LABELS: Record<GenerationStatus, string> = {
  QUEUED: "En cola",
  RUNNING: "Ejecutando",
  COMPLETED: "Completado",
  FAILED: "Fallido",
  CANCELLED: "Cancelado",
};

export default function GenerationJobsPage() {
  const { currentOrgId } = useAuth();
  const [items, setItems] = useState<GenerationJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<GenerationStatus | "">("");
  const [typeFilter, setTypeFilter] = useState<GenerationType | "">("");

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      if (typeFilter) params.generation_type = typeFilter;
      setItems(await api.listGenerationJobs(currentOrgId, params));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar generaciones");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, statusFilter, typeFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Historial de generaciones</h1>
        <Button asChild>
          <Link href="/generate">Nueva generación</Link>
        </Button>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <Select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as GenerationStatus | "")}
          className="w-52"
        >
          <option value="">Todos los estados</option>
          {GENERATION_STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </Select>
        <Select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as GenerationType | "")}
          className="w-52"
        >
          <option value="">Todos los tipos</option>
          {GENERATION_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </Select>
      </div>

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fecha</TableHead>
              <TableHead>Tipo</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Proveedor</TableHead>
              <TableHead>Costo</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground">
                  Cargando…
                </TableCell>
              </TableRow>
            )}
            {!loading && items.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground">
                  Sin generaciones
                </TableCell>
              </TableRow>
            )}
            {items.map((j) => (
              <TableRow key={j.id}>
                <TableCell className="text-muted-foreground">{formatDate(j.created_at)}</TableCell>
                <TableCell>{j.generation_type}</TableCell>
                <TableCell>
                  <Link href={`/generation-jobs/${j.id}`} className="text-primary hover:underline">
                    {STATUS_LABELS[j.status]}
                  </Link>
                </TableCell>
                <TableCell className="text-muted-foreground">{j.provider}</TableCell>
                <TableCell className="text-muted-foreground">
                  {j.visibility === "restricted" ? "—" : j.estimated_cost ?? "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
