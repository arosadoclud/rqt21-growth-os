"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type { Member, Role } from "@rqt21/contracts";
import { ROLES } from "@rqt21/contracts";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function MembersPage() {
  const { currentOrgId, organizations } = useAuth();
  const currentOrg = organizations.find((o) => o.id === currentOrgId);
  const canManage = currentOrg?.role === "OWNER" || currentOrg?.role === "ADMIN";

  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("SALES");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const list = await api.listMembers(currentOrgId);
      setMembers(list);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar miembros");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await api.addMember(currentOrgId, {
        email,
        full_name: fullName,
        password,
        role,
      });
      setEmail("");
      setFullName("");
      setPassword("");
      setRole("SALES");
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Error creando miembro");
    } finally {
      setSubmitting(false);
    }
  };

  const changeRole = async (member: Member, next: Role) => {
    if (!currentOrgId || next === member.role) return;
    try {
      await api.updateMember(currentOrgId, member.id, { role: next });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error cambiando rol");
    }
  };

  if (!currentOrgId) {
    return <p className="text-sm text-slate-500">Selecciona una organización.</p>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Miembros</h1>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Nombre</th>
              <th className="px-4 py-2 font-medium">Correo</th>
              <th className="px-4 py-2 font-medium">Rol</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-slate-400">
                  Cargando…
                </td>
              </tr>
            )}
            {!loading && members.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-slate-400">
                  Sin miembros
                </td>
              </tr>
            )}
            {members.map((m) => (
              <tr key={m.id} className="border-t border-slate-100">
                <td className="px-4 py-2 text-slate-900">{m.full_name}</td>
                <td className="px-4 py-2 text-slate-600">{m.email}</td>
                <td className="px-4 py-2">
                  {canManage ? (
                    <select
                      value={m.role}
                      onChange={(e) => void changeRole(m, e.target.value as Role)}
                      className="rounded-md border border-slate-300 bg-white px-2 py-1"
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="text-slate-700">{m.role}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {canManage && (
        <form
          onSubmit={onCreate}
          className="space-y-3 rounded-xl border border-slate-200 bg-white p-4"
        >
          <h2 className="text-lg font-medium text-slate-900">Añadir miembro</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-slate-700">Nombre</span>
              <input
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Correo</span>
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Contraseña temporal</span>
              <input
                required
                minLength={8}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="block text-sm">
              <span className="text-slate-700">Rol</span>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as Role)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2"
              >
                {ROLES.filter((r) => currentOrg?.role === "OWNER" || r !== "OWNER").map(
                  (r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ),
                )}
              </select>
            </label>
          </div>
          {formError && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {formError}
            </div>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-fg disabled:opacity-60"
          >
            {submitting ? "Guardando…" : "Añadir"}
          </button>
        </form>
      )}
    </div>
  );
}
