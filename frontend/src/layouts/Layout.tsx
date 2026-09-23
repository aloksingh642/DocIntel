import { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

const NAV = [
  { to: "/", label: "Dashboard", icon: "▦" },
  { to: "/documents", label: "Documents", icon: "📄" },
  { to: "/upload", label: "Upload", icon: "⬆" },
  { to: "/review", label: "Review queue", icon: "🔍" },
  { to: "/candidates", label: "Candidates", icon: "👤" },
  { to: "/jobs", label: "Jobs", icon: "💼" },
  { to: "/analytics", label: "Analytics", icon: "📊" },
  { to: "/settings", label: "Settings", icon: "⚙" },
];

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col bg-slate-900 text-slate-200">
        <div className="flex items-center gap-2 px-5 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-lg font-bold text-white">ID</div>
          <div>
            <div className="text-sm font-semibold text-white">IDP System</div>
            <div className="text-xs text-slate-400">AI document pipeline</div>
          </div>
        </div>
        <nav className="mt-2 flex-1 space-y-1 px-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                  isActive ? "bg-brand-600 text-white" : "text-slate-300 hover:bg-slate-800"
                }`
              }
            >
              <span className="w-5 text-center">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-800 p-4">
          <div className="text-sm font-medium text-white">{user?.name}</div>
          <div className="text-xs text-slate-400">{user?.email}</div>
          <span className="mt-1 inline-block rounded-full bg-slate-800 px-2 py-0.5 text-xs text-brand-100">
            {user?.role}
          </span>
          <button
            className="mt-3 w-full rounded-lg bg-slate-800 py-1.5 text-xs text-slate-300 hover:bg-slate-700"
            onClick={() => { logout(); navigate("/login"); }}
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="ml-60 flex-1 p-8">{children}</main>
    </div>
  );
}
