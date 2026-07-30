"use client";

import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, responseMessage } from "@/lib/api-client";
import { WorkspaceResourcePanel, type WorkspaceView } from "@/components/workspace-resource-panels";

type ActionKey = "feedback" | "invite" | "structure" | "assignLecturer" | "departmentOverview" | "bulkUpload" | "reviewCycle" | "reviewTasks" | "reviewDashboard" | "reviewDecision" | "reviewFollowUp" | "operationsDashboard" | "teachingPlan" | "moduleReadiness" | "workload" | "academicCalendar" | "handover";



type ReviewTaskSummary = {
  id: string;
  review_cycle_id?: string | null;
  reviewer_role_code?: string | null;
  review_kind?: string | null;
  round_number: number;
  target_id: string;
  status: string;
  due_at?: string | null;
  instructions?: string | null;
};

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
  moduleContext?: Record<string, unknown>;
};

type ModuleContext = {
  module_id: string;
  module_offering_id: string;
  module_code: string;
  module_name: string;
  offering_code: string;
  academic_period: string;
  qualification_level?: string | null;
  delivery_mode?: string | null;
  learning_outcomes: Array<{ code: string; statement: string }>;
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

type UnifiedAIResponse = {
  conversation: ConversationSummary;
  user_message: { id: string; role: "user"; content_text: string };
  assistant_message: { id: string; role: "assistant"; content_text: string };
  classification: { task_type: string; human_review_required: boolean };
  output: {
    output_type: string;
    title: string;
    markdown: string;
    requires_human_review: boolean;
    approval_disclaimer?: string | null;
    metadata?: {
      generated_output_id?: string;
      output_version_id?: string;
      version_number?: number;
      workflow_status?: string;
      risk_level?: string;
      safety_status?: string;
      module_context?: Record<string, unknown>;
    };
  };
  sources: SourceCard[];
  integrity_warnings: string[];
  provider: string;
  model: string;
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

function availableActions(role: string): { key: ActionKey; label: string; description: string }[] {
  const common = [
    { key: "feedback" as const, label: "Send feedback", description: "Rate an output or workflow and report quality, safety, or usability issues." },
    {
      key: "bulkUpload" as const,
      label: "Bulk upload",
      description: "Add authorised materials as immutable versions without replacing previous uploads.",
    },
  ];
  if (role === "institution_administrator") {
    return [
      { key: "invite", label: "Invite user", description: "Create a scoped institution invitation and independent role assignment." },
      { key: "structure", label: "Institution structure", description: "Add configurable faculties, schools, departments, centres, or other units." },
      { key: "academicCalendar", label: "Academic calendar", description: "Configure institution-wide academic dates without inheriting Head of Department authority." },
      ...common,
    ];
  }
  if (role === "head_of_department") {
    return [
      { key: "assignLecturer", label: "Assign lecturer", description: "Assign or reassign a lecturer to a module offering while preserving history." },
      { key: "departmentOverview", label: "Department overview", description: "Review active offerings, assignments, moderation, and workload." },
      { key: "operationsDashboard", label: "Teaching operations", description: "Track teaching plans, session delivery, readiness, workload pressure, handovers, and deadlines." },
      { key: "teachingPlan", label: "Teaching plans", description: "Create versioned module teaching plans and monitor delivery sessions." },
      { key: "moduleReadiness", label: "Module readiness", description: "Create readiness requirements, attach evidence, and surface blockers." },
      { key: "workload", label: "Workload", description: "Allocate scoped workload activities and review utilisation." },
      { key: "academicCalendar", label: "Academic calendar", description: "Create teaching, assessment, moderation, and departmental milestones." },
      { key: "handover", label: "Lecturer handover", description: "Create and track immutable lecturer continuity packages." },
      { key: "reviewCycle", label: "Create review cycle", description: "Assign an exact output version and sealed review pack to internal or external reviewers." },
      { key: "reviewDashboard", label: "Review oversight", description: "Track due cycles, assigned tasks, submissions, and blocking findings in the department." },
      { key: "reviewDecision", label: "Record review decision", description: "Consider submitted reviewer evidence and record the authorised academic decision." },
      { key: "reviewFollowUp", label: "Review follow-up", description: "Respond to findings or resubmit a corrected immutable output version." },
      ...common,
    ];
  }
  if (["module_coordinator", "programme_coordinator"].includes(role)) {
    return [
      { key: "operationsDashboard", label: "Teaching operations", description: "Review scoped plans, readiness, workload, handovers, and deadlines." },
      { key: "teachingPlan", label: "Teaching plans", description: "Create and monitor versioned plans and delivery sessions." },
      { key: "moduleReadiness", label: "Module readiness", description: "Manage readiness evidence and blockers within scope." },
      { key: "workload", label: "Workload", description: "Review and allocate scoped teaching workload." },
      { key: "academicCalendar", label: "Academic calendar", description: "Manage academic milestones within scope." },
      { key: "handover", label: "Lecturer handover", description: "Oversee module continuity and handover packages." },
      { key: "reviewCycle", label: "Create review cycle", description: "Assign scoped moderation or external review without granting broader access." },
      { key: "reviewDecision", label: "Record review decision", description: "Record an authorised decision after all reviewer submissions are available." },
      { key: "reviewFollowUp", label: "Review follow-up", description: "Respond to findings or resubmit a corrected version within scope." },
      ...common,
    ];
  }
  if (role === "lecturer") {
    return [
      { key: "teachingPlan", label: "My teaching plans", description: "Plan module delivery and record teaching-session progress." },
      { key: "moduleReadiness", label: "Module readiness", description: "Contribute readiness evidence and resolve assigned requirements." },
      { key: "workload", label: "My workload", description: "Review your weighted workload and configured limit." },
      { key: "academicCalendar", label: "Academic calendar", description: "Review upcoming teaching and assessment milestones." },
      { key: "handover", label: "Lecturer handover", description: "Prepare or accept an assigned module handover package." },
      { key: "reviewFollowUp", label: "Review follow-up", description: "Respond to findings and resubmit corrected output versions without losing earlier evidence." },
      ...common,
    ];
  }
  if (["internal_moderator", "external_moderator", "external_reviewer"].includes(role)) {
    return [
      { key: "reviewTasks", label: "Review tasks", description: "Accept, perform, record findings, and submit only the review work assigned to you." },
      ...common,
    ];
  }
  return common;
}

export function WorkspaceShell({ activeRole }: { activeRole: string }) {
  const router = useRouter();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [drawer, setDrawer] = useState<ActionKey | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatItem[]>([]);
  const [composerText, setComposerText] = useState("");
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [sending, setSending] = useState(false);
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeView, setActiveView] = useState<WorkspaceView>("conversation");
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [moduleContexts, setModuleContexts] = useState<ModuleContext[]>([]);
  const [selectedModuleOfferingId, setSelectedModuleOfferingId] = useState("");
  const [selectedReviewOutputId, setSelectedReviewOutputId] = useState("");
  const actions = useMemo(() => availableActions(activeRole), [activeRole]);

  useEffect(() => {
    void loadConversations();
    void loadModuleContexts();
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
    setConversations(data);
  }

  async function loadModuleContexts() {
    const response = await apiFetch("teaching-contexts");
    if (!response.ok) return;
    const data = (await response.json()) as ModuleContext[];
    setModuleContexts(data);
  }

  async function openConversation(id: string) {
    setActiveView("conversation");
    setLoadingConversation(true);
    setActiveConversationId(id);
    setSidebarOpen(false);
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
          outputTitle: message.role === "assistant" ? String(block.title ?? "Teaching output") : undefined,
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
    const storedContext = data.conversation && (data.conversation as ConversationSummary & { context?: Record<string, unknown> }).context;
    if (storedContext && typeof storedContext.module_offering_id === "string") setSelectedModuleOfferingId(storedContext.module_offering_id);
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

  async function sendMessage() {
    const content = composerText.trim();
    if (!content || sending) return;
    setSending(true);
    setNotice(null);
    const conversationId = await ensureConversation();
    if (!conversationId) {
      setSending(false);
      return;
    }
    const optimisticId = `local-${Date.now()}`;
    setMessages((current) => [...current, { id: optimisticId, role: "user", content }]);
    setComposerText("");
    const attachmentsForRequest = pendingAttachments;
    const response = await apiFetch(`conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({
        content,
        attachment_version_ids: pendingAttachments.map((item) => item.versionId),
        module_offering_id: selectedModuleOfferingId || null,
      }),
    });
    if (!response.ok) {
      setMessages((current) => current.filter((item) => item.id !== optimisticId));
      setComposerText(content);
      setPendingAttachments(attachmentsForRequest);
      setNotice(await responseMessage(response));
      setSending(false);
      return;
    }
    const data = (await response.json()) as UnifiedAIResponse;
    setPendingAttachments([]);
    setMessages((current) => [
      ...current.map((item) =>
        item.id === optimisticId ? { ...item, id: data.user_message.id } : item,
      ),
      {
        id: data.assistant_message.id,
        role: "assistant",
        content: data.output.markdown,
        outputType: data.output.output_type,
        outputTitle: data.output.title,
        sources: data.sources,
        provider: data.provider,
        model: data.model,
        warnings: data.integrity_warnings,
        requiresHumanReview: data.output.requires_human_review,
        approvalDisclaimer: data.output.approval_disclaimer,
        generatedOutputId: data.output.metadata?.generated_output_id,
        outputVersionId: data.output.metadata?.output_version_id,
        versionNumber: data.output.metadata?.version_number,
        workflowStatus: data.output.metadata?.workflow_status,
        riskLevel: data.output.metadata?.risk_level,
        safetyStatus: data.output.metadata?.safety_status,
        moduleContext: data.output.metadata?.module_context,
      },
    ]);
    setConversations((current) => {
      const updated = current.map((conversation) =>
        conversation.id === data.conversation.id ? data.conversation : conversation,
      );
      return [...updated].sort(
        (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
      );
    });
    setSending(false);
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
    conversation: activeTitle || "Teaching and learning workspace",
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

  return (
    <main id="main-content" className="workspace-grid">
      <button
        className="mobile-sidebar-toggle"
        type="button"
        aria-label="Open conversation navigation"
        onClick={() => setSidebarOpen((value) => !value)}
      >
        ☰
      </button>
      <aside className={`sidebar ${sidebarOpen ? "mobile-open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark" aria-label="Lecturer Support Agent home">LS</div>
          <div><strong>Lecturer Support</strong><span>AI work area</span></div>
        </div>
        <button className="primary-nav-button" type="button" onClick={startNewConversation}>＋ New conversation</button>
        <div className="sidebar-section-label">Recent conversations</div>
        <nav aria-label="Recent conversations" className="conversation-nav">
          {conversations.length === 0 && <span className="sidebar-empty">No saved conversations yet.</span>}
          {conversations.map((conversation) => (
            <button
              key={conversation.id}
              type="button"
              className={conversation.id === activeConversationId ? "conversation-nav-item active" : "conversation-nav-item"}
              onClick={() => void openConversation(conversation.id)}
              title={conversation.title}
            >
              <span>{conversation.title}</span>
            </button>
          ))}
        </nav>
        <nav aria-label="Workspace resources" className="nav-stack compact-nav">
          {[
            { key: "search" as const, icon: "⌕", label: "Search", shortcut: "Ctrl K" },
            { key: "library" as const, icon: "▣", label: "Library" },
            { key: "files" as const, icon: "↥", label: "Files" },
            { key: "saved" as const, icon: "☆", label: "Saved outputs" },
            { key: "notifications" as const, icon: "◉", label: "Notifications", badge: unreadNotifications },
            { key: "insights" as const, icon: "◒", label: "Insights" },
            ...(["institution_administrator", "head_of_department", "module_coordinator", "programme_coordinator", "lecturer", "internal_moderator"].includes(activeRole) ? [{ key: "reports" as const, icon: "▤", label: "Reports" }] : []),
            ...(activeRole === "institution_administrator" ? [{ key: "audit" as const, icon: "◇", label: "Audit centre" }] : []),
            ...(activeRole === "institution_administrator" ? [{ key: "settings" as const, icon: "⚙", label: "Platform settings" }, { key: "operations" as const, icon: "◈", label: "Platform operations" }] : []),
          ].map((item) => (
            <button key={item.key} type="button" className={activeView === item.key ? "nav-item active" : "nav-item"} onClick={() => changeView(item.key)}>
              <span aria-hidden="true">{item.icon}</span><span>{item.label}</span>
              {item.shortcut && <kbd>{item.shortcut}</kbd>}
              {!!item.badge && <b className="nav-badge">{item.badge > 99 ? "99+" : item.badge}</b>}
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
            {activeView === "conversation" && <label className="module-context-select">
              <span>Teaching context</span>
              <select value={selectedModuleOfferingId} onChange={(event) => setSelectedModuleOfferingId(event.target.value)}>
                <option value="">Generic teaching assistance</option>
                {moduleContexts.map((context) => (
                  <option value={context.module_offering_id} key={context.module_offering_id}>
                    {context.module_code} · {context.offering_code}
                  </option>
                ))}
              </select>
            </label>}
            <button className="theme-button" type="button" onClick={toggleTheme} aria-label={`Use ${theme === "light" ? "dark" : "light"} appearance`}>{theme === "light" ? "◐" : "☀"}</button>
            <button className="context-button" type="button" onClick={() => setDrawer(actions[0]?.key ?? null)}>
              Role actions
            </button>
          </div>
        </header>

        {activeView === "conversation" ? <>
        <div className="message-scroll" ref={scrollRef} aria-live="polite">
          {loadingConversation ? (
            <div className="conversation-loading"><span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" /></div>
          ) : messages.length === 0 ? (
            <div className="conversation-empty">
              <div className="orb" aria-hidden="true">✦</div>
              <h2>What would you like to create, review, or organise?</h2>
              <p>
                Ask for a lesson plan, practical activity, rubric, quiz, case study, marking guide,
                moderation review, or a day-to-day teaching task. The system chooses the appropriate
                inline output and uses verified sources when they are genuinely available.
              </p>
              <div className="capability-chips" aria-label="Supported examples">
                <span>Lesson planning</span><span>Assessments</span><span>Rubrics</span><span>Moderation</span>
              </div>
            </div>
          ) : (
            <div className="message-list">
              {messages.map((message) => <MessageCard key={message.id} message={message} activeRole={activeRole} onOpenReview={(outputId) => { setSelectedReviewOutputId(outputId); setDrawer("reviewCycle"); }} />)}
              {sending && <AssistantThinking />}
            </div>
          )}
          {notice && <div className="notice conversation-notice" role="status">{notice}</div>}
        </div>

        <div className="composer-wrap">
          <div className="composer" aria-label="AI request composer">
            <textarea
              aria-label="Message"
              placeholder="Message Lecturer Support Agent"
              rows={2}
              value={composerText}
              onChange={(event) => setComposerText(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              disabled={sending}
            />
            {!!pendingAttachments.length && (
              <div className="attachment-chip-row">
                {pendingAttachments.map((item) => (
                  <button key={item.versionId} type="button" className="attachment-chip" onClick={() => setPendingAttachments((current) => current.filter((entry) => entry.versionId !== item.versionId))}>
                    <span>▣</span>{item.filename}<b aria-label="Remove attachment">×</b>
                  </button>
                ))}
              </div>
            )}
            <div className="composer-row">
              <button
                type="button"
                className="icon-button"
                title="Attach or bulk-upload authorised files"
                onClick={() => setDrawer("bulkUpload")}
              >＋</button>
              <span className="composer-hint">Enter to send · Shift+Enter for a new line</span>
              <button type="button" className="send-button" disabled={sending || !composerText.trim()} onClick={() => void sendMessage()}>
                {sending ? "Working…" : "Send"}
              </button>
            </div>
          </div>
          <p className="ai-disclaimer">AI-generated teaching materials require professional judgement. Verified source cards indicate retrieval, not automatic institutional approval.</p>
        </div>
        </> : (
          <WorkspaceResourcePanel
            activeView={activeView}
            activeRole={activeRole}
            onOpenConversation={(id) => void openConversation(id)}
            onAttachVersion={(versionId, filename) => {
              setPendingAttachments((current) => current.some((item) => item.versionId === versionId) ? current : [...current, { versionId, filename, status: "attached" }]);
              setNotice(`${filename} is attached to your next message.`);
            }}
            onReturnToConversation={() => changeView("conversation")}
            onOpenRoleAction={(action) => { setDrawer(action as ActionKey); changeView("conversation"); }}
            onUnreadCountChange={setUnreadNotifications}
          />
        )}
      </section>

      <aside className={`action-rail ${drawer ? "open" : ""}`} aria-label="Role-aware actions">
        <div className="action-rail-header">
          <div><span className="eyebrow">Role-aware tools</span><h2>Context actions</h2></div>
          <button type="button" className="icon-button" onClick={() => setDrawer(null)} aria-label="Close actions">×</button>
        </div>
        <div className="action-list">
          {actions.map((action) => (
            <button
              type="button"
              key={action.key}
              className={drawer === action.key ? "action-card active" : "action-card"}
              onClick={() => setDrawer(action.key)}
            >
              <strong>{action.label}</strong><span>{action.description}</span>
            </button>
          ))}
        </div>
        <div className="action-form-area">
          {drawer === "feedback" && <FeedbackForm defaultTargetId={activeConversationId || ""} onResult={setNotice} />}
          {drawer === "invite" && <InviteUserForm onResult={setNotice} />}
          {drawer === "structure" && <CreateStructureForm onResult={setNotice} />}
          {drawer === "assignLecturer" && <AssignLecturerForm onResult={setNotice} />}
          {drawer === "departmentOverview" && <DepartmentOverviewForm onResult={setNotice} />}
          {drawer === "operationsDashboard" && <OperationsDashboardForm onResult={setNotice} />}
          {drawer === "teachingPlan" && <TeachingPlanForm onResult={setNotice} />}
          {drawer === "moduleReadiness" && <ModuleReadinessForm onResult={setNotice} />}
          {drawer === "workload" && <WorkloadForm activeRole={activeRole} onResult={setNotice} />}
          {drawer === "academicCalendar" && <AcademicCalendarForm onResult={setNotice} />}
          {drawer === "handover" && <HandoverForm onResult={setNotice} />}
          {drawer === "reviewCycle" && <CreateReviewCycleForm defaultOutputId={selectedReviewOutputId} onResult={setNotice} />}
          {drawer === "reviewTasks" && <ReviewTasksPanel onResult={setNotice} />}
          {drawer === "reviewDashboard" && <ReviewDashboardForm onResult={setNotice} />}
          {drawer === "reviewDecision" && <ReviewDecisionForm onResult={setNotice} />}
          {drawer === "reviewFollowUp" && <ReviewFollowUpForm onResult={setNotice} />}
          {drawer === "bulkUpload" && (
            <BulkUploadForm
              onResult={setNotice}
              onAttachments={(items) => {
                setPendingAttachments((current) => {
                  const merged = [...current];
                  for (const item of items) if (!merged.some((existing) => existing.versionId === item.versionId)) merged.push(item);
                  return merged;
                });
                setDrawer(null);
              }}
            />
          )}
        </div>
      </aside>
    </main>
  );
}

function MessageCard({ message, activeRole, onOpenReview }: { message: ChatItem; activeRole: string; onOpenReview: (outputId: string) => void }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(message.content);
  const [draft, setDraft] = useState(message.content);
  const [versionNumber, setVersionNumber] = useState(message.versionNumber || 1);
  const [workflowStatus, setWorkflowStatus] = useState(message.workflowStatus || "draft");
  const [safetyStatus, setSafetyStatus] = useState(message.safetyStatus || "passed");
  const [versions, setVersions] = useState<Array<{ id: string; version_number: number; change_reason: string; created_at: string }>>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  if (message.role === "user") {
    return <article className="message-row user-message"><div className="message-bubble">{message.content}</div></article>;
  }

  async function saveVersion() {
    if (!message.generatedOutputId || !draft.trim()) return;
    setBusy(true); setActionNotice(null);
    const reason = window.prompt("Briefly describe this edit", "Lecturer edit in unified conversation");
    if (!reason) { setBusy(false); return; }
    const response = await apiFetch(`teaching-outputs/${message.generatedOutputId}/versions`, {
      method: "POST",
      body: JSON.stringify({ content_markdown: draft, change_reason: reason }),
    });
    if (!response.ok) { setActionNotice(await responseMessage(response)); setBusy(false); return; }
    const data = await response.json();
    setContent(data.current_version.content_text);
    setDraft(data.current_version.content_text);
    setVersionNumber(data.current_version.version_number);
    setWorkflowStatus(data.lifecycle.workflow_status);
    setSafetyStatus(data.safety_review.status);
    setEditing(false); setBusy(false);
    setActionNotice(`Saved as version ${data.current_version.version_number}. Earlier versions remain unchanged.`);
  }

  async function loadVersions() {
    if (!message.generatedOutputId) return;
    setHistoryOpen((value) => !value);
    if (versions.length) return;
    const response = await apiFetch(`teaching-outputs/${message.generatedOutputId}/versions`);
    if (response.ok) setVersions(await response.json());
  }

  async function restoreVersion(id: string, number: number) {
    if (!message.generatedOutputId) return;
    const response = await apiFetch(`teaching-outputs/${message.generatedOutputId}/versions/${id}/restore`, {
      method: "POST",
      body: JSON.stringify({ change_reason: `Restore version ${number} as a new current version` }),
    });
    if (!response.ok) { setActionNotice(await responseMessage(response)); return; }
    const data = await response.json();
    setContent(data.current_version.content_text); setDraft(data.current_version.content_text);
    setVersionNumber(data.current_version.version_number); setWorkflowStatus(data.lifecycle.workflow_status);
    setSafetyStatus(data.safety_review.status); setVersions([]);
    setActionNotice(`Version ${number} was restored as new version ${data.current_version.version_number}.`);
  }

  async function exportOutput(format: string, audience: string) {
    if (!message.generatedOutputId) return;
    setBusy(true); setActionNotice(null);
    const response = await apiFetch(`teaching-outputs/${message.generatedOutputId}/exports`, {
      method: "POST", body: JSON.stringify({ export_format: format, audience }),
    });
    if (!response.ok) { setActionNotice(await responseMessage(response)); setBusy(false); return; }
    const job = await response.json();
    const download = await apiFetch(`teaching-outputs/exports/${job.id}/download`);
    if (!download.ok) { setActionNotice(await responseMessage(download)); setBusy(false); return; }
    const blob = await download.blob();
    const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
    anchor.href = url; anchor.download = job.filename || `teaching-output.${format}`; anchor.click();
    URL.revokeObjectURL(url); setBusy(false); setActionNotice(`${job.filename} generated from version ${versionNumber}.`);
  }

  async function saveToWorkspace() {
    if (!message.generatedOutputId || !message.outputVersionId) return;
    setBusy(true); setActionNotice(null);
    const response = await apiFetch("workspace/saved-outputs", {
      method: "POST",
      body: JSON.stringify({
        generated_output_id: message.generatedOutputId,
        output_version_id: message.outputVersionId,
        label: message.outputTitle || null,
        tags: [message.outputType || "teaching_output"],
        is_pinned: false,
      }),
    });
    setActionNotice(response.ok ? `Saved version ${versionNumber} to Saved outputs.` : await responseMessage(response));
    setBusy(false);
  }

  async function transition(action: string) {
    if (!message.generatedOutputId) return;
    const reason = window.prompt("Record the reason for this workflow action", humanize(action));
    if (!reason) return;
    const response = await apiFetch(`teaching-outputs/${message.generatedOutputId}/workflow`, {
      method: "POST", body: JSON.stringify({ action, reason }),
    });
    if (!response.ok) { setActionNotice(await responseMessage(response)); return; }
    const data = await response.json(); setWorkflowStatus(data.new_status);
    setActionNotice(`Workflow updated: ${humanize(data.new_status)}.`);
  }

  const mayApprove = ["head_of_department", "module_coordinator", "programme_coordinator"].includes(activeRole);
  const mayCreateReview = mayApprove;
  return (
    <article className="message-row assistant-message">
      <div className="assistant-avatar" aria-hidden="true">✦</div>
      <div className="assistant-content">
        <div className="response-meta">
          <span className="output-badge">{humanize(message.outputType || "response")}</span>
          <span className="version-pill">Version {versionNumber}</span>
          <span className={`workflow-pill ${workflowStatus}`}>{humanize(workflowStatus)}</span>
          {message.riskLevel && message.riskLevel !== "none" && <span className="risk-pill">{humanize(message.riskLevel)} risk</span>}
          {message.provider && <span>{message.provider} · {message.model}</span>}
        </div>
        {editing ? (
          <div className="inline-output-editor">
            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} rows={20} aria-label="Edit teaching output" />
            <div className="inline-action-row"><button disabled={busy} onClick={() => void saveVersion()} type="button">Save new version</button><button type="button" onClick={() => { setDraft(content); setEditing(false); }}>Cancel</button></div>
          </div>
        ) : <MarkdownView content={content} />}
        {message.generatedOutputId && !editing && (
          <div className="output-action-bar">
            <button type="button" onClick={() => setEditing(true)}>Edit</button>
            <button type="button" onClick={() => void loadVersions()}>Version history</button>
            <button type="button" disabled={busy} onClick={() => void saveToWorkspace()}>Save</button>
            {workflowStatus === "draft" && <button type="button" onClick={() => void transition("submit_for_review")}>Submit for review</button>}
            {mayCreateReview && workflowStatus === "under_review" && message.generatedOutputId && <button type="button" onClick={() => onOpenReview(message.generatedOutputId!)}>Create review cycle</button>}
            {mayApprove && workflowStatus === "under_review" && <button type="button" onClick={() => void transition("approve")}>Approve</button>}
            {mayApprove && workflowStatus === "approved" && <button type="button" onClick={() => void transition("release")}>Release</button>}
            <details className="export-menu"><summary>Export</summary><div><button onClick={() => void exportOutput("docx", "lecturer_pack")} type="button">DOCX lecturer pack</button><button onClick={() => void exportOutput("pdf", "lecturer_pack")} type="button">PDF lecturer pack</button><button onClick={() => void exportOutput("pptx", "generic")} type="button">PowerPoint</button><button onClick={() => void exportOutput("xlsx", "generic")} type="button">Excel</button><button onClick={() => void exportOutput("docx", "student_copy")} type="button">Student copy</button></div></details>
          </div>
        )}
        {historyOpen && <div className="version-history"><strong>Immutable version history</strong>{versions.map((version) => <div key={version.id}><span>Version {version.version_number}</span><small>{version.change_reason}</small>{version.version_number !== versionNumber && <button type="button" onClick={() => void restoreVersion(version.id, version.version_number)}>Restore as new version</button>}</div>)}</div>}
        {message.requiresHumanReview && message.approvalDisclaimer && (
          <div className="review-note"><strong>Human review required · {humanize(safetyStatus)}</strong><span>{message.approvalDisclaimer}</span></div>
        )}
        {actionNotice && <div className="output-action-notice">{actionNotice}</div>}
        {message.warnings?.map((warning) => <div className="integrity-warning" key={warning}>{warning}</div>)}
        {!!message.sources?.length && (
          <div className="source-section">
            <button className="source-toggle" type="button" onClick={() => setSourcesOpen((value) => !value)}>
              <span className="source-stack" aria-hidden="true"><i /><i /><i /></span>
              Sources · {message.sources.length}
              <span>{sourcesOpen ? "Hide" : "View"}</span>
            </button>
            {sourcesOpen && <div className="source-grid">{message.sources.map((source) => <SourceItem key={source.source_key} source={source} />)}</div>}
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
  return source.url ? <a className="source-item" href={source.url} target="_blank" rel="noreferrer">{card}</a> : <div className="source-item">{card}</div>;
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

function AssistantThinking() {
  return (
    <article className="message-row assistant-message">
      <div className="assistant-avatar" aria-hidden="true">✦</div>
      <div className="assistant-thinking"><span /><span /><span /><p>Preparing the most suitable teaching output…</p></div>
    </article>
  );
}

function humanize(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}


function CreateReviewCycleForm({ defaultOutputId, onResult }: { defaultOutputId: string; onResult: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    const values = new FormData(event.currentTarget);
    const externalGrant = String(values.get("external_access_grant_id") || "").trim();
    const response = await apiFetch("reviews/cycles", {
      method: "POST",
      body: JSON.stringify({
        generated_output_id: values.get("generated_output_id"),
        review_kind: values.get("review_kind"),
        due_at: values.get("due_at") ? new Date(String(values.get("due_at"))).toISOString() : null,
        instructions: values.get("instructions"),
        criteria: String(values.get("criteria") || "").split("\n").map((item) => item.trim()).filter(Boolean),
        assignees: [{
          user_id: values.get("reviewer_user_id"),
          reviewer_role_code: values.get("reviewer_role_code"),
          external_access_grant_id: externalGrant || null,
        }],
        supporting_document_version_ids: [], supporting_export_ids: [],
      }),
    });
    const data = await response.json().catch(() => ({}));
    onResult(response.ok ? `Review cycle ${data.cycle_number} created. The sealed pack targets output version ${data.initiating_output_version_id}.` : await responseMessage(response));
    setBusy(false);
  }
  return (
    <form className="form-card review-workflow-panel" onSubmit={submit}>
      <h3>Create review cycle</h3>
      <p>The reviewer receives one exact output version and only the actions included in the assigned task. Their recommendation does not itself approve or release the material.</p>
      <label><span>Review type</span><select name="review_kind"><option value="internal_moderation">Internal moderation</option><option value="external_moderation">External moderation</option><option value="external_review">External review</option><option value="quality_review">Quality review</option></select></label>
      <label><span>Output ID</span><input name="generated_output_id" defaultValue={defaultOutputId} required /></label>
      <Field label="Reviewer user ID" name="reviewer_user_id" />
      <label><span>Reviewer role</span><select name="reviewer_role_code"><option value="internal_moderator">Internal Moderator</option><option value="external_moderator">External Moderator</option><option value="external_reviewer">External Reviewer</option></select></label>
      <Field label="External access grant ID (external roles only)" name="external_access_grant_id" required={false} />
      <Field label="Due date" name="due_at" type="datetime-local" required={false} />
      <label><span>Review criteria, one per line</span><textarea name="criteria" rows={5} defaultValue={"Alignment with learning outcomes\nValidity and level appropriateness\nClarity and fairness\nMarking guide consistency\nAssessment safety and confidentiality"} required /></label>
      <label><span>Instructions</span><textarea name="instructions" rows={4} defaultValue="Review the sealed pack, record evidence-based findings, and submit a recommendation. Do not distribute the assessment or answer material." required /></label>
      <button disabled={busy} className="submit-button">{busy ? "Assigning…" : "Create sealed review cycle"}</button>
    </form>
  );
}

function ReviewTasksPanel({ onResult }: { onResult: (message: string) => void }) {
  const [tasks, setTasks] = useState<ReviewTaskSummary[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() {
    setBusy(true); const response = await apiFetch("reviews/tasks");
    if (response.ok) { const data = await response.json(); setTasks(data); if (!selectedTaskId && data[0]) setSelectedTaskId(data[0].id); }
    else onResult(await responseMessage(response)); setBusy(false);
  }
  useEffect(() => { void load(); }, []);
  async function taskAction(action: "accept" | "start") {
    if (!selectedTaskId) return;
    const response = await apiFetch(`reviews/tasks/${selectedTaskId}/${action}`, { method: "POST", body: JSON.stringify({ reason: `${humanize(action)} assigned review task` }) });
    onResult(response.ok ? `Review task ${humanize(action)}ed.` : await responseMessage(response)); await load();
  }
  async function addFinding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selectedTaskId) return; const values = new FormData(event.currentTarget);
    const response = await apiFetch(`reviews/tasks/${selectedTaskId}/findings`, { method: "POST", body: JSON.stringify({
      criterion_code: values.get("criterion_code") || null, category: values.get("category"), severity: values.get("severity"),
      title: values.get("title"), description: values.get("description"), evidence_locator: values.get("evidence_locator") || null,
      recommendation: values.get("recommendation") || null, is_blocking: values.get("is_blocking") === "on", metadata: {},
    }) });
    onResult(response.ok ? "Evidence-based finding recorded in the assigned review task." : await responseMessage(response));
  }
  async function submitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selectedTaskId) return; const values = new FormData(event.currentTarget);
    const response = await apiFetch(`reviews/tasks/${selectedTaskId}/submit`, { method: "POST", body: JSON.stringify({
      recommendation: values.get("recommendation"), summary: values.get("summary"),
      criterion_assessments: [{ criterion: "overall", judgement: values.get("recommendation") }], declaration_accepted: values.get("declaration") === "on",
    }) });
    onResult(response.ok ? "Review submitted as immutable evidence. The authorised decision-maker can now consider it." : await responseMessage(response)); await load();
  }
  return (
    <div className="form-card review-workflow-panel">
      <h3>Review tasks</h3><p>Only tasks assigned to your active account appear here. External access is checked again for every read, finding, and submission.</p>
      <button className="secondary-button" type="button" disabled={busy} onClick={() => void load()}>{busy ? "Loading…" : "Refresh tasks"}</button>
      <label><span>Assigned task</span><select value={selectedTaskId} onChange={(event) => setSelectedTaskId(event.target.value)}><option value="">No task selected</option>{tasks.map((task) => <option value={task.id} key={task.id}>{humanize(task.review_kind || "review")} · Round {task.round_number} · {humanize(task.status)}</option>)}</select></label>
      {selectedTaskId && <div className="inline-action-row"><button type="button" onClick={() => void taskAction("accept")}>Accept</button><button type="button" onClick={() => void taskAction("start")}>Start review</button></div>}
      <form onSubmit={addFinding} className="nested-review-form"><strong>Record finding</strong><Field label="Criterion code" name="criterion_code" required={false} /><Field label="Category" name="category" /><label><span>Severity</span><select name="severity"><option value="info">Information</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></label><Field label="Finding title" name="title" /><label><span>Description</span><textarea name="description" rows={4} required /></label><Field label="Evidence locator" name="evidence_locator" required={false} /><label><span>Recommendation</span><textarea name="recommendation" rows={3} /></label><label className="check-row"><input name="is_blocking" type="checkbox" />Blocking finding</label><button className="submit-button">Save finding</button></form>
      <form onSubmit={submitReview} className="nested-review-form"><strong>Submit review</strong><label><span>Recommendation</span><select name="recommendation"><option value="approve">Approve</option><option value="approve_with_conditions">Approve with conditions</option><option value="changes_required">Changes required</option><option value="reject">Reject</option></select></label><label><span>Reviewer summary</span><textarea name="summary" rows={5} required /></label><label className="check-row"><input name="declaration" type="checkbox" required />I confirm that this submission reflects my independent review of the assigned version.</label><button className="submit-button">Submit immutable review</button></form>
    </div>
  );
}

function ReviewDashboardForm({ onResult }: { onResult: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const values = new FormData(event.currentTarget);
    const response = await apiFetch(`reviews/dashboard/departments/${values.get("organisational_unit_id")}`);
    const data = await response.json().catch(() => null);
    onResult(response.ok ? `Review oversight — active cycles: ${data.active_cycles}; decision pending: ${data.decision_pending_cycles}; overdue: ${data.overdue_cycles}; open findings: ${data.open_findings}; blocking findings: ${data.blocking_findings}.` : await responseMessage(response)); setBusy(false);
  }
  return <form className="form-card review-workflow-panel" onSubmit={submit}><h3>Review oversight</h3><p>Departmental summaries respect the active Head of Department scope and do not expose unrelated units.</p><Field label="Department unit ID" name="organisational_unit_id" /><button disabled={busy} className="submit-button">{busy ? "Loading…" : "Load review dashboard"}</button></form>;
}


function ReviewDecisionForm({ onResult }: { onResult: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const values = new FormData(event.currentTarget);
    const conditions = String(values.get("conditions") || "").split("\n").map((item) => item.trim()).filter(Boolean);
    const response = await apiFetch(`reviews/cycles/${values.get("cycle_id")}/decision`, { method: "POST", body: JSON.stringify({
      decision: values.get("decision"), reason: values.get("reason"), conditions,
      correction_due_at: values.get("correction_due_at") ? new Date(String(values.get("correction_due_at"))).toISOString() : null,
    }) });
    const data = await response.json().catch(() => ({}));
    onResult(response.ok ? `Academic decision recorded for review round ${data.round_number}: ${humanize(data.decision)}. Reviewer recommendations remain separately preserved.` : await responseMessage(response)); setBusy(false);
  }
  return <form className="form-card review-workflow-panel" onSubmit={submit}><h3>Record review decision</h3><p>This action is available only to an authorised academic decision-maker. It does not edit or erase any reviewer submission.</p><Field label="Review cycle ID" name="cycle_id" /><label><span>Decision</span><select name="decision"><option value="approved">Approved</option><option value="approved_with_conditions">Approved with conditions</option><option value="changes_required">Changes required</option><option value="rejected">Rejected</option></select></label><label><span>Reason</span><textarea name="reason" rows={5} required /></label><label><span>Conditions, one per line</span><textarea name="conditions" rows={4} /></label><Field label="Correction due date" name="correction_due_at" type="datetime-local" required={false} /><button disabled={busy} className="submit-button">{busy ? "Recording…" : "Record authorised decision"}</button></form>;
}

function ReviewFollowUpForm({ onResult }: { onResult: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  const [findings, setFindings] = useState<Array<{ id: string; severity: string; title: string; status: string; is_blocking: boolean }>>([]);
  async function loadFindings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const values = new FormData(event.currentTarget);
    const response = await apiFetch(`reviews/cycles/${values.get("cycle_id")}/findings`);
    if (response.ok) setFindings(await response.json()); else onResult(await responseMessage(response)); setBusy(false);
  }
  async function respond(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const values = new FormData(event.currentTarget);
    const related = String(values.get("related_output_version_id") || "").trim();
    const response = await apiFetch(`reviews/findings/${values.get("finding_id")}/responses`, { method: "POST", body: JSON.stringify({ response_type: values.get("response_type"), body: values.get("body"), related_output_version_id: related || null, metadata: {} }) });
    onResult(response.ok ? "Finding response and correction evidence recorded." : await responseMessage(response)); setBusy(false);
  }
  async function resubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const values = new FormData(event.currentTarget);
    const response = await apiFetch(`reviews/cycles/${values.get("cycle_id")}/resubmit`, { method: "POST", body: JSON.stringify({ corrected_output_version_id: values.get("corrected_output_version_id"), resolution_summary: values.get("resolution_summary") }) });
    const data = await response.json().catch(() => ({}));
    onResult(response.ok ? `Corrections resubmitted as review round ${data.current_round}. Earlier review evidence remains unchanged.` : await responseMessage(response)); setBusy(false);
  }
  return <div className="form-card review-workflow-panel"><h3>Review follow-up</h3><p>Respond to findings and resubmit only after saving corrections as a new output version.</p><form className="nested-review-form" onSubmit={loadFindings}><strong>View cycle findings</strong><Field label="Review cycle ID" name="cycle_id" /><button disabled={busy} className="secondary-button">Load findings</button></form>{!!findings.length && <div className="version-history"><strong>Findings</strong>{findings.map((finding) => <div key={finding.id}><span>{humanize(finding.severity)} · {finding.title}</span><small>{humanize(finding.status)}{finding.is_blocking ? " · Blocking" : ""}</small></div>)}</div>}<form className="nested-review-form" onSubmit={respond}><strong>Respond to finding</strong><Field label="Finding ID" name="finding_id" /><label><span>Response type</span><select name="response_type"><option value="acknowledgement">Acknowledgement</option><option value="action_plan">Action plan</option><option value="resolution_evidence">Resolution evidence</option><option value="dispute">Dispute</option><option value="clarification">Clarification</option></select></label><label><span>Response</span><textarea name="body" rows={4} required /></label><Field label="Related corrected output version ID" name="related_output_version_id" required={false} /><button disabled={busy} className="submit-button">Record response</button></form><form className="nested-review-form" onSubmit={resubmit}><strong>Resubmit corrected version</strong><Field label="Review cycle ID" name="cycle_id" /><Field label="Current corrected output version ID" name="corrected_output_version_id" /><label><span>Resolution summary</span><textarea name="resolution_summary" rows={5} required /></label><button disabled={busy} className="submit-button">Create next review round</button></form></div>;
}

function FeedbackForm({ defaultTargetId, onResult }: { defaultTargetId: string; onResult: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const values = new FormData(event.currentTarget);
    const response = await apiFetch("feedback", { method: "POST", body: JSON.stringify({
      target_type: values.get("target_type"), target_id: values.get("target_id"),
      rating: Number(values.get("rating")), feedback_type: values.get("feedback_type"),
      comment: values.get("comment") || null, issue_codes: [], consent_for_research: Boolean(values.get("consent_for_research")),
    }) });
    onResult(response.ok ? "Thank you. Your feedback was recorded for authorised product evaluation." : await responseMessage(response)); setBusy(false);
  }
  return <form className="form-card" onSubmit={submit}><h3>Send product feedback</h3><p>Operational feedback is not treated as research consent unless you explicitly opt in.</p><label><span>Target</span><select name="target_type" defaultValue="conversation"><option value="conversation">Conversation</option><option value="generated_output">Generated output</option><option value="review_task">Review task</option></select></label><label><span>Target ID</span><input name="target_id" defaultValue={defaultTargetId} required /></label><label><span>Rating</span><select name="rating" defaultValue="4">{[1,2,3,4,5].map((value)=><option key={value} value={value}>{value} / 5</option>)}</select></label><label><span>Feedback type</span><select name="feedback_type" defaultValue="quality"><option value="quality">Output quality</option><option value="usability">Usability</option><option value="source_integrity">Source integrity</option><option value="safety">Safety concern</option><option value="bug">Technical issue</option></select></label><label><span>Comments</span><textarea name="comment" rows={5}/></label><label className="checkbox-row"><input type="checkbox" name="consent_for_research"/><span>I consent to this feedback being considered for an approved research evaluation.</span></label><input type="hidden" name="target_id_default" value={defaultTargetId}/><button disabled={busy} className="submit-button">{busy?"Submitting…":"Submit feedback"}</button></form>;
}

function Field({ label, name, type = "text", required = true }: { label: string; name: string; type?: string; required?: boolean }) {
  return <label><span>{label}</span><input name={name} type={type} required={required} /></label>;
}


function BulkUploadForm({ onResult, onAttachments }: { onResult: (message: string) => void; onAttachments: (items: PendingAttachment[]) => void }) {
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!files.length) { onResult("Select at least one file or ZIP archive."); return; }
    setBusy(true);
    const values = new FormData(event.currentTarget);
    const form = new FormData();
    const metadataFiles = files.map((file, index) => ({
      client_item_key: `web-${Date.now()}-${index}`,
      title: file.name.replace(/\.[^.]+$/, "").replaceAll("_", " "),
      document_type: String(values.get("document_type") || "teaching_material"),
      change_reason: String(values.get("change_reason") || "Teaching material upload"),
      metadata: { uploaded_from: "unified_work_area" },
    }));
    for (const file of files) form.append("files", file);
    form.append("metadata_json", JSON.stringify({
      scope_type: String(values.get("scope_type") || "institution"),
      scope_id: values.get("scope_id") || null,
      change_reason: String(values.get("change_reason") || "Teaching material upload"),
      org_unit_id: values.get("scope_type") === "organisational_unit" ? values.get("scope_id") || null : null,
      programme_id: values.get("scope_type") === "programme" ? values.get("scope_id") || null : null,
      module_id: values.get("scope_type") === "module" ? values.get("scope_id") || null : null,
      visibility: String(values.get("visibility") || "private"),
      auto_process: true, expand_archives: true, files: metadataFiles,
    }));
    const response = await apiFetch("bulk-uploads", { method: "POST", body: form });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) { onResult(await responseMessage(response)); setBusy(false); return; }
    const attachments: PendingAttachment[] = (data.items || []).filter((item: { document_version_id?: string }) => item.document_version_id).map((item: { document_version_id: string; original_filename: string; status: string }, index: number) => ({
      versionId: item.document_version_id, filename: item.original_filename, status: item.status,
    }));
    onAttachments(attachments);
    onResult(`Upload batch completed: ${data.batch.completed_item_count} stored, ${data.batch.failed_item_count} failed. Uploaded versions were attached to your next message.`);
    setFiles([]); setBusy(false);
  }
  return (
    <form className="form-card upload-form" onSubmit={submit}>
      <h3>Bulk upload</h3>
      <p>Upload individual files, multiple files, or one safe ZIP package. Every changed file creates a new immutable version with uploader, role, date, checksum, and provenance.</p>
      <label className="drop-zone"><span>Choose files or ZIP archive</span><input type="file" multiple onChange={(event) => setFiles(Array.from(event.target.files || []))} /><small>{files.length ? `${files.length} file(s) selected` : "PDF, DOCX, PPTX, XLSX, text, transcripts, media, and safe ZIP packages"}</small></label>
      {!!files.length && <div className="selected-file-list">{files.map((file) => <span key={`${file.name}-${file.size}`}>{file.name}<small>{Math.ceil(file.size / 1024)} KB</small></span>)}</div>}
      <label><span>Content type</span><select name="document_type"><option value="teaching_material">Teaching material</option><option value="lesson_plan">Lesson plan</option><option value="assessment">Assessment</option><option value="rubric">Rubric</option><option value="marking_guide">Marking guide</option><option value="policy">Policy or guideline</option><option value="archive">Mixed ZIP archive</option></select></label>
      <label><span>Scope</span><select name="scope_type"><option value="institution">Institution</option><option value="organisational_unit">Faculty, school, or department</option><option value="programme">Programme</option><option value="module">Module or course</option></select></label>
      <Field label="Scope ID (leave blank for institution)" name="scope_id" required={false} />
      <label><span>Visibility</span><select name="visibility"><option value="private">Private</option><option value="module">Module</option><option value="programme">Programme</option><option value="department">Department</option><option value="institution">Institution</option></select></label>
      <Field label="Change reason" name="change_reason" />
      <button disabled={busy || !files.length} className="submit-button">{busy ? "Uploading and processing…" : "Upload and attach"}</button>
    </form>
  );
}

function InviteUserForm({ onResult }: { onResult: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    const values = new FormData(event.currentTarget);
    const response = await apiFetch("users/invitations", {
      method: "POST",
      body: JSON.stringify({
        email: values.get("email"), position_title: values.get("position_title"),
        roles: [{ role_code: values.get("role_code"), scope_type: "institution", include_descendants: false, constraints: {} }],
      }),
    });
    const data = await response.json().catch(() => ({}));
    onResult(response.ok ? `Invitation created. ${data.invitation_url ?? "Email delivery integration remains pending."}` : await responseMessage(response));
    setBusy(false);
  }
  return <form className="form-card" onSubmit={submit}><h3>Invite user</h3><Field label="Email" name="email" type="email" /><Field label="Position title" name="position_title" required={false} /><label><span>System role</span><select name="role_code"><option value="lecturer">Lecturer</option><option value="module_coordinator">Module Coordinator</option><option value="programme_coordinator">Programme Coordinator</option><option value="head_of_department">Head of Department</option><option value="internal_moderator">Internal Moderator</option></select></label><button disabled={busy} className="submit-button">{busy ? "Creating…" : "Create invitation"}</button></form>;
}

function CreateStructureForm({ onResult }: { onResult: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    const values = new FormData(event.currentTarget);
    const response = await apiFetch("institution/unit-types", { method: "POST", body: JSON.stringify({ code: values.get("code"), display_name: values.get("display_name"), plural_name: values.get("plural_name"), level_order: Number(values.get("level_order")), allows_children: true, metadata_schema: {} }) });
    onResult(await responseMessage(response)); setBusy(false);
  }
  return <form className="form-card" onSubmit={submit}><h3>Add unit type</h3><Field label="Code" name="code" /><Field label="Display name" name="display_name" /><Field label="Plural name" name="plural_name" /><Field label="Hierarchy order" name="level_order" type="number" /><button disabled={busy} className="submit-button">{busy ? "Saving…" : "Save unit type"}</button></form>;
}

function AssignLecturerForm({ onResult }: { onResult: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    const values = new FormData(event.currentTarget);
    const response = await apiFetch("academic-assignments/lecturers", { method: "POST", body: JSON.stringify({ lecturer_user_id: values.get("lecturer_user_id"), module_offering_id: values.get("module_offering_id"), responsibility_type: values.get("responsibility_type"), workload_percentage: Number(values.get("workload_percentage")), valid_from: new Date(String(values.get("valid_from"))).toISOString() }) });
    onResult(await responseMessage(response)); setBusy(false);
  }
  return <form className="form-card" onSubmit={submit}><h3>Assign lecturer</h3><Field label="Lecturer user ID" name="lecturer_user_id" /><Field label="Module offering ID" name="module_offering_id" /><Field label="Responsibility" name="responsibility_type" /><Field label="Workload %" name="workload_percentage" type="number" /><Field label="Valid from" name="valid_from" type="datetime-local" /><button disabled={busy} className="submit-button">{busy ? "Assigning…" : "Assign lecturer"}</button></form>;
}

function DepartmentOverviewForm({ onResult }: { onResult: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    const values = new FormData(event.currentTarget);
    const response = await apiFetch(`academic-assignments/departments/${values.get("organisational_unit_id")}/overview`);
    const data = await response.json().catch(() => null);
    onResult(response.ok ? `Active offerings: ${data.active_module_offerings}; unassigned: ${data.unassigned_module_offerings}; lecturer assignments: ${data.active_lecturer_assignments}.` : await responseMessage(response)); setBusy(false);
  }
  return <form className="form-card" onSubmit={submit}><h3>Department overview</h3><Field label="Department unit ID" name="organisational_unit_id" /><button disabled={busy} className="submit-button">{busy ? "Loading…" : "Load overview"}</button></form>;
}


function OperationsDashboardForm({ onResult }: { onResult: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const values=new FormData(event.currentTarget);
    const response=await apiFetch(`department-operations/dashboards/departments/${values.get("organisational_unit_id")}`);
    const data=await response.json().catch(()=>null);
    onResult(response.ok ? `Operations: ${data.active_module_offerings} offerings; ${data.modules_without_active_teaching_plan} without plans; ${data.readiness_at_risk_or_blocked} readiness risks; ${data.overloaded_lecturers} overloaded lecturers; ${data.overdue_handovers} overdue handovers.` : await responseMessage(response)); setBusy(false);
  }
  return <form className="form-card" onSubmit={submit}><h3>Department teaching operations</h3><p>Attention-first view of delivery, readiness, workload, handovers, and deadlines.</p><Field label="Department unit ID" name="organisational_unit_id"/><button disabled={busy} className="submit-button">{busy?"Loading…":"Load operations"}</button></form>;
}

function TeachingPlanForm({ onResult }: { onResult: (message: string) => void }) {
  const [busy,setBusy]=useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); const v=new FormData(event.currentTarget); const response=await apiFetch("department-operations/teaching-plans",{method:"POST",body:JSON.stringify({module_offering_id:v.get("module_offering_id"),title:v.get("title"),planned_contact_hours:Number(v.get("planned_contact_hours")),summary:v.get("summary"),weekly_schedule:[],learning_outcome_mapping:[],assessment_milestones:[],resource_requirements:[]})}); onResult(await responseMessage(response)); setBusy(false); }
  return <form className="form-card" onSubmit={submit}><h3>Create teaching plan</h3><Field label="Module offering ID" name="module_offering_id"/><Field label="Plan title" name="title"/><Field label="Planned contact hours" name="planned_contact_hours" type="number"/><label><span>Summary</span><textarea name="summary" rows={4}/></label><button disabled={busy} className="submit-button">{busy?"Creating…":"Create versioned plan"}</button></form>;
}

function ModuleReadinessForm({ onResult }: { onResult: (message: string) => void }) {
  const [busy,setBusy]=useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); const v=new FormData(event.currentTarget); const response=await apiFetch("department-operations/readiness/profiles",{method:"POST",body:JSON.stringify({module_offering_id:v.get("module_offering_id"),requirements:[{requirement_code:"MODULE_GUIDE",category:"teaching_materials",title:"Current module guide",required:true,blocking:true,weight:2},{requirement_code:"TEACHING_PLAN",category:"delivery",title:"Approved teaching plan",required:true,blocking:true,weight:2},{requirement_code:"ASSESSMENT_PLAN",category:"assessment",title:"Assessment plan and dates",required:true,blocking:false,weight:1}]})}); onResult(await responseMessage(response)); setBusy(false); }
  return <form className="form-card" onSubmit={submit}><h3>Start module readiness</h3><p>Creates a configurable evidence checklist. Every update remains auditable.</p><Field label="Module offering ID" name="module_offering_id"/><button disabled={busy} className="submit-button">{busy?"Creating…":"Create readiness profile"}</button></form>;
}

function WorkloadForm({ activeRole, onResult }: { activeRole: string; onResult: (message: string) => void }) {
  const [busy,setBusy]=useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); const v=new FormData(event.currentTarget); const user=String(v.get("user_id")); const period=String(v.get("academic_period_id")); const response=await apiFetch(`department-operations/workloads/${user}?academic_period_id=${period}`); const data=await response.json().catch(()=>null); onResult(response.ok ? `Workload: ${data.weighted_hours} weighted hours; utilisation ${data.utilisation_percentage ?? "not configured"}%; ${data.overloaded?"overloaded":"within configured limit"}.` : await responseMessage(response)); setBusy(false); }
  return <form className="form-card" onSubmit={submit}><h3>{activeRole==="lecturer"?"My workload":"Lecturer workload"}</h3><Field label="User ID" name="user_id"/><Field label="Academic period ID" name="academic_period_id"/><button disabled={busy} className="submit-button">{busy?"Loading…":"Review workload"}</button></form>;
}

