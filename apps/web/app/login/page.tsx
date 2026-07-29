"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const { status, applyLogin } = useAuth();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (status === "authenticated") router.replace("/dashboard");
  }, [status, router]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.login({ email, password });
      applyLogin(res);
      router.replace("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 401 ? "Credenciales inválidas" : err.detail);
      } else {
        setError("No se pudo conectar con el servidor");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(600px circle at 15% 20%, hsl(var(--primary) / 0.15), transparent 60%)," +
            "radial-gradient(500px circle at 85% 80%, hsl(var(--lime) / 0.12), transparent 60%)",
        }}
      />
      <Card className="relative w-full max-w-sm animate-slide-up shadow-premium-lg">
        <CardHeader className="space-y-1">
          <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-base font-bold text-primary-foreground shadow-glow">
            R
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">RQT21 Growth OS</h1>
          <p className="text-sm text-muted-foreground">Ingresa a tu cuenta</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-5">
            <div className="space-y-3">
              <label className="block">
                <span className="text-sm font-medium text-muted-foreground">Correo</span>
                <Input
                  type="email"
                  required
                  autoComplete="email"
                  className="mt-1"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-muted-foreground">Contraseña</span>
                <Input
                  type="password"
                  required
                  autoComplete="current-password"
                  className="mt-1"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
            </div>

            {error && (
              <div
                role="alert"
                className="animate-slide-up rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                {error}
              </div>
            )}

            <Button type="submit" disabled={busy} className="w-full">
              {busy ? "Ingresando…" : "Ingresar"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
