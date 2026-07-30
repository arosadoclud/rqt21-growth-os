import type { ComponentType, ReactNode } from "react";

import { Pagination } from "@/components/design-system/pagination";
import { LoadingSkeleton, StatePanel } from "@/components/design-system/state-panel";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

export interface DataTableColumn<T> {
  key: string;
  label: string;
  render: (item: T) => ReactNode;
  className?: string;
  mobileClassName?: string;
}

interface DataTableProps<T> {
  items: T[];
  columns: DataTableColumn<T>[];
  rowKey: (item: T) => string;
  loading?: boolean;
  emptyTitle: string;
  emptyDescription: ReactNode;
  emptyIcon?: ComponentType<{ className?: string }>;
  emptyActionLabel?: string;
  onEmptyAction?: () => void;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  pageSizeOptions?: number[];
  ariaLabel: string;
  className?: string;
}

export function DataTable<T>({
  items,
  columns,
  rowKey,
  loading = false,
  emptyTitle,
  emptyDescription,
  emptyIcon,
  emptyActionLabel,
  onEmptyAction,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions,
  ariaLabel,
  className,
}: DataTableProps<T>) {
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageItems = items.slice((safePage - 1) * pageSize, safePage * pageSize);

  if (loading) {
    return (
      <Card className={cn("bg-card/80 shadow-none", className)}>
        <CardContent className="p-5"><LoadingSkeleton rows={6} /></CardContent>
      </Card>
    );
  }

  if (items.length === 0) {
    return (
      <StatePanel
        icon={emptyIcon}
        title={emptyTitle}
        description={emptyDescription}
        actionLabel={emptyActionLabel}
        onAction={onEmptyAction}
      />
    );
  }

  return (
    <Card className={cn("overflow-hidden bg-card/85 shadow-none", className)}>
      <div className="hidden overflow-x-auto md:block">
        <Table aria-label={ariaLabel}>
          <TableHeader>
            <TableRow className="bg-interactive/35 hover:bg-interactive/35">
              {columns.map((column) => (
                <TableHead
                  key={column.key}
                  className={cn(
                    "h-11 text-[11px] font-semibold uppercase tracking-[0.12em]",
                    column.className,
                  )}
                >
                  {column.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageItems.map((item) => (
              <TableRow key={rowKey(item)} className="hover:bg-interactive/35">
                {columns.map((column) => (
                  <TableCell key={column.key} className={column.className}>
                    {column.render(item)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <ul className="divide-y divide-border md:hidden" aria-label={ariaLabel}>
        {pageItems.map((item) => (
          <li key={rowKey(item)} className="space-y-3 p-4">
            {columns.map((column) => (
              <div
                key={column.key}
                className={cn(
                  "flex min-w-0 items-start justify-between gap-4",
                  column.mobileClassName,
                )}
              >
                <span className="shrink-0 text-xs text-muted-foreground">{column.label}</span>
                <div className="min-w-0 text-right text-sm">{column.render(item)}</div>
              </div>
            ))}
          </li>
        ))}
      </ul>

      <Pagination
        page={safePage}
        pageSize={pageSize}
        totalItems={items.length}
        onPageChange={onPageChange}
        onPageSizeChange={onPageSizeChange}
        pageSizeOptions={pageSizeOptions}
      />
    </Card>
  );
}
