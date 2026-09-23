import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import type { Document, Page } from "../types";
import { Card, EmptyState, PageHeader, Spinner, StatusBadge } from "../components/ui";
import { useToast } from "../hooks/useToast";
import { useAuth } from "../hooks/useAuth";

const STATUSES = ["", "completed", "failed", "needs_review", "queued", "processing"];
const TYPES = ["", "resume", "invoice", "contract", "purchase_order", "certificate", "other"];

export default function Documents() {
  const [page, setPage] = useState<Page<Document> | null>(null);
  const [pageNum, setPageNum] = useState(1);
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [dupes, setDupes] = useState(false);
  const { notify } = useToast();
  const { user } = useAuth();

  const load = useCallback(() => {
    const params = new URLSearchParams({ page: String(pageNum), page_size: "15" });
    if (status) params.set("status", status);
    if (type) params.set("document_type", type);
    if (dupes) params.set("duplicates_only", "true");
    api.get<Page<Document>>(`/documents?${params}`).then(setPage).catch((e) => notify("error", e.message));
  }, [pageNum, status, type, dupes, notify]);

  useEffect(load, [load]);

  const retry = async (id: number) => {
    try {
      await api.post(`/documents/${id}/retry`);
      notify("success", "Retry queued");
      load();
    } catch (e: any) { notify("error", e.message); }
  };

  const remove = async (id: number) => {
    if (!confirm("Delete this document and its stored file?")) return;
    try {
      await api.delete(`/documents/${id}`);
      notify("success", "Document deleted");
      load();
    } catch (e: any) { notify("error", e.message); }
  };

  return (
    <div>
      <PageHeader
        title="Documents"
        subtitle="Every upload's classification, extraction and review state"
        actions={<Link to="/upload" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">+ Upload</Link>}
      />

      <Card className="mb-4">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <select className="rounded-lg border border-slate-300 px-3 py-1.5" value={status} onChange={(e) => { setStatus(e.target.value); setPageNum(1); }}>
            <option value="">All statuses</option>
            {STATUSES.filter(Boolean).map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
          </select>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5" value={type} onChange={(e) => { setType(e.target.value); setPageNum(1); }}>
            <option value="">All types</option>
            {TYPES.filter(Boolean).map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <label className="flex items-center gap-2 text-slate-600">
            <input type="checkbox" checked={dupes} onChange={(e) => { setDupes(e.target.checked); setPageNum(1); }} />
            Duplicates only
          </label>
        </div>
      </Card>

      {!page ? <Spinner /> : page.items.length === 0 ? (
        <Card><EmptyState title="No documents found" hint="Try different filters or upload a document" /></Card>
      ) : (
        <Card className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="px-5 py-3">File</th>
                <th className="px-5 py-3">Type</th>
                <th className="px-5 py-3">Confidence</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Duplicate</th>
                <th className="px-5 py-3">Uploaded</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {page.items.map((d) => (
                <tr key={d.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  <td className="px-5 py-3">
                    <Link to={`/documents/${d.id}`} className="font-medium text-brand-600 hover:underline">{d.filename}</Link>
                    <div className="text-xs text-slate-400">{(d.file_size / 1024).toFixed(1)} KB • {d.file_type}</div>
                  </td>
                  <td className="px-5 py-3 text-slate-600">{d.document_type ?? "—"}</td>
                  <td className="px-5 py-3 text-slate-600">
                    {d.classification_confidence != null ? `${Math.round(d.classification_confidence * 100)}%` : "—"}
                  </td>
                  <td className="px-5 py-3"><StatusBadge status={d.processing_status} /></td>
                  <td className="px-5 py-3 text-slate-600">
                    {d.is_duplicate
                      ? <span className="text-purple-600">{d.duplicate_type === "exact_file" ? "exact" : `${Math.round((d.duplicate_similarity ?? 0) * 100)}% similar`}</span>
                      : "—"}
                  </td>
                  <td className="px-5 py-3 text-slate-500">{d.created_at ? new Date(d.created_at).toLocaleDateString() : "—"}</td>
                  <td className="px-5 py-3 text-right">
                    {d.processing_status === "failed" && user?.role !== "viewer" && (
                      <button onClick={() => retry(d.id)} className="mr-3 text-xs font-medium text-amber-600 hover:underline">Retry</button>
                    )}
                    {user?.role === "admin" && (
                      <button onClick={() => remove(d.id)} className="text-xs font-medium text-rose-600 hover:underline">Delete</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {page && page.pages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
          <span>Page {page.page} of {page.pages} ({page.total} documents)</span>
          <div className="space-x-2">
            <button disabled={page.page <= 1} onClick={() => setPageNum((p) => p - 1)} className="rounded-lg border border-slate-300 px-3 py-1 disabled:opacity-40">Prev</button>
            <button disabled={page.page >= page.pages} onClick={() => setPageNum((p) => p + 1)} className="rounded-lg border border-slate-300 px-3 py-1 disabled:opacity-40">Next</button>
          </div>
        </div>
      )}
    </div>
  );
}
