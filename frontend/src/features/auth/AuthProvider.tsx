import React, { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient, envelopeMessage } from "../../shared/api/client";
import { useToast } from "../../shared/ui";
import { AuthContext, CurrentUser, TOKEN_STORAGE_KEY } from "./authContext";

/**
 * Session provider: resolves the bearer token against `/api/v1/me` on start-up and
 * exposes the permissions the server resolved (deny-by-default RBAC).
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  const fetchMe = useCallback(async (bearer: string) => {
    const response = await apiClient.get("/me", {
      headers: { Authorization: `Bearer ${bearer}` },
    });
    const data = response.data as CurrentUser;
    setUser(data);
    setToken(bearer);
    localStorage.setItem(TOKEN_STORAGE_KEY, bearer);
    return data;
  }, []);

  const login = useCallback(
    async (bearer: string) => {
      try {
        await fetchMe(bearer);
      } catch (err: unknown) {
        toast(envelopeMessage(err), "error");
        throw err;
      }
    },
    [fetchMe, toast]
  );

  const logout = useCallback(() => {
    setUser(null);
    setToken(null);
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }, []);

  const hasPermission = useCallback(
    (permission: string) => (user ? user.permissions.includes(permission) : false),
    [user]
  );

  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!stored) {
      setLoading(false);
      return;
    }
    fetchMe(stored)
      .catch(() => {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
      })
      .finally(() => setLoading(false));
  }, [fetchMe]);

  const value = useMemo(
    () => ({ user, token, login, logout, hasPermission, loading }),
    [user, token, login, logout, hasPermission, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
