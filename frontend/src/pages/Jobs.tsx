import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import type { Job } from "../types";
import { Card, EmptyState, PageHeader, SkillBadge, Spinner } from "../components/ui";
import { useToast } from "../hooks/useToast";
import { useAuth } from "../hooks/useAuth";

export default function Jobs() {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [skillsText, setSkillsText] = useState("");
  const [niceText, setNiceText] = useState("");
  const [showForm, setShowForm] = useState(false);
  const { notify } = useToast();
  const { user } = useAuth();
  const navigate = useNavigate();

  const load = useCallback(() => {
    api.get<Job[]>("/jobs").then(setJobs).catch((e) => notify("error", e.message));
  }, [notify]);
  useEffect(load, [load]);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    const required_skills = skillsText.split(",").map((s) => s.trim()).filter(Boolean);
    const nice_to_have_skills = niceText.split(",").map((s) => s.trim()).filter(Boolean);
    if (!required_skills.length) { notify("error", "Add at least one required skill"); return; }
    try {
      const job = await api.post<Job>("/jobs", { title, description: description || null, required_skills, nice_to_have_skills });
      notify("success", "Job created");
      navigate(`/jobs/${job.id}`);
    } catch (e2: any) { notify("error", e2.message); }
  };

  return (
    <div>
      <PageHeader
        title="Jobs & Skill Matching"
        subtitle="Define required skills, then match every candidate with a transparent formula"
        actions={user?.role !== "viewer" && (
          <button onClick={() => setShowForm((s) => !s)} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
            {showForm ? "Close" : "+ New job"}
          </button>
        )}
      />

      {showForm && (
        <Card className="mb-4">
          <form onSubmit={create} className="space-y-3">
            <div>
              <label className="text-xs font-medium text-slate-500">Job title</label>
              <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
                     placeholder="Python Backend Developer" value={title} onChange={(e) => setTitle(e.target.value)} required />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500">Required skills (comma separated, order irrelevant)</label>
              <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
                     placeholder="Python, FastAPI, PostgreSQL, Docker, AWS" value={skillsText} onChange={(e) => setSkillsText(e.target.value)} />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500">Nice-to-have skills (optional, lower weight in the score)</label>
              <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
                     placeholder="Machine Learning, Kubernetes" value={niceText} onChange={(e) => setNiceText(e.target.value)} />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500">Description (optional)</label>
              <textarea className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
                        rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
            <button className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">Create job</button>
          </form>
        </Card>
      )}

      {!jobs ? <Spinner /> : jobs.length === 0 ? (
        <Card><EmptyState title="No jobs yet" hint="Create a job requirement to start matching candidates" /></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {jobs.map((j) => (
            <Card key={j.id} className="transition hover:shadow-md">
              <Link to={`/jobs/${j.id}`} className="font-semibold text-slate-900 hover:text-brand-600">{j.title}</Link>
              {j.description && <p className="mt-1 line-clamp-2 text-sm text-slate-500">{j.description}</p>}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {j.required_skills.map((s) => <SkillBadge key={s}>{s}</SkillBadge>)}
              </div>
              {j.nice_to_have_skills.length > 0 && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <span className="text-xs text-slate-400">nice:</span>
                  {j.nice_to_have_skills.map((s) => (
                    <span key={s} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-500">{s}</span>
                  ))}
                </div>
              )}
              <div className="mt-3 text-xs text-slate-400">
                Created {j.created_at ? new Date(j.created_at).toLocaleDateString() : ""}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
