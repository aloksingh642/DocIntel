import { createContext, useContext, useState, ReactNode, useCallback } from "react";

interface Toast { id: number; kind: "success" | "error" | "info"; message: string }

const Ctx = createContext<{ notify: (kind: Toast["kind"], message: string) => void }>(
  null as never
);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const notify = useCallback((kind: Toast["kind"], message: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, kind, message }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000);
  }, []);

  const colors: Record<string, string> = {
    success: "bg-emerald-600",
    error: "bg-rose-600",
    info: "bg-slate-700",
  };

  return (
    <Ctx.Provider value={{ notify }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id} className={`${colors[t.kind]} max-w-sm rounded-lg px-4 py-3 text-sm text-white shadow-lg`}>
            {t.message}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export const useToast = () => useContext(Ctx);
