"use client";

import Link from "next/link";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const nav = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/calendar", label: "Calendario" },
  { href: "/reviews", label: "Revisiones" },
  { href: "/leads", label: "Leads" },
  { href: "/generate", label: "Generar" },
  { href: "/generation-jobs", label: "Generaciones" },
  { href: "/brand-voice", label: "Voz de marca" },
  { href: "/ai-usage", label: "Uso IA" },
  { href: "/assets", label: "Activos" },
  { href: "/publishing", label: "Publicaciones" },
  { href: "/automations", label: "Automatizaciones" },
  { href: "/notifications", label: "Notificaciones" },
  { href: "/brands", label: "Marcas" },
  { href: "/products", label: "Productos" },
  { href: "/campaigns", label: "Campañas" },
  { href: "/content", label: "Contenidos" },
  { href: "/tracking-links", label: "Enlaces" },
  { href: "/members", label: "Miembros" },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { status, user, organizations, currentOrgId, setCurrentOrgId, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  if (status !== "authenticated" || !user) {
    return (
      <div className="flex h-screen items-center justify-center text-slate-500">
        Cargando…
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-6">
            <Link href="/dashboard" className="text-lg font-semibold text-slate-900">
              RQT21
            </Link>
            <nav className="flex gap-4 text-sm">
              {nav.map((n) => {
                const active = pathname?.startsWith(n.href);
                return (
                  <Link
                    key={n.href}
                    href={n.href}
                    className={
                      active
                        ? "font-medium text-brand"
                        : "text-slate-600 hover:text-slate-900"
                    }
                  >
                    {n.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center gap-3 text-sm">
            {organizations.length > 0 && (
              <select
                value={currentOrgId ?? ""}
                onChange={(e) => setCurrentOrgId(e.target.value)}
                className="rounded-md border border-slate-300 bg-white px-2 py-1"
                aria-label="Seleccionar organización"
              >
                {organizations.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name} · {o.role}
                  </option>
                ))}
              </select>
            )}
            <span className="hidden text-slate-500 md:inline">{user.email}</span>
            <button
              type="button"
              onClick={() => {
                void logout().then(() => router.replace("/login"));
              }}
              className="rounded-md border border-slate-300 px-3 py-1 text-slate-700 hover:bg-slate-50"
            >
              Salir
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}
