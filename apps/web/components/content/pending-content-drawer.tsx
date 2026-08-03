"use client";

import { useRef, useState } from "react";
import { Calendar, Check, Copy, ImageUp } from "lucide-react";

import { Drawer } from "@/components/design-system/drawer";
import { Button } from "@/components/ui/button";

function formatDateTime(iso: string | null): string {
  if (!iso) return "Instantáneo — sale al subir la foto";
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: "long",
      day: "numeric",
      month: "long",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

interface PendingContentItem {
  title: string;
  caption: string | null;
  cta: string | null;
  scheduled_for: string | null;
}

/** Full-text preview for a pending headline/story — so the person
 * designing the flyer image can read the exact title and caption (in
 * large, legible text) instead of squinting at a truncated card, and
 * copy either straight into their design tool. Shared between
 * headline-management.tsx and story-management.tsx since both need the
 * exact same "click the card, see the full content, upload the photo"
 * flow. */
export function PendingContentDrawer({
  open,
  onOpenChange,
  item,
  uploading,
  disabled,
  onUpload,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: PendingContentItem | null;
  uploading: boolean;
  disabled: boolean;
  onUpload: (file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [copied, setCopied] = useState<"title" | "caption" | null>(null);

  const copy = async (text: string, which: "title" | "caption") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(which);
      window.setTimeout(() => setCopied((current) => (current === which ? null : current)), 2000);
    } catch {
      window.prompt("Copia el texto:", text);
    }
  };

  if (!item) return null;

  return (
    <Drawer open={open} onOpenChange={onOpenChange} title="Contenido de la publicación">
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Calendar className="h-4 w-4 shrink-0" />
          {formatDateTime(item.scheduled_for)}
        </div>

        <section>
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Título</h3>
            <Button type="button" variant="ghost" size="sm" onClick={() => void copy(item.title, "title")}>
              {copied === "title" ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              {copied === "title" ? "Copiado" : "Copiar"}
            </Button>
          </div>
          <p className="mt-2 text-2xl font-bold leading-tight tracking-tight text-foreground">{item.title}</p>
        </section>

        {item.caption && (
          <section>
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Caption</h3>
              <Button type="button" variant="ghost" size="sm" onClick={() => void copy(item.caption ?? "", "caption")}>
                {copied === "caption" ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                {copied === "caption" ? "Copiado" : "Copiar"}
              </Button>
            </div>
            <p className="mt-2 whitespace-pre-wrap text-base leading-7 text-foreground">{item.caption}</p>
          </section>
        )}

        {item.cta && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Llamado a la acción</h3>
            <p className="mt-2 text-base font-medium text-foreground">{item.cta}</p>
          </section>
        )}

        <div className="border-t border-border pt-5">
          <input
            ref={inputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onUpload(file);
              event.target.value = "";
            }}
          />
          <Button
            type="button"
            className="w-full"
            disabled={disabled}
            onClick={() => inputRef.current?.click()}
          >
            <ImageUp className="h-4 w-4" />
            {uploading ? "Subiendo…" : "Subir foto"}
          </Button>
        </div>
      </div>
    </Drawer>
  );
}
