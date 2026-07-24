"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  CalendarDays,
  ClipboardCheck,
  Sparkles,
  ListChecks,
  Mic2,
  Gauge,
  ImageIcon,
  Send,
  Zap,
  Bell,
  Building2,
  Package,
  Megaphone,
  FileText,
  Link2,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "General",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/calendar", label: "Calendario", icon: CalendarDays },
    ],
  },
  {
    label: "Contenido con IA",
    items: [
      { href: "/reviews", label: "Revisiones", icon: ClipboardCheck },
      { href: "/generate", label: "Generar", icon: Sparkles },
      { href: "/generation-jobs", label: "Generaciones", icon: ListChecks },
      { href: "/brand-voice", label: "Voz de marca", icon: Mic2 },
      { href: "/ai-usage", label: "Uso de IA", icon: Gauge },
      { href: "/content", label: "Contenidos", icon: FileText },
    ],
  },
  {
    label: "Publicación",
    items: [
      { href: "/assets", label: "Activos", icon: ImageIcon },
      { href: "/publishing", label: "Publicaciones", icon: Send },
      { href: "/automations", label: "Automatizaciones", icon: Zap },
      { href: "/notifications", label: "Notificaciones", icon: Bell },
    ],
  },
  {
    label: "Crecimiento",
    items: [
      { href: "/leads", label: "Leads", icon: Users },
      { href: "/tracking-links", label: "Enlaces", icon: Link2 },
    ],
  },
  {
    label: "Organización",
    items: [
      { href: "/brands", label: "Marcas", icon: Building2 },
      { href: "/products", label: "Productos", icon: Package },
      { href: "/campaigns", label: "Campañas", icon: Megaphone },
      { href: "/members", label: "Miembros", icon: Users },
    ],
  },
];

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-60 shrink-0 border-r border-border bg-card md:flex md:flex-col">
      <div className="flex h-14 items-center gap-2 border-b border-border px-5">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
          R
        </div>
        <Link href="/dashboard" className="text-sm font-semibold tracking-tight">
          RQT21 Growth OS
        </Link>
      </div>

      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <p className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              {group.label}
            </p>
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const active = pathname?.startsWith(item.href);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
                      active
                        ? "bg-accent font-medium text-accent-foreground"
                        : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
