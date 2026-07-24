"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Bell } from "lucide-react";
import type { Notification } from "@rqt21/contracts";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatDate } from "@/lib/ui";

const POLL_INTERVAL_MS = 30_000;

export function NotificationBell() {
  const { currentOrgId } = useAuth();
  const [items, setItems] = useState<Notification[]>([]);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    try {
      setItems(await api.listNotifications(currentOrgId, true));
    } catch {
      // Silent — the bell is a convenience surface, not a source of truth;
      // /notifications shows real errors on its own.
    }
  }, [currentOrgId]);

  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [load]);

  const markRead = async (id: string) => {
    if (!currentOrgId) return;
    try {
      await api.markNotificationRead(currentOrgId, id);
      await load();
    } catch {
      // best-effort
    }
  };

  if (!currentOrgId) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label="Notificaciones">
          <Bell className="h-4 w-4" />
          {items.length > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-medium text-destructive-foreground">
              {items.length > 9 ? "9+" : items.length}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel>Notificaciones sin leer</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {items.length === 0 && (
          <p className="px-2 py-3 text-sm text-muted-foreground">Sin novedades.</p>
        )}
        {items.slice(0, 6).map((n) => (
          <DropdownMenuItem
            key={n.id}
            onSelect={() => void markRead(n.id)}
            className="flex flex-col items-start gap-0.5 whitespace-normal"
          >
            <span className="font-medium">{n.title}</span>
            <span className="text-xs text-muted-foreground">{n.message}</span>
            <span className="text-[11px] text-muted-foreground">{formatDate(n.created_at)}</span>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/notifications" className="justify-center text-sm text-primary">
            Ver todas
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
