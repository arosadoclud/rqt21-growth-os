"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { PremiumSidebar } from "@/components/layout/premium-sidebar";
import { PremiumTopbar } from "@/components/layout/premium-topbar";
import { useAuth } from "@/lib/auth-context";

const SIDEBAR_KEY = "rqt21.sidebarCollapsed";

export function PremiumAppShell({ children }: { children: React.ReactNode }) {
  const { status, user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  useEffect(() => {
    setSidebarCollapsed(window.localStorage.getItem(SIDEBAR_KEY) === "true");
  }, []);

  const closeMobileNav = useCallback(() => setMobileNavOpen(false), []);
  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem(SIDEBAR_KEY, String(next));
      return next;
    });
  }, []);

  if (status !== "authenticated" || !user) {
    return (
      <div className="surface-grid flex h-screen items-center justify-center bg-background">
        <div className="flex items-center gap-3 text-sm text-muted-foreground" role="status">
          <span className="h-2 w-2 animate-pulse rounded-full bg-lime" />
          Preparando tu workspace…
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <PremiumSidebar
        collapsed={sidebarCollapsed}
        mobileOpen={mobileNavOpen}
        onToggleCollapsed={toggleSidebar}
        onCloseMobile={closeMobileNav}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <PremiumTopbar onOpenMobileNav={() => setMobileNavOpen(true)} />
        <main className="surface-grid flex-1 overflow-y-auto px-4 py-6 md:px-7 md:py-8 xl:px-10">
          <div key={pathname} className="mx-auto max-w-[1440px] animate-slide-up">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
