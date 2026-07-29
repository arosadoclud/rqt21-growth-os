"use client";

import { ChevronsUpDown, LogOut, Menu, User as UserIcon } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { HelpDrawer } from "@/components/layout/help-drawer";
import { NotificationBell } from "@/components/layout/notification-bell";
import { ThemeToggle } from "@/components/theme-toggle";
import { useAuth } from "@/lib/auth-context";

export function AppHeader({ onOpenMobileNav }: { onOpenMobileNav?: () => void }) {
  const { user, organizations, currentOrgId, setCurrentOrgId, logout } = useAuth();
  const router = useRouter();
  const currentOrg = organizations.find((o) => o.id === currentOrgId);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-card/80 px-4 backdrop-blur-md md:px-6">
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          className="px-2 md:hidden"
          aria-label="Abrir menú"
          onClick={onOpenMobileNav}
        >
          <Menu className="h-4 w-4" />
        </Button>
        {organizations.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="gap-2">
                <span className="max-w-[14rem] truncate">
                  {currentOrg ? `${currentOrg.name} · ${currentOrg.role}` : "Organización"}
                </span>
                <ChevronsUpDown className="h-3.5 w-3.5 opacity-60" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-64">
              <DropdownMenuLabel>Organizaciones</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {organizations.map((o) => (
                <DropdownMenuItem key={o.id} onSelect={() => setCurrentOrgId(o.id)}>
                  <span className="truncate">
                    {o.name} <span className="text-muted-foreground">· {o.role}</span>
                  </span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      <div className="flex items-center gap-1">
        <HelpDrawer />
        <NotificationBell />
        <ThemeToggle />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accent text-accent-foreground">
                <UserIcon className="h-3.5 w-3.5" />
              </span>
              <span className="hidden max-w-[12rem] truncate md:inline">{user?.email}</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="truncate">{user?.email}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={() => {
                void logout().then(() => router.replace("/login"));
              }}
              className="text-destructive focus:text-destructive"
            >
              <LogOut className="mr-2 h-4 w-4" />
              Salir
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
