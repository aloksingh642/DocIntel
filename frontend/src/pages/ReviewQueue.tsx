import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import type { Document, Page } from "../types";
import { Card, EmptyState, PageHeader, Spinner, StatusBadge } from "../components/ui";
import { useToast } from "../hooks/useToast";
import { useAuth } from "../hooks/useAuth";

/** Consolidated human-review queue: low-confidence classifications and
 * suspected duplicates waiting for an approve/reject decision. */
export default function ReviewQueue() {
  const [docs, setDocs] = useState<Document[] | null>(null);
  const { notify } = useToast();
  const { user } = useAuth();
  const canReview = user?.role !== "viewer";

  const load = useCallback(() => {
    Promise.all([
      api.get<Page<Document>>("/documents?status=needs_review&page_size=50"),
      api.get<Page<Document>>("/documents?duplicates_only=true&page_size=50"),
    ])
      .then(([review, dupes]) => {
        const byId = new Map<number, Document>();
        [...review.items, ...dupes.items].forEach((d) => {
          if (d.processing_status !== "failed") byId.set(d.id, d);
        });
        setDocs([...byId.values()].sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? "")));
      })
      .catch((e) => notify("error", e.message));
  }, [notify]);

  useEffect(load, [load]);

  const decide = async (doc: Document, action: "approve" | "reject") => {
    try {
      await api.post(`/documents/${doc.id}/review`, { action });
      notify("success", `"${doc.filename}" ${action}d`);
      load();
    } catch (e: any) { notify("error", e.message); }
  };

  if (!docs) return <Spinner />;

  return (
    <div>
      <PageHeader
        title="Review queue"
        subtitle="Documents flagged for human judgment — low AI confidence or suspected duplicates"
      />

      {docs.length === 0 ? (
        <Card><EmptyState title="All clear 🎉" hint="Nothing is waiting for review" /></Card>
      ) : (
        <div className="space-y-4">
          {docs.map((d) => (
            <Card key={d.id}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <Link to={`/documents/${d.id}`} className="font-medium text-brand-600 hover:underline">
                    {d.filename}
                  </Link>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <StatusBadge status={d.processing_status} />
                    <span>type: <span className="font-medium capitalize">{d.document_type ?? "unknown"}</span></span>
                    {d.classification_confidence != null && (
                      <span>confidence: <span className={d.classification_confidence >= 0.8 ? "text-emerald-600" : "text-amber-600"}>
                        {Math.round(d.classification_confidence * 100)}%</span></span>
                    )}
                    {d.is_duplicate && (
                      <span className="text-purple-600">
                        {d.duplicate_type === "exact_file" ? "exact duplicate"
                          : `${Math.round((d.duplicate_similarity ?? 0) * 100)}% similar to doc #${d.duplicate_of_id}`}
                      </span>
                    )}
                  </div>
                  {d.processing_error && (
                    <div className="mt-1 text-xs text-amber-600">{d.processing_error}</div>
                  )}
                </div>
                {canReview && (
                  <div className="flex gap-2">
                    <button onClick={() => decide(d, "approve")}
                            className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700">
                      Approve
                    </button>
                    <button onClick={() => decide(d, "reject")}
                            className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-rose-700">
                      Reject
                    </button>
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
