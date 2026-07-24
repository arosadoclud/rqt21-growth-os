"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type { Member, Role } from "@rqt21/contracts";
import { ROLES } from "@rqt21/contracts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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
    return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Miembros</h1>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nombre</TableHead>
              <TableHead>Correo</TableHead>
              <TableHead>Rol</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={3} className="text-center text-muted-foreground">Cargando…</TableCell></TableRow>
            )}
            {!loading && members.length === 0 && (
              <TableRow><TableCell colSpan={3} className="text-center text-muted-foreground">Sin miembros</TableCell></TableRow>
            )}
            {members.map((m) => (
              <TableRow key={m.id}>
                <TableCell className="font-medium">{m.full_name}</TableCell>
                <TableCell className="text-muted-foreground">{m.email}</TableCell>
                <TableCell>
                  {canManage ? (
                    <Select
                      value={m.role}
                      onChange={(e) => void changeRole(m, e.target.value as Role)}
                      className="w-40"
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </Select>
                  ) : (
                    <span>{m.role}</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {canManage && (
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground text-lg">Añadir miembro</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onCreate} className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-sm">
                  <span className="text-muted-foreground">Nombre</span>
                  <Input required value={fullName} onChange={(e) => setFullName(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Correo</span>
                  <Input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Contraseña temporal</span>
                  <Input required minLength={8} type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Rol</span>
                  <Select value={role} onChange={(e) => setRole(e.target.value as Role)} className="mt-1">
                    {ROLES.filter((r) => currentOrg?.role === "OWNER" || r !== "OWNER").map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </Select>
                </label>
              </div>
              {formError && (
                <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </div>
              )}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Guardando…" : "Añadir"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
