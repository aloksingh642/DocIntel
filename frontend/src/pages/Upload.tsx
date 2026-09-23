import { DragEvent, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import type { Document, ProcessingLog } from "../types";
import { Card, PageHeader, StatusBadge } from "../components/ui";
import { useToast } from "../hooks/useToast";

interface TrackedJob {
  fileName: string;
  documentId: number;
  status: string;
  logs: ProcessingLog[];
  done: boolean;
}

export default function Upload() {
  const [dragging, setDragging] = useState(false);
  const [jobs, setJobs] = useState<TrackedJob[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const { notify } = useToast();

  const pollUntilDone = (docId: number, key: string) => {
    const timer = setInterval(async () => {
      try {
        const data = await api.get<{ processing_status: string; logs: ProcessingLog[] }>(
          `/documents/${docId}/status`
        );
        const done = ["completed", "failed", "needs_review"].includes(data.processing_status);
        setJobs((prev) =>
          prev.map((job) =>
            job.documentId + job.fileName === key
              ? { ...job, logs: data.logs, status: data.processing_status, done }
              : job
          )
        );
        if (done) clearInterval(timer);
      } catch { /* keep polling */ }
    }, 800);
  };

  const uploadFiles = async (files: FileList | null) => {
    if (!files) return;
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("file", file);
      try {
        const data = await api.upload<{ document: Document; exact_duplicate: boolean }>(
          "/documents/upload", form
        );
        const job: TrackedJob = {
          fileName: file.name,
          documentId: data.document.id,
          status: data.document.processing_status,
          logs: [],
          done: data.exact_duplicate,
        };
        setJobs((prev) => [...prev, job]);
        if (!data.exact_duplicate) {
          pollUntilDone(data.document.id, job.documentId + job.fileName);
          notify("success", `${file.name} uploaded — processing…`);
        } else {
          notify("info", `${file.name} is an exact duplicate of document #${data.document.id}`);
        }
      } catch (e: any) {
        notify("error", `${file.name}: ${e.message}`);
      }
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    uploadFiles(e.dataTransfer.files);
  };

  return (
    <div>
      <PageHeader title="Upload documents" subtitle="PDF, DOCX, TXT, JPG, PNG — processed asynchronously by the AI pipeline" />

      <Card>
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-16 text-center transition ${
            dragging ? "border-brand-500 bg-brand-50" : "border-slate-300 hover:border-brand-400 hover:bg-slate-50"
          }`}
        >
          <div className="text-5xl">⬆️</div>
          <div className="mt-3 text-lg font-medium text-slate-700">Drag & drop your documents</div>
          <div className="mt-1 text-sm text-slate-500">or <span className="font-medium text-brand-600">browse files</span></div>
          <div className="mt-3 flex gap-2">
            {["PDF", "DOCX", "TXT", "JPG", "PNG"].map((t) => (
              <span key={t} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-500">{t}</span>
            ))}
          </div>
          <input ref={inputRef} type="file" multiple className="hidden"
                 accept=".pdf,.docx,.txt,.jpg,.jpeg,.png"
                 onChange={(e) => uploadFiles(e.target.files)} />
        </div>
      </Card>

      {jobs.length > 0 && (
        <div className="mt-6 space-y-4">
          {jobs.map((job) => (
            <Card key={job.documentId + "-" + job.fileName}>
              <div className="flex items-center justify-between">
                <div className="font-medium text-slate-800">{job.fileName}</div>
                <StatusBadge status={job.status} />
              </div>
              <div className="mt-3 space-y-1 text-xs">
                {job.logs.filter((l) => l.stage !== "extract_note").map((log) => (
                  <div key={log.id} className="flex items-center gap-2">
                    <span>{log.status === "success" ? "✅" : log.status === "failed" ? "❌" : "ℹ️"}</span>
                    <span className="text-slate-600">
                      {log.stage}{log.processing_time != null ? ` (${log.processing_time}s)` : ""}
                      {log.message ? ` — ${log.message}` : ""}
                    </span>
                  </div>
                ))}
                {!job.done && job.logs.length === 0 && <div className="text-slate-400">Queued…</div>}
              </div>
              {job.done && (
                <Link to={`/documents/${job.documentId}`} className="mt-2 inline-block text-sm font-medium text-brand-600 hover:underline">
                  View document details →
                </Link>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
