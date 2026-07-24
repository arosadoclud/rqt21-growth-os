"use client";

import { useCallback, useEffect, useState } from "react";
import type { Notification } from "@rqt21/contracts";
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

  if (!currentOrgId) return <p>Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Notificaciones</h1>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
        >
          Actualizar
        </button>
      </div>
      <p className="text-xs text-slate-500">
        Sin tiempo real — actualiza manualmente o vuelve a esta página para ver novedades.
      </p>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} />
        Solo no leídas
      </label>

      <ul className="space-y-2">
        {loading && <li className="text-sm text-slate-400">Cargando…</li>}
        {!loading && items.length === 0 && (
          <li className="text-sm text-slate-400">Sin notificaciones</li>
        )}
        {items.map((n) => (
          <li
            key={n.id}
            className={`rounded-xl border p-4 text-sm ${
              n.read_at ? "border-slate-200 bg-white" : "border-brand/40 bg-brand/5"
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-medium text-slate-900">{n.title}</p>
                <p className="mt-1 text-slate-600">{n.message}</p>
                <p className="mt-1 text-xs text-slate-400">
                  {n.notification_type} · {formatDate(n.created_at)}
                </p>
              </div>
              {!n.read_at && (
                <button
                  type="button"
                  onClick={() => void markRead(n.id)}
                  className="shrink-0 rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"
                >
                  Marcar leída
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
