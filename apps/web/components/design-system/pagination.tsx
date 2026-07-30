import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";

interface PaginationProps {
  page: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  pageSizeOptions?: number[];
}

export function Pagination({
  page,
  pageSize,
  totalItems,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 25, 50],
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const safePage = Math.min(Math.max(page, 1), totalPages);
  const firstItem = totalItems === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const lastItem = Math.min(safePage * pageSize, totalItems);

  return (
    <nav
      className="flex flex-col gap-3 border-t border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
      aria-label="Paginación"
    >
      <p className="text-xs text-muted-foreground">
        Mostrando <span className="font-medium text-foreground">{firstItem}–{lastItem}</span>{" "}
        de <span className="font-medium text-foreground">{totalItems}</span>
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {onPageSizeChange && (
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Por página
            <Select
              value={String(pageSize)}
              onChange={(event) => onPageSizeChange(Number(event.target.value))}
              className="h-8 w-20"
              aria-label="Registros por página"
            >
              {pageSizeOptions.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </Select>
          </label>
        )}
        <span className="min-w-20 text-center text-xs text-muted-foreground">
          {safePage} de {totalPages}
        </span>
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          disabled={safePage <= 1}
          onClick={() => onPageChange(safePage - 1)}
          aria-label="Página anterior"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          disabled={safePage >= totalPages}
          onClick={() => onPageChange(safePage + 1)}
          aria-label="Página siguiente"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </nav>
  );
}
