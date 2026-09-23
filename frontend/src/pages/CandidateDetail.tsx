import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../services/api";
import { CANDIDATE_STATUSES, type CandidateProfile } from "../types";
import { Card, CandidateStatusChip, PageHeader, SkillBadge, Spinner, StatusBadge, TagChip } from "../components/ui";
import { useToast } from "../hooks/useToast";
import { useAuth } from "../hooks/useAuth";

export default function CandidateDetail() {
  const { id } = useParams();
  const [cand, setCand] = useState<CandidateProfile | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<any>({});
  const [noteText, setNoteText] = useState("");
  const [tagText, setTagText] = useState("");
  const { notify } = useToast();
  const { user } = useAuth();
  const canReview = user?.role !== "viewer";

  const load = () => api.get<CandidateProfile>(`/candidates/${id}`).then(setCand).catch((e) => notify("error", e.message));

  const setStatus = async (status: string) => {
    try {
      await api.put(`/candidates/${id}/status`, { status });
      notify("success", `Candidate marked "${status}"`);
      load();
    } catch (e: any) { notify("error", e.message); }
  };

  const addNote = async () => {
    if (!noteText.trim()) return;
    try {
      await api.post(`/candidates/${id}/notes`, { text: noteText.trim() });
      setNoteText("");
      load();
    } catch (e: any) { notify("error", e.message); }
  };

  const addTag = async () => {
    if (!tagText.trim()) return;
    try {
      await api.post(`/candidates/${id}/tags`, { tag: tagText.trim() });
      setTagText("");
      load();
    } catch (e: any) { notify("error", e.message); }
  };

  const removeTag = async (tag: string) => {
    try {
      await api.delete(`/candidates/${id}/tags/${encodeURIComponent(tag)}`);
      load();
    } catch (e: any) { notify("error", e.message); }
  };
  useEffect(() => { load(); }, [id]);

  const startEdit = () => {
    setDraft({
      name: cand?.name ?? "", email: cand?.email ?? "", phone: cand?.phone ?? "",
      location: cand?.location ?? "", skills: cand?.skills ?? [],
    });
    setEditing(true);
  };

  const save = async () => {
    try {
      const skillsText: string[] = typeof draft.skills === "string"
        ? draft.skills.split(",").map((s: string) => s.trim()).filter(Boolean)
        : draft.skills;
      await api.put(`/candidates/${id}`, { ...draft, skills: skillsText });
      notify("success", "Candidate updated (audit recorded)");
      setEditing(false);
      load();
    } catch (e: any) { notify("error", e.message); }
  };

  if (!cand) return <Spinner />;

  const field = "w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none";

  return (
    <div>
      <PageHeader
        title={cand.name ?? "Candidate profile"}
        subtitle={cand.professional_summary ?? undefined}
        actions={user?.role !== "viewer" && !editing && (
          <button onClick={startEdit} className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">Edit & review</button>
        )}
      />

      {editing ? (
        <Card className="mb-4 space-y-3">
          <h3 className="text-sm font-semibold text-slate-700">Human review — correct extracted values</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <input className={field} placeholder="Name" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
            <input className={field} placeholder="Email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} />
            <input className={field} placeholder="Phone" value={draft.phone} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} />
            <input className={field} placeholder="Location" value={draft.location} onChange={(e) => setDraft({ ...draft, location: e.target.value })} />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500">Skills (comma separated)</label>
            <input className={field} value={Array.isArray(draft.skills) ? draft.skills.join(", ") : draft.skills}
                   onChange={(e) => setDraft({ ...draft, skills: e.target.value })} />
          </div>
          <div className="flex gap-2">
            <button onClick={save} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">Save changes</button>
            <button onClick={() => setEditing(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">Cancel</button>
          </div>
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-4">
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-slate-700">Contact</h3>
              <dl className="space-y-2 text-sm">
                <Info k="Email" v={cand.email} />
                <Info k="Phone" v={cand.phone} />
                <Info k="Location" v={cand.location} />
                <Info k="LinkedIn" v={cand.linkedin} />
                <Info k="GitHub" v={cand.github} />
                <Info k="Experience" v={cand.total_experience_years != null ? `${cand.total_experience_years} years` : null} />
              </dl>
            </Card>

            {/* ATS pipeline status */}
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-slate-700">Pipeline status</h3>
              <div className="flex items-center gap-2">
                <CandidateStatusChip status={cand.status} />
                {canReview && (
                  <select
                    value={cand.status}
                    onChange={(e) => setStatus(e.target.value)}
                    className="rounded-lg border border-slate-300 px-2 py-1 text-xs focus:border-brand-500 focus:outline-none"
                  >
                    {CANDIDATE_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                )}
              </div>
              <div className="mt-3">
                <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Tags</div>
                <div className="flex flex-wrap gap-1.5">
                  {cand.tags.map((t) => (
                    <TagChip key={t} onRemove={canReview ? () => removeTag(t) : undefined}>{t}</TagChip>
                  ))}
                  {cand.tags.length === 0 && <span className="text-xs text-slate-400">No tags</span>}
                </div>
                {canReview && (
                  <div className="mt-2 flex gap-1">
                    <input
                      value={tagText}
                      onChange={(e) => setTagText(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && addTag()}
                      placeholder="Add tag…"
                      className="w-full rounded-lg border border-slate-300 px-2 py-1 text-xs focus:border-brand-500 focus:outline-none"
                    />
                    <button onClick={addTag} className="rounded-lg bg-slate-700 px-2 py-1 text-xs text-white hover:bg-slate-800">+</button>
                  </div>
                )}
              </div>
            </Card>
          </div>

          <Card className="lg:col-span-2">
            <h3 className="mb-2 text-sm font-semibold text-slate-700">Skills</h3>
            <div className="flex flex-wrap gap-1.5">
              {cand.skills.length ? cand.skills.map((s) => <SkillBadge key={s}>{s}</SkillBadge>) : <span className="text-sm text-slate-400">None</span>}
            </div>

            {cand.education.length > 0 && (
              <>
                <h3 className="mb-2 mt-5 text-sm font-semibold text-slate-700">Education</h3>
                {cand.education.map((e) => (
                  <div key={e.id} className="mb-1 text-sm text-slate-700">
                    <span className="font-medium">{[e.degree, e.field].filter(Boolean).join(" — ")}</span>
                    {e.institution && <span className="text-slate-500"> · {e.institution}</span>}
                    {e.end_year && <span className="text-slate-400"> ({e.end_year})</span>}
                  </div>
                ))}
              </>
            )}

            {cand.experiences.length > 0 && (
              <>
                <h3 className="mb-2 mt-5 text-sm font-semibold text-slate-700">Experience</h3>
                {cand.experiences.map((e) => (
                  <div key={e.id} className="mb-1 text-sm text-slate-700">
                    {[e.job_title, e.company].filter(Boolean).join(" @ ") || e.description}
                  </div>
                ))}
              </>
            )}

            {cand.certifications.length > 0 && (
              <>
                <h3 className="mb-2 mt-5 text-sm font-semibold text-slate-700">Certifications</h3>
                {cand.certifications.map((c) => (
                  <div key={c.id} className="mb-1 text-sm text-slate-700">{c.name}{c.issuer && <span className="text-slate-500"> · {c.issuer}</span>}</div>
                ))}
              </>
            )}

            {cand.projects.length > 0 && (
              <>
                <h3 className="mb-2 mt-5 text-sm font-semibold text-slate-700">Projects</h3>
                {cand.projects.map((p) => (
                  <div key={p.id} className="mb-1 text-sm text-slate-700">
                    <span className="font-medium">{p.name}</span>
                    {p.technologies && <span className="text-slate-500"> · {p.technologies}</span>}
                    {p.description && <div className="text-slate-500">{p.description}</div>}
                  </div>
                ))}
              </>
            )}
          </Card>

          <Card>
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Source documents</h3>
            {cand.documents.length === 0 ? <p className="text-sm text-slate-400">None</p> : cand.documents.map((d) => (
              <div key={d.id} className="mb-2 flex items-center justify-between text-sm">
                <Link to={`/documents/${d.id}`} className="font-medium text-brand-600 hover:underline">{d.filename}</Link>
                <StatusBadge status={d.processing_status} />
              </div>
            ))}
          </Card>

          <Card className="lg:col-span-2">
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Skill matches</h3>
            {cand.skill_matches.length === 0 ? (
              <p className="text-sm text-slate-400">No job matches yet — run a match from a job page.</p>
            ) : cand.skill_matches.map((m, i) => (
              <div key={i} className="mb-2 flex items-center gap-3 text-sm">
                <Link to={`/jobs/${m.job_id}`} className="font-medium text-brand-600 hover:underline">Job #{m.job_id}</Link>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-brand-500" style={{ width: `${m.match_percentage}%` }} />
                </div>
                <span className="w-12 text-right font-semibold text-slate-700">{m.match_percentage}%</span>
              </div>
            ))}
          </Card>

          {/* recruiter notes timeline */}
          <Card className="lg:col-span-3">
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Notes</h3>
            {cand.notes.length === 0 ? (
              <p className="text-sm text-slate-400">No notes yet.</p>
            ) : (
              <div className="mb-3 space-y-2">
                {cand.notes.map((n) => (
                  <div key={n.id} className="flex items-start gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm">
                    <span className="text-slate-400">💬</span>
                    <div className="flex-1 text-slate-700">{n.text}</div>
                    <div className="whitespace-nowrap text-xs text-slate-400">
                      {n.created_at ? new Date(n.created_at).toLocaleString() : ""}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {canReview && (
              <div className="flex gap-2">
                <input
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addNote()}
                  placeholder="Add a note (e.g. interview feedback)…"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
                />
                <button onClick={addNote} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
                  Add
                </button>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

function Info({ k, v }: { k: string; v: string | null }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-500">{k}</dt>
      <dd className="text-right font-medium text-slate-700">{v ?? "—"}</dd>
    </div>
  );
}
