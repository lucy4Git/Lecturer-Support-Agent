"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiFetch, responseMessage } from "@/lib/api-client";

export type CommercialView = "insights" | "reports" | "audit" | "settings" | "operations";

type Props = {
  activeView: CommercialView;
  activeRole: string;
};

type Overview = {
  scope: { scope_type: string; scope_id?: string | null };
  period_start: string;
  period_end: string;
  cards: Array<{ key: string; label: string; value: string | number; status: string; description?: string }>;
  output_mix: Array<{ label: string; value: number }>;
  provider_mix: Array<{ label: string; value: number }>;
  teaching_delivery: Record<string, number>;
  readiness: Record<string, number>;
  moderation: Record<string, number>;
  workload: Record<string, number>;
  alerts: Array<{ id: string; severity: string; title: string; message: string; action_path?: string | null }>;
  data_notes: string[];
};

type Usage = {
  request_count: number;
  successful_count: number;
  failed_count: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost: string;
  currency_code: string;
  average_latency_ms?: number | null;
  providers: Array<{ provider: string; requests: number; input_tokens: number; output_tokens: number; estimated_cost: string }>;
  policy_status: { warning_codes?: string[]; local_only?: boolean; hard_blocked?: boolean };
};

type ReportRun = {
  id: string;
  report_type: string;
  scope_type: string;
  status: string;
  output_format: string;
  result_sha256?: string | null;
  created_at: string;
  completed_at?: string | null;
};

type AuditEvent = {
  id: string;
  occurred_at: string;
  actor_role_code?: string | null;
  action: string;
  resource_type: string;
  correlation_id: string;
};

type Setting = {
  id: string;
  category: string;
  setting_key: string;
  value: Record<string, unknown>;
  value_type: string;
  version_number: number;
  secret_reference_only: boolean;
  updated_at: string;
};

function needsOrganisationScope(role: string) {
  return ["head_of_department", "module_coordinator", "programme_coordinator"].includes(role);
}

export function CommercialGovernancePanel({ activeView, activeRole }: Props) {
  if (activeView === "operations") return <PlatformOperationsPanel activeRole={activeRole} />;
  if (activeView === "insights") return <InsightsPanel activeRole={activeRole} />;
  if (activeView === "reports") return <ReportsPanel activeRole={activeRole} />;
  if (activeView === "audit") return <AuditPanel />;
  return <SettingsPanel />;
}