function AcademicCalendarForm({ onResult }: { onResult: (message: string) => void }) {
  const [busy,setBusy]=useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); const v=new FormData(event.currentTarget); const response=await apiFetch("department-operations/calendar/events",{method:"POST",body:JSON.stringify({academic_period_id:v.get("academic_period_id"),organisational_unit_id:v.get("organisational_unit_id")||null,event_type:v.get("event_type"),title:v.get("title"),starts_at:new Date(String(v.get("starts_at"))).toISOString(),ends_at:new Date(String(v.get("ends_at"))).toISOString(),all_day:false,visibility:"department",metadata:{}})}); onResult(await responseMessage(response)); setBusy(false); }
  return <form className="form-card" onSubmit={submit}><h3>Academic calendar event</h3><Field label="Academic period ID" name="academic_period_id"/><Field label="Department unit ID" name="organisational_unit_id" required={false}/><Field label="Event type" name="event_type"/><Field label="Title" name="title"/><Field label="Starts" name="starts_at" type="datetime-local"/><Field label="Ends" name="ends_at" type="datetime-local"/><button disabled={busy} className="submit-button">{busy?"Saving…":"Add event"}</button></form>;
}

function HandoverForm({ onResult }: { onResult: (message: string) => void }) {
  const [busy,setBusy]=useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); const v=new FormData(event.currentTarget); const response=await apiFetch("department-operations/handovers",{method:"POST",body:JSON.stringify({module_offering_id:v.get("module_offering_id"),outgoing_user_id:v.get("outgoing_user_id"),incoming_user_id:v.get("incoming_user_id")||null,title:v.get("title"),summary:v.get("summary"),checklist:[],document_version_ids:[],open_actions:[],risks_and_dependencies:[]})}); onResult(await responseMessage(response)); setBusy(false); }
  return <form className="form-card" onSubmit={submit}><h3>Create lecturer handover</h3><Field label="Module offering ID" name="module_offering_id"/><Field label="Outgoing lecturer user ID" name="outgoing_user_id"/><Field label="Incoming lecturer user ID" name="incoming_user_id" required={false}/><Field label="Title" name="title"/><label><span>Continuity summary</span><textarea name="summary" rows={4}/></label><button disabled={busy} className="submit-button">{busy?"Creating…":"Create handover package"}</button></form>;
}
