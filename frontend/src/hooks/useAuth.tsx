import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api } from "../services/api";
import type { User } from "../types";

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("idp_token");
    const saved = localStorage.getItem("idp_user");
    if (!token) { setLoading(false); return; }
    if (saved) setUser(JSON.parse(saved));
    api.get<User>("/auth/me")
      .then((u) => { setUser(u); localStorage.setItem("idp_user", JSON.stringify(u)); })
      .catch(() => { localStorage.removeItem("idp_token"); localStorage.removeItem("idp_user"); setUser(null); })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const resp = await api.post<{ access_token: string; user: User }>("/auth/login", { email, password });
    const any = resp as any;
    localStorage.setItem("idp_token", any.access_token);
    localStorage.setItem("idp_user", JSON.stringify(any.user));
    setUser(any.user);
  };

  const register = async (name: string, email: string, password: string) => {
    await api.post("/auth/register", { name, email, password });
    await login(email, password);
  };

  const logout = () => {
    api.post("/auth/logout").catch(() => undefined); // clear the cookie too
    localStorage.removeItem("idp_token");
    localStorage.removeItem("idp_user");
    setUser(null);
  };

  return <Ctx.Provider value={{ user, loading, login, register, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
