"use client";

import { FormEvent, KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, responseMessage } from "@/lib/api-client";
import { WorkspaceResourcePanel, type WorkspaceView } from "@/components/workspace-resource-panels";

type ConversationSummary = {
  id: string;
  title: string;
  updated_at: string;
  is_archived: boolean;
};

type SourceCard = {
  number: number;
  source_key: string;
  title: string;
  authors: string[];
  publisher_or_organisation?: string | null;
  publication_date?: string | null;
  url?: string | null;
  doi?: string | null;
  verified_retrieval: boolean;
  cited_in_response: boolean;
  source_kind?: string;
  institutional?: boolean;
  document_version_id?: string | null;
  locator?: string | null;
  access_label?: string | null;
};

type ChatItem = {
  id: string;
  role: "user" | "assistant";
  content: string;
  outputType?: string;
  outputTitle?: string;
  sources?: SourceCard[];
  provider?: string;
  model?: string;
  warnings?: string[];
  requiresHumanReview?: boolean;
  approvalDisclaimer?: string | null;
  generatedOutputId?: string;
  outputVersionId?: string;
  versionNumber?: number;
  workflowStatus?: string;
  riskLevel?: string;
  safetyStatus?: string;
  pendingConfirmation?: {
    action: string;
    label: string;
    details: Record<string, string>;
    confirmToken: string;
  } | null;
};

type PendingAttachment = {
  versionId: string;
  filename: string;
  status: string;
};

type ConversationDetail = {
  conversation: ConversationSummary;
  messages: Array<{
    id: string;
    role: "user" | "assistant";
    content_text: string;
    content_blocks: Array<Record<string, unknown>>;
  }>;
};

const roleLabels: Record<string, string> = {
  institution_administrator: "Institution Administrator",
  head_of_department: "Head of Department",
  lecturer: "Lecturer",
  module_coordinator: "Module Coordinator",
  programme_coordinator: "Programme Coordinator",
  internal_moderator: "Internal Moderator",
  external_moderator: "External Moderator",
  external_reviewer: "External Reviewer",
};

const PROMPT_SUGGESTIONS: Record<string, string[]> = {
  institution_administrator: [
    "Show me the institution structure and active departments",
    "List all users and their roles",
    "What is the current status of knowledge ingestion?",
    "Show outstanding moderation cycles",
  ],
  head_of_department: [
    "Show the workload of all lecturers in my department",
    "Which modules have no lecturer assigned this semester?",
    "Show outstanding moderation in my department",
    "Assign a lecturer to a module",
  ],
  module_coordinator: [
    "What is the readiness status of my assigned modules?",
    "Show assessment alignment for my modules",
    "Generate a 12-week teaching plan for my module",
    "Show moderation status for my modules",
  ],
  programme_coordinator: [
    "Show programme outcome coverage across all modules",
    "Which modules have assessment gaps in my programme?",
    "Show the workload distribution across my programme",
    "Generate a programme readiness summary",
  ],
  lecturer: [
    "Create a lesson plan for next week's lecture on relational databases",
    "Generate a quiz on data structures with 10 questions",
    "Draft a rubric for a programming assignment",
    "Prepare a handover summary for my module",
  ],
  internal_moderator: [
    "Show my assigned moderation tasks",
    "What are the outstanding findings for my current review?",
    "Help me write a moderation report for Test 2",
    "Submit my review findings",
  ],
  external_moderator: [
    "Show my assigned external moderation tasks",
    "What materials are included in my review pack?",
    "Record a finding for the assessment I am reviewing",
    "Submit my moderation recommendation",
  ],
  external_reviewer: [
    "Show my assigned review tasks",
    "What is the scope of my external review?",
    "Record an observation about the assessment quality",
    "Submit my review",
  ],
};

