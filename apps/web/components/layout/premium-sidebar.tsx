"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  Building2,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  FileText,
  Gauge,
  ImageIcon,
  Link2,
  ListChecks,
  Megaphone,
  Package,
  PanelLeftClose,
  Send,
  Sparkles,
  UploadCloud,
  Users,
  X,
  Zap,
} from "lucide-react";

import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Resumen",
    items: [{ href: "/dashboard", label: "Inicio", icon: BarChart3, exact: true }],
  },
  {
    label: "Estrategia y contenido",
    items: [
      { href: "/brands", label: "Marcas", icon: Building2 },
      { href: "/products", label: "Productos", icon: Package },
      { href: "/campaigns", label: "Campañas", icon: Megaphone },
      { href: "/content", label: "Contenidos", icon: FileText },
      { href: "/calendar", label: "Calendario editorial", icon: CalendarDays },
      { href: "/reviews", label: "Revisiones", icon: ClipboardCheck },
      { href: "/brand-voice", label: "Voz de marca", icon: Gauge },
    ],
  },
  {
    label: "Distribución",
    items: [
      { href: "/assets", label: "Biblioteca de recursos", icon: ImageIcon },
      { href: "/publishing", label: "Publicaciones", icon: Send, exact: true },
      { href: "/publishing/upload-reel", label: "Nueva publicación", icon: UploadCloud },
      { href: "/publishing/connections", label: "Conexiones", icon: Link2 },
      { href: "/tracking-links", label: "Enlaces y tracking", icon: Link2 },
    ],
  },
  {
    label: "Conversión",
    items: [{ href: "/leads", label: "Leads", icon: Users }],
  },
  {
    label: "Automatización",
    items: [
      { href: "/automations", label: "Automatizaciones", icon: Zap },
      { href: "/generate", label: "Generación con IA", icon: Sparkles },
      { href: "/generation-jobs", label: "Historial de IA", icon: ListChecks },
      { href: "/ai-usage", label: "Uso de IA", icon: Bot },
      { href: "/notifications", label: "Notificaciones", icon: Bell },
    ],
  },
  {
    label: "Administración",
    items: [
      { href: "/members", label: "Equipo y roles", icon: Users },
      { href: "/manual", label: "Manual", icon: BookOpen },
    ],
  },
];

function isActive(pathname: string | null, item: NavItem) {
  if (!pathname) return false;
  return item.exact ? pathname === item.href : pathname.startsWith(item.href);
}

function Navigation({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();

  return (
    <nav aria-label="Navegación principal" className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
      {NAV_GROUPS.map((group) => (
        <div key={group.label}>
          {!collapsed && (
            <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground/75">
              {group.label}
            </p>
          )}
          {collapsed && <div className="mx-auto mb-2 h-px w-7 bg-border" aria-hidden />}
          <div className="space-y-0.5">
            {group.items.map((item) => {
              const active = isActive(pathname, item);
              const Icon = item.icon;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavigate}
                  title={collapsed ? item.label : undefined}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "group relative flex min-h-10 items-center rounded-lg text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    collapsed ? "justify-center px-2" : "gap-3 px-2.5",
                    active
                      ? "bg-interactive font-medium text-foreground"
                      : "text-muted-foreground hover:bg-interactive/70 hover:text-foreground",
                  )}
                >
                  {active && (
                    <span
                      aria-hidden
                      className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-lime"
                    />
                  )}
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0",
                      active ? "text-lime" : "text-muted-foreground group-hover:text-foreground",
                    )}
                  />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

function Brand({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <Link
      href="/dashboard"
      aria-label="RQT21 Growth OS — Inicio"
      className={cn("flex h-16 items-center", collapsed ? "justify-center" : "gap-3 px-5")}
    >
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-lime text-sm font-black text-[#101512] shadow-glow">
        R
      </span>
      {!collapsed && (
        <span className="min-w-0">
          <span className="block truncate text-sm font-semibold tracking-[-0.02em]">
            RQT21 Growth OS
          </span>
          <span className="block text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            Growth Intelligence
          </span>
        </span>
      )}
    </Link>
  );
}

interface PremiumSidebarProps {
  collapsed: boolean;
  mobileOpen: boolean;
  onToggleCollapsed: () => void;
  onCloseMobile: () => void;
}

export function PremiumSidebar({
  collapsed,
  mobileOpen,
  onToggleCollapsed,
  onCloseMobile,
}: PremiumSidebarProps) {
  useEffect(() => {
    if (!mobileOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCloseMobile();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mobileOpen, onCloseMobile]);

  return (
    <>
      <aside
        className={cn(
          "relative hidden shrink-0 border-r border-border bg-sidebar transition-[width] duration-200 md:flex md:flex-col",
          collapsed ? "w-[76px]" : "w-64",
        )}
      >
        <Brand collapsed={collapsed} />
        <Navigation collapsed={collapsed} />
        <div className="border-t border-border p-3">
          <button
            type="button"
            onClick={onToggleCollapsed}
            aria-label={collapsed ? "Expandir barra lateral" : "Contraer barra lateral"}
            title={collapsed ? "Expandir barra lateral" : "Contraer barra lateral"}
            className={cn(
              "flex min-h-10 w-full items-center rounded-lg text-sm text-muted-foreground transition-colors hover:bg-interactive hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              collapsed ? "justify-center" : "gap-3 px-2.5",
            )}
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <PanelLeftClose className="h-4 w-4" />
                <span>Contraer navegación</span>
                <ChevronLeft className="ml-auto h-3.5 w-3.5" />
              </>
            )}
          </button>
        </div>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            type="button"
            aria-label="Cerrar navegación"
            className="absolute inset-0 bg-black/65 backdrop-blur-sm"
            onClick={onCloseMobile}
          />
          <aside
            role="dialog"
            aria-modal="true"
            aria-label="Navegación principal"
            className="relative flex h-full w-[min(88vw,320px)] animate-slide-in-right flex-col border-r border-border bg-sidebar shadow-premium-lg"
          >
            <div className="flex items-center justify-between border-b border-border pr-3">
              <Brand />
              <button
                type="button"
                autoFocus
                onClick={onCloseMobile}
                aria-label="Cerrar menú"
                className="flex h-10 w-10 items-center justify-center rounded-lg text-muted-foreground hover:bg-interactive hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <Navigation collapsed={false} onNavigate={onCloseMobile} />
          </aside>
        </div>
      )}
    </>
  );
}