function Header({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <header className="resource-panel-header"><div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2><p>{description}</p></div></header>;
}

function ScopeControl({ activeRole, scopeId, setScopeId, onLoad, loading }: { activeRole: string; scopeId: string; setScopeId: (value: string) => void; onLoad: () => void; loading: boolean }) {
  if (!needsOrganisationScope(activeRole)) return null;
  return (
    <div className="governance-toolbar">
      <label><span>Authorised academic-unit ID</span><input value={scopeId} onChange={(event) => setScopeId(event.target.value)} placeholder="Department or authorised unit UUID" /></label>
      <button type="button" onClick={onLoad} disabled={loading || !scopeId.trim()}>{loading ? "Loading…" : "Load scope"}</button>
    </div>
  );
}

function scopeQuery(activeRole: string, scopeId: string) {
  if (needsOrganisationScope(activeRole)) return `scope_type=organisational_unit&scope_id=${encodeURIComponent(scopeId)}`;
  if (["lecturer", "internal_moderator", "external_moderator", "external_reviewer"].includes(activeRole)) return "scope_type=user";
  return "scope_type=institution";
}

function InsightsPanel({ activeRole }: { activeRole: string }) {
  const [scopeId, setScopeId] = useState("");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canAutoLoad = !needsOrganisationScope(activeRole);

  useEffect(() => { if (canAutoLoad) void load(); }, [activeRole]);

  async function load() {
    setLoading(true); setError(null);
    const query = scopeQuery(activeRole, scopeId);
    const [overviewResponse, usageResponse] = await Promise.all([
      apiFetch(`analytics/overview?${query}&days=30`),
      apiFetch(`analytics/ai-usage?${query}`),
    ]);
    if (!overviewResponse.ok || !usageResponse.ok) {
      setError(!overviewResponse.ok ? await responseMessage(overviewResponse) : await responseMessage(usageResponse));
      setLoading(false); return;
    }
    setOverview(await overviewResponse.json()); setUsage(await usageResponse.json()); setLoading(false);
  }

  const maxOutput = useMemo(() => Math.max(1, ...(overview?.output_mix.map((item) => item.value) ?? [1])), [overview]);
  return (
    <section className="resource-panel analytics-panel">
      <Header eyebrow="Teaching intelligence" title="Insights" description="Role-scoped teaching, readiness, moderation, workload, and governed AI usage signals. Analytics never widen your active institutional permissions." />
      <ScopeControl activeRole={activeRole} scopeId={scopeId} setScopeId={setScopeId} onLoad={load} loading={loading} />
      {loading && <div className="analytics-loading">Calculating authorised insights…</div>}
      {error && <div className="resource-error">{error}</div>}
      {overview && <>
        <div className="metric-grid">{overview.cards.map((card) => <article className={`metric-card ${card.status}`} key={card.key}><span>{card.label}</span><strong>{card.value}</strong><p>{card.description}</p></article>)}</div>
        <div className="analytics-grid">
          <article className="analytics-card"><h3>Teaching output mix</h3><div className="bar-list">{overview.output_mix.length ? overview.output_mix.map((item) => <div key={item.label}><span>{item.label}</span><div><i style={{ width: `${Math.max(4, item.value / maxOutput * 100)}%` }} /></div><b>{item.value}</b></div>) : <p>No outputs in this period.</p>}</div></article>
          <article className="analytics-card"><h3>Operational status</h3><DataRows title="Teaching delivery" values={overview.teaching_delivery} /><DataRows title="Module readiness" values={overview.readiness} /><DataRows title="Moderation" values={overview.moderation} /><div className="analytics-total"><span>Weighted workload hours</span><b>{overview.workload.weighted_hours ?? 0}</b></div></article>
          <article className="analytics-card"><h3>AI provider mix</h3><DataRows values={Object.fromEntries(overview.provider_mix.map((item) => [item.label, item.value]))} /><div className="usage-summary"><span>Requests this month <b>{usage?.request_count ?? 0}</b></span><span>Tokens <b>{((usage?.input_tokens ?? 0) + (usage?.output_tokens ?? 0)).toLocaleString()}</b></span><span>Estimated usage <b>{usage?.currency_code} {usage?.estimated_cost ?? "0"}</b></span></div>{usage?.policy_status.warning_codes?.map((warning) => <p className="analytics-warning" key={warning}>{humanise(warning)}</p>)}</article>
          <article className="analytics-card"><h3>Attention required</h3>{overview.alerts.length ? overview.alerts.map((alert) => <div className={`insight-alert ${alert.severity}`} key={alert.id}><strong>{alert.title}</strong><p>{alert.message}</p></div>) : <p>No open insight alerts for this scope.</p>}</article>
        </div>
        <div className="analytics-notes">{overview.data_notes.map((note) => <p key={note}>ⓘ {note}</p>)}</div>
      </>}
    </section>
  );
}

function DataRows({ title, values }: { title?: string; values: Record<string, number> }) {
  return <div className="data-rows">{title && <h4>{title}</h4>}{Object.keys(values).length ? Object.entries(values).map(([key, value]) => <div key={key}><span>{humanise(key)}</span><b>{value}</b></div>) : <p>No records.</p>}</div>;
}

function ReportsPanel({ activeRole }: { activeRole: string }) {
  const [scopeId, setScopeId] = useState("");
  const [reportType, setReportType] = useState("teaching_operations_summary");
  const [runs, setRuns] = useState<ReportRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { void loadRuns(); }, []);
  async function loadRuns() { const response = await apiFetch("analytics/report-runs"); if (response.ok) setRuns(await response.json()); }
  async function generate(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError(null);
    const scopeType = needsOrganisationScope(activeRole) ? "organisational_unit" : (["lecturer", "internal_moderator"].includes(activeRole) ? "user" : "institution");
    const response = await apiFetch("analytics/report-runs", { method: "POST", body: JSON.stringify({ report_type: reportType, scope_type: scopeType, scope_id: scopeType === "organisational_unit" ? scopeId || null : null, parameters: {}, output_format: "json" }) });
    if (!response.ok) { setError(await responseMessage(response)); setLoading(false); return; }
    const run = await response.json(); setRuns((current) => [run, ...current]); setLoading(false);
  }
  return <section className="resource-panel"><Header eyebrow="Evidence-based reporting" title="Reports" description="Generate immutable, checksum-protected teaching and operations report snapshots within your active role and scope." />
    <form className="governance-form" onSubmit={generate}><label><span>Report</span><select value={reportType} onChange={(e) => setReportType(e.target.value)}><option value="teaching_operations_summary">Teaching operations summary</option><option value="module_readiness_summary">Module readiness summary</option><option value="moderation_progress">Moderation progress</option><option value="ai_usage_governance">AI usage governance</option><option value="lecturer_activity_summary">Lecturer activity summary</option></select></label>{needsOrganisationScope(activeRole) && <label><span>Authorised academic-unit ID</span><input required value={scopeId} onChange={(e) => setScopeId(e.target.value)} /></label>}<button type="submit" disabled={loading}>{loading ? "Generating…" : "Generate report"}</button></form>
    {error && <div className="resource-error">{error}</div>}
    <div className="report-list">{runs.map((run) => <article key={run.id}><div><span className="resource-kicker">{humanise(run.report_type)}</span><strong>{humanise(run.scope_type)}</strong><small>{formatDate(run.created_at)}</small></div><span className={`status-dot ${run.status === "completed" ? "ready" : "pending"}`}>{humanise(run.status)}</span><code>{run.result_sha256?.slice(0, 12) ?? "pending"}</code></article>)}</div>
  </section>;
}