export function WorkspaceShell({ activeRole }: { activeRole: string }) {
  const router = useRouter();
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);

  const [notice, setNotice] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatItem[]>([]);
  const [composerText, setComposerText] = useState("");
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [sending, setSending] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [streamingStatus, setStreamingStatus] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeView, setActiveView] = useState<WorkspaceView>("conversation");
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [uploadingFiles, setUploadingFiles] = useState(false);
  const [renamingConvId, setRenamingConvId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState("");
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editMessageText, setEditMessageText] = useState("");

  useEffect(() => {
    void loadConversations();
    void loadWorkspaceNavigation();
    const storedTheme = window.localStorage.getItem("lsa-theme") === "dark" ? "dark" : "light";
    setTheme(storedTheme);
    document.documentElement.dataset.theme = storedTheme;
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  useEffect(() => {
    function handleShortcut(event: globalThis.KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setActiveView("search");
        setSidebarOpen(false);
      }
    }
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  async function loadWorkspaceNavigation() {
    const response = await apiFetch("workspace/navigation");
    if (!response.ok) return;
    const data = await response.json();
    const notifications = (data.items || []).find((item: { key: string }) => item.key === "notifications");
    setUnreadNotifications(Number(notifications?.badge_count || 0));
  }

  function changeView(view: WorkspaceView) {
    setActiveView(view);
    setSidebarOpen(false);
    setNotice(null);
  }

  function toggleTheme() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    window.localStorage.setItem("lsa-theme", next);
  }

  async function loadConversations() {
    const response = await apiFetch("conversations?limit=50");
    if (!response.ok) return;
    const data = (await response.json()) as ConversationSummary[];
    setConversations(data.filter((c) => !c.is_archived));
  }

  async function openConversation(id: string) {
    setActiveView("conversation");
    setLoadingConversation(true);
    setActiveConversationId(id);
    setSidebarOpen(false);
    setEditingMessageId(null);
    const response = await apiFetch(`conversations/${id}`);
    if (!response.ok) {
      setNotice(await responseMessage(response));
      setLoadingConversation(false);
      return;
    }
    const data = (await response.json()) as ConversationDetail;
    setMessages(
      data.messages.map((message) => {
        const block = message.content_blocks?.[0] ?? {};
        return {
          id: message.id,
          role: message.role,
          content: message.content_text,
          outputType: message.role === "assistant" ? String(block.output_type ?? "generic_answer") : undefined,
          outputTitle: message.role === "assistant" ? String(block.title ?? "") : undefined,
          generatedOutputId: typeof block.generated_output_id === "string" ? block.generated_output_id : undefined,
          outputVersionId: typeof block.output_version_id === "string" ? block.output_version_id : undefined,
          versionNumber: typeof block.version_number === "number" ? block.version_number : undefined,
          workflowStatus: typeof block.workflow_status === "string" ? block.workflow_status : undefined,
          riskLevel: typeof block.risk_level === "string" ? block.risk_level : undefined,
          safetyStatus: typeof block.safety_status === "string" ? block.safety_status : undefined,
          requiresHumanReview: Boolean(block.requires_human_review),
          approvalDisclaimer: typeof block.approval_disclaimer === "string" ? block.approval_disclaimer : undefined,
        } as ChatItem;
      }),
    );
    setLoadingConversation(false);
  }

  function startNewConversation() {
    setActiveView("conversation");
    setActiveConversationId(null);
    setMessages([]);
    setComposerText("");
    setNotice(null);
    setPendingAttachments([]);
    setSidebarOpen(false);
    setEditingMessageId(null);
    setTimeout(() => composerRef.current?.focus(), 50);
  }

  async function ensureConversation(): Promise<string | null> {
    if (activeConversationId) return activeConversationId;
    const response = await apiFetch("conversations", {
      method: "POST",
      body: JSON.stringify({ title: null, context: {} }),
    });
    if (!response.ok) {
      setNotice(await responseMessage(response));
      return null;
    }
    const conversation = (await response.json()) as ConversationSummary;
    setActiveConversationId(conversation.id);
    setConversations((current) => [conversation, ...current]);
    return conversation.id;
  }

  function stopGeneration() {
    abortRef.current?.abort();
    abortRef.current = null;
    setSending(false);
    setStreamingText("");
    setStreamingStatus("");
  }

  async function streamRequest(conversationId: string, content: string, attachmentVersionIds: string[], optimisticId: string, originalContent: string) {
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const response = await fetch(`/api/backend/conversations/${conversationId}/messages/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, attachment_version_ids: attachmentVersionIds }),
        signal: ctrl.signal,
      });

      if (!response.ok || !response.body) {
        setMessages((current) => current.filter((item) => item.id !== optimisticId));
        setComposerText(originalContent);
        setNotice("The request could not be completed. Please try again.");
        setSending(false);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let accText = "";
      let doneData: Record<string, unknown> | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6)) as Record<string, unknown>;
            if (event.type === "thinking") {
              setStreamingStatus(String(event.status ?? "Working…"));
            } else if (event.type === "token") {
              accText += String(event.text ?? "");
              setStreamingText(accText);
            } else if (event.type === "done") {
              doneData = event;
            } else if (event.type === "error") {
              setNotice(String(event.detail ?? "An error occurred."));
              setMessages((current) => current.filter((item) => item.id !== optimisticId));
              setComposerText(originalContent);
              setSending(false);
              setStreamingText("");
              setStreamingStatus("");
              return;
            }
          } catch {}
        }
      }

      setStreamingText("");
      setStreamingStatus("");

      if (doneData) {
        const d = doneData;
        // Build pendingConfirmation from server-side pending_action_token
        let pendingConf: ChatItem["pendingConfirmation"] = null;
        if (d.pending_action_token) {
          const details: Record<string, string> = {};
          if (Array.isArray(d.pending_action_details)) {
            for (const row of d.pending_action_details as Array<{key: string; value: string}>) {
              details[row.key] = row.value;
            }
          }
          pendingConf = {
            action: String(d.pending_action_label ?? ""),
            label: String(d.pending_action_label ?? "Confirm action"),
            details,
            confirmToken: String(d.pending_action_token),
          };
        }
        const assistantMsg: ChatItem = {
          id: String(d.assistant_message_id ?? `assist-${Date.now()}`),
          role: "assistant",
          content: accText,
          outputType: String(d.output_type ?? "generic_answer"),
          outputTitle: String(d.title ?? ""),
          sources: (d.sources as ChatItem["sources"]) ?? [],
          warnings: (d.integrity_warnings as string[]) ?? [],
          requiresHumanReview: Boolean(d.requires_human_review),
          approvalDisclaimer: d.approval_disclaimer as string | null,
          generatedOutputId: d.generated_output_id ? String(d.generated_output_id) : undefined,
          outputVersionId: d.output_version_id ? String(d.output_version_id) : undefined,
          versionNumber: d.version_number ? Number(d.version_number) : undefined,
          workflowStatus: String(d.workflow_status ?? "draft"),
          riskLevel: String(d.risk_level ?? "none"),
          safetyStatus: String(d.safety_status ?? "passed"),
          pendingConfirmation: pendingConf,
        };
        setMessages((current) => [
          ...current.map((item) => item.id === optimisticId ? { ...item, id: String(d.user_message_id ?? optimisticId) } : item),
          assistantMsg,
        ]);
        const convTitle = String(d.conversation_title ?? "");
        const convId = String(d.conversation_id ?? conversationId);
        setConversations((current) => {
          const nowStr = new Date().toISOString();
          const updated = current.map((c) => c.id === convId ? { ...c, title: convTitle, updated_at: nowStr } : c);
          if (!updated.some((c) => c.id === convId)) {
            updated.unshift({ id: convId, title: convTitle, updated_at: nowStr, is_archived: false });
          }
          return [...updated].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
        });
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setNotice("Connection interrupted. Please try again.");
        setMessages((current) => current.filter((item) => item.id !== optimisticId));
        setComposerText(originalContent);
      }
    } finally {
      abortRef.current = null;
      setSending(false);
      setStreamingText("");
      setStreamingStatus("");
    }
  }

  async function sendMessage() {
    const content = composerText.trim();
    if (!content || sending) return;
    setSending(true);
    setStreamingText("");
    setStreamingStatus("");
    setNotice(null);
    const conversationId = await ensureConversation();
    if (!conversationId) { setSending(false); return; }
    const optimisticId = `local-${Date.now()}`;
    setMessages((current) => [...current, { id: optimisticId, role: "user", content }]);
    setComposerText("");
    const attachmentsForRequest = pendingAttachments;
    setPendingAttachments([]);
    await streamRequest(conversationId, content, attachmentsForRequest.map((a) => a.versionId), optimisticId, content);
  }

  async function retryLastMessage() {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser || sending || !activeConversationId) return;
    setMessages((current) => {
      const idx = current.findLastIndex((m) => m.role === "assistant");
      return idx >= 0 ? current.slice(0, idx) : current;
    });
    setSending(true);
    setStreamingText("");
    setStreamingStatus("");
    setNotice(null);
    const optimisticId = `local-retry-${Date.now()}`;
    await streamRequest(activeConversationId, lastUser.content, [], optimisticId, lastUser.content);
  }

  async function sendEditedMessage(messageId: string, newContent: string) {
    if (!activeConversationId || sending) return;
    const idx = messages.findIndex((m) => m.id === messageId);
    if (idx < 0) return;
    setEditingMessageId(null);
    setMessages((current) => current.slice(0, idx));
    setSending(true);
    setStreamingText("");
    setStreamingStatus("");
    const optimisticId = `local-edit-${Date.now()}`;
    setMessages((current) => [...current, { id: optimisticId, role: "user", content: newContent }]);
    await streamRequest(activeConversationId, newContent, [], optimisticId, newContent);
  }

  async function confirmAction(confirmToken: string, label: string) {
    if (!activeConversationId || sending) return;
    setSending(true);
    setStreamingText("");
    setStreamingStatus("");
    setNotice(null);
    const optimisticId = `local-confirm-${Date.now()}`;
    setMessages((current) => [...current, { id: optimisticId, role: "user", content: `Confirm: ${label}` }]);
    // Clear the confirmation card from the preceding message
    setMessages((current) => current.map((m) => m.pendingConfirmation?.confirmToken === confirmToken ? { ...m, pendingConfirmation: null } : m));
    await streamRequest(activeConversationId, `__confirm__${confirmToken}`, [], optimisticId, `Confirm: ${label}`);
  }

  async function cancelAction(confirmToken: string) {
    if (!activeConversationId || sending) return;
    setSending(true);
    setStreamingText("");
    setStreamingStatus("");
    setNotice(null);
    const optimisticId = `local-cancel-${Date.now()}`;
    setMessages((current) => [
      ...current.map((m) => m.pendingConfirmation?.confirmToken === confirmToken ? { ...m, pendingConfirmation: null } : m),
      { id: optimisticId, role: "user", content: "Cancel" },
    ]);
    await streamRequest(activeConversationId, `__cancel__${confirmToken}`, [], optimisticId, "Cancel");
  }

  async function handleFileAttach(files: FileList) {
    if (!files.length || uploadingFiles) return;
    setUploadingFiles(true);
    setNotice("Uploading and scanning…");
    const form = new FormData();
    const metadataFiles = Array.from(files).map((file, index) => ({
      client_item_key: `web-${Date.now()}-${index}`,
      title: file.name.replace(/\.[^.]+$/, "").replaceAll("_", " "),
      document_type: "teaching_material",
      change_reason: "Attached via conversation composer",
      metadata: { uploaded_from: "conversation_composer" },
    }));
    for (const file of Array.from(files)) form.append("files", file);
    form.append("metadata_json", JSON.stringify({
      scope_type: "institution",
      scope_id: null,
      change_reason: "Conversation attachment",
      visibility: "private",
      auto_process: true,
      expand_archives: false,
      files: metadataFiles,
    }));
    const response = await apiFetch("bulk-uploads", { method: "POST", body: form });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      setNotice(await responseMessage(response));
      setUploadingFiles(false);
      return;
    }
    const attached: PendingAttachment[] = (data.items || [])
      .filter((item: { document_version_id?: string }) => item.document_version_id)
      .map((item: { document_version_id: string; original_filename: string; status: string }) => ({
        versionId: item.document_version_id,
        filename: item.original_filename,
        status: item.status,
      }));
    setPendingAttachments((current) => {
      const merged = [...current];
      for (const a of attached) if (!merged.some((e) => e.versionId === a.versionId)) merged.push(a);
      return merged;
    });
    setNotice(attached.length ? `${attached.length} file(s) attached. ${data.batch?.failed_item_count > 0 ? `${data.batch.failed_item_count} failed.` : ""}` : "Upload failed or files were not processed.");
    setUploadingFiles(false);
  }

  async function renameConversation(id: string, newTitle: string) {
    if (!newTitle.trim()) return;
    const response = await apiFetch(`conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title: newTitle.trim() }),
    });
    if (response.ok) {
      setConversations((current) => current.map((c) => c.id === id ? { ...c, title: newTitle.trim() } : c));
    }
    setRenamingConvId(null);
  }

  async function archiveConversation(id: string) {
    const response = await apiFetch(`conversations/${id}`, { method: "DELETE" });
    if (response.ok) {
      setConversations((current) => current.filter((c) => c.id !== id));
      if (activeConversationId === id) startNewConversation();
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  }

  async function signOut() {
    await fetch("/api/session/logout", { method: "POST" });
    router.replace("/sign-in");
    router.refresh();
  }

  const activeTitle = conversations.find((item) => item.id === activeConversationId)?.title;
  const viewTitles: Record<WorkspaceView, string> = {
    conversation: activeTitle || "Lecturer Support Agent",
    search: "Search",
    library: "Library",
    files: "Files",
    saved: "Saved outputs",
    notifications: "Notifications",
    insights: "Insights",
    reports: "Reports",
    audit: "Audit centre",
    settings: "Platform settings",
    operations: "Platform operations",
  };

  const suggestions = PROMPT_SUGGESTIONS[activeRole] ?? PROMPT_SUGGESTIONS["lecturer"];

  return (
    <main id="main-content" className="workspace-grid">
      <button
        className="mobile-sidebar-toggle"
        type="button"
        aria-label="Open navigation"
        onClick={() => setSidebarOpen((v) => !v)}
      >
        ☰
      </button>
      <aside className={`sidebar ${sidebarOpen ? "mobile-open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark" aria-label="Lecturer Support Agent">LS</div>
          <div><strong>Lecturer Support</strong><span>AI assistant</span></div>
        </div>
        <button className="primary-nav-button" type="button" onClick={startNewConversation}>＋ New conversation</button>
        <div className="sidebar-section-label">Recent conversations</div>
        <nav aria-label="Recent conversations" className="conversation-nav">
          {conversations.length === 0 && <span className="sidebar-empty">No conversations yet.</span>}
          {conversations.map((conv) => (
            <div key={conv.id} className="conv-nav-row">
              {renamingConvId === conv.id ? (
                <form
                  className="conv-rename-form"
                  onSubmit={(e) => { e.preventDefault(); void renameConversation(conv.id, renameText); }}
                >
                  <input
                    autoFocus
                    value={renameText}
                    onChange={(e) => setRenameText(e.target.value)}
                    onBlur={() => void renameConversation(conv.id, renameText)}
                    onKeyDown={(e) => { if (e.key === "Escape") setRenamingConvId(null); }}
                    aria-label="Rename conversation"
                  />
                </form>
              ) : (
                <button
                  type="button"
                  className={conv.id === activeConversationId ? "conversation-nav-item active" : "conversation-nav-item"}
                  onClick={() => void openConversation(conv.id)}
                  title={conv.title}
                >
                  <span>{conv.title}</span>
                </button>
              )}
              {renamingConvId !== conv.id && (
                <div className="conv-actions">
                  <button
                    type="button"
                    aria-label="Rename"
                    title="Rename"
                    onClick={() => { setRenamingConvId(conv.id); setRenameText(conv.title); }}
                  >✎</button>
                  <button
                    type="button"
                    aria-label="Archive"
                    title="Archive"
                    onClick={() => void archiveConversation(conv.id)}
                  >⊗</button>
                </div>
              )}
            </div>
          ))}
        </nav>
        <nav aria-label="Workspace" className="nav-stack compact-nav">
          {[
            { key: "search" as const, icon: "⌕", label: "Search", shortcut: "Ctrl K" },
            { key: "library" as const, icon: "▣", label: "Library" },
            { key: "files" as const, icon: "↥", label: "Files" },
            { key: "saved" as const, icon: "☆", label: "Saved outputs" },
            { key: "notifications" as const, icon: "◉", label: "Notifications", badge: unreadNotifications },
            { key: "insights" as const, icon: "◒", label: "Insights" },
            ...( ["institution_administrator", "head_of_department", "module_coordinator", "programme_coordinator", "lecturer", "internal_moderator"].includes(activeRole) ? [{ key: "reports" as const, icon: "▤", label: "Reports" }] : []),
            ...(activeRole === "institution_administrator" ? [{ key: "audit" as const, icon: "◇", label: "Audit centre" }, { key: "settings" as const, icon: "⚙", label: "Platform settings" }, { key: "operations" as const, icon: "◈", label: "Platform operations" }] : []),
          ].map((item) => (
            <button key={item.key} type="button" aria-label={item.label} title={item.label} className={activeView === item.key ? "nav-item active" : "nav-item"} onClick={() => changeView(item.key)}>
              <span aria-hidden="true">{item.icon}</span>
              <span aria-hidden="true">{item.label}</span>
              {item.shortcut && <kbd>{item.shortcut}</kbd>}
              {"badge" in item && !!item.badge && <b className="nav-badge">{(item.badge as number) > 99 ? "99+" : item.badge}</b>}
            </button>
          ))}
        </nav>
        <div className="role-card">
          <span className="eyebrow">Active role</span>
          <strong>{roleLabels[activeRole] ?? activeRole.replaceAll("_", " ")}</strong>
          <button type="button" className="link-button" onClick={signOut}>Sign out</button>
        </div>
      </aside>

      <section className="conversation-area">
        <header className="topbar">
          <div>
            <span className="eyebrow">Lecturer Support Agent</span>
            <h1>{viewTitles[activeView]}</h1>
          </div>
          <div className="topbar-actions">
            <button className="theme-button" type="button" onClick={toggleTheme} aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}>
              {theme === "light" ? "◐" : "☀"}
            </button>
          </div>
        </header>

        {activeView === "conversation" ? (
          <>
            <div className="message-scroll" ref={scrollRef} aria-live="polite">
              {loadingConversation ? (
                <div className="conversation-loading"><span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" /></div>
              ) : messages.length === 0 && !sending ? (
                <div className="conversation-empty">
                  <div className="orb" aria-hidden="true">✦</div>
                  <h2>What would you like to work on?</h2>
                  <p>
                    Ask me to prepare teaching material, create assessments, review academic work,
                    analyse workload, work with institutional knowledge, or help with your authorised
                    academic responsibilities.
                  </p>
                  <div className="suggestion-grid" aria-label="Example prompts">
                    {suggestions.map((s) => (
                      <button
                        key={s}
                        type="button"
                        className="suggestion-chip"
                        onClick={() => { setComposerText(s); composerRef.current?.focus(); }}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="message-list">
                  {messages.map((message, idx) => (
                    <MessageCard
                      key={message.id}
                      message={message}
                      activeRole={activeRole}
                      isLastAssistant={message.role === "assistant" && idx === messages.length - 1}
                      isEditing={editingMessageId === message.id}
                      editText={editMessageText}
                      onEditStart={() => { setEditingMessageId(message.id); setEditMessageText(message.content); }}
                      onEditChange={setEditMessageText}
                      onEditSend={() => void sendEditedMessage(message.id, editMessageText)}
                      onEditCancel={() => setEditingMessageId(null)}
                      onRetry={() => void retryLastMessage()}
                      onConfirm={(token, label) => void confirmAction(token, label)}
                      onCancel={(token) => void cancelAction(token)}
                    />
                  ))}
                  {sending && <AssistantStreaming text={streamingText} status={streamingStatus} />}
                </div>
              )}
              {notice && <div className="notice conversation-notice" role="status">{notice}</div>}
            </div>

            <div className="composer-wrap">
              <div className="composer" aria-label="Message composer">
                <textarea
                  ref={composerRef}
                  aria-label="Message"
                  placeholder="Message Lecturer Support Agent…"
                  rows={2}
                  value={composerText}
                  onChange={(e) => setComposerText(e.target.value)}
                  onKeyDown={handleComposerKeyDown}
                  disabled={sending}
                />
                {!!pendingAttachments.length && (
                  <div className="attachment-chip-row">
                    {pendingAttachments.map((item) => (
                      <button
                        key={item.versionId}
                        type="button"
                        className="attachment-chip"
                        onClick={() => setPendingAttachments((c) => c.filter((e) => e.versionId !== item.versionId))}
                      >
                        <span>▣</span>{item.filename}<b aria-label="Remove">×</b>
                      </button>
                    ))}
                  </div>
                )}
                <div className="composer-row">
                  <button
                    type="button"
                    className="icon-button"
                    title={uploadingFiles ? "Uploading…" : "Attach file"}
                    disabled={sending || uploadingFiles}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    {uploadingFiles ? "…" : "＋"}
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    aria-hidden="true"
                    style={{ display: "none" }}
                    onChange={(e) => { if (e.target.files) void handleFileAttach(e.target.files); e.target.value = ""; }}
                  />
                  <span className="composer-hint">Enter to send · Shift+Enter for new line</span>
                  {sending ? (
                    <button type="button" className="stop-button" onClick={stopGeneration} aria-label="Stop">◼ Stop</button>
                  ) : (
                    <button
                      type="button"
                      className="send-button"
                      disabled={!composerText.trim()}
                      onClick={() => void sendMessage()}
                    >Send</button>
                  )}
                </div>
              </div>
              <p className="ai-disclaimer">AI-generated content requires professional judgement. Cited sources indicate retrieval, not automatic institutional approval.</p>
            </div>
          </>
        ) : (
          <WorkspaceResourcePanel
            activeView={activeView}
            activeRole={activeRole}
            onOpenConversation={(id) => void openConversation(id)}
            onAttachVersion={(versionId, filename) => {
              setPendingAttachments((c) => c.some((e) => e.versionId === versionId) ? c : [...c, { versionId, filename, status: "attached" }]);
              setNotice(`${filename} attached to your next message.`);
              changeView("conversation");
            }}
            onReturnToConversation={() => changeView("conversation")}
            onOpenRoleAction={() => changeView("conversation")}
            onUnreadCountChange={setUnreadNotifications}
          />
        )}
      </section>
    </main>
  );
}

function MessageCard({
  message, activeRole, isLastAssistant, isEditing, editText,
  onEditStart, onEditChange, onEditSend, onEditCancel, onRetry, onConfirm, onCancel,
}: {
  message: ChatItem;
  activeRole: string;
  isLastAssistant: boolean;
  isEditing: boolean;
  editText: string;
  onEditStart: () => void;
  onEditChange: (text: string) => void;
  onEditSend: () => void;
  onEditCancel: () => void;
  onRetry: () => void;
  onConfirm: (token: string, label: string) => void;
  onCancel: (token: string) => void;
}) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [editingOutput, setEditingOutput] = useState(false);
  const [outputContent, setOutputContent] = useState(message.content);
  const [outputDraft, setOutputDraft] = useState(message.content);
  const [versionNumber, setVersionNumber] = useState(message.versionNumber || 1);
  const [workflowStatus, setWorkflowStatus] = useState(message.workflowStatus || "draft");
  const [safetyStatus, setSafetyStatus] = useState(message.safetyStatus || "passed");
  const [versions, setVersions] = useState<Array<{ id: string; version_number: number; change_reason: string; created_at: string }>>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  if (message.role === "user") {
    if (isEditing) {
      return (
        <article className="message-row user-message">
          <div className="user-edit-form">
            <textarea
              autoFocus
              value={editText}
              onChange={(e) => onEditChange(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onEditSend(); } if (e.key === "Escape") onEditCancel(); }}
              rows={3}
              aria-label="Edit message"
            />
            <div className="inline-action-row">
              <button type="button" onClick={onEditSend} className="submit-button" style={{ padding: "8px 14px", fontSize: "13px" }}>Resend</button>
              <button type="button" onClick={onEditCancel}>Cancel</button>
            </div>
          </div>
        </article>
      );
    }
    return (
      <article className="message-row user-message">
        <div className="user-message-wrap">
          <div className="message-bubble">{message.content}</div>
          <button type="button" className="msg-action-btn" title="Edit and resend" onClick={onEditStart} aria-label="Edit message">✎</button>
        </div>
      </article>
    );
  }

  async function saveOutputVersion() {
    if (!message.generatedOutputId || !outputDraft.trim()) return;
    setBusy(true); setActionNotice(null);
    const reason = window.prompt("Briefly describe this edit", "Lecturer edit");
    if (!reason) { setBusy(false); return; }
    const response = await apiFetch(`teaching-outputs/${message.generatedOutputId}/versions`, {
      method: "POST",
      body: JSON.stringify({ content_markdown: outputDraft, change_reason: reason }),
    });
    if (!response.ok) { setActionNotice(await responseMessage(response)); setBusy(false); return; }
    const data = await response.json();
    setOutputContent(data.current_version.content_text);
    setOutputDraft(data.current_version.content_text);
    setVersionNumber(data.current_version.version_number);
    setWorkflowStatus(data.lifecycle.workflow_status);
    setSafetyStatus(data.safety_review.status);
    setEditingOutput(false); setBusy(false);
    setActionNotice(`Saved as version ${data.current_version.version_number}.`);
  }

  async function loadVersionHistory() {
    if (!message.generatedOutputId) return;
    setHistoryOpen((v) => !v);
    if (versions.length) return;
    const r = await apiFetch(`teaching-outputs/${message.generatedOutputId}/versions`);
    if (r.ok) setVersions(await r.json());
  }

  async function restoreVersion(id: string, number: number) {
    if (!message.generatedOutputId) return;
    const r = await apiFetch(`teaching-outputs/${message.generatedOutputId}/versions/${id}/restore`, {
      method: "POST",
      body: JSON.stringify({ change_reason: `Restore version ${number}` }),
    });
    if (!r.ok) { setActionNotice(await responseMessage(r)); return; }
    const data = await r.json();
    setOutputContent(data.current_version.content_text); setOutputDraft(data.current_version.content_text);
    setVersionNumber(data.current_version.version_number); setWorkflowStatus(data.lifecycle.workflow_status);
    setSafetyStatus(data.safety_review.status); setVersions([]);
    setActionNotice(`Version ${number} restored as version ${data.current_version.version_number}.`);
  }

  async function exportOutput(format: string, audience: string) {
    if (!message.generatedOutputId) return;
    setBusy(true); setActionNotice(null);
    const r1 = await apiFetch(`teaching-outputs/${message.generatedOutputId}/exports`, {
      method: "POST", body: JSON.stringify({ export_format: format, audience }),
    });
    if (!r1.ok) { setActionNotice(await responseMessage(r1)); setBusy(false); return; }
    const job = await r1.json();
    const r2 = await apiFetch(`teaching-outputs/exports/${job.id}/download`);
    if (!r2.ok) { setActionNotice(await responseMessage(r2)); setBusy(false); return; }
    const blob = await r2.blob();
    const url = URL.createObjectURL(blob); const a = document.createElement("a");
    a.href = url; a.download = job.filename || `output.${format}`; a.click();
    URL.revokeObjectURL(url); setBusy(false);
    setActionNotice(`${job.filename} exported.`);
  }

  async function saveToWorkspace() {
    if (!message.generatedOutputId || !message.outputVersionId) return;
    setBusy(true); setActionNotice(null);
    const r = await apiFetch("workspace/saved-outputs", {
      method: "POST",
      body: JSON.stringify({ generated_output_id: message.generatedOutputId, output_version_id: message.outputVersionId, label: message.outputTitle || null, tags: [message.outputType || "teaching_output"], is_pinned: false }),
    });
    setActionNotice(r.ok ? `Saved to Saved outputs (version ${versionNumber}).` : await responseMessage(r));
    setBusy(false);
  }

  async function transition(action: string) {
    if (!message.generatedOutputId) return;
    const reason = window.prompt("Reason for this action", humanize(action));
    if (!reason) return;
    const r = await apiFetch(`teaching-outputs/${message.generatedOutputId}/workflow`, {
      method: "POST", body: JSON.stringify({ action, reason }),
    });
    if (!r.ok) { setActionNotice(await responseMessage(r)); return; }
    const data = await r.json(); setWorkflowStatus(data.new_status);
    setActionNotice(`Status: ${humanize(data.new_status)}.`);
  }

  function copyContent() {
    void navigator.clipboard.writeText(outputContent).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); });
  }

  const mayApprove = ["head_of_department", "module_coordinator", "programme_coordinator"].includes(activeRole);
  const hasConfirmation = !!message.pendingConfirmation;

  return (
    <article className="message-row assistant-message">
      <div className="assistant-avatar" aria-hidden="true">✦</div>
      <div className="assistant-content">
        {message.outputType && message.outputType !== "generic_answer" && (
          <div className="response-meta">
            <span className="output-badge">{humanize(message.outputType)}</span>
            {versionNumber > 0 && <span className="version-pill">v{versionNumber}</span>}
            <span className={`workflow-pill ${workflowStatus}`}>{humanize(workflowStatus)}</span>
            {message.riskLevel && message.riskLevel !== "none" && <span className="risk-pill">{humanize(message.riskLevel)} risk</span>}
          </div>
        )}

        {editingOutput ? (
          <div className="inline-output-editor">
            <textarea value={outputDraft} onChange={(e) => setOutputDraft(e.target.value)} rows={20} aria-label="Edit output" />
            <div className="inline-action-row">
              <button disabled={busy} onClick={() => void saveOutputVersion()} type="button" className="submit-button" style={{ padding: "8px 14px", fontSize: "13px" }}>Save version</button>
              <button type="button" onClick={() => { setOutputDraft(outputContent); setEditingOutput(false); }}>Cancel</button>
            </div>
          </div>
        ) : (
          <MarkdownView content={outputContent} />
        )}

        {hasConfirmation && message.pendingConfirmation && (
          <div className="confirmation-card">
            <strong>{message.pendingConfirmation.label}</strong>
            <div className="confirmation-details">
              {Object.entries(message.pendingConfirmation.details).map(([k, v]) => (
                <div key={k}><span>{k}</span><b>{v}</b></div>
              ))}
            </div>
            <div className="inline-action-row">
              <button
                type="button"
                className="submit-button"
                style={{ padding: "10px 18px" }}
                onClick={() => onConfirm(message.pendingConfirmation!.confirmToken, message.pendingConfirmation!.label)}
              >Confirm</button>
              <button type="button" className="secondary-button" style={{ padding: "10px 18px" }}
                onClick={() => onCancel(message.pendingConfirmation!.confirmToken)}>Cancel</button>
            </div>
          </div>
        )}

        <div className="msg-action-bar">
          <button type="button" onClick={copyContent} className="msg-action-btn" title={copied ? "Copied!" : "Copy"} aria-label="Copy response">
            {copied ? "✓" : "⎘"}
          </button>
          {isLastAssistant && (
            <button type="button" onClick={onRetry} className="msg-action-btn" title="Regenerate response" aria-label="Regenerate">↻</button>
          )}
        </div>

        {message.generatedOutputId && !editingOutput && (
          <div className="output-action-bar">
            <button type="button" onClick={() => setEditingOutput(true)}>Edit</button>
            <button type="button" onClick={() => void loadVersionHistory()}>History</button>
            <button type="button" disabled={busy} onClick={() => void saveToWorkspace()}>Save</button>
            {workflowStatus === "draft" && <button type="button" onClick={() => void transition("submit_for_review")}>Submit for review</button>}
            {mayApprove && workflowStatus === "under_review" && <button type="button" onClick={() => void transition("approve")}>Approve</button>}
            {mayApprove && workflowStatus === "approved" && <button type="button" onClick={() => void transition("release")}>Release</button>}
            <details className="export-menu">
              <summary>Export</summary>
              <div>
                <button onClick={() => void exportOutput("docx", "lecturer_pack")} type="button">DOCX</button>
                <button onClick={() => void exportOutput("pdf", "lecturer_pack")} type="button">PDF</button>
                <button onClick={() => void exportOutput("pptx", "generic")} type="button">PowerPoint</button>
                <button onClick={() => void exportOutput("docx", "student_copy")} type="button">Student copy</button>
              </div>
            </details>
          </div>
        )}

        {historyOpen && (
          <div className="version-history">
            <strong>Version history</strong>
            {versions.map((v) => (
              <div key={v.id}>
                <span>v{v.version_number}</span>
                <small>{v.change_reason}</small>
                {v.version_number !== versionNumber && (
                  <button type="button" onClick={() => void restoreVersion(v.id, v.version_number)}>Restore</button>
                )}
              </div>
            ))}
          </div>
        )}

        {message.requiresHumanReview && message.approvalDisclaimer && (
          <div className="review-note">
            <strong>Human review required · {humanize(safetyStatus)}</strong>
            <span>{message.approvalDisclaimer}</span>
          </div>
        )}
        {actionNotice && <div className="output-action-notice">{actionNotice}</div>}
        {message.warnings?.map((w) => <div className="integrity-warning" key={w}>{w}</div>)}

        {!!message.sources?.length && (
          <div className="source-section">
            <button className="source-toggle" type="button" onClick={() => setSourcesOpen((v) => !v)}>
              <span className="source-stack" aria-hidden="true"><i /><i /><i /></span>
              Sources · {message.sources.length}
              <span>{sourcesOpen ? "Hide" : "View"}</span>
            </button>
            {sourcesOpen && (
              <div className="source-grid">
                {message.sources.map((source) => <SourceItem key={source.source_key} source={source} />)}
              </div>
            )}
          </div>
        )}
      </div>
    </article>
  );
}

function SourceItem({ source }: { source: SourceCard }) {
  const authors = source.authors.length ? source.authors.slice(0, 3).join(", ") : "Author not listed";
  const card = (
    <>
      <span className="source-number">{source.number}</span>
      <div>
        <strong>{source.title}</strong>
        <p>{authors}{source.publication_date ? ` · ${source.publication_date}` : ""}</p>
        <small>{source.locator ? `${source.locator} · ` : ""}{source.publisher_or_organisation || source.doi || "Retrieved source"}</small>
      </div>
      <span className={source.cited_in_response ? "verification-pill cited" : "verification-pill"}>
        {source.institutional ? "Institutional" : source.cited_in_response ? "Cited" : "Retrieved"}
      </span>
    </>
  );
  return source.url
    ? <a className="source-item" href={source.url} target="_blank" rel="noreferrer">{card}</a>
    : <div className="source-item">{card}</div>;
}

function MarkdownView({ content }: { content: string }) {
  const lines = content.split("\n");
  return (
    <div className="markdown-view">
      {lines.map((line, index) => {
        const key = `${index}-${line.slice(0, 20)}`;
        if (line.startsWith("### ")) return <h4 key={key}>{line.slice(4)}</h4>;
        if (line.startsWith("## ")) return <h3 key={key}>{line.slice(3)}</h3>;
        if (line.startsWith("# ")) return <h2 key={key}>{line.slice(2)}</h2>;
        if (line.startsWith("> ")) return <blockquote key={key}>{renderInline(line.slice(2))}</blockquote>;
        if (/^[-*] /.test(line)) return <div className="markdown-list-item" key={key}><span>•</span><p>{renderInline(line.slice(2))}</p></div>;
        if (/^\d+\. /.test(line)) {
          const match = line.match(/^(\d+)\. (.*)$/);
          return <div className="markdown-list-item" key={key}><span>{match?.[1]}.</span><p>{renderInline(match?.[2] || "")}</p></div>;
        }
        if (!line.trim()) return <div className="markdown-spacer" key={key} />;
        return <p key={key}>{renderInline(line)}</p>;
      })}
    </div>
  );
}

function renderInline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|\[S\d+\])/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>;
    if (/^\[S\d+\]$/.test(part)) return <sup className="citation-marker" key={`${part}-${index}`}>{part}</sup>;
    return part;
  });
}

function AssistantStreaming({ text, status }: { text: string; status: string }) {
  return (
    <article className="message-row assistant-message" aria-live="polite">
      <div className="assistant-avatar" aria-hidden="true">✦</div>
      <div className="assistant-content">
        {text ? (
          <>
            <MarkdownView content={text} />
            <span className="streaming-cursor" aria-hidden="true" />
          </>
        ) : (
          <div className="assistant-thinking">
            <span /><span /><span />
            <p>{status || "Working on your request…"}</p>
          </div>
        )}
      </div>
    </article>
  );
}

function humanize(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (l) => l.toUpperCase());
}
