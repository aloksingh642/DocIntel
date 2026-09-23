import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../services/api";
import type { Job, MatchResult } from "../types";
import { Card, EmptyState, PageHeader, SkillBadge, Spinner } from "../components/ui";
import { useToast } from "../hooks/useToast";
import { useAuth } from "../hooks/useAuth";

export default function JobMatch() {
  const { id } = useParams();
  const [job, setJob] = useState<Job | null>(null);
  const [matches, setMatches] = useState<MatchResult[] | null>(null);
  const [running, setRunning] = useState(false);
  const { notify } = useToast();
  const { user } = useAuth();

  const load = useCallback(() => {
    api.get<Job>(`/jobs/${id}`).then(setJob).catch(() => null);
    api.get<MatchResult[]>(`/jobs/${id}/matches`).then(setMatches).catch(() => setMatches([]));
  }, [id]);
  useEffect(load, [load]);

  const runMatch = async () => {
    setRunning(true);
    try {
      const results = await api.post<MatchResult[]>(`/jobs/${id}/match`);
      setMatches(results);
      notify("success", `Matched ${results.length} candidate(s)`);
    } catch (e: any) { notify("error", e.message); }
    finally { setRunning(false); }
  };

  if (!job) return <Spinner />;

  const tiered = job.nice_to_have_skills.length > 0;

  return (
    <div>
      <PageHeader
        title={job.title}
        subtitle={job.description ?? undefined}
        actions={user?.role !== "viewer" && (
          <button onClick={runMatch} disabled={running}
                  className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60">
            {running ? "Matching…" : matches?.length ? "Re-run match" : "Run match"}
          </button>
        )}
      />

      <Card className="mb-4">
        <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Required skills</div>
        <div className="flex flex-wrap gap-1.5">
          {job.required_skills.map((s) => <SkillBadge key={s}>{s}</SkillBadge>)}
        </div>
        {tiered && (
          <>
            <div className="mb-2 mt-3 text-xs font-medium uppercase tracking-wide text-slate-400">
              Nice to have (lower weight)
            </div>
            <div className="flex flex-wrap gap-1.5">
              {job.nice_to_have_skills.map((s) => (
                <span key={s} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-500">{s}</span>
              ))}
            </div>
          </>
        )}
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
          <strong>How matching works:</strong>{" "}
          {tiered
            ? "score = w_required × (matched required ÷ total required) + w_nice × (matched nice ÷ total nice), × 100 (default weights 0.7 / 0.3, admin-configurable)."
            : "score = matched required skills ÷ total required skills × 100."}
          {" "}Only skills explicitly extracted from a candidate's documents count — nothing is inferred.
        </p>
      </Card>

      {!matches ? <Spinner /> : matches.length === 0 ? (
        <Card><EmptyState title="No match results" hint="Run a match to compare candidates against this job" /></Card>
      ) : (
        <div className="space-y-4">
          {matches.map((m) => (
            <Card key={m.candidate_id}>
              <div className="flex items-center justify-between gap-4">
                <Link to={`/candidates/${m.candidate_id}`} className="font-semibold text-slate-900 hover:text-brand-600">
                  {m.candidate_name ?? `Candidate #${m.candidate_id}`}
                </Link>
                <div className="flex items-center gap-3">
                  <div className="h-2.5 w-40 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className={`h-full rounded-full ${m.match_percentage >= 75 ? "bg-emerald-500" : m.match_percentage >= 40 ? "bg-amber-500" : "bg-rose-400"}`}
                      style={{ width: `${m.match_percentage}%` }}
                    />
                  </div>
                  <span className="w-14 text-right text-lg font-bold text-slate-800">{m.match_percentage}%</span>
                </div>
              </div>

              <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <div className="mb-1 text-xs font-medium text-emerald-600">✓ Matched — required ({m.matched_skills.length})</div>
                  <div className="flex flex-wrap gap-1.5">
                    {m.matched_skills.map((s) => <SkillBadge key={s}>{s}</SkillBadge>)}
                    {!m.matched_skills.length && <span className="text-slate-400">—</span>}
                  </div>
                </div>
                <div>
                  <div className="mb-1 text-xs font-medium text-rose-600">✗ Missing — required ({m.missing_skills.length})</div>
                  <div className="flex flex-wrap gap-1.5">
                    {m.missing_skills.map((s) => <SkillBadge key={s} missing>{s}</SkillBadge>)}
                    {!m.missing_skills.length && <span className="text-emerald-600">All requirements met</span>}
                  </div>
                </div>
              </div>

              {(m.matched_nice.length > 0 || m.missing_nice.length > 0) && (
                <div className="mt-3 grid gap-3 border-t border-slate-100 pt-3 text-sm sm:grid-cols-2">
                  <div>
                    <div className="mb-1 text-xs font-medium text-teal-600">✓ Matched — nice-to-have ({m.matched_nice.length})</div>
                    <div className="flex flex-wrap gap-1.5">
                      {m.matched_nice.map((s) => <SkillBadge key={s}>{s}</SkillBadge>)}
                    </div>
                  </div>
                  <div>
                    <div className="mb-1 text-xs font-medium text-amber-500">✗ Missing — nice-to-have ({m.missing_nice.length})</div>
                    <div className="flex flex-wrap gap-1.5">
                      {m.missing_nice.map((s) => (
                        <span key={s} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-400">{s}</span>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              <div className="mt-2 text-xs text-slate-400">{m.formula}</div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
