import type { ReactNode } from "react";

export function SectionHeader({
  title,
  description,
  action,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 className="text-base font-semibold tracking-[-0.02em] text-foreground">{title}</h2>
        {description && <div className="mt-1 text-sm text-muted-foreground">{description}</div>}
      </div>
      {action}
    </div>
  );
}
