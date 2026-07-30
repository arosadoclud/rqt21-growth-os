"use client";

import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Pencil,
  Plus,
  RefreshCw,
  ShieldCheck,
  UserCog,
  UserRoundCheck,
  Users,
} from "lucide-react";
import type { Member, Role } from "@rqt21/contracts";
import { ROLES } from "@rqt21/contracts";

import {
  DataTable,
  type DataTableColumn,
} from "@/components/design-system/data-table";
import { Drawer } from "@/components/design-system/drawer";
import { FilterBar } from "@/components/design-system/filter-bar";
import { MetricCard } from "@/components/design-system/metric-card";
import { PageHeader } from "@/components/design-system/page-header";
import { StatusBadge } from "@/components/design-system/status-badge";
import { StatePanel } from "@/components/design-system/state-panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

import {
  ROLE_DESCRIPTIONS,
  ROLE_LABELS,
  ROLE_TONES,
} from "./operations-config";

export function TeamManagement() {
  const { currentOrgId, organizations, user } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canManage = organization?.role === "OWNER" || organization?.role === "ADMIN";
  const [items, setItems] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<Role | "">("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Member | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      setItems(await api.listMembers(currentOrgId));
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar el equipo.",
      );
    } finally {
      setLoading(false);
    }
  }, [currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => setPage(1), [pageSize, roleFilter, search]);

  const filteredItems = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("es");
    return items.filter((member) => {
      if (roleFilter && member.role !== roleFilter) return false;
      if (!query) return true;
      return [member.full_name, member.email, ROLE_LABELS[member.role]].some((value) =>
        value.toLocaleLowerCase("es").includes(query),
      );
    });
  }, [items, roleFilter, search]);

  const canEditMember = (member: Member) =>
    canManage &&
    member.user_id !== user?.id &&
    !(organization?.role === "ADMIN" && member.role === "OWNER");

  const columns: DataTableColumn<Member>[] = [
    {
      key: "member",
      label: "Miembro",
      render: (member) => (
        <div className="min-w-0">
          <p className="truncate font-semibold text-foreground">{member.full_name}</p>
          <p className="mt-1 truncate text-xs text-muted-foreground">{member.email}</p>
        </div>
      ),
      mobileClassName: "items-start",
    },
    {
      key: "role",
      label: "Rol",
      render: (member) => (
        <StatusBadge
          label={ROLE_LABELS[member.role]}
          tone={ROLE_TONES[member.role]}
        />
      ),
    },
    {
      key: "permissions",
      label: "Alcance",
      render: (member) => (
        <span className="block max-w-sm text-xs leading-5 text-muted-foreground">
          {ROLE_DESCRIPTIONS[member.role]}
        </span>
      ),
    },
    {
      key: "actions",
      label: "Acciones",
      render: (member) =>
        canEditMember(member) ? (
          <Button variant="ghost" size="sm" onClick={() => setEditing(member)}>
            <Pencil className="h-3.5 w-3.5" />
            Cambiar rol
          </Button>
        ) : (
          <span className="text-xs text-muted-foreground">
            {member.user_id === user?.id ? "Tu cuenta" : "Protegido"}
          </span>
        ),
      className: "w-32",
    },
  ];

  if (!currentOrgId) {
    return (
      <StatePanel
        icon={Users}
        title="Selecciona una organización"
        description="El equipo aparecerá cuando elijas una organización."
      />
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administración"
        title="Equipo y roles"
        description="Consulta quién tiene acceso y asigna el nivel de permisos adecuado para cada responsabilidad."
        metadata={<StatusBadge label={`${items.length} miembros`} />}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
            {canManage && (
              <Button size="sm" onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" />
                Añadir miembro
              </Button>
            )}
          </>
        }
      />

      {error && <InlineError>{error}</InlineError>}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Resumen del equipo">
        <MetricCard
          label="Miembros"
          value={items.length}
          helper="Accesos registrados"
          icon={Users}
          loading={loading}
        />
        <MetricCard
          label="Administración"
          value={items.filter((member) => ["OWNER", "ADMIN"].includes(member.role)).length}
          helper="Propietarios y administradores"
          icon={ShieldCheck}
          tone="info"
          loading={loading}
        />
        <MetricCard
          label="Operación"
          value={items.filter((member) => ["MARKETER", "SALES"].includes(member.role)).length}
          helper="Marketing y ventas"
          icon={UserRoundCheck}
          tone="positive"
          loading={loading}
        />
        <MetricCard
          label="Consulta"
          value={items.filter((member) => ["ANALYST", "VIEWER"].includes(member.role)).length}
          helper="Analistas y observadores"
          icon={UserCog}
          loading={loading}
        />
      </section>

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchLabel="Buscar miembros"
        searchPlaceholder="Buscar por nombre, correo o rol…"
        hasFilters={Boolean(search || roleFilter)}
        onClear={() => {
          setSearch("");
          setRoleFilter("");
        }}
      >
        <Select
          value={roleFilter}
          onChange={(event) => setRoleFilter(event.target.value as Role | "")}
          aria-label="Filtrar miembros por rol"
          className="lg:w-44"
        >
          <option value="">Todos los roles</option>
          {ROLES.map((role) => (
            <option key={role} value={role}>{ROLE_LABELS[role]}</option>
          ))}
        </Select>
      </FilterBar>

      {!canManage && (
        <p className="rounded-xl border border-border bg-interactive/35 px-4 py-3 text-sm text-muted-foreground">
          Tu rol puede consultar el equipo, pero solo propietarios y administradores pueden añadir miembros o cambiar permisos.
        </p>
      )}

      <DataTable
        items={filteredItems}
        columns={columns}
        rowKey={(member) => member.id}
        loading={loading}
        emptyIcon={Users}
        emptyTitle="No encontramos miembros"
        emptyDescription="Ajusta los filtros o añade la primera persona al equipo."
        emptyActionLabel={canManage ? "Añadir miembro" : undefined}
        onEmptyAction={canManage ? () => setCreateOpen(true) : undefined}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
        ariaLabel="Listado de miembros del equipo"
      />

      <AddMemberDrawer
        open={createOpen}
        onOpenChange={setCreateOpen}
        currentOrgId={currentOrgId}
        currentRole={organization?.role}
        onCreated={async () => {
          setCreateOpen(false);
          await load();
        }}
      />

      <EditRoleDrawer
        open={Boolean(editing)}
        onOpenChange={(open) => {
          if (!open) setEditing(null);
        }}
        member={editing}
        currentOrgId={currentOrgId}
        currentRole={organization?.role}
        onSaved={async () => {
          setEditing(null);
          await load();
        }}
      />
    </div>
  );
}