function AuditPanel() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [action, setAction] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  async function load(event?: FormEvent) { event?.preventDefault(); setLoading(true); const response = await apiFetch(`audit-centre/events?limit=100&action=${encodeURIComponent(action)}`); if (response.ok) { const data = await response.json(); setEvents(data.events || []); } else setNotice(await responseMessage(response)); setLoading(false); }
  useEffect(() => { void load(); }, []);
  async function exportEvents(format: "json" | "csv") { const response = await apiFetch("audit-centre/exports", { method: "POST", body: JSON.stringify({ action: action || null, output_format: format }) }); setNotice(response.ok ? `Audit ${format.toUpperCase()} export created with integrity checksum.` : await responseMessage(response)); }
  return <section className="resource-panel"><Header eyebrow="Governed evidence" title="Audit centre" description="Search tenant-scoped audit evidence, review security events, and produce checksum-protected exports. Audit Centre access is reserved for the Institution Administrator." />
    <form className="audit-filter" onSubmit={load}><input value={action} onChange={(e) => setAction(e.target.value)} placeholder="Filter by action, for example output.released" /><button type="submit">{loading ? "Searching…" : "Search"}</button><button type="button" onClick={() => void exportEvents("json")}>Export JSON</button><button type="button" onClick={() => void exportEvents("csv")}>Export CSV</button></form>
    {notice && <div className="notice">{notice}</div>}
    <div className="audit-table" role="table"><div className="audit-row heading"><span>Time</span><span>Action</span><span>Resource</span><span>Role</span><span>Correlation</span></div>{events.map((item) => <div className="audit-row" key={item.id}><span>{formatDate(item.occurred_at)}</span><strong>{item.action}</strong><span>{humanise(item.resource_type)}</span><span>{humanise(item.actor_role_code || "system")}</span><code>{item.correlation_id.slice(0, 10)}</code></div>)}</div>
  </section>;
}

