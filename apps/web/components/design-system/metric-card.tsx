import type { ComponentType, ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type MetricTone = "neutral" | "positive" | "warning" | "critical" | "info";

const toneStyles: Record<MetricTone, { icon: string; accent: string }> = {
  neutral: { icon: "bg-interactive text-muted-foreground", accent: "bg-border" },
  positive: { icon: "bg-success/15 text-success", accent: "bg-success" },
  warning: { icon: "bg-warning/15 text-warning", accent: "bg-warning" },
  critical: { icon: "bg-destructive/15 text-destructive", accent: "bg-destructive" },
  info: { icon: "bg-info/15 text-info", accent: "bg-info" },
};

interface MetricCardProps {
  label: string;
  value: ReactNode;
  helper?: ReactNode;
  icon?: ComponentType<{ className?: string }>;
  tone?: MetricTone;
  loading?: boolean;
  className?: string;
}

export function MetricCard({
  label,
  value,
  helper,
  icon: Icon,
  tone = "neutral",
  loading = false,
  className,
}: MetricCardProps) {
  const styles = toneStyles[tone];

  return (
    <Card className={cn("relative overflow-hidden bg-card/80 shadow-none", className)}>
      <span aria-hidden className={cn("absolute inset-x-0 top-0 h-px", styles.accent)} />
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          {Icon && (
            <span className={cn("flex h-8 w-8 items-center justify-center rounded-lg", styles.icon)}>
              <Icon className="h-4 w-4" />
            </span>
          )}
        </div>
        {loading ? (
          <div className="mt-5 h-9 w-24 animate-pulse rounded-md bg-muted" aria-label="Cargando" />
        ) : (
          <div className="metric-numbers mt-4 text-3xl font-semibold tracking-[-0.04em] text-foreground">
            {value}
          </div>
        )}
        {helper && <div className="mt-2 text-xs leading-5 text-muted-foreground">{helper}</div>}
      </CardContent>
    </Card>
  );
}
