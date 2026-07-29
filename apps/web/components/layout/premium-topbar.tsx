"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Menu, Plus, User as UserIcon } from "lucide-react";

import { HelpDrawer } from "@/components/layout/help-drawer";
import { NotificationBell } from "@/components/layout/notification-bell";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/lib/auth-context";

const ROUTE_LABELS: Record<string, string> = {
  dashboard: "Inicio",
  brands: "Marcas",
  products: "Productos",
  campaigns: "Campañas",
  content: "Contenidos",
  calendar: "Calendario editorial",
  reviews: "Revisiones",
  assets: "Biblioteca de recursos",
  publishing: "Publicaciones",
  connections: "Conexiones",
  leads: "Leads",
  automations: "Automatizaciones",
  generate: "Generación con IA",
  "generation-jobs": "Historial de IA",
  notifications: "Notificaciones",
  members: "Equipo y roles",
  manual: "Manual",
};

function currentRouteLabel(pathname: string | null) {
  const segments = pathname?.split("/").filter(Boolean) ?? [];
  const lastNamedSegment = [...segments].reverse().find((segment) => ROUTE_LABELS[segment]);
  return lastNamedSegment ? ROUTE_LABELS[lastNamedSegment] : "RQT21 Growth OS";
}

export function PremiumTopbar({ onOpenMobileNav }: { onOpenMobileNav: () => void }) {
  const { user, organizations, currentOrgId, setCurrentOrgId, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const currentOrg = organizations.find((organization) => organization.id === currentOrgId);

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-background/85 px-4 backdrop-blur-xl md:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          aria-label="Abrir menú"
          onClick={onOpenMobileNav}
        >
          <Menu className="h-4 w-4" />
        </Button>
        <div className="hidden min-w-0 items-center gap-2 text-sm sm:flex">
          <span className="text-muted-foreground">Workspace</span>
          <span aria-hidden className="text-muted-foreground/45">/</span>
          <span className="truncate font-medium text-foreground">{currentRouteLabel(pathname)}</span>
        </div>
        {organizations.length > 0 && (
          <Select
            aria-label="Organización"
            value={currentOrgId ?? ""}
            onChange={(event) => setCurrentOrgId(event.target.value)}
            className="max-w-[11rem] border-border bg-elevated font-medium sm:max-w-[15rem]"
            title={`Organización activa: ${currentOrg?.name ?? ""}`}
          >
            {organizations.map((organization) => (
              <option key={organization.id} value={organization.id}>
                {organization.name} · {organization.role}
              </option>
            ))}
          </Select>
        )}
      </div>

      <div className="flex items-center gap-1">
        <Button asChild size="sm" className="hidden gap-1.5 sm:inline-flex">
          <Link href="/generate">
            <Plus className="h-4 w-4" />
            Crear
          </Link>
        </Button>
        <HelpDrawer />
        <NotificationBell />
        <ThemeToggle />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="gap-2 px-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-full border border-border bg-interactive text-foreground">
                <UserIcon className="h-3.5 w-3.5" />
              </span>
              <span className="hidden max-w-[10rem] truncate lg:inline">{user?.email}</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-60">
            <DropdownMenuLabel>
              <span className="block truncate">{user?.full_name}</span>
              <span className="block truncate text-xs font-normal text-muted-foreground">
                {user?.email}
              </span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={() => {
                void logout().then(() => router.replace("/login"));
              }}
              className="text-destructive focus:text-destructive"
            >
              <LogOut className="mr-2 h-4 w-4" />
              Cerrar sesión
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <Button
          variant="ghost"
          size="sm"
          className="hidden gap-1.5 xl:inline-flex"
          onClick={() => {
            void logout().then(() => router.replace("/login"));
          }}
        >
          <LogOut className="h-4 w-4" />
          Salir
        </Button>
      </div>
    </header>
  );
}
