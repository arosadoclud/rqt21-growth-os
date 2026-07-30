import { PremiumAppShell } from "@/components/layout/premium-app-shell";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <PremiumAppShell>{children}</PremiumAppShell>;
}
