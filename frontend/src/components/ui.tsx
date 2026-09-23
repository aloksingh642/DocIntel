import { ReactNode } from "react";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex items-start justify-between">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}>{children}</div>;
}

export function StatCard({ label, value, accent = "text-slate-900", hint }: { label: string; value: ReactNode; accent?: string; hint?: string }) {
  return (
    <Card>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-2 text-3xl font-bold ${accent}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-400">{hint}</div>}
    </Card>
  );
}

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-700",
  failed: "bg-rose-100 text-rose-700",
  needs_review: "bg-amber-100 text-amber-700",
  queued: "bg-sky-100 text-sky-700",
  processing: "bg-sky-100 text-sky-700",
  extracting: "bg-sky-100 text-sky-700",
  classifying: "bg-sky-100 text-sky-700",
  duplicate_check: "bg-sky-100 text-sky-700",
  uploaded: "bg-slate-100 text-slate-600",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[status] ?? "bg-slate-100 text-slate-600"}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function SkillBadge({ children, missing = false }: { children: ReactNode; missing?: boolean }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
        missing ? "bg-rose-50 text-rose-600 line-through decoration-rose-300" : "bg-brand-50 text-brand-600"
      }`}
    >
      {children}
    </span>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 py-14 text-center">
      <div className="text-4xl">🗂</div>
      <div className="font-medium text-slate-700">{title}</div>
      {hint && <div className="text-sm text-slate-400">{hint}</div>}
    </div>
  );
}

const CANDIDATE_STATUS_COLORS: Record<string, string> = {
  new: "bg-sky-100 text-sky-700",
  reviewing: "bg-amber-100 text-amber-700",
  shortlisted: "bg-indigo-100 text-indigo-700",
  interviewed: "bg-purple-100 text-purple-700",
  offer: "bg-teal-100 text-teal-700",
  hired: "bg-emerald-100 text-emerald-700",
  rejected: "bg-slate-200 text-slate-500",
};

export function CandidateStatusChip({ status }: { status: string }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${CANDIDATE_STATUS_COLORS[status] ?? "bg-slate-100 text-slate-600"}`}>
      {status}
    </span>
  );
}

export function TagChip({ children, onRemove }: { children: ReactNode; onRemove?: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-teal-50 px-2.5 py-0.5 text-xs font-medium text-teal-700">
      #{children}
      {onRemove && (
        <button onClick={onRemove} className="text-teal-400 hover:text-teal-700" aria-label="remove">×</button>
      )}
    </span>
  );
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-10">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
    </div>
  );
}
