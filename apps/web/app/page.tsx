"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function RootRedirect() {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated") router.replace("/dashboard");
    else if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  return (
    <div className="flex h-screen items-center justify-center text-slate-500">
      Cargando…
    </div>
  );
}
