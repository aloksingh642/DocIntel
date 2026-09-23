import { useEffect, useState } from "react";
import { api } from "../services/api";
import { Card, PageHeader, Spinner } from "../components/ui";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const COLORS = ["#6366f1", "#22c55e", "#f59e0b", "#06b6d4", "#a855f7", "#ef4444", "#64748b"];

export default function Analytics() {
  const [days, setDays] = useState(30);
  const [docs, setDocs] = useState<any>(null);
  const [skills, setSkills] = useState<{ skill: string; count: number }[]>([]);
  const [cands, setCands] = useState<any>(null);

  useEffect(() => {
    api.get(`/analytics/documents?days=${days}`).then(setDocs).catch(() => null);
    api.get<{ skill: string; count: number }[]>("/analytics/skills?limit=15").then(setSkills).catch(() => null);
    api.get("/analytics/candidates").then(setCands).catch(() => null);
  }, [days]);

  if (!docs || !cands) return <Spinner />;

  return (
    <div>
      <PageHeader
        title="Analytics"
        subtitle="Document, candidate and skill intelligence"
        actions={
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={365}>Last year</option>
          </select>
        }
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="lg:col-span-2">
          <h3 className="mb-4 text-sm font-semibold text-slate-700">Uploads over time</h3>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={docs.uploads_over_time}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" fontSize={10} />
              <YAxis allowDecimals={false} fontSize={11} />
              <Tooltip />
              <Area type="monotone" dataKey="count" stroke="#6366f1" fill="#6366f1" fillOpacity={0.15} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h3 className="mb-4 text-sm font-semibold text-slate-700">Skill distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={skills} layout="vertical" margin={{ left: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis type="number" allowDecimals={false} fontSize={11} />
              <YAxis type="category" dataKey="skill" fontSize={11} width={110} />
              <Tooltip />
              <Bar dataKey="count" fill="#6366f1" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h3 className="mb-4 text-sm font-semibold text-slate-700">Experience distribution (years)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={cands.experience_distribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="bucket" fontSize={12} />
              <YAxis allowDecimals={false} fontSize={11} />
              <Tooltip />
              <Bar dataKey="count" fill="#22c55e" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h3 className="mb-4 text-sm font-semibold text-slate-700">Education distribution</h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={cands.education_distribution} dataKey="count" nameKey="degree" outerRadius={85}
                   label={(e: any) => `${e.degree} (${e.count})`}>
                {cands.education_distribution.map((_: any, i: number) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h3 className="mb-4 text-sm font-semibold text-slate-700">Location distribution</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={cands.location_distribution} layout="vertical" margin={{ left: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis type="number" allowDecimals={false} fontSize={11} />
              <YAxis type="category" dataKey="location" fontSize={11} width={120} />
              <Tooltip />
              <Bar dataKey="count" fill="#06b6d4" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}
