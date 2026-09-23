import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../services/api";
import type { Document, ProcessingLog } from "../types";
import { Card, PageHeader, SkillBadge, Spinner, StatusBadge } from "../components/ui";
import { useToast } from "../hooks/useToast";
import { useAuth } from "../hooks/useAuth";

interface StatusData { id: number; processing_status: string; processing_error: string | null; logs: ProcessingLog[] }

export default function DocumentDetail() {
  const { id } = useParams();
  const [doc, setDoc] = useState<Document | null>(null);
  const [status, setStatus] = useState<StatusData | null>(null);
  const [extraction, setExtraction] = useState<any>(null);
  const { notify } = useToast();
  const { user } = useAuth();

  const load = useCallback(async () => {
    try {
      const [d, s] = await Promise.all([
        api.get<Document>(`/documents/${id}`),
        api.get<StatusData>(`/documents/${id}/status`),
      ]);
      setDoc(d);
      setStatus(s);
      if (d.candidate_id) {
        api.get(`/documents/${id}/extraction`).then(setExtraction).catch(() => null);
      }
    } catch (e: any) {
      notify("error", e.message);
    }
  }, [id, notify]);

  useEffect(() => {
    load();
    const t = setInterval(() => {
      if (status && ["queued", "processing", "extracting", "classifying", "duplicate_check", "uploaded"].includes(status.processing_status)) {
        load();
      }
    }, 1000);
    return () => clearInterval(t);
  }, [load, status?.processing_status]);

  const review = async (action: "approve" | "reject") => {
    try {
      await api.post(`/documents/${id}/review`, { action });
      notify("success", `Document ${action}d`);
      load();
    } catch (e: any) { notify("error", e.message); }
  };

  const download = async () => {
    const token = localStorage.getItem("idp_token");
    const resp = await fetch(`/api/v1/documents/${id}/file`, { headers: { Authorization: `Bearer ${token}` } });
    if (!resp.ok) { notify("error", "Download failed"); return; }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = doc?.filename ?? "document";
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!doc || !status) return <Spinner />;

  const cand = extraction?.candidate;

  return (
    <div>
      <PageHeader
        title={doc.filename}
        subtitle={`Uploaded ${doc.created_at ? new Date(doc.created_at).toLocaleString() : ""}`}
        actions={
          <div className="flex gap-2">
            <button onClick={download} className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50">Download file</button>
            {status.processing_status === "needs_review" && user?.role !== "viewer" && (
              <>
                <button onClick={() => review("approve")} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-700">Approve</button>
                <button onClick={() => review("reject")} className="rounded-lg bg-rose-600 px-4 py-2 text-sm text-white hover:bg-rose-700">Reject</button>
              </>
            )}
          </div>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {/* left column: metadata + classification + processing trace */}
        <div className="space-y-4">
          <Card>
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Document</h3>
            <dl className="space-y-2 text-sm">
              <Row k="Status" v={<StatusBadge status={doc.processing_status} />} />
              <Row k="File type" v={doc.file_type} />
              <Row k="Size" v={`${(doc.file_size / 1024).toFixed(1)} KB`} />
              <Row k="Processed" v={doc.processed_at ? new Date(doc.processed_at).toLocaleString() : "—"} />
            </dl>
            {status.processing_error && (
              <div className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-600">{status.processing_error}</div>
            )}
          </Card>

          <Card>
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Classification</h3>
            {doc.document_type ? (
              <dl className="space-y-2 text-sm">
                <Row k="Document type" v={<span className="font-medium capitalize">{doc.document_type}</span>} />
                <Row k="Confidence" v={
                  <span className={doc.classification_confidence! >= 0.8 ? "text-emerald-600" : "text-amber-600"}>
                    {Math.round((doc.classification_confidence ?? 0) * 100)}%
                  </span>
                } />
              </dl>
            ) : <p className="text-sm text-slate-400">Not classified yet.</p>}
          </Card>

          <Card>
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Duplicate detection</h3>
            {doc.is_duplicate ? (
              <div className="text-sm text-slate-600">
                <span className="font-medium text-purple-600">Possible duplicate detected</span>
                <div className="mt-1">
                  Type: {doc.duplicate_type === "exact_file" ? "exact file match" : "content similarity"}
                  {doc.duplicate_similarity != null && <> — similarity {Math.round(doc.duplicate_similarity * 100)}%</>}
                </div>
                {doc.duplicate_of_id && (
                  <Link className="mt-1 inline-block font-medium text-brand-600 hover:underline" to={`/documents/${doc.duplicate_of_id}`}>
                    View matching document →
                  </Link>
                )}
              </div>
            ) : (
              <p className="text-sm text-emerald-600">No duplicate detected</p>
            )}
          </Card>

          <Card>
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Processing trace</h3>
            <div className="space-y-1.5 text-xs">
              {status.logs.filter((l) => l.stage !== "extract_note").map((log) => (
                <div key={log.id} className="flex items-start gap-2">
                  <span>{log.status === "success" ? "✅" : log.status === "failed" ? "❌" : "ℹ️"}</span>
                  <div className="text-slate-600">
                    <span className="font-medium">{log.stage}</span>
                    {log.processing_time != null && <span className="text-slate-400"> · {log.processing_time}s</span>}
                    {log.message && <div className="text-slate-500">{log.message}</div>}
                  </div>
                </div>
              ))}
              {status.logs.length === 0 && <p className="text-slate-400">Waiting for the worker…</p>}
            </div>
          </Card>
        </div>

        {/* right column: extracted info */}
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Extracted information</h3>
            {!cand ? (
              <p className="text-sm text-slate-400">
                {doc.document_type === "resume" ? "Extraction has not completed yet." : "Structured extraction currently applies to resumes."}
              </p>
            ) : (
              <div className="space-y-4">
                <div className="grid gap-2 text-sm sm:grid-cols-2">
                  <Row k="Name" v={cand.name ?? "—"} />
                  <Row k="Email" v={cand.email ?? "—"} />
                  <Row k="Phone" v={cand.phone ?? "—"} />
                  <Row k="Location" v={cand.location ?? "—"} />
                  <Row k="LinkedIn" v={cand.linkedin ?? "—"} />
                  <Row k="GitHub" v={cand.github ?? "—"} />
                  <Row k="Experience" v={extraction.total_experience_years != null ? `${extraction.total_experience_years} years` : "—"} />
                </div>
                {doc.extraction_confidence != null && (
                  <div className="text-xs text-slate-500">
                    Extraction confidence: <span className="font-medium">{Math.round(doc.extraction_confidence * 100)}%</span>
                    {" "}— treat extracted values as <em>extracted, not verified</em>.
                  </div>
                )}
                <div>
                  <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Skills</div>
                  <div className="flex flex-wrap gap-1.5">
                    {extraction.skills.length === 0
                      ? <span className="text-sm text-slate-400">None extracted</span>
                      : extraction.skills.map((s: string) => <SkillBadge key={s}>{s}</SkillBadge>)}
                  </div>
                </div>
                {extraction.education?.length > 0 && (
                  <div>
                    <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Education</div>
                    {extraction.education.map((e: any, i: number) => (
                      <div key={i} className="text-sm text-slate-700">
                        {[e.degree, e.field].filter(Boolean).join(" — ")}
                        {e.institution && <span className="text-slate-500"> · {e.institution}</span>}
                        {e.end_year && <span className="text-slate-400"> ({e.end_year})</span>}
                      </div>
                    ))}
                  </div>
                )}
                {extraction.certifications?.length > 0 && (
                  <div>
                    <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Certifications</div>
                    {extraction.certifications.map((c: any, i: number) => (
                      <div key={i} className="text-sm text-slate-700">{c.name}{c.issuer && <span className="text-slate-500"> · {c.issuer}</span>}</div>
                    ))}
                  </div>
                )}
                {doc.candidate_id && (
                  <Link to={`/candidates/${doc.candidate_id}`} className="inline-block text-sm font-medium text-brand-600 hover:underline">
                    Open candidate profile →
                  </Link>
                )}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-500">{k}</dt>
      <dd className="text-right font-medium text-slate-700">{String(v ?? "—") === "—" ? "—" : v}</dd>
    </div>
  );
}
