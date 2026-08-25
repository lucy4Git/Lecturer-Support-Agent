"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiFetch, responseMessage } from "@/lib/api-client";
import { CommercialGovernancePanel } from "@/components/commercial-governance-panels";

export type WorkspaceView = "conversation" | "search" | "library" | "sources" | "files" | "saved" | "notifications" | "insights" | "reports" | "audit" | "settings" | "operations";

type SearchResult = {
  kind: string;
  id: string;
  title: string;
  snippet?: string | null;
  updated_at: string;
  action_path?: string | null;
  metadata: Record<string, unknown>;
};

type LibraryItem = {
  document_id: string;
  document_version_id: string;
  title: string;
  document_type: string;
  original_filename: string;
  version_number: number;
  version_status: string;
  visibility: string;
  updated_at: string;
  indexed: boolean;
  access_label: string;
};

type SavedOutput = {
  id: string;
  generated_output_id: string;
  output_version_id: string;
  label?: string | null;
  note?: string | null;
  folder?: string | null;
  tags: string[];
  is_pinned: boolean;
  output_title?: string | null;
  output_type?: string | null;
  version_number?: number | null;
  content_preview?: string | null;
  updated_at: string;
};

type Notification = {
  id: string;
  notification_type: string;
  title: string;
  body: string;
  severity: string;
  action_path?: string | null;
  read_at?: string | null;
  created_at: string;
};

type Props = {
  activeView: Exclude<WorkspaceView, "conversation">;
  activeRole: string;
  initialSearchQuery?: string;
  onOpenConversation: (conversationId: string) => void;
  onAttachVersion: (versionId: string, filename: string) => void;
  onReturnToConversation: () => void;
  onOpenRoleAction: (action: string) => void;
  onUnreadCountChange: (count: number) => void;
};

export function WorkspaceResourcePanel(props: Props) {
  if (["insights", "reports", "audit", "settings", "operations"].includes(props.activeView)) {
    return <CommercialGovernancePanel activeView={props.activeView as "insights" | "reports" | "audit" | "settings" | "operations"} activeRole={props.activeRole} />;
  }
  if (props.activeView === "search") return <SearchPanel {...props} />;
  if (props.activeView === "library") return <LibraryPanel mode="library" {...props} />;
  if (props.activeView === "sources") return <SourcesPanel {...props} />;
  if (props.activeView === "files") return <LibraryPanel mode="files" {...props} />;
  if (props.activeView === "saved") return <SavedOutputsPanel {...props} />;
  return <NotificationsPanel {...props} />;
}

function PanelHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: React.ReactNode }) {
  return (
    <header className="resource-panel-header">
      <div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2><p>{description}</p></div>
      {actions && <div className="resource-header-actions">{actions}</div>}
    </header>
  );
}

