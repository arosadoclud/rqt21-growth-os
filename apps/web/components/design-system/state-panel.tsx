import type { ComponentType, ReactNode } from "react";
import { AlertCircle, Inbox } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface StatePanelProps {
  title: string;
  description: ReactNode;
  icon?: ComponentType<{ className?: string }>;
  actionLabel?: string;
  onAction?: () => void;
  tone?: "neutral" | "error";
  compact?: boolean;
  className?: string;
}

export function StatePanel({
  title,
  description,
  icon: Icon,
  actionLabel,
  onAction,
  tone = "neutral",
  compact = false,
  className,
}: StatePanelProps) {
  const StateIcon = Icon ?? (tone === "error" ? AlertCircle : Inbox);

  return (
    <div
      role={tone === "error" ? "alert" : undefined}
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-dashed px-5 text-center",
        compact ? "min-h-36 py-6" : "min-h-56 py-10",
        tone === "error"
          ? "border-destructive/30 bg-destructive/5"
          : "border-border bg-card/40",
        className,
      )}
    >
      <span
        className={cn(
          "flex h-10 w-10 items-center justify-center rounded-xl",
          tone === "error"
            ? "bg-destructive/10 text-destructive"
            : "bg-interactive text-muted-foreground",
        )}
      >
        <StateIcon className="h-5 w-5" />
      </span>
      <h3 className="mt-4 text-sm font-semibold text-foreground">{title}</h3>
      <div className="mt-1 max-w-md text-sm leading-6 text-muted-foreground">{description}</div>
      {actionLabel && onAction && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

export function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-label="Cargando contenido" role="status">
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={index}
          className="h-14 animate-pulse rounded-lg border border-border/60 bg-muted/50"
        />
      ))}
      <span className="sr-only">Cargando…</span>
    </div>
  );
}