function SettingsPanel() {
  type Integration = { id: string; code: string; display_name: string; integration_type: string; status: string; last_test_status?: string | null; secret_reference?: string | null };
  type SSO = { id: string; code: string; display_name: string; protocol: string; issuer_url: string; is_enabled: boolean; client_secret_reference?: string | null };
  const [settings, setSettings] = useState<Setting[]>([]);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [ssoConnections, setSsoConnections] = useState<SSO[]>([]);
  const [category, setCategory] = useState("institution");
  const [key, setKey] = useState("default_locale");
  const [value, setValue] = useState('{"value":"en-GB"}');
  const [notice, setNotice] = useState<string | null>(null);
  async function load() {
    const [settingsResponse, integrationsResponse, ssoResponse] = await Promise.all([
      apiFetch("platform-settings"), apiFetch("integrations"), apiFetch("sso-connections"),
    ]);
    if (settingsResponse.ok) setSettings(await settingsResponse.json()); else setNotice(await responseMessage(settingsResponse));
    if (integrationsResponse.ok) setIntegrations(await integrationsResponse.json());
    if (ssoResponse.ok) setSsoConnections(await ssoResponse.json());
  }
  useEffect(() => { void load(); }, []);
  async function save(event: FormEvent) {
    event.preventDefault(); let parsed: Record<string, unknown>;
    try { parsed = JSON.parse(value); } catch { setNotice("Setting value must be valid JSON."); return; }
    const response = await apiFetch(`platform-settings/${encodeURIComponent(category)}/${encodeURIComponent(key)}`, { method: "PUT", body: JSON.stringify({ scope_type: "institution", value: parsed, value_type: "json", description: "Configured in the commercial platform settings view." }) });
    if (!response.ok) { setNotice(await responseMessage(response)); return; }
    setNotice("Setting saved as a new version without storing live secrets."); await load();
  }
  async function createIntegration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const values = new FormData(event.currentTarget);
    const response = await apiFetch("integrations", { method: "POST", body: JSON.stringify({
      code: values.get("code"), display_name: values.get("display_name"), integration_type: values.get("integration_type"),
      base_url: values.get("base_url") || null, authentication_type: "oauth2", secret_reference: values.get("secret_reference") || null,
      capabilities: [], configuration: {},
    }) });
    setNotice(response.ok ? "Integration connection created with a secret reference only." : await responseMessage(response));
    if (response.ok) { event.currentTarget.reset(); await load(); }
  }
  async function createSSO(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const values = new FormData(event.currentTarget);
    const redirectUri = `${window.location.origin}/sso/callback`;
    const response = await apiFetch("sso-connections", { method: "POST", body: JSON.stringify({
      code: values.get("code"), display_name: values.get("display_name"), protocol: "oidc", issuer_url: values.get("issuer_url"),
      client_id: values.get("client_id"), client_secret_reference: values.get("client_secret_reference") || null,
      scopes: ["openid", "profile", "email"], claim_mapping: {}, default_role_code: null, is_enabled: true,
      redirect_uris: [redirectUri], allow_account_linking_by_verified_email: false,
    }) });
    setNotice(response.ok ? "OIDC connection created. Add its actual secret only to the referenced environment variable." : await responseMessage(response));
    if (response.ok) { event.currentTarget.reset(); await load(); }
  }
  async function testIntegration(id: string) {
    const response = await apiFetch(`integrations/${id}/test`, { method: "POST" });
    setNotice(response.ok ? "Connection test completed; review the recorded status." : await responseMessage(response));
    await load();
  }
  return <section className="resource-panel"><Header eyebrow="Commercial configuration" title="Platform settings" description="Configure non-secret institution settings, standards-based integrations and OIDC connections. API keys and client secrets remain only in environment variables or a secret manager." />
    <form className="governance-form settings-form" onSubmit={save}><label><span>Category</span><input value={category} onChange={(e) => setCategory(e.target.value)} /></label><label><span>Setting key</span><input value={key} onChange={(e) => setKey(e.target.value)} /></label><label className="wide"><span>JSON value</span><textarea rows={5} value={value} onChange={(e) => setValue(e.target.value)} /></label><button type="submit">Save version</button></form>
    <div className="operations-control-grid">
      <form className="governance-form" onSubmit={createIntegration}><h3>Academic-system integration</h3><label><span>Code</span><input name="code" pattern="[a-z0-9_-]+" required /></label><label><span>Name</span><input name="display_name" required /></label><label><span>Type</span><select name="integration_type"><option value="canvas">Canvas</option><option value="moodle">Moodle</option><option value="oneroster_csv">OneRoster CSV</option><option value="oneroster_rest">OneRoster REST</option><option value="generic_rest">Generic REST</option></select></label><label><span>Base URL</span><input name="base_url" type="url" /></label><label><span>Secret environment variable</span><input name="secret_reference" placeholder="CANVAS_API_TOKEN" /></label><button type="submit">Create integration</button></form>
      <form className="governance-form" onSubmit={createSSO}><h3>OpenID Connect SSO</h3><label><span>Code</span><input name="code" pattern="[a-z0-9_-]+" required /></label><label><span>Name</span><input name="display_name" required /></label><label><span>Issuer URL</span><input name="issuer_url" type="url" required /></label><label><span>Client ID</span><input name="client_id" required /></label><label><span>Client secret environment variable</span><input name="client_secret_reference" placeholder="ENTRA_CLIENT_SECRET" /></label><button type="submit">Create SSO connection</button></form>
    </div>
    {notice && <div className="notice">{notice}</div>}
    <div className="settings-list">{settings.map((item) => <article key={item.id}><div><span className="resource-kicker">{item.category}</span><strong>{item.setting_key}</strong><small>Version {item.version_number} · {formatDate(item.updated_at)}</small></div><code>{JSON.stringify(item.value)}</code>{item.secret_reference_only && <span className="verification-pill cited">Secret reference only</span>}</article>)}</div>
    <div className="operations-lists">
      <article className="analytics-card"><h3>Integration connections</h3><div className="data-rows">{integrations.map((item) => <div key={item.id}><span>{item.display_name}<small>{humanise(item.integration_type)} · {item.secret_reference ? "secret reference configured" : "no secret reference"}</small></span><button type="button" onClick={() => void testIntegration(item.id)}>{humanise(item.last_test_status || item.status)}</button></div>)}</div></article>
      <article className="analytics-card"><h3>SSO connections</h3><div className="data-rows">{ssoConnections.map((item) => <div key={item.id}><span>{item.display_name}<small>{item.issuer_url}</small></span><b>{item.is_enabled ? "Enabled" : "Disabled"}</b></div>)}</div></article>
    </div>
  </section>;
}

