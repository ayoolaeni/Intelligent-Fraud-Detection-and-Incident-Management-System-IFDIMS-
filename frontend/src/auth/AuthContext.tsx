import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import * as api from "../api/endpoints";
import { getAccessToken, setAccessToken, setUnauthorizedHandler } from "../api/client";
import type { User } from "../api/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  sessionExpired: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  clearSessionExpired: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      setAccessToken(null);
      setSessionExpired(true);
    });

    const token = getAccessToken();
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => {
        setAccessToken(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const result = await api.login(email, password);
    setAccessToken(result.access_token);
    setUser(result.user);
    setSessionExpired(false);
  };

  const logout = () => {
    setAccessToken(null);
    setUser(null);
  };

  const value = useMemo(
    () => ({ user, loading, sessionExpired, login, logout, clearSessionExpired: () => setSessionExpired(false) }),
    [user, loading, sessionExpired]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
