"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { MeResponse, OrganizationSummary, UserPublic } from "@rqt21/contracts";
import { api, ApiError } from "./api";

interface AuthState {
  status: "loading" | "authenticated" | "anonymous";
  user: UserPublic | null;
  organizations: OrganizationSummary[];
  currentOrgId: string | null;
}

interface AuthContextValue extends AuthState {
  setCurrentOrgId: (id: string) => void;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
  applyLogin: (payload: MeResponse) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const ORG_KEY = "rqt21.currentOrgId";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    status: "loading",
    user: null,
    organizations: [],
    currentOrgId: null,
  });

  const pickInitialOrg = (orgs: OrganizationSummary[]): string | null => {
    if (typeof window === "undefined") return orgs[0]?.id ?? null;
    const stored = window.localStorage.getItem(ORG_KEY);
    if (stored && orgs.some((o) => o.id === stored)) return stored;
    return orgs[0]?.id ?? null;
  };

  const refresh = useCallback(async () => {
    try {
      const me = await api.me();
      const currentOrgId = pickInitialOrg(me.organizations);
      setState({
        status: "authenticated",
        user: me.user,
        organizations: me.organizations,
        currentOrgId,
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setState({
          status: "anonymous",
          user: null,
          organizations: [],
          currentOrgId: null,
        });
      } else {
        setState({
          status: "anonymous",
          user: null,
          organizations: [],
          currentOrgId: null,
        });
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const setCurrentOrgId = useCallback((id: string) => {
    if (typeof window !== "undefined") window.localStorage.setItem(ORG_KEY, id);
    setState((s) => ({ ...s, currentOrgId: id }));
  }, []);

  const applyLogin = useCallback((payload: MeResponse) => {
    const currentOrgId = pickInitialOrg(payload.organizations);
    if (currentOrgId && typeof window !== "undefined") {
      window.localStorage.setItem(ORG_KEY, currentOrgId);
    }
    setState({
      status: "authenticated",
      user: payload.user,
      organizations: payload.organizations,
      currentOrgId,
    });
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // ignore
    }
    if (typeof window !== "undefined") window.localStorage.removeItem(ORG_KEY);
    setState({
      status: "anonymous",
      user: null,
      organizations: [],
      currentOrgId: null,
    });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, setCurrentOrgId, refresh, logout, applyLogin }),
    [state, setCurrentOrgId, refresh, logout, applyLogin],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
