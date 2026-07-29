"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Bell,
  CheckCircle2,
  Clock,
  ImageOff,
  Link2Off,
  Gauge,
  Trophy,
  XCircle,
} from "lucide-react";
import type { Notification, NotificationType } from "@rqt21/contracts";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatDate } from "@/lib/ui";

const POLL_INTERVAL_MS = 30_000;

const TYPE_META: Record<
  NotificationType,
  { icon: React.ComponentType<{ className?: string }>; tone: "success" | "warning" | "destructive" | "primary" }
> = {
  CONTENT_APPROVED: { icon: CheckCircle2, tone: "success" },
  PUBLICATION_UPCOMING: { icon: Clock, tone: "primary" },
  PUBLICATION_SUCCEEDED: { icon: CheckCircle2, tone: "success" },
  PUBLICATION_FAILED: { icon: XCircle, tone: "destructive" },
  ASSET_REJECTED: { icon: ImageOff, tone: "warning" },
  CONNECTION_EXPIRED: { icon: Link2Off, tone: "warning" },
  AI_BUDGET_NEAR_LIMIT: { icon: Gauge, tone: "warning" },
  LEAD_WON: { icon: Trophy, tone: "success" },
};

const TONE_CLASSES: Record<string, string> = {
  success: "bg-success/15 text-success",
  warning: "bg-warning/15 text-warning",
  destructive: "bg-destructive/15 text-destructive",
  primary: "bg-primary/15 text-primary",
};

export function NotificationBell() {
  const { currentOrgId } = useAuth();
  const [items, setItems] = useState<Notification[]>([]);
  const [justArrivedId, setJustArrivedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    try {
      const fresh = await api.listNotifications(currentOrgId, true);
      setItems((prev) => {
        const prevIds = new Set(prev.map((n) => n.id));
        const newest = fresh.find((n) => !prevIds.has(n.id));
        if (newest && prev.length > 0) setJustArrivedId(newest.id);
        return fresh;
      });
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

  useEffect(() => {
    if (!justArrivedId) return;
    const t = setTimeout(() => setJustArrivedId(null), 2500);
    return () => clearTimeout(t);
  }, [justArrivedId]);

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
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-medium text-destructive-foreground shadow-sm">
              {items.length > 9 ? "9+" : items.length}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-96">
        <DropdownMenuLabel className="flex items-center justify-between">
          <span>Notificaciones sin leer</span>
          {items.length > 0 && (
            <span className="text-xs font-normal text-muted-foreground">{items.length}</span>
          )}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {items.length === 0 && (
          <div className="flex flex-col items-center gap-2 px-2 py-8 text-center">
            <CheckCircle2 className="h-8 w-8 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">Estás al día — sin novedades.</p>
          </div>
        )}
        {items.slice(0, 6).map((n) => {
          const meta = TYPE_META[n.notification_type];
          const Icon = meta?.icon ?? Bell;
          const tone = meta?.tone ?? "primary";
          return (
            <DropdownMenuItem
              key={n.id}
              onSelect={() => void markRead(n.id)}
              className={cn(
                "flex items-start gap-3 whitespace-normal py-2.5",
                n.id === justArrivedId && "animate-slide-in-right bg-accent/50"
              )}
            >
              <span className={cn("mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full", TONE_CLASSES[tone])}>
                <Icon className="h-3.5 w-3.5" />
              </span>
              <span className="flex flex-col gap-0.5">
                <span className="font-medium leading-tight">{n.title}</span>
                <span className="text-xs text-muted-foreground">{n.message}</span>
                <span className="text-[11px] text-muted-foreground/70">{formatDate(n.created_at)}</span>
              </span>
            </DropdownMenuItem>
          );
        })}
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
