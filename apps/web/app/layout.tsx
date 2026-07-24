import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { ThemeProvider } from "@/components/theme-provider";

export const metadata: Metadata = {
  title: "RQT21 Growth OS",
  description: "Commercial funnel platform for Recetas Que Transforman 21",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
