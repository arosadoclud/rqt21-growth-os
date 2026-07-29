"use client";

import { useState } from "react";
import Link from "next/link";
import {
  HelpCircle,
  X,
  Building2,
  Sparkles,
  Send,
  ClipboardCheck,
  Wand2,
} from "lucide-react";

import { Button } from "@/components/ui/button";

interface HelpStep {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
  href: string;
  cta: string;
}

const STEPS: HelpStep[] = [
  {
    icon: Building2,
    title: "1. Creá una marca",
    body: "Todo el contenido (texto, imágenes, video) se genera dentro de una marca — nombre, slug y sitio web. Es lo primero que necesitás antes de generar nada.",
    href: "/brands",
    cta: "Ir a Marcas",
  },
  {
    icon: Sparkles,
    title: "2. Generá contenido con IA",
    body: "Elegí la plataforma (Facebook/Instagram), el tipo de contenido (Reel, foto, texto o video) y completá el brief. Cuanto más específico el tema, mejor sale el resultado.",
    href: "/generate",
    cta: "Ir a Generar",
  },
  {
    icon: ClipboardCheck,
    title: "3. Revisá antes de publicar",
    body: "Nada se publica automáticamente. Cada generación queda como borrador para que la revises y apruebes — es una decisión de diseño, no un límite técnico.",
    href: "/reviews",
    cta: "Ir a Revisiones",
  },
  {
    icon: Send,
    title: "4. Conectá tus cuentas",
    body: "Para publicar de verdad necesitás una conexión activa a Facebook/Instagram. Se configura una sola vez y queda lista para todas las publicaciones futuras.",
    href: "/publishing/connections",
    cta: "Ir a Conexiones",
  },
];

export function HelpDrawer() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Ayuda"
        onClick={() => setOpen(true)}
      >
        <HelpCircle className="h-4 w-4" />
      </Button>

      {open && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div
            role="presentation"
            className="fixed inset-0 bg-black/50 animate-fade-in"
            onClick={() => setOpen(false)}
          />
          <aside className="relative flex h-full w-full max-w-sm flex-col bg-card shadow-premium-lg animate-slide-in-right">
            <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-5">
              <div className="flex items-center gap-2">
                <Wand2 className="h-4 w-4 text-primary" />
                <span className="text-sm font-semibold">Cómo usar RQT21 Growth OS</span>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Cerrar ayuda"
                className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
              <p className="text-sm text-muted-foreground">
                El flujo básico tiene 4 pasos. Seguilos en orden la primera vez.
              </p>
              {STEPS.map((step) => (
                <div key={step.title} className="rounded-xl border border-border bg-background/50 p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                      <step.icon className="h-3.5 w-3.5" />
                    </span>
                    <span className="text-sm font-semibold">{step.title}</span>
                  </div>
                  <p className="mb-3 text-xs leading-relaxed text-muted-foreground">{step.body}</p>
                  <Link
                    href={step.href}
                    onClick={() => setOpen(false)}
                    className="text-xs font-medium text-primary hover:underline"
                  >
                    {step.cta} →
                  </Link>
                </div>
              ))}
              <div className="rounded-xl border border-dashed border-border p-4 text-center">
                <p className="text-xs text-muted-foreground">
                  Guía completa paso a paso, con capturas, en la sección{" "}
                  <Link href="/manual" onClick={() => setOpen(false)} className="font-medium text-primary hover:underline">
                    Manual
                  </Link>
                  .
                </p>
              </div>
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
