import type { Role } from "@rqt21/contracts";

export function canWriteGrowth(role: Role | undefined): boolean {
  return role === "OWNER" || role === "ADMIN" || role === "MARKETER";
}

export function canAdmin(role: Role | undefined): boolean {
  return role === "OWNER" || role === "ADMIN";
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}