function SearchPanel({ initialSearchQuery = "", onOpenConversation, onAttachVersion, onReturnToConversation, onOpenRoleAction }: Props) {
  const [query, setQuery] = useState(initialSearchQuery);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [archived, setArchived] = useState<{ id: string; title: string; updated_at: string }[]>([]);
  const [archivedLoading, setArchivedLoading] = useState(false);

  async function search(event?: FormEvent) {
    event?.preventDefault();
    const cleaned = query.trim();
    if (cleaned.length < 2) { setError("Enter at least two characters."); return; }
    setLoading(true); setError(null);
    const kinds = filter === "all" ? "" : filter;
    const response = await apiFetch(`workspace/search?q=${encodeURIComponent(cleaned)}&kinds=${encodeURIComponent(kinds)}`);
    if (!response.ok) { setError(await responseMessage(response)); setLoading(false); return; }
    const data = await response.json();
    setResults(data.results || []); setLoading(false);
  }

  async function loadArchived() {
    setArchivedLoading(true);
    const response = await apiFetch("conversations?archived=true&limit=100");
    if (response.ok) setArchived(await response.json());
    setArchivedLoading(false);
  }

  async function unarchive(id: string) {
    const response = await apiFetch(`conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_archived: false }),
    });
    if (response.ok) setArchived((current) => current.filter((c) => c.id !== id));
  }

  function selectFilter(key: string) {
    setFilter(key);
    if (key === "archived" && archived.length === 0 && !archivedLoading) void loadArchived();
  }

  function activate(result: SearchResult) {
    const path = result.action_path || "";
    if (path.startsWith("conversation:")) onOpenConversation(path.split(":")[1]);
    else if (path.startsWith("file:")) onAttachVersion(path.split(":")[1], result.title);
    else if (path.startsWith("action:")) onOpenRoleAction(path.split(":")[1]);
  }

  return (
    <section className="resource-panel">
      <PanelHeader eyebrow="Everything in one place" title="Search" description="Search only the conversations, generated outputs, files, and review work your active role may access." />
      <form className="global-search-form" onSubmit={search}>
        <span aria-hidden="true">⌕</span>
        <input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search teaching work, files, outputs, or review tasks" aria-label="Search workspace" />
        <button type="submit" disabled={loading}>{loading ? "Searching…" : "Search"}</button>
      </form>
      <div className="filter-row" aria-label="Search categories">
        {[['all','All'],['conversation','Conversations'],['output','Outputs'],['document','Files'],['review_task','Review tasks'],['archived','Archived']].map(([key,label]) => (
          <button type="button" key={key} className={filter === key ? "filter-chip active" : "filter-chip"} onClick={() => selectFilter(key)}>{label}</button>
        ))}
      </div>
      {filter === "archived" ? (
        <>
          {archivedLoading && <div className="resource-panel-loading">Loading archived conversations…</div>}
          {!archivedLoading && archived.length === 0 && <EmptyState title="No archived conversations" body="Conversations you archive will appear here." />}
          <div className="resource-card-grid search-results">
            {archived.map((conv) => (
              <div className="resource-card search-result-card archived-result" key={conv.id}>
                <button type="button" className="archived-result-open" onClick={() => onOpenConversation(conv.id)}>
                  <span className="resource-kicker">Archived conversation</span>
                  <strong>{conv.title}</strong>
                  <small>{formatDate(conv.updated_at)}</small>
                </button>
                <button type="button" className="text-action" onClick={() => void unarchive(conv.id)}>Unarchive</button>
              </div>
            ))}
          </div>
        </>
      ) : (
        <>
          {error && <div className="resource-error">{error}</div>}
          {!loading && query.trim().length >= 2 && results.length === 0 && !error && <EmptyState title="No authorised results" body="Try a broader term or check another category." />}
          <div className="resource-card-grid search-results">
            {results.map((result) => (
              <button type="button" className="resource-card search-result-card" key={`${result.kind}-${result.id}`} onClick={() => activate(result)}>
                <div className={`resource-icon kind-${result.kind}`}>{iconForKind(result.kind)}</div>
                <div><span className="resource-kicker">{humanise(result.kind)}</span><strong>{result.title}</strong>{result.snippet && <p>{result.snippet}</p>}<small>{formatDate(result.updated_at)}</small></div>
                <span className="resource-arrow">→</span>
              </button>
            ))}
          </div>
        </>
      )}
      {!!results.length && filter !== "archived" && <button type="button" className="text-action" onClick={onReturnToConversation}>Return to conversation</button>}
    </section>
  );
}

function LibraryPanel({ mode, onAttachVersion, onReturnToConversation, onOpenRoleAction }: Props & { mode: "library" | "files" }) {
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState(mode === "files" ? "mine" : "all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { void load(); }, [view, mode]);
  async function load() {
    setLoading(true); setError(null);
    const response = await apiFetch(`workspace/${mode}?view=${view}`);
    if (!response.ok) { setError(await responseMessage(response)); setLoading(false); return; }
    const data = await response.json(); setItems(data.items || []); setLoading(false);
  }

  const title = mode === "library" ? "Library" : "Files";
  const description = mode === "library"
    ? "Your permitted institutional and shared academic knowledge, with immutable versions and clear access labels."
    : "Your uploads and authorised shared files. Attach any available version to the next AI request without leaving this work area.";
  return (
    <section className="resource-panel">
      <PanelHeader eyebrow="Authorised knowledge" title={title} description={description} actions={<button type="button" className="primary-compact-button" onClick={() => onOpenRoleAction("bulkUpload")}>＋ Upload</button>} />
      <div className="filter-row">
        <button type="button" className={view === "all" ? "filter-chip active" : "filter-chip"} onClick={() => setView("all")}>All accessible</button>
        <button type="button" className={view === "mine" ? "filter-chip active" : "filter-chip"} onClick={() => setView("mine")}>My uploads</button>
        <button type="button" className={view === "institutional" ? "filter-chip active" : "filter-chip"} onClick={() => setView("institutional")}>Institutional</button>
      </div>
      {loading && <ResourceSkeleton count={6} />}
      {error && <div className="resource-error">{error}</div>}
      {!loading && !error && items.length === 0 && <EmptyState title={`No ${title.toLowerCase()} available`} body="Upload authorised content or change the access filter." />}
      <div className="resource-card-grid file-grid">
        {items.map((item) => (
          <article className="resource-card file-card" key={item.document_version_id}>
            <div className="file-card-top"><div className="resource-icon kind-document">▤</div><span className={item.indexed ? "status-dot ready" : "status-dot pending"}>{item.indexed ? "AI ready" : "Processing"}</span></div>
            <span className="resource-kicker">{humanise(item.document_type)}</span>
            <strong>{item.title}</strong><p>{item.original_filename}</p>
            <div className="file-meta"><span>Version {item.version_number}</span><span>{humanise(item.visibility)}</span><span>{item.access_label}</span></div>
            <div className="resource-actions"><button type="button" onClick={() => { onAttachVersion(item.document_version_id, item.original_filename); onReturnToConversation(); }}>Attach to conversation</button></div>
          </article>
        ))}
      </div>
    </section>
  );
}

function SavedOutputsPanel({ onReturnToConversation }: Props) {
  const [items, setItems] = useState<SavedOutput[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { void load(); }, []);
  async function load() {
    setLoading(true); const response = await apiFetch("workspace/saved-outputs");
    if (!response.ok) { setError(await responseMessage(response)); setLoading(false); return; }
    setItems(await response.json()); setLoading(false);
  }
  async function remove(id: string) {
    const response = await apiFetch(`workspace/saved-outputs/${id}`, { method: "DELETE" });
    if (response.ok) setItems((current) => current.filter((item) => item.id !== id));
    else setError(await responseMessage(response));
  }
  return (
    <section className="resource-panel">
      <PanelHeader eyebrow="Reusable teaching work" title="Saved outputs" description="Pinned lesson plans, assessments, rubrics, marking guides, and reports remain linked to the exact immutable version you saved." />
      {loading && <ResourceSkeleton count={4} />}{error && <div className="resource-error">{error}</div>}
      {!loading && !error && items.length === 0 && <EmptyState title="Nothing saved yet" body="Use Save on a generated output inside a conversation to keep its exact version here." />}
      <div className="resource-card-grid saved-grid">
        {items.map((item) => <article className="resource-card saved-card" key={item.id}>
          <div className="saved-card-heading"><div className="resource-icon kind-output">☆</div>{item.is_pinned && <span className="pin-label">Pinned</span>}</div>
          <span className="resource-kicker">{humanise(item.output_type || "teaching output")} · Version {item.version_number}</span>
          <strong>{item.label || item.output_title || "Saved teaching output"}</strong>
          {item.content_preview && <p>{item.content_preview}</p>}
          {!!item.tags.length && <div className="tag-row">{item.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>}
          <div className="resource-actions"><button type="button" onClick={onReturnToConversation}>Open conversations</button><button type="button" className="danger-text" onClick={() => void remove(item.id)}>Remove</button></div>
        </article>)}
      </div>
    </section>
  );
}

function SourcesPanel({ onReturnToConversation }: Props) {
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/api/v1/library/documents?limit=40")
      .then(async (r) => {
        const d = await r.json();
        setItems(Array.isArray(d.items) ? d.items : []);
      })
      .catch(() => setError("Could not load sources."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="resource-panel">
      <div className="resource-panel-header">
        <div>
          <h2>Sources</h2>
          <p>Authorised knowledge retrieved and cited during your AI conversations. Sources are drawn from institutional documents and verified academic literature.</p>
        </div>
        <div className="resource-header-actions">
          <button type="button" className="secondary-compact-button" onClick={onReturnToConversation}>← Back to conversation</button>
        </div>
      </div>
      {error && <p className="resource-error">{error}</p>}
      {loading ? (
        <div className="resource-card-grid">{[...Array(4)].map((_, i) => <div key={i} className="resource-card skeleton-card"><i /><i /><i /></div>)}</div>
      ) : items.length === 0 ? (
        <div className="resource-empty"><div>⬡</div><strong>No sources yet</strong><p>Sources appear here after the AI retrieves and cites documents during a conversation.</p></div>
      ) : (
        <div className="resource-card-grid">
          {items.map((it) => (
            <article key={it.document_id} className="resource-card">
              <span className="resource-kicker">{it.document_type || "document"}</span>
              <strong>{it.title || it.original_filename}</strong>
              <p>{it.original_filename}</p>
              <small>{it.updated_at ? new Date(it.updated_at).toLocaleDateString() : ""}</small>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function NotificationsPanel({ onUnreadCountChange, onOpenRoleAction, onReturnToConversation }: Props) {
  const [items, setItems] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { void load(); }, []);
  async function load() {
    setLoading(true); const response = await apiFetch("workspace/notifications");
    if (!response.ok) { setError(await responseMessage(response)); setLoading(false); return; }
    const data = await response.json(); setItems(data.items || []); setUnread(data.unread_count || 0); onUnreadCountChange(data.unread_count || 0); setLoading(false);
  }
  async function mark(item: Notification) {
    const response = await apiFetch(`workspace/notifications/${item.id}`, { method: "PATCH", body: JSON.stringify({ read: !item.read_at }) });
    if (response.ok) void load(); else setError(await responseMessage(response));
  }
  async function readAll() {
    const response = await apiFetch("workspace/notifications/read-all", { method: "POST" });
    if (response.ok) void load(); else setError(await responseMessage(response));
  }
  function activate(path?: string | null) {
    if (!path) return;
    if (path.startsWith("action:")) onOpenRoleAction(path.split(":")[1]);
    else onReturnToConversation();
  }
  return (
    <section className="resource-panel">
      <PanelHeader eyebrow="What needs your attention" title="Notifications" description="Assignments, reviews, deadlines, readiness risks, exports, and access changes addressed to your account." actions={unread > 0 ? <button type="button" className="secondary-compact-button" onClick={() => void readAll()}>Mark all read</button> : undefined} />
      {loading && <ResourceSkeleton count={5} />}{error && <div className="resource-error">{error}</div>}
      {!loading && !error && items.length === 0 && <EmptyState title="You are all caught up" body="New teaching, review, and departmental actions will appear here." />}
      <div className="notification-list">
        {items.map((item) => <article className={item.read_at ? "notification-card read" : "notification-card unread"} key={item.id}>
          <button type="button" className="notification-main" onClick={() => activate(item.action_path)}>
            <span className={`notification-severity ${item.severity}`} /><div><span className="resource-kicker">{humanise(item.notification_type)}</span><strong>{item.title}</strong><p>{item.body}</p><small>{formatDate(item.created_at)}</small></div><span className="resource-arrow">→</span>
          </button><button type="button" className="notification-read-toggle" onClick={() => void mark(item)}>{item.read_at ? "Mark unread" : "Mark read"}</button>
        </article>)}
      </div>
    </section>
  );
}

function ResourceSkeleton({ count }: { count: number }) { return <div className="resource-card-grid">{Array.from({ length: count }, (_, index) => <div className="resource-card skeleton-card" key={index}><i /><i /><i /></div>)}</div>; }
function EmptyState({ title, body }: { title: string; body: string }) { return <div className="resource-empty"><div>✦</div><strong>{title}</strong><p>{body}</p></div>; }
function humanise(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }
function formatDate(value: string) { return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
function iconForKind(kind: string) { if (kind === "conversation") return "◌"; if (kind === "output") return "✦"; if (kind === "review_task") return "✓"; return "▤"; }