function AddMemberDrawer({
  open,
  onOpenChange,
  currentOrgId,
  currentRole,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentOrgId: string;
  currentRole?: Role;
  onCreated: () => Promise<void>;
}) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("SALES");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const availableRoles = ROLES.filter(
    (candidate) => currentRole === "OWNER" || candidate !== "OWNER",
  );

  useEffect(() => {
    if (!open) return;
    setEmail("");
    setFullName("");
    setPassword("");
    setRole("SALES");
    setError(null);
  }, [open]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.addMember(currentOrgId, {
        email: email.trim(),
        full_name: fullName.trim(),
        password,
        role,
      });
      await onCreated();
    } catch (createError) {
      setError(
        createError instanceof ApiError
          ? createError.detail
          : "No pudimos añadir el miembro.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title="Añadir miembro"
      description="Crea el acceso inicial y asigna el rol de acuerdo con sus responsabilidades."
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancelar
          </Button>
          <Button type="submit" form="add-member-form" disabled={busy}>
            {busy ? "Añadiendo…" : "Añadir miembro"}
          </Button>
        </div>
      }
    >
      <form id="add-member-form" onSubmit={submit} className="space-y-5">
        <FormField label="Nombre">
          <Input required value={fullName} onChange={(event) => setFullName(event.target.value)} />
        </FormField>
        <FormField label="Correo">
          <Input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
        </FormField>
        <FormField
          label="Contraseña temporal"
          helper="Comparte la contraseña por un canal seguro y solicita que sea reemplazada."
        >
          <Input
            required
            minLength={8}
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </FormField>
        <FormField label="Rol" helper={ROLE_DESCRIPTIONS[role]}>
          <Select value={role} onChange={(event) => setRole(event.target.value as Role)}>
            {availableRoles.map((candidate) => (
              <option key={candidate} value={candidate}>{ROLE_LABELS[candidate]}</option>
            ))}
          </Select>
        </FormField>
        {error && <InlineError>{error}</InlineError>}
      </form>
    </Drawer>
  );
}

function EditRoleDrawer({
  open,
  onOpenChange,
  member,
  currentOrgId,
  currentRole,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  member: Member | null;
  currentOrgId: string;
  currentRole?: Role;
  onSaved: () => Promise<void>;
}) {
  const [role, setRole] = useState<Role>("VIEWER");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const availableRoles = ROLES.filter(
    (candidate) => currentRole === "OWNER" || candidate !== "OWNER",
  );

  useEffect(() => {
    if (!member) return;
    setRole(member.role);
    setError(null);
  }, [member]);

  if (!member) return null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.updateMember(currentOrgId, member.id, { role });
      await onSaved();
    } catch (saveError) {
      setError(
        saveError instanceof ApiError
          ? saveError.detail
          : "No pudimos cambiar el rol.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title="Cambiar rol"
      description={`${member.full_name} · ${member.email}`}
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancelar
          </Button>
          <Button type="submit" form="edit-role-form" disabled={busy || role === member.role}>
            {busy ? "Guardando…" : "Guardar rol"}
          </Button>
        </div>
      }
    >
      <form id="edit-role-form" onSubmit={submit} className="space-y-5">
        <FormField label="Nuevo rol" helper={ROLE_DESCRIPTIONS[role]}>
          <Select value={role} onChange={(event) => setRole(event.target.value as Role)}>
            {availableRoles.map((candidate) => (
              <option key={candidate} value={candidate}>{ROLE_LABELS[candidate]}</option>
            ))}
          </Select>
        </FormField>
        <div className="rounded-xl border border-warning/25 bg-warning/5 p-4 text-sm text-warning">
          El cambio se aplicará inmediatamente a los permisos de esta organización.
        </div>
        {error && <InlineError>{error}</InlineError>}
      </form>
    </Drawer>
  );
}

function FormField({
  label,
  helper,
  children,
}: {
  label: string;
  helper?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5 text-sm">
      <span className="font-medium text-foreground">{label}</span>
      {children}
      {helper && <span className="block text-xs leading-5 text-muted-foreground">{helper}</span>}
    </label>
  );
}

function InlineError({ children }: { children: React.ReactNode }) {
  return (
    <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive">
      {children}
    </div>
  );
}
