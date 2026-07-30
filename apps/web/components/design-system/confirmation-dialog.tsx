"use client";

import { useEffect, useId, useRef } from "react";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

interface ConfirmationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  busy?: boolean;
  tone?: "default" | "danger";
  onConfirm: () => void | Promise<void>;
}

export function ConfirmationDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  busy = false,
  tone = "default",
  onConfirm,
}: ConfirmationDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const timer = window.setTimeout(() => cancelRef.current?.focus(), 0);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onOpenChange(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [busy, onOpenChange, open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-foreground/30 backdrop-blur-[2px]"
        aria-label="Cerrar confirmación"
        disabled={busy}
        onClick={() => onOpenChange(false)}
      />
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="relative w-full max-w-md rounded-2xl border border-border bg-elevated p-5 shadow-2xl sm:p-6"
      >
        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-destructive/10 text-destructive">
          <AlertTriangle className="h-5 w-5" />
        </span>
        <h2 id={titleId} className="mt-4 text-lg font-semibold tracking-tight text-foreground">
          {title}
        </h2>
        <p id={descriptionId} className="mt-2 text-sm leading-6 text-muted-foreground">
          {description}
        </p>
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            ref={cancelRef}
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() => onOpenChange(false)}
          >
            {cancelLabel}
          </Button>
          <Button
            type="button"
            variant={tone === "danger" ? "destructive" : "default"}
            disabled={busy}
            onClick={() => void onConfirm()}
          >
            {busy ? "Procesando…" : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
