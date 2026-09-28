import { createContext, useContext } from "react";

export interface CurrentUser {
  user_id: string;
  username: string;
  display_name: string;
  is_system: boolean;
  permissions: string[];
}

export interface AuthContextValue {
  user: CurrentUser | null;
  token: string | null;
  login: (token: string) => Promise<void>;
  logout: () => void;
  hasPermission: (perm: string) => boolean;
  loading: boolean;
}

/**
 * Local storage key for the bearer token. The API only keeps a SHA-256 digest
 * server-side (docs/11 section 3); the browser holds the raw token for the session.
 */
export const TOKEN_STORAGE_KEY = "law_rag_token";

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
