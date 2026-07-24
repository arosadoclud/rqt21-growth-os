"use client";

import { useCallback, useEffect, useState } from "react";
import type { Notification } from "@rqt21/contracts";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatDate } from "@/lib/ui";

export default function NotificationsPage() {
  const { currentOrgId } = useAuth();
  const [items, setItems] = useState<Notification[]>([]);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      setItems(await api.listNotifications(currentOrgId, unreadOnly));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar notificaciones");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, unreadOnly]);

  useEffect(() => {
    void load();
  }, [load]);

  const markRead = async (id: string) => {
    if (!currentOrgId) return;
    try {
      await api.markNotificationRead(currentOrgId, id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error");
    }
  };

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Notificaciones</h1>
        <Button variant="outline" size="sm" onClick={() => void load()}>
          Actualizar
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Sin tiempo real — actualiza manualmente o vuelve a esta página para ver novedades.
      </p>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} className="rounded border-input" />
        Solo no leídas
      </label>

      <ul className="space-y-2">
        {loading && <li className="text-sm text-muted-foreground">Cargando…</li>}
        {!loading && items.length === 0 && (
          <li className="text-sm text-muted-foreground">Sin notificaciones</li>
        )}
        {items.map((n) => (
          <li key={n.id}>
            <Card className={cn(!n.read_at && "border-primary/40 bg-primary/5")}>
              <CardContent className="flex items-start justify-between gap-4 p-4">
                <div>
                  <p className="font-medium">{n.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{n.message}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {n.notification_type} · {formatDate(n.created_at)}
                  </p>
                </div>
                {!n.read_at && (
                  <Button variant="outline" size="sm" className="shrink-0" onClick={() => void markRead(n.id)}>
                    Marcar leída
                  </Button>
                )}
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
