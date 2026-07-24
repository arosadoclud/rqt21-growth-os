"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
    <div className="flex min-h-screen items-center justify-center px-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-5 rounded-2xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <div>
          <h1 className="text-xl font-semibold text-slate-900">RQT21 Growth OS</h1>
          <p className="text-sm text-slate-500">Ingresa a tu cuenta</p>
        </div>

        <div className="space-y-3">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Correo</span>
            <input
              type="email"
              required
              autoComplete="email"
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Contraseña</span>
            <input
              type="password"
              required
              autoComplete="current-password"
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
          >
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md bg-brand px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-fg disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy ? "Ingresando…" : "Ingresar"}
        </button>
      </form>
    </div>
  );
}
