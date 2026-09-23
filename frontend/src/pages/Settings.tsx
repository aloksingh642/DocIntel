import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "../services/api";
import type { RuntimeSetting, WebhookRow } from "../types";
import { Card, PageHeader, Spinner } from "../components/ui";
import { useToast } from "../hooks/useToast";
import { useAuth } from "../hooks/useAuth";

export default function Settings() {
  const [config, setConfig] = useState<any>(null);
  const [runtime, setRuntime] = useState<RuntimeSetting[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [aliases, setAliases] = useState<{ id: number; alias: string; canonical: string }[]>([]);
  const [users, setUsers] = useState<{ id: number; name: string; email: string; role: string }[]>([]);
  const [audit, setAudit] = useState<any[] | null>(null);
  const [webhooks, setWebhooks] = useState<WebhookRow[]>([]);
  const [alias, setAlias] = useState("");
  const [canonical, setCanonical] = useState("");
  const [hookUrl, setHookUrl] = useState("");
  const [hookSecret, setHookSecret] = useState("");
  const [pwCurrent, setPwCurrent] = useState("");
  const [pwNew, setPwNew] = useState("");
  const [pwConfirm, setPwConfirm] = useState("");
  const { notify } = useToast();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const load = useCallback(() => {
    api.get("/admin/config").then(setConfig).catch(() => null);
    api.get<RuntimeSetting[]>("/admin/settings").then(setRuntime).catch(() => null);
    api.get<{ id: number; alias: string; canonical: string }[]>("/skills/aliases").then(setAliases).catch(() => null);
    api.get<WebhookRow[]>("/admin/webhooks").then(setWebhooks).catch(() => null);
    if (isAdmin) {
      api.get<typeof users>("/auth/users").then(setUsers).catch(() => null);
      api.get<any[]>("/admin/audit-logs?limit=20").then(setAudit).catch(() => null);
    }
  }, [isAdmin]);
  useEffect(load, [load]);

  useEffect(() => {
    setDraft(Object.fromEntries(runtime.map((r) => [r.key, String(r.value)])));
  }, [runtime]);

  const input = "rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none";

  const saveSettings = async (e: FormEvent) => {
    e.preventDefault();
    const changed: Record<string, number> = {};
    for (const r of runtime) if (draft[r.key] !== String(r.value)) changed[r.key] = Number(draft[r.key]);
    if (!Object.keys(changed).length) { notify("info", "No changes to save"); return; }
    try {
      await api.put("/admin/settings", { values: changed });
      notify("success", "Settings updated — applied immediately");
      load();
    } catch (e2: any) { notify("error", e2.message); }
  };

  const changePassword = async (e: FormEvent) => {
    e.preventDefault();
    if (pwNew !== pwConfirm) { notify("error", "New passwords do not match"); return; }
    try {
      await api.post("/auth/change-password", { current_password: pwCurrent, new_password: pwNew });
      notify("success", "Password changed");
      setPwCurrent(""); setPwNew(""); setPwConfirm("");
    } catch (e2: any) { notify("error", e2.message); }
  };

  const addWebhook = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.post("/admin/webhooks", { url: hookUrl, secret: hookSecret || null });
      notify("success", "Webhook registered");
      setHookUrl(""); setHookSecret("");
      load();
    } catch (e2: any) { notify("error", e2.message); }
  };

  const toggleWebhook = async (id: number) => {
    try { await api.put(`/admin/webhooks/${id}/toggle`, {}); load(); }
    catch (e: any) { notify("error", e.message); }
  };

  const deleteWebhook = async (id: number) => {
    if (!confirm("Delete this webhook?")) return;
    try { await api.delete(`/admin/webhooks/${id}`); notify("success", "Webhook deleted"); load(); }
    catch (e: any) { notify("error", e.message); }
  };

  const addAlias = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.post("/skills/aliases", { alias, canonical });
      notify("success", "Alias saved — applies to all future normalization");
      setAlias(""); setCanonical("");
      load();
    } catch (e2: any) { notify("error", e2.message); }
  };

  const changeRole = async (id: number, role: string) => {
    try {
      await api.put(`/auth/users/${id}/role?role=${role}`, {});
      notify("success", "Role updated");
      load();
    } catch (e: any) { notify("error", e.message); }
  };

  if (!config) return <Spinner />;

  return (
    <div>
      <PageHeader title="Settings" subtitle="Runtime configuration, skill aliases, users, webhooks and audit trail" />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Environment</h3>
          <dl className="space-y-2 text-sm">
            <Row k="AI provider" v={config.ai_provider} />
            <Row k="Max file size" v={`${config.max_file_size_mb} MB`} />
            <Row k="Allowed types" v={config.allowed_extensions.join(", ")} />
            <Row k="OCR engine" v={config.ocr_available ? "available" : "not installed (images will fail gracefully)"} />
            <Row k="Database" v={config.database} />
          </dl>
        </Card>

        <Card>
          <h3 className="mb-1 text-sm font-semibold text-slate-700">Processing thresholds</h3>
          <p className="mb-3 text-xs text-slate-500">Applied at runtime — no redeploy required.</p>
          <form onSubmit={saveSettings} className="space-y-3">
            {runtime.map((r) => (
              <div key={r.key}>
                <div className="flex items-center justify-between text-sm">
                  <label className="text-slate-600">{r.label}
                    {r.overridden && <span className="ml-2 rounded-full bg-brand-50 px-2 py-0.5 text-xs text-brand-600">custom</span>}
                  </label>
                  <input
                    type="number" step="0.01" min={r.min ?? undefined} max={r.max ?? undefined}
                    className={`${input} w-24 text-right`}
                    value={draft[r.key] ?? String(r.value)}
                    disabled={!isAdmin}
                    onChange={(e) => setDraft({ ...draft, [r.key]: e.target.value })}
                  />
                </div>
                <p className="text-xs text-slate-400">{r.help} Default: {r.default}</p>
              </div>
            ))}
            {isAdmin && (
              <button className="rounded-lg bg-brand-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-700">
                Save thresholds
              </button>
            )}
          </form>
        </Card>

        <Card>
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Change password</h3>
          <form onSubmit={changePassword} className="space-y-2">
            <input type="password" className={`${input} w-full`} placeholder="Current password"
                   value={pwCurrent} onChange={(e) => setPwCurrent(e.target.value)} required />
            <input type="password" className={`${input} w-full`} placeholder="New password (min 8 chars)"
                   value={pwNew} onChange={(e) => setPwNew(e.target.value)} required minLength={8} />
            <input type="password" className={`${input} w-full`} placeholder="Confirm new password"
                   value={pwConfirm} onChange={(e) => setPwConfirm(e.target.value)} required minLength={8} />
            <button className="rounded-lg bg-slate-700 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-800">
              Change password
            </button>
          </form>
        </Card>

        <Card>
          <h3 className="mb-1 text-sm font-semibold text-slate-700">Webhooks</h3>
          <p className="mb-3 text-xs text-slate-500">
            Notified when a document finishes processing. Payload is HMAC-SHA256 signed
            with your secret in the <code>X-IDP-Signature</code> header.
          </p>
          {isAdmin && (
            <form onSubmit={addWebhook} className="mb-3 space-y-2">
              <input className={`${input} w-full`} placeholder="https://your-service.example/hooks/idp"
                     value={hookUrl} onChange={(e) => setHookUrl(e.target.value)} required />
              <div className="flex gap-2">
                <input className={`${input} w-full`} placeholder="Signing secret (optional)"
                       value={hookSecret} onChange={(e) => setHookSecret(e.target.value)} />
                <button className="rounded-lg bg-brand-600 px-4 py-1.5 text-sm font-medium text-white">Add</button>
              </div>
            </form>
          )}
          <div className="space-y-2 text-sm">
            {webhooks.map((w) => (
              <div key={w.id} className="flex items-center justify-between gap-2 rounded-md bg-slate-50 px-3 py-2">
                <div className="min-w-0">
                  <div className="truncate font-medium text-slate-800">{w.url}</div>
                  <div className="text-xs text-slate-400">
                    {w.event} • {w.delivery_count} deliveries
                    {w.last_delivery && (
                      <> • last: {w.last_delivery.success
                        ? <span className="text-emerald-600">OK ({w.last_delivery.status_code})</span>
                        : <span className="text-rose-500">failed{w.last_delivery.error ? ` (${w.last_delivery.error})` : ""}</span>}
                      </>
                    )}
                    {w.has_secret && " • signed"}
                  </div>
                </div>
                {isAdmin && (
                  <div className="flex shrink-0 gap-2">
                    <button onClick={() => toggleWebhook(w.id)}
                            className={`rounded-md px-2 py-1 text-xs ${w.active ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>
                      {w.active ? "Disable" : "Enable"}
                    </button>
                    <button onClick={() => deleteWebhook(w.id)}
                            className="rounded-md bg-rose-100 px-2 py-1 text-xs text-rose-600">Delete</button>
                  </div>
                )}
              </div>
            ))}
            {webhooks.length === 0 && <p className="text-sm text-slate-400">No webhooks registered.</p>}
          </div>
        </Card>

        <Card>
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Skill aliases</h3>
          {isAdmin && (
            <form onSubmit={addAlias} className="mb-3 flex gap-2">
              <input className={`${input} w-1/2`} placeholder="postgres" value={alias} onChange={(e) => setAlias(e.target.value)} required />
              <span className="self-center text-slate-400">→</span>
              <input className={`${input} w-1/2`} placeholder="PostgreSQL" value={canonical} onChange={(e) => setCanonical(e.target.value)} required />
              <button className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white">Add</button>
            </form>
          )}
          <div className="max-h-56 space-y-1 overflow-y-auto text-sm">
            {aliases.slice(0, 30).map((a) => (
              <div key={a.id} className="flex justify-between rounded-md bg-slate-50 px-3 py-1.5">
                <span className="text-slate-600">{a.alias}</span>
                <span className="font-medium text-slate-800">{a.canonical}</span>
              </div>
            ))}
            {aliases.length === 0 && <p className="text-sm text-slate-400">No custom aliases (seeded defaults always apply).</p>}
          </div>
        </Card>

        {isAdmin && (
          <Card>
            <h3 className="mb-3 text-sm font-semibold text-slate-700">User management</h3>
            <div className="space-y-2 text-sm">
              {users.map((u) => (
                <div key={u.id} className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2">
                  <div>
                    <div className="font-medium text-slate-800">{u.name}</div>
                    <div className="text-xs text-slate-400">{u.email}</div>
                  </div>
                  <select value={u.role} onChange={(e) => changeRole(u.id, e.target.value)}
                          className="rounded-lg border border-slate-300 px-2 py-1 text-xs">
                    <option value="admin">admin</option>
                    <option value="recruiter">recruiter</option>
                    <option value="viewer">viewer</option>
                  </select>
                </div>
              ))}
            </div>
          </Card>
        )}

        {isAdmin && audit && (
          <Card className="lg:col-span-2">
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Audit trail (latest)</h3>
            <div className="max-h-64 space-y-1 overflow-y-auto text-xs">
              {audit.map((a) => (
                <div key={a.id} className="rounded-md bg-slate-50 px-3 py-1.5 text-slate-600">
                  <span className="font-medium text-slate-800">{a.action}</span>
                  {" "}on {a.entity}{a.entity_id ? ` #${a.entity_id}` : ""}
                  {a.new_value && <span className="text-slate-500"> — {a.new_value}</span>}
                  <div className="text-slate-400">{a.created_at ? new Date(a.created_at).toLocaleString() : ""}</div>
                </div>
              ))}
              {audit.length === 0 && <p className="text-sm text-slate-400">No audit events yet.</p>}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-500">{k}</dt>
      <dd className="text-right font-medium text-slate-700">{v}</dd>
    </div>
  );
}