type OperationsSummaryData = { counts: Record<string, number>; dead_letter_count: number; oldest_queued_at?: string | null };
type OperationalJob = { id: string; job_type: string; status: string; attempt_count: number; max_attempts: number; created_at: string; completed_at?: string | null; last_error_code?: string | null };
type OperationalSchedule = { id: string; code: string; job_type: string; interval_seconds?: number | null; is_enabled: boolean; next_run_at?: string | null; last_run_at?: string | null };
type RetentionRun = { id: string; status: string; dry_run: boolean; candidate_count: number; action_count: number; skipped_count: number; created_at: string; completed_at?: string | null };
type DeliveryEvidence = { id: string; channel: string; status: string; attempt_count: number; delivered_at?: string | null; last_error_code?: string | null; created_at: string };

function PlatformOperationsPanel({ activeRole }: { activeRole: string }) {
  const [summary, setSummary] = useState<OperationsSummaryData | null>(null);
  const [jobs, setJobs] = useState<OperationalJob[]>([]);
  const [schedules, setSchedules] = useState<OperationalSchedule[]>([]);
  const [retentionRuns, setRetentionRuns] = useState<RetentionRun[]>([]);
  const [deliveries, setDeliveries] = useState<DeliveryEvidence[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [scheduleCode, setScheduleCode] = useState("external-access-expiry");
  const [jobType, setJobType] = useState("external_access.expire");
  const [intervalMinutes, setIntervalMinutes] = useState(60);

  async function load() {
    setLoading(true); setNotice(null);
    const [summaryResponse, jobsResponse, schedulesResponse, retentionResponse, deliveryResponse] = await Promise.all([
      apiFetch("operations/summary"), apiFetch("operations/jobs?limit=50"), apiFetch("operations/schedules"),
      apiFetch("operations/retention-runs?limit=20"), apiFetch("operations/notification-deliveries?limit=30"),
    ]);
    if (!summaryResponse.ok) { setNotice(await responseMessage(summaryResponse)); setLoading(false); return; }
    setSummary(await summaryResponse.json());
    if (jobsResponse.ok) setJobs(await jobsResponse.json());
    if (schedulesResponse.ok) setSchedules(await schedulesResponse.json());
    if (retentionResponse.ok) setRetentionRuns(await retentionResponse.json());
    if (deliveryResponse.ok) setDeliveries(await deliveryResponse.json());
    setLoading(false);
  }
  useEffect(() => { if (activeRole === "institution_administrator") void load(); }, [activeRole]);

  async function createSchedule(event: FormEvent) {
    event.preventDefault();
    const response = await apiFetch("operations/schedules", { method: "POST", body: JSON.stringify({
      code: scheduleCode.trim(), job_type: jobType, interval_seconds: Math.max(60, intervalMinutes * 60),
      payload: {}, is_enabled: true,
    }) });
    setNotice(response.ok ? "Governed interval schedule created. The worker materialises due jobs without bypassing tenant isolation." : await responseMessage(response));
    if (response.ok) await load();
  }

  async function requestRetention(dryRun: boolean) {
    const response = await apiFetch("operations/retention-runs", { method: "POST", body: JSON.stringify({ dry_run: dryRun, max_candidates: 1000 }) });
    setNotice(response.ok ? (dryRun ? "Retention preview queued; no records will be changed." : "Reversible retention run queued. Hard deletion is not supported.") : await responseMessage(response));
    if (response.ok) await load();
  }

  if (activeRole !== "institution_administrator") return <section className="resource-panel"><Header eyebrow="Restricted operations" title="Platform operations" description="Platform operations are reserved for the independent Institution Administrator role." /></section>;
  const queueTotal = Object.values(summary?.counts || {}).reduce((total, value) => total + value, 0);
  return <section className="resource-panel"><Header eyebrow="Operational control" title="Platform operations" description="Monitor durable jobs, schedules, notification delivery, retention evidence, and recovery signals without exposing provider credentials." />
    <div className="analytics-card-grid">
      <article className="analytics-card"><span>Tracked jobs</span><strong>{queueTotal}</strong><small>{summary?.dead_letter_count ?? 0} dead-letter records</small></article>
      <article className="analytics-card"><span>Active schedules</span><strong>{schedules.filter((item) => item.is_enabled).length}</strong><small>Interval schedules only; cron remains disabled until runtime validation.</small></article>
      <article className="analytics-card"><span>Retention evidence</span><strong>{retentionRuns.length}</strong><small>Dry-run and reversible actions are retained.</small></article>
      <article className="analytics-card"><span>Delivery evidence</span><strong>{deliveries.length}</strong><small>In-app delivery is supported; unconfigured channels fail visibly.</small></article>
    </div>
    <div className="operations-control-grid">
      <form className="governance-form" onSubmit={createSchedule}><h3>Create interval schedule</h3><label><span>Code</span><input value={scheduleCode} onChange={(event) => setScheduleCode(event.target.value)} pattern="[a-z0-9_.-]+" required /></label><label><span>Job type</span><select value={jobType} onChange={(event) => setJobType(event.target.value)}><option value="external_access.expire">Expire external access</option><option value="notifications.dispatch">Dispatch notifications</option><option value="outbox.publish">Publish outbox</option><option value="governance.apply_retention">Apply retention</option></select></label><label><span>Interval (minutes)</span><input type="number" min={1} value={intervalMinutes} onChange={(event) => setIntervalMinutes(Number(event.target.value))} /></label><button type="submit">Create schedule</button></form>
      <article className="governance-form"><h3>Retention controls</h3><p>Preview candidates first. Execution supports only reversible archive or expiry actions and never performs implicit hard deletion.</p><div className="button-row"><button type="button" onClick={() => void requestRetention(true)}>Run preview</button><button type="button" onClick={() => void requestRetention(false)}>Run reversible actions</button></div></article>
    </div>
    {notice && <div className="notice">{notice}</div>}
    {loading && <div className="resource-loading">Loading operational evidence…</div>}
    <div className="operations-lists">
      <article className="analytics-card"><h3>Recent durable jobs</h3><div className="report-list">{jobs.map((item) => <div key={item.id}><div><span className="resource-kicker">{humanise(item.job_type)}</span><strong>{humanise(item.status)}</strong><small>{formatDate(item.created_at)} · attempt {item.attempt_count}/{item.max_attempts}</small></div><span className={`status-dot ${item.status === "completed" ? "ready" : item.status === "dead_letter" ? "critical" : "pending"}`}>{item.last_error_code ? humanise(item.last_error_code) : humanise(item.status)}</span></div>)}</div></article>
      <article className="analytics-card"><h3>Schedules</h3><div className="data-rows">{schedules.map((item) => <div key={item.id}><span>{item.code}<small>{humanise(item.job_type)} · every {Math.round((item.interval_seconds || 0) / 60)} min</small></span><b>{item.is_enabled ? "Enabled" : "Disabled"}</b></div>)}</div></article>
      <article className="analytics-card"><h3>Retention runs</h3><div className="data-rows">{retentionRuns.map((item) => <div key={item.id}><span>{item.dry_run ? "Preview" : "Reversible execution"}<small>{formatDate(item.created_at)}</small></span><b>{item.candidate_count} / {item.action_count} / {item.skipped_count}</b></div>)}</div></article>
      <article className="analytics-card"><h3>Notification delivery</h3><div className="data-rows">{deliveries.map((item) => <div key={item.id}><span>{humanise(item.channel)}<small>{formatDate(item.created_at)}</small></span><b>{humanise(item.status)}</b></div>)}</div></article>
    </div>
  </section>;
}

function humanise(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }
function formatDate(value: string) { return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
