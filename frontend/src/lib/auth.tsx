"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import * as api from "./api";

interface AuthContextValue {
  user: api.User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
}

const Ctx = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<api.User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!api.getToken()) {
      setLoading(false);
      return;
    }
    api
      .getMe()
      .then(setUser)
      .catch(() => api.setToken(null))
      .finally(() => setLoading(false));
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    await api.login(email, password);
    setUser(await api.getMe());
  }, []);

  const signOut = useCallback(() => {
    api.setToken(null);
    setUser(null);
  }, []);

  return (
    <Ctx.Provider value={{ user, loading, signIn, signOut }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth harus dipakai di dalam <AuthProvider>");
  return ctx;
}
