import type { ReactNode } from "react";
import { Filter, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface FilterBarProps {
  search: string;
  onSearchChange: (value: string) => void;
  searchLabel: string;
  searchPlaceholder: string;
  hasFilters: boolean;
  onClear: () => void;
  children?: ReactNode;
  className?: string;
}

export function FilterBar({
  search,
  onSearchChange,
  searchLabel,
  searchPlaceholder,
  hasFilters,
  onClear,
  children,
  className,
}: FilterBarProps) {
  return (
    <Card className={cn("bg-card/80 shadow-none", className)}>
      <CardContent className="p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <label className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder={searchPlaceholder}
              className="pl-9"
              aria-label={searchLabel}
            />
          </label>
          {children && (
            <div className="grid gap-3 sm:grid-cols-2 lg:flex lg:items-center">
              {children}
            </div>
          )}
          {hasFilters ? (
            <Button variant="ghost" size="sm" onClick={onClear}>
              Limpiar filtros
            </Button>
          ) : (
            <span className="flex min-h-8 items-center justify-end gap-2 text-xs text-muted-foreground">
              <Filter className="h-3.5 w-3.5" />
              Sin filtros
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
