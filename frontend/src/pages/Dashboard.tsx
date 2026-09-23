import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import type { Overview } from "../types";
import { Card, EmptyState, PageHeader, Spinner, StatCard } from "../components/ui";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const PIE_COLORS = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4", "#a855f7", "#64748b"];

export default function Dashboard() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [docs, setDocs] = useState<any>(null);
  const [skills, setSkills] = useState<{ skill: string; count: number }[]>([]);

  useEffect(() => {
    api.get<Overview>("/analytics/overview").then(setOverview).catch(() => null);
    api.get("/analytics/documents").then(setDocs).catch(() => null);
    api.get<{ skill: string; count: number }[]>("/analytics/skills?limit=8").then(setSkills).catch(() => null);
  }, []);

  if (!overview || !docs) return <Spinner />;

  const typeData = docs.by_type;
  const statusData = docs.by_status;

  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Pipeline health and document intelligence at a glance" />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        <StatCard label="Documents" value={overview.total_documents} />
        <StatCard label="Processed" value={overview.processed_documents} accent="text-emerald-600" />
        <StatCard label="Failed" value={overview.failed_documents} accent="text-rose-600" />
        <StatCard label="Needs review" value={overview.needs_review_documents} accent="text-amber-600" />
        <StatCard label="Candidates" value={overview.total_candidates} accent="text-brand-600" />
        <StatCard label="Duplicates" value={overview.duplicate_documents} accent="text-purple-600" />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="mb-4 text-sm font-semibold text-slate-700">Documents by type</h3>
          {typeData.length === 0 ? <EmptyState title="No documents yet" hint="Upload a document to see classification stats" /> : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={typeData} dataKey="count" nameKey="type" outerRadius={80} label={(e: any) => `${e.type} (${e.count})`}>
                  {typeData.map((_: any, i: number) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card>
          <h3 className="mb-4 text-sm font-semibold text-slate-700">Processing status</h3>
          {statusData.length === 0 ? <EmptyState title="No activity yet" /> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={statusData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="status" fontSize={11} />
                <YAxis allowDecimals={false} fontSize={11} />
                <Tooltip />
                <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                  {statusData.map((row: any, i: number) => (
                    <Cell key={i} fill={row.status === "completed" ? "#22c55e" : row.status === "failed" ? "#ef4444" : row.status === "needs_review" ? "#f59e0b" : "#6366f1"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <h3 className="mb-4 text-sm font-semibold text-slate-700">Top skills across candidates</h3>
          {skills.length === 0 ? <EmptyState title="No skills extracted yet" /> : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={skills} layout="vertical" margin={{ left: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis type="number" allowDecimals={false} fontSize={11} />
                <YAxis type="category" dataKey="skill" fontSize={12} width={110} />
                <Tooltip />
                <Bar dataKey="count" fill="#6366f1" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      <div className="mt-6 text-sm text-slate-500">
        <Link to="/upload" className="font-medium text-brand-600 hover:underline">Upload a document</Link>
        {" "}to feed the pipeline, or explore{" "}
        <Link to="/candidates" className="font-medium text-brand-600 hover:underline">candidates</Link>.
      </div>
    </div>
  );
}
