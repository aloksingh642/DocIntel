import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { CANDIDATE_STATUSES, CandidateSummary, Page } from "../types";
import { Card, CandidateStatusChip, EmptyState, PageHeader, SkillBadge, Spinner, TagChip } from "../components/ui";
import { useAuth } from "../hooks/useAuth";

function downloadCsv(params: URLSearchParams) {
  const token = localStorage.getItem("idp_token");
  fetch(`/api/v1/candidates/export.csv?${params}`, {
    headers: { Authorization: `Bearer ${token}`, "X-Access-Token": token ?? "" },
  })
    .then((r) => r.blob())
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "candidates_export.csv";
      a.click();
      URL.revokeObjectURL(url);
    });
}

export default function Candidates() {
  const [page, setPage] = useState<Page<CandidateSummary> | null>(null);
  const [semanticHits, setSemanticHits] = useState<CandidateSummary[] | null>(null);
  const [mode, setMode] = useState<"structured" | "semantic">("structured");
  const [q, setQ] = useState("");
  const [skill, setSkill] = useState("");
  const [location, setLocation] = useState("");
  const [status, setStatus] = useState("");
  const [tag, setTag] = useState("");
  const [minExp, setMinExp] = useState("");
  const [pageNum, setPageNum] = useState(1);
  const { user } = useAuth();

  const buildFilters = useCallback(() => {
    const params = new URLSearchParams();
    if (mode === "structured" && q) params.set("q", q);
    if (skill) params.set("skill", skill);
    if (location) params.set("location", location);
    if (status) params.set("status", status);
    if (tag) params.set("tag", tag);
    if (minExp) params.set("min_experience", minExp);
    return params;
  }, [mode, q, skill, location, status, tag, minExp]);

  const load = useCallback(() => {
    if (mode === "semantic") {
      if (!q.trim()) { setSemanticHits([]); return; }
      api.get<CandidateSummary[]>(`/candidates/semantic-search?q=${encodeURIComponent(q)}`)
        .then((hits) => { setSemanticHits(hits); setPage(null); })
        .catch(() => null);
      return;
    }
    const params = buildFilters();
    params.set("page", String(pageNum));
    params.set("page_size", "15");
    api.get<Page<CandidateSummary>>(`/candidates/search?${params}`)
      .then((p) => { setPage(p); setSemanticHits(null); })
      .catch(() => null);
  }, [mode, q, pageNum, buildFilters]);

  useEffect(load, [load]);

  const submit = (e: FormEvent) => { e.preventDefault(); setPageNum(1); load(); };
  const input = "rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none";

  const items: CandidateSummary[] = mode === "semantic" ? (semanticHits ?? []) : (page?.items ?? []);

  return (
    <div>
      <PageHeader
        title="Candidates"
        subtitle="Structured profiles assembled from processed resumes"
        actions={
          <button
            onClick={() => { const params = buildFilters(); params.delete("page"); downloadCsv(params); }}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            ⬇ Export CSV
          </button>
        }
      />

      <Card className="mb-4">
        <div className="mb-3 flex gap-1 rounded-lg bg-slate-100 p-1 text-sm w-fit">
          {(["structured", "semantic"] as const).map((m) => (
            <button key={m} onClick={() => setMode(m)}
                    className={`rounded-md px-3 py-1 font-medium capitalize transition ${mode === m ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}>
              {m === "structured" ? "Filters" : "Semantic search"}
            </button>
          ))}
        </div>
        <form onSubmit={submit} className="flex flex-wrap items-center gap-2">
          <input className={`${input} w-72`}
                 placeholder={mode === "semantic"
                   ? "e.g. python backend developer with docker experience"
                   : "Name, email, company, title…"}
                 value={q} onChange={(e) => setQ(e.target.value)} />
          {mode === "structured" && (
            <>
              <input className={`${input} w-36`} placeholder="Skill (e.g. Python)" value={skill} onChange={(e) => setSkill(e.target.value)} />
              <input className={`${input} w-32`} placeholder="Location" value={location} onChange={(e) => setLocation(e.target.value)} />
              <input className={`${input} w-24`} placeholder="Min. years" type="number" min="0" step="0.5" value={minExp} onChange={(e) => setMinExp(e.target.value)} />
              <input className={`${input} w-24`} placeholder="Tag" value={tag} onChange={(e) => setTag(e.target.value)} />
            </>
          )}
          <select className={input} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Any status</option>
            {CANDIDATE_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <button className="rounded-lg bg-brand-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-700">Search</button>
        </form>
        {mode === "semantic" && (
          <p className="mt-2 text-xs text-slate-400">
            Ranks profiles by cosine similarity between your query and each candidate's full profile.
          </p>
        )}
      </Card>

      {(mode === "structured" && !page) || (mode === "semantic" && semanticHits === null) ? <Spinner /> : items.length === 0 ? (
        <Card><EmptyState title="No candidates match" hint="Process resumes or adjust the search" /></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((c) => (
            <Card key={c.id} className="transition hover:shadow-md">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <Link to={`/candidates/${c.id}`} className="font-semibold text-slate-900 hover:text-brand-600">
                    {c.name ?? "Unnamed candidate"}
                  </Link>
                  <div className="text-xs text-slate-400">{c.email ?? "no email"}</div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <CandidateStatusChip status={c.status} />
                  <div className="flex gap-1">
                    {c.total_experience_years != null && (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{c.total_experience_years}y</span>
                    )}
                    {c.score != null && (
                      <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-semibold text-brand-600">
                        {Math.round(c.score * 100)}%
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="mt-1 text-xs text-slate-500">{c.location ?? ""}</div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {c.tags.map((t) => <TagChip key={t}>{t}</TagChip>)}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {c.skills.slice(0, 6).map((s) => <SkillBadge key={s}>{s}</SkillBadge>)}
                {c.skills.length > 6 && <span className="text-xs text-slate-400">+{c.skills.length - 6} more</span>}
              </div>
            </Card>
          ))}
        </div>
      )}

      {mode === "structured" && page && page.pages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
          <span>Page {page.page} of {page.pages} ({page.total} candidates)</span>
          <div className="space-x-2">
            <button disabled={page.page <= 1} onClick={() => setPageNum((p) => p - 1)} className="rounded-lg border border-slate-300 px-3 py-1 disabled:opacity-40">Prev</button>
            <button disabled={page.page >= page.pages} onClick={() => setPageNum((p) => p + 1)} className="rounded-lg border border-slate-300 px-3 py-1 disabled:opacity-40">Next</button>
          </div>
        </div>
      )}
    </div>
  );
}
