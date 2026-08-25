"use client";

import { type FormEvent, type KeyboardEvent, useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, responseMessage } from "@/lib/api-client";
import { WorkspaceResourcePanel, type WorkspaceView } from "@/components/workspace-resource-panels";

// ── SVG icon micro-library ──────────────────────────────────────────────
const IPlus = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>;
const IChevronLeft = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="15 18 9 12 15 6"/></svg>;
const IChevronRight = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"/></svg>;
const ISearch = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>;
const ILibrary = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>;
const IFiles = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>;
const ISaved = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>;
const IBell = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>;
const ISources = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>;
const IChart = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>;
const IReport = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>;
const IAudit = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>;
const ISettings = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>;
const IOps = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>;
const ISend = () => <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>;
const IAttach = () => <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>;
const IStop = () => <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>;
const IMoon = () => <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>;
const ISun = () => <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>;
const ICopy = () => <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>;
const IRetry = () => <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-5.36"/></svg>;
const IEdit = () => <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>;
const IMore = () => <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>;
const ITrash = () => <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>;
const IArchive = () => <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>;
const IMenu = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>;
const ICheck = () => <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>;
const IChevronDown = () => <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>;
const ISave = () => <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>;
const IHistory = () => <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-5.36"/><polyline points="12 7 12 12 15 14"/></svg>;
const IMoreDots = () => <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>;

// ── Types ───────────────────────────────────────────────────────────────
type ConversationSummary = {
  id: string;
  title: string;
  updated_at: string;
  is_archived: boolean;
  context?: Record<string, unknown>;
};

type ModelCatalogEntry = {
  provider: string;
  provider_display_name: string;
  model_id: string;
  model_display_name: string;
  configured: boolean;
  allowed_by_policy: boolean;
  availability: "available" | "unavailable" | "unknown";
};

type AISelection = { mode: "auto" } | { mode: "explicit"; provider: string; model: string };

// ── Generation lifecycle — the single authoritative source of truth for
// whether a request is in flight, streaming, stopping, or has reached a
// terminal state. Stop visibility, composer lock, and the streaming
// indicator are all DERIVED from this rather than independent booleans, so
// they cannot contradict each other. `requestId` is the request-ownership
// token: a stream reader checks it against the currently-active id before
// touching visible state, so late frames from an abandoned request (e.g.
// after switching conversations) are ignored rather than leaking in.
type GenerationStatus = "idle" | "sending" | "streaming" | "stopping" | "stopped" | "completed" | "error";
type GenerationState = {
  status: GenerationStatus;
  requestId: string | null;
  conversationId: string | null;
};
type GenerationAction =
  | { type: "START"; requestId: string; conversationId: string }
  | { type: "FIRST_TOKEN" }
  | { type: "STOP_REQUESTED" }
  | { type: "STOPPED" }
  | { type: "COMPLETED" }
  | { type: "ERROR" }
  | { type: "RESET" };

const INITIAL_GENERATION_STATE: GenerationState = { status: "idle", requestId: null, conversationId: null };

function generationReducer(state: GenerationState, action: GenerationAction): GenerationState {
  switch (action.type) {
    case "START":
      return { status: "sending", requestId: action.requestId, conversationId: action.conversationId };
    case "FIRST_TOKEN":
      return state.status === "sending" ? { ...state, status: "streaming" } : state;
    case "STOP_REQUESTED":
      return state.status === "sending" || state.status === "streaming" ? { ...state, status: "stopping" } : state;
    case "STOPPED":
      return state.status === "stopping" ? { ...state, status: "stopped" } : state;
    case "COMPLETED":
      return state.status === "sending" || state.status === "streaming" ? { ...state, status: "completed" } : state;
    case "ERROR":
      return { ...state, status: "error" };
    case "RESET":
      return INITIAL_GENERATION_STATE;
    default:
      return state;
  }
}

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

// ── Constants ───────────────────────────────────────────────────────────
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

const roleInitials: Record<string, string> = {
  institution_administrator: "IA",
  head_of_department: "HD",
  lecturer: "LC",
  module_coordinator: "MC",
  programme_coordinator: "PC",
  internal_moderator: "IM",
  external_moderator: "EM",
  external_reviewer: "ER",
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

// ── WorkspaceShell ──────────────────────────────────────────────────────
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
  const [conversationLoadError, setConversationLoadError] = useState(false);
  const [genState, dispatchGen] = useReducer(generationReducer, INITIAL_GENERATION_STATE);
  // Derived, not independent state: Stop visibility/composer lock/streaming
  // indicator all read from `sending` below, which is a pure function of
  // genState.status — they cannot diverge from the lifecycle by construction.
  const sending = genState.status === "sending" || genState.status === "streaming" || genState.status === "stopping";
  const [streamingText, setStreamingText] = useState("");
  const [streamingStatus, setStreamingStatus] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  // Request ownership: the reader loop checks this ref (not React state, to
  // avoid stale-closure reads inside the async loop) before touching visible
  // state, so frames from an abandoned request are ignored rather than
  // leaking into whatever conversation is now open.
  const activeRequestIdRef = useRef<string | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [activeView, setActiveView] = useState<WorkspaceView>("conversation");
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [uploadingFiles, setUploadingFiles] = useState(false);
  const [renamingConvId, setRenamingConvId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState("");
  const [openConvMenuId, setOpenConvMenuId] = useState<string | null>(null);
  const [pendingDeleteConvId, setPendingDeleteConvId] = useState<string | null>(null);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editMessageText, setEditMessageText] = useState("");
  const [availableModels, setAvailableModels] = useState<ModelCatalogEntry[]>([]);
  const [modelsStatus, setModelsStatus] = useState<"loading" | "ready" | "error">("loading");
  const [selectedModel, setSelectedModel] = useState<AISelection>({ mode: "auto" });
  const [modelMenuOpen, setModelMenuOpen] = useState(false);

  useEffect(() => {
    void loadConversations();
    void loadWorkspaceNavigation();
    void loadAvailableModels();
    const storedTheme = window.localStorage.getItem("lsa-theme") === "dark" ? "dark" : "light";
    setTheme(storedTheme);
    document.documentElement.dataset.theme = storedTheme;
    const storedCollapsed = window.localStorage.getItem("lsa-sidebar-collapsed") === "true";
    setSidebarCollapsed(storedCollapsed);
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

  async function loadAvailableModels() {
    setModelsStatus((current) => (current === "ready" ? current : "loading"));
    try {
      const response = await apiFetch("conversations/providers");
      if (!response.ok) throw new Error("request_failed");
      const data = (await response.json()) as ModelCatalogEntry[];
      setAvailableModels(data.filter((item) => item.configured && item.allowed_by_policy && item.availability !== "unavailable"));
      setModelsStatus("ready");
    } catch {
      setModelsStatus("error");
    }
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

  function toggleSidebarCollapse() {
    const next = !sidebarCollapsed;
    setSidebarCollapsed(next);
    setAccountMenuOpen(false);
    window.localStorage.setItem("lsa-sidebar-collapsed", String(next));
  }

  async function loadConversations() {
    const response = await apiFetch("conversations?limit=50");
    if (!response.ok) return;
    const data = (await response.json()) as ConversationSummary[];
    setConversations(data.filter((c) => !c.is_archived));
  }

  async function openConversation(id: string) {
    if (id === activeConversationId && !conversationLoadError) return;
    if (sending) stopGeneration();
    setActiveView("conversation");
    setLoadingConversation(true);
    setConversationLoadError(false);
    setActiveConversationId(id);
    setSidebarOpen(false);
    setEditingMessageId(null);
    try {
      const response = await apiFetch(`conversations/${id}`);
      if (!response.ok) {
        setConversationLoadError(true);
        return;
      }
      const data = (await response.json()) as ConversationDetail;
      let storedSelection: AISelection | undefined;
      try {
        storedSelection = data.conversation.context?.ai_selection as AISelection | undefined;
      } catch {
        storedSelection = undefined;
      }
      setSelectedModel(storedSelection && storedSelection.mode === "explicit" ? storedSelection : { mode: "auto" });
      setMessages(
        (data.messages ?? []).map((message) => {
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
    } catch {
      setConversationLoadError(true);
    } finally {
      setLoadingConversation(false);
    }
  }

  function startNewConversation() {
    if (sending) stopGeneration();
    setActiveView("conversation");
    setActiveConversationId(null);
    setMessages([]);
    setComposerText("");
    setNotice(null);
    setConversationLoadError(false);
    setLoadingConversation(false);
    setPendingAttachments([]);
    setSidebarOpen(false);
    setEditingMessageId(null);
    setSelectedModel({ mode: "auto" });
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

  // Shared by Stop and unexpected-EOF handling: appends whatever partial text
  // had streamed in as one interrupted assistant turn. Reads `text` from a
  // parameter (render-time value at the call site), never from inside a
  // setState updater — see the note on why that duplicates messages under
  // React Strict Mode.
  function pushInterruptedMessage(text: string, reason: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    setMessages((current) => [
      ...current,
      {
        id: `interrupted-${Date.now()}`,
        role: "assistant",
        content: trimmed,
        outputType: "generic_answer",
        requiresHumanReview: false,
        warnings: [reason],
      } as ChatItem,
    ]);
  }

  function stopGeneration() {
    if (genState.status !== "sending" && genState.status !== "streaming") return; // idempotent — no legal transition from here
    dispatchGen({ type: "STOP_REQUESTED" });
    activeRequestIdRef.current = null; // disown immediately: any in-flight frames are now "late"
    abortRef.current?.abort();
    abortRef.current = null;
    pushInterruptedMessage(streamingText, "Generation was stopped before it finished.");
    setStreamingText("");
    setStreamingStatus("");
    dispatchGen({ type: "STOPPED" });
  }

  async function streamRequest(conversationId: string, content: string, attachmentVersionIds: string[], optimisticId: string, originalContent: string, requestId: string) {
    const owns = () => activeRequestIdRef.current === requestId;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const response = await fetch(`/api/backend/conversations/${conversationId}/messages/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content,
          attachment_version_ids: attachmentVersionIds,
          preferred_provider: selectedModel.mode === "auto" ? "auto" : selectedModel.provider,
          preferred_model: selectedModel.mode === "auto" ? null : selectedModel.model,
        }),
        signal: ctrl.signal,
      });

      if (!owns()) { await response.body?.cancel().catch(() => {}); return; }

      if (!response.ok || !response.body) {
        setMessages((current) => current.filter((item) => item.id !== optimisticId));
        setComposerText(originalContent);
        setNotice("The request could not be completed. Please try again.");
        dispatchGen({ type: "ERROR" });
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let accText = "";
      let doneData: Record<string, unknown> | null = null;
      let sawError = false;
      let firstTokenSeen = false;

      while (true) {
        const { done, value } = await reader.read();
        if (!owns()) { await reader.cancel().catch(() => {}); return; } // abandoned mid-read — ignore any further frames
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6)) as Record<string, unknown>;
            if (!owns()) continue; // parsed but request was abandoned mid-batch
            if (event.type === "thinking") {
              setStreamingStatus(String(event.status ?? "Working…"));
            } else if (event.type === "token") {
              if (!firstTokenSeen) { firstTokenSeen = true; dispatchGen({ type: "FIRST_TOKEN" }); }
              accText += String(event.text ?? "");
              setStreamingText(accText);
            } else if (event.type === "done") {
              doneData = event;
            } else if (event.type === "error") {
              sawError = true;
              setNotice(String(event.detail ?? "An error occurred."));
              setMessages((current) => current.filter((item) => item.id !== optimisticId));
              setComposerText(originalContent);
              setStreamingText("");
              setStreamingStatus("");
              dispatchGen({ type: "ERROR" });
              return;
            }
          } catch {}
        }
      }

      if (!owns()) return;

      setStreamingText("");
      setStreamingStatus("");

      if (!doneData && !sawError) {
        // Unexpected EOF: the connection closed without a done or error
        // frame — e.g. a dropped connection or a killed backend process.
        // Silently discarding `accText` here (the previous behaviour) is
        // exactly the "response remains incomplete, nothing visible happens"
        // symptom reported in production. Treat it the same as a user Stop:
        // preserve whatever text arrived, and surface it as interrupted
        // rather than leaving no trace at all.
        pushInterruptedMessage(accText, "The connection was interrupted before the response finished.");
        if (!accText.trim()) {
          setMessages((current) => current.filter((item) => item.id !== optimisticId));
          setComposerText(originalContent);
          setNotice("The connection was interrupted before a response arrived. Please try again.");
        }
        dispatchGen({ type: "ERROR" });
        return;
      }

      if (doneData) {
        const d = doneData;
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
        if (owns()) dispatchGen({ type: "COMPLETED" });
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError" && owns()) {
        setNotice("Connection interrupted. Please try again.");
        setMessages((current) => current.filter((item) => item.id !== optimisticId));
        setComposerText(originalContent);
        dispatchGen({ type: "ERROR" });
      }
      // AbortError means Stop already drove the state to "stopped" — nothing
      // further to do here, and definitely no state write for an abandoned
      // (non-owning) request.
    } finally {
      if (owns()) {
        abortRef.current = null;
        setStreamingText("");
        setStreamingStatus("");
      }
    }
  }

  // Common entry into the lifecycle: idle/stopped/completed/error → sending.
  // Returns the fresh requestId that streamRequest must be called with.
  function beginGeneration(conversationId: string): string {
    const requestId = `req-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    activeRequestIdRef.current = requestId;
    dispatchGen({ type: "START", requestId, conversationId });
    setStreamingText("");
    setStreamingStatus("");
    return requestId;
  }

  async function sendMessage() {
    const content = composerText.trim();
    if (!content || sending) return;
    const requestId = beginGeneration(activeConversationId ?? "pending");
    setNotice(null);
    const conversationId = await ensureConversation();
    if (!conversationId) { dispatchGen({ type: "ERROR" }); return; }
    const optimisticId = `local-${Date.now()}`;
    setMessages((current) => [...current, { id: optimisticId, role: "user", content }]);
    setComposerText("");
    const attachmentsForRequest = pendingAttachments;
    setPendingAttachments([]);
    await streamRequest(conversationId, content, attachmentsForRequest.map((a) => a.versionId), optimisticId, content, requestId);
  }

  async function retryLastMessage() {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser || sending || !activeConversationId) return;
    setMessages((current) => {
      const idx = current.findLastIndex((m) => m.role === "assistant");
      return idx >= 0 ? current.slice(0, idx) : current;
    });
    const requestId = beginGeneration(activeConversationId);
    setNotice(null);
    const optimisticId = `local-retry-${Date.now()}`;
    await streamRequest(activeConversationId, lastUser.content, [], optimisticId, lastUser.content, requestId);
  }

  async function sendEditedMessage(messageId: string, newContent: string) {
    if (!activeConversationId || sending) return;
    const idx = messages.findIndex((m) => m.id === messageId);
    if (idx < 0) return;
    setEditingMessageId(null);
    setMessages((current) => current.slice(0, idx));
    const requestId = beginGeneration(activeConversationId);
    const optimisticId = `local-edit-${Date.now()}`;
    setMessages((current) => [...current, { id: optimisticId, role: "user", content: newContent }]);
    await streamRequest(activeConversationId, newContent, [], optimisticId, newContent, requestId);
  }

  async function confirmAction(confirmToken: string, label: string) {
    if (!activeConversationId || sending) return;
    const requestId = beginGeneration(activeConversationId);
    setNotice(null);
    const optimisticId = `local-confirm-${Date.now()}`;
    setMessages((current) => [...current, { id: optimisticId, role: "user", content: `Confirm: ${label}` }]);
    setMessages((current) => current.map((m) => m.pendingConfirmation?.confirmToken === confirmToken ? { ...m, pendingConfirmation: null } : m));
    await streamRequest(activeConversationId, `__confirm__${confirmToken}`, [], optimisticId, `Confirm: ${label}`, requestId);
  }

  async function cancelAction(confirmToken: string) {
    if (!activeConversationId || sending) return;
    const requestId = beginGeneration(activeConversationId);
    setNotice(null);
    const optimisticId = `local-cancel-${Date.now()}`;
    setMessages((current) => [
      ...current.map((m) => m.pendingConfirmation?.confirmToken === confirmToken ? { ...m, pendingConfirmation: null } : m),
      { id: optimisticId, role: "user", content: "Cancel" },
    ]);
    await streamRequest(activeConversationId, `__cancel__${confirmToken}`, [], optimisticId, "Cancel", requestId);
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
      scope_type: null,
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
    setNotice(attached.length ? `${attached.length} file(s) attached.${data.batch?.failed_item_count > 0 ? ` ${data.batch.failed_item_count} failed.` : ""}` : "Upload failed or files were not processed.");
    setUploadingFiles(false);
  }

  async function renameConversation(id: string, newTitle: string) {
    const trimmed = newTitle.trim().slice(0, 300);
    setRenamingConvId(null);
    if (!trimmed) return;
    const previous = conversations.find((c) => c.id === id)?.title ?? "";
    if (trimmed === previous) return;
    setConversations((current) => current.map((c) => c.id === id ? { ...c, title: trimmed } : c));
    const response = await apiFetch(`conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title: trimmed }),
    });
    if (!response.ok) {
      setConversations((current) => current.map((c) => c.id === id ? { ...c, title: previous } : c));
      setNotice("The rename could not be saved. Please try again.");
    }
  }

  async function archiveConversation(id: string) {
    setOpenConvMenuId(null);
    const removed = conversations.find((c) => c.id === id);
    setConversations((current) => current.filter((c) => c.id !== id));
    const response = await apiFetch(`conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_archived: true }),
    });
    if (response.ok) {
      if (activeConversationId === id) startNewConversation();
    } else if (removed) {
      setConversations((current) => [removed, ...current]);
      setNotice("The conversation could not be archived. Please try again.");
    }
  }

  async function deleteConversation(id: string) {
    setOpenConvMenuId(null);
    setPendingDeleteConvId(null);
    const removed = conversations.find((c) => c.id === id);
    setConversations((current) => current.filter((c) => c.id !== id));
    const response = await apiFetch(`conversations/${id}`, { method: "DELETE" });
    if (response.ok) {
      if (activeConversationId === id) startNewConversation();
    } else if (removed) {
      setConversations((current) => [removed, ...current]);
      setNotice("The conversation could not be deleted. Please try again.");
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
    sources: "Sources",
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
  const roleInitial = roleInitials[activeRole] ?? activeRole.slice(0, 2).toUpperCase();

  const navItems = [
    { key: "search" as const, Icon: ISearch, label: "Search", shortcut: "Ctrl K" },
    { key: "library" as const, Icon: ILibrary, label: "Library" },
    { key: "sources" as const, Icon: ISources, label: "Sources" },
    { key: "files" as const, Icon: IFiles, label: "Files" },
    { key: "saved" as const, Icon: ISaved, label: "Saved outputs" },
    { key: "notifications" as const, Icon: IBell, label: "Notifications", badge: unreadNotifications },
    { key: "insights" as const, Icon: IChart, label: "Insights" },
    ...(["institution_administrator","head_of_department","module_coordinator","programme_coordinator","lecturer","internal_moderator"].includes(activeRole) ? [{ key: "reports" as const, Icon: IReport, label: "Reports" }] : []),
    ...(activeRole === "institution_administrator" ? [
      { key: "audit" as const, Icon: IAudit, label: "Audit centre" },
      { key: "settings" as const, Icon: ISettings, label: "Platform settings" },
      { key: "operations" as const, Icon: IOps, label: "Platform operations" },
    ] : []),
  ];

  return (
    <main
      id="main-content"
      className={`workspace-grid${sidebarCollapsed ? " sidebar-collapsed" : ""}`}
    >
      {/* Mobile sidebar overlay */}
      <div
        className={`sidebar-overlay${sidebarOpen ? " visible" : ""}`}
        aria-hidden="true"
        onClick={() => setSidebarOpen(false)}
      />

      {/* Mobile hamburger */}
      <button
        className="mobile-sidebar-toggle"
        type="button"
        aria-label="Open navigation"
        onClick={() => setSidebarOpen((v) => !v)}
      >
        <IMenu />
      </button>

      {/* ── Sidebar ──────────────────────────────────────────────────── */}
      <aside className={`sidebar${sidebarOpen ? " mobile-open" : ""}`}>
        {/* Brand + collapse toggle */}
        <div className="sidebar-head">
          <div className="brand-mark" aria-label="Lecturer Support Agent">LS</div>
          {!sidebarCollapsed && (
            <div className="brand-text">
              <strong>Lecturer Support</strong>
              <span>AI assistant</span>
            </div>
          )}
          <button
            type="button"
            className="sidebar-collapse-btn"
            onClick={toggleSidebarCollapse}
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {sidebarCollapsed ? <IChevronRight /> : <IChevronLeft />}
          </button>
        </div>

        {/* New conversation */}
        <button type="button" className="sidebar-new-btn" onClick={startNewConversation}>
          <IPlus />
          <span>New conversation</span>
        </button>

        <div className="sidebar-sep" />

        {/* Workspace navigation — permanent product capabilities, above conversation history */}
        <nav aria-label="Workspace" className="nav-stack compact-nav">
          {navItems.map((item) => (
            <button
              key={item.key}
              type="button"
              aria-label={item.label}
              title={item.label}
              className={activeView === item.key ? "nav-item active" : "nav-item"}
              onClick={() => changeView(item.key)}
            >
              <item.Icon />
              <span>{item.label}</span>
              {"shortcut" in item && item.shortcut && <kbd>{item.shortcut}</kbd>}
              {"badge" in item && !!item.badge && (
                <b className="nav-badge">{(item.badge as number) > 99 ? "99+" : item.badge}</b>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-sep" />

        {/* Recent conversations — independently scrollable, hidden entirely when collapsed */}
        {!sidebarCollapsed && (
          <div className="sidebar-history">
            <div className="sidebar-section-label">Recent conversations</div>
            <nav aria-label="Recent conversations" className="conversation-nav">
              {conversations.length === 0 && <span className="sidebar-empty">No conversations yet.</span>}
              {conversations.map((conv) => (
                <ConversationRow
                  key={conv.id}
                  conv={conv}
                  isActive={conv.id === activeConversationId}
                  isRenaming={renamingConvId === conv.id}
                  renameText={renameText}
                  menuOpen={openConvMenuId === conv.id}
                  confirmingDelete={pendingDeleteConvId === conv.id}
                  onOpen={() => void openConversation(conv.id)}
                  onRenameTextChange={setRenameText}
                  onRenameStart={() => { setRenamingConvId(conv.id); setRenameText(conv.title); setOpenConvMenuId(null); }}
                  onRenameSubmit={() => void renameConversation(conv.id, renameText)}
                  onRenameCancel={() => setRenamingConvId(null)}
                  onToggleMenu={() => setOpenConvMenuId((v) => (v === conv.id ? null : conv.id))}
                  onCloseMenu={() => setOpenConvMenuId(null)}
                  onArchive={() => void archiveConversation(conv.id)}
                  onRequestDelete={() => { setPendingDeleteConvId(conv.id); setOpenConvMenuId(null); }}
                  onCancelDelete={() => setPendingDeleteConvId(null)}
                  onConfirmDelete={() => void deleteConversation(conv.id)}
                />
              ))}
            </nav>
          </div>
        )}

        {/* Account control */}
        <div className="role-card">
          {accountMenuOpen && (
            <div className="account-menu" role="menu">
              <button
                type="button"
                role="menuitem"
                onClick={() => { setAccountMenuOpen(false); changeView("settings"); }}
              >
                Settings
              </button>
              <div className="account-menu-sep" />
              <button
                type="button"
                role="menuitem"
                className="danger"
                onClick={signOut}
              >
                Sign out
              </button>
            </div>
          )}
          <button
            type="button"
            className="account-btn"
            aria-haspopup="true"
            aria-expanded={accountMenuOpen}
            onClick={() => setAccountMenuOpen((v) => !v)}
          >
            <div className="role-avatar" aria-hidden="true">{roleInitial}</div>
            <div className="role-card-text">
              <strong>{roleLabels[activeRole] ?? activeRole.replaceAll("_", " ")}</strong>
              <span>My account</span>
            </div>
            <span className="account-chevron"><IChevronDown /></span>
          </button>
        </div>
      </aside>

      {/* ── Content area ─────────────────────────────────────────────── */}
      <section className="conversation-area">
        <header className="topbar">
          <h1>
            {activeView === "conversation"
              ? (activeTitle || "New conversation")
              : viewTitles[activeView]}
          </h1>
          <div className="topbar-actions">
            <button
              className="theme-button"
              type="button"
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
            >
              {theme === "light" ? <IMoon /> : <ISun />}
            </button>
          </div>
        </header>

        {activeView === "conversation" ? (
          <>
            <div className="message-scroll" ref={scrollRef} aria-live="polite">
              {loadingConversation ? (
                <div className="conversation-loading">
                  <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
                </div>
              ) : conversationLoadError ? (
                <div className="conversation-load-error">
                  <div className="orb" aria-hidden="true">!</div>
                  <h2>This conversation couldn't be loaded.</h2>
                  <p>Please try again, or start a new conversation.</p>
                  <div className="conversation-load-error-actions">
                    <button
                      type="button"
                      className="context-button"
                      onClick={() => { if (activeConversationId) void openConversation(activeConversationId); }}
                    >
                      <IRetry /> Retry
                    </button>
                    <button type="button" className="context-button" onClick={startNewConversation}>
                      <IPlus /> New conversation
                    </button>
                  </div>
                </div>
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
                {!!pendingAttachments.length && (
                  <div className="attachment-chip-row">
                    {pendingAttachments.map((item) => (
                      <button
                        key={item.versionId}
                        type="button"
                        className="attachment-chip"
                        onClick={() => setPendingAttachments((c) => c.filter((e) => e.versionId !== item.versionId))}
                      >
                        <IFiles />{item.filename}<b aria-label="Remove">×</b>
                      </button>
                    ))}
                  </div>
                )}
                <textarea
                  ref={composerRef}
                  aria-label="Message"
                  placeholder="Message Lecturer Support Agent…"
                  rows={1}
                  value={composerText}
                  onChange={(e) => setComposerText(e.target.value)}
                  onKeyDown={handleComposerKeyDown}
                  disabled={sending}
                />
                <div className="composer-row">
                  <button
                    type="button"
                    className="icon-button"
                    title={uploadingFiles ? "Uploading…" : "Attach file"}
                    aria-label={uploadingFiles ? "Uploading…" : "Attach file"}
                    disabled={sending || uploadingFiles}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <IAttach />
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    aria-hidden="true"
                    style={{ display: "none" }}
                    onChange={(e) => { if (e.target.files) void handleFileAttach(e.target.files); e.target.value = ""; }}
                  />
                  <ModelSelector
                    models={availableModels}
                    status={modelsStatus}
                    selected={selectedModel}
                    open={modelMenuOpen}
                    onToggle={() => {
                      setModelMenuOpen((v) => !v);
                      if (modelsStatus === "error") void loadAvailableModels();
                    }}
                    onClose={() => setModelMenuOpen(false)}
                    onSelect={(value) => { setSelectedModel(value); setModelMenuOpen(false); }}
                  />
                  <span className="composer-hint">Enter to send · Shift+Enter for new line</span>
                  {sending ? (
                    <button type="button" className="stop-button" onClick={stopGeneration} aria-label="Stop generation">
                      <IStop /> Stop
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="send-button"
                      disabled={!composerText.trim()}
                      onClick={() => void sendMessage()}
                      aria-label="Send message"
                    >
                      <ISend />
                    </button>
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

// ── ConversationRow ──────────────────────────────────────────────────────
function ConversationRow({
  conv,
  isActive,
  isRenaming,
  renameText,
  menuOpen,
  confirmingDelete,
  onOpen,
  onRenameTextChange,
  onRenameStart,
  onRenameSubmit,
  onRenameCancel,
  onToggleMenu,
  onCloseMenu,
  onArchive,
  onRequestDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  conv: ConversationSummary;
  isActive: boolean;
  isRenaming: boolean;
  renameText: string;
  menuOpen: boolean;
  confirmingDelete: boolean;
  onOpen: () => void;
  onRenameTextChange: (v: string) => void;
  onRenameStart: () => void;
  onRenameSubmit: () => void;
  onRenameCancel: () => void;
  onToggleMenu: () => void;
  onCloseMenu: () => void;
  onArchive: () => void;
  onRequestDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
}) {
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!menuOpen) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) onCloseMenu();
    }
    function handleKey(e: globalThis.KeyboardEvent) {
      if (e.key === "Escape") onCloseMenu();
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [menuOpen, onCloseMenu]);

  if (confirmingDelete) {
    return (
      <div className="conv-nav-row conv-confirm">
        <p>Delete conversation?</p>
        <small>This removes it from your conversation list.</small>
        <div className="conv-confirm-actions">
          <button type="button" onClick={onCancelDelete}>Cancel</button>
          <button type="button" className="danger" onClick={onConfirmDelete}>Delete</button>
        </div>
      </div>
    );
  }

  if (isRenaming) {
    return (
      <div className="conv-nav-row">
        <form
          className="conv-rename-form"
          onSubmit={(e) => { e.preventDefault(); onRenameSubmit(); }}
        >
          <input
            autoFocus
            maxLength={300}
            value={renameText}
            onChange={(e) => onRenameTextChange(e.target.value)}
            onBlur={onRenameSubmit}
            onKeyDown={(e) => { if (e.key === "Escape") onRenameCancel(); }}
            aria-label="Rename conversation"
          />
        </form>
      </div>
    );
  }

  return (
    <div className={menuOpen ? "conv-nav-row menu-open" : "conv-nav-row"} ref={menuRef}>
      <button
        type="button"
        className={isActive ? "conversation-nav-item active" : "conversation-nav-item"}
        onClick={onOpen}
        title={conv.title}
      >
        <span>{conv.title}</span>
      </button>
      <button
        type="button"
        className="conv-menu-trigger"
        aria-label="Conversation options"
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        onClick={onToggleMenu}
      >
        <IMore />
      </button>
      {menuOpen && (
        <div className="conv-menu" role="menu">
          <button type="button" role="menuitem" onClick={onRenameStart}><IEdit /> Rename</button>
          <button type="button" role="menuitem" onClick={onArchive}><IArchive /> Archive</button>
          <button type="button" role="menuitem" className="danger" onClick={onRequestDelete}><ITrash /> Delete</button>
        </div>
      )}
    </div>
  );
}

// ── ModelSelector ────────────────────────────────────────────────────────
function ModelSelector({
  models,
  status,
  selected,
  open,
  onToggle,
  onClose,
  onSelect,
}: {
  models: ModelCatalogEntry[];
  status: "loading" | "ready" | "error";
  selected: AISelection;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
  onSelect: (value: AISelection) => void;
}) {
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) onClose();
    }
    function handleKey(e: globalThis.KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open, onClose]);

  const selectedEntry = selected.mode === "explicit"
    ? models.find((m) => m.provider === selected.provider && m.model_id === selected.model)
    : undefined;
  const currentLabel = selected.mode === "auto" ? "Auto" : (selectedEntry?.model_display_name ?? (selected.mode === "explicit" ? selected.model : "Auto"));

  const groups = new Map<string, { display: string; items: ModelCatalogEntry[] }>();
  for (const m of models) {
    if (!groups.has(m.provider)) groups.set(m.provider, { display: m.provider_display_name, items: [] });
    groups.get(m.provider)!.items.push(m);
  }

  return (
    <div className="model-selector" ref={menuRef}>
      <button
        type="button"
        className="model-selector-btn"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={onToggle}
        title={currentLabel}
      >
        <span className="model-selector-label">{currentLabel}</span>
        <IChevronDown />
      </button>
      {open && (
        <div className="model-menu" role="listbox" aria-label="AI model">
          <div className="model-menu-label">AI model</div>
          <div className="model-menu-scroll">
            <button
              type="button"
              role="option"
              aria-selected={selected.mode === "auto"}
              className={selected.mode === "auto" ? "model-option active" : "model-option"}
              onClick={() => onSelect({ mode: "auto" })}
              onFocus={(e) => e.currentTarget.scrollIntoView({ block: "nearest" })}
            >
              <span className="model-option-check">{selected.mode === "auto" ? "✓" : ""}</span>
              <span className="model-option-text">
                <strong>Auto</strong>
                <small>Best available model for the request</small>
              </span>
            </button>

            {status === "loading" && (
              <div className="model-menu-status" role="status" aria-live="polite">
                <span className="model-menu-status-dot" aria-hidden="true" />
                Loading available models…
              </div>
            )}

            {status === "error" && (
              <div className="model-menu-status" role="status" aria-live="polite">
                Models temporarily unavailable
                <small>Auto will continue to work</small>
              </div>
            )}

            {status === "ready" && [...groups.entries()].map(([providerKey, group]) => (
              <div key={providerKey}>
                <div className="model-menu-sep" />
                <div className="model-menu-group-label">{group.display}</div>
                {group.items.map((m) => {
                  const isSelected = selected.mode === "explicit" && selected.provider === m.provider && selected.model === m.model_id;
                  return (
                    <button
                      key={m.model_id}
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      className={isSelected ? "model-option active" : "model-option"}
                      title={m.model_display_name}
                      onClick={() => onSelect({ mode: "explicit", provider: m.provider, model: m.model_id })}
                      onFocus={(e) => e.currentTarget.scrollIntoView({ block: "nearest" })}
                    >
                      <span className="model-option-check">{isSelected ? "✓" : ""}</span>
                      <span className="model-option-text">
                        <strong>{m.model_display_name}</strong>
                      </span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── MessageCard ─────────────────────────────────────────────────────────
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
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!moreOpen) return;
    function handleClick(e: globalThis.MouseEvent) {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) setMoreOpen(false);
    }
    function handleKey(e: globalThis.KeyboardEvent) {
      if (e.key === "Escape") setMoreOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => { document.removeEventListener("mousedown", handleClick); document.removeEventListener("keydown", handleKey); };
  }, [moreOpen]);

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
          <button type="button" className="msg-action-btn" title="Edit and resend" onClick={onEditStart} aria-label="Edit message">
            <IEdit /><span>Edit</span>
          </button>
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

        {/* ── Unified response-action-bar ── */}
        <div className="response-action-bar">
          <button type="button" onClick={copyContent} className="rab-btn" title={copied ? "Copied!" : "Copy response"} aria-label="Copy response">
            {copied ? <ICheck /> : <ICopy />}<span>{copied ? "Copied" : "Copy"}</span>
          </button>
          {isLastAssistant && (
            <button type="button" onClick={onRetry} className="rab-btn" title="Regenerate" aria-label="Regenerate response">
              <IRetry /><span>Retry</span>
            </button>
          )}
          {message.generatedOutputId && !editingOutput && (
            <button type="button" disabled={busy} onClick={() => void saveToWorkspace()} className="rab-btn" title="Save to workspace">
              <ISave /><span>Save</span>
            </button>
          )}
          {!!message.sources?.length && (
            <button type="button" className="rab-btn rab-sources" onClick={() => setSourcesOpen((v) => !v)} aria-expanded={sourcesOpen}>
              <span className="source-stack" aria-hidden="true"><i /><i /><i /></span>
              <span>Sources · {message.sources.length}</span>
            </button>
          )}
          {message.generatedOutputId && !editingOutput && (
            <div className="rab-more-wrap" ref={moreRef}>
              <button
                type="button"
                className={`rab-btn rab-more-btn${moreOpen ? " rab-more-btn--open" : ""}`}
                aria-label="More actions"
                aria-haspopup="menu"
                aria-expanded={moreOpen}
                onClick={() => setMoreOpen((v) => !v)}
              >
                <IMoreDots />
              </button>
              {moreOpen && (
                <div className="more-menu" role="menu">
                  <button type="button" role="menuitem" className="more-menu-item" onClick={() => { setEditingOutput(true); setMoreOpen(false); }}>
                    <IEdit /> Edit
                  </button>
                  <button type="button" role="menuitem" className="more-menu-item" onClick={() => { void loadVersionHistory(); setMoreOpen(false); }}>
                    <IHistory /> Version history
                  </button>
                  {workflowStatus === "draft" && (
                    <button type="button" role="menuitem" className="more-menu-item" onClick={() => { void transition("submit_for_review"); setMoreOpen(false); }}>
                      Submit for review
                    </button>
                  )}
                  {mayApprove && workflowStatus === "under_review" && (
                    <button type="button" role="menuitem" className="more-menu-item" onClick={() => { void transition("approve"); setMoreOpen(false); }}>
                      Approve
                    </button>
                  )}
                  {mayApprove && workflowStatus === "approved" && (
                    <button type="button" role="menuitem" className="more-menu-item" onClick={() => { void transition("release"); setMoreOpen(false); }}>
                      Release
                    </button>
                  )}
                  <div className="more-menu-divider" role="separator" />
                  <button type="button" role="menuitem" className="more-menu-item" onClick={() => { void exportOutput("docx", "lecturer_pack"); setMoreOpen(false); }}>Export DOCX</button>
                  <button type="button" role="menuitem" className="more-menu-item" onClick={() => { void exportOutput("pdf", "lecturer_pack"); setMoreOpen(false); }}>Export PDF</button>
                  <button type="button" role="menuitem" className="more-menu-item" onClick={() => { void exportOutput("pptx", "generic"); setMoreOpen(false); }}>Export PowerPoint</button>
                  <button type="button" role="menuitem" className="more-menu-item" onClick={() => { void exportOutput("docx", "student_copy"); setMoreOpen(false); }}>Student copy</button>
                </div>
              )}
            </div>
          )}
        </div>

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

        {!!message.sources?.length && sourcesOpen && (
          <div className="source-grid">
            {message.sources.map((source) => <SourceItem key={source.source_key} source={source} />)}
          </div>
        )}
      </div>
    </article>
  );
}

// ── SourceItem ──────────────────────────────────────────────────────────
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

// ── Markdown rendering ──────────────────────────────────────────────────
type MdBlock =
  | { type: "h1" | "h2" | "h3"; text: string }
  | { type: "table"; headers: string[]; rows: string[][] }
  | { type: "code"; lang: string; text: string }
  | { type: "blockquote"; text: string }
  | { type: "ul"; items: string[] }
  | { type: "ol"; items: string[] }
  | { type: "hr" }
  | { type: "p"; text: string };

function parseMd(raw: string): MdBlock[] {
  const lines = raw.split("\n");
  const blocks: MdBlock[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) { i++; continue; }

    // Fenced code block
    if (trimmed.startsWith("```")) {
      const lang = trimmed.slice(3).trim();
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        code.push(lines[i]);
        i++;
      }
      i++;
      blocks.push({ type: "code", lang, text: code.join("\n") });
      continue;
    }

    // Horizontal rule
    if (/^[-*_]{3,}$/.test(trimmed)) { blocks.push({ type: "hr" }); i++; continue; }

    // Headings
    if (trimmed.startsWith("### ")) { blocks.push({ type: "h3", text: trimmed.slice(4) }); i++; continue; }
    if (trimmed.startsWith("## ")) { blocks.push({ type: "h2", text: trimmed.slice(3) }); i++; continue; }
    if (trimmed.startsWith("# ")) { blocks.push({ type: "h1", text: trimmed.slice(2) }); i++; continue; }

    // Table: consecutive lines starting with |
    if (trimmed.startsWith("|")) {
      const tlines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        tlines.push(lines[i]);
        i++;
      }
      const parseCells = (l: string): string[] => {
        const t = l.trim();
        const inner = t.endsWith("|") ? t.slice(1, -1) : t.slice(1);
        return inner.split("|").map((c) => c.trim());
      };
      const isSep = (l: string) => /^[\s|:\-]+$/.test(l);
      const rows = tlines.filter((l) => !isSep(l));
      if (rows.length >= 1) {
        blocks.push({ type: "table", headers: parseCells(rows[0]), rows: rows.slice(1).map(parseCells) });
      }
      continue;
    }

    // Blockquote
    if (trimmed.startsWith("> ")) {
      const bq: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("> ")) {
        bq.push(lines[i].trim().slice(2));
        i++;
      }
      blocks.push({ type: "blockquote", text: bq.join(" ") });
      continue;
    }

    // Unordered list
    if (/^[-*+] /.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*+] /.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*+] /, ""));
        i++;
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    // Ordered list
    if (/^\d+\. /.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\. /.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+\.\s+/, ""));
        i++;
      }
      blocks.push({ type: "ol", items });
      continue;
    }

    // Paragraph: accumulate until blank or block-level marker
    const pLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith("#") &&
      !lines[i].trim().startsWith("```") &&
      !lines[i].trim().startsWith("> ") &&
      !lines[i].trim().startsWith("|") &&
      !/^[-*+] /.test(lines[i].trim()) &&
      !/^\d+\. /.test(lines[i].trim()) &&
      !/^[-*_]{3,}$/.test(lines[i].trim())
    ) {
      pLines.push(lines[i]);
      i++;
    }
    if (pLines.length) blocks.push({ type: "p", text: pLines.join(" ") });
  }

  return blocks;
}

function renderInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[S\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
        if (part.startsWith("*") && part.endsWith("*")) return <em key={i}>{part.slice(1, -1)}</em>;
        if (part.startsWith("`") && part.endsWith("`")) return <code key={i} className="inline-code">{part.slice(1, -1)}</code>;
        if (/^\[S\d+\]$/.test(part)) return <sup key={i} className="citation-marker">{part}</sup>;
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

function MarkdownView({ content }: { content: string }) {
  const blocks = parseMd(content);
  return (
    <div className="markdown-view">
      {blocks.map((block, idx) => {
        switch (block.type) {
          case "h1": return <h2 key={idx}>{renderInline(block.text)}</h2>;
          case "h2": return <h3 key={idx}>{renderInline(block.text)}</h3>;
          case "h3": return <h4 key={idx}>{renderInline(block.text)}</h4>;
          case "hr": return <hr key={idx} className="md-hr" />;
          case "code":
            return (
              <div key={idx} className="md-code-block">
                {block.lang && <div className="md-code-lang">{block.lang}</div>}
                <pre><code>{block.text}</code></pre>
              </div>
            );
          case "blockquote":
            return <blockquote key={idx}>{renderInline(block.text)}</blockquote>;
          case "ul":
            return (
              <ul key={idx} className="md-ul">
                {block.items.map((item, ii) => <li key={ii}>{renderInline(item)}</li>)}
              </ul>
            );
          case "ol":
            return (
              <ol key={idx} className="md-ol">
                {block.items.map((item, ii) => <li key={ii}>{renderInline(item)}</li>)}
              </ol>
            );
          case "table":
            return (
              <div key={idx} className="md-table-wrap">
                <table className="md-table">
                  <thead>
                    <tr>{block.headers.map((h, hi) => <th key={hi}>{renderInline(h)}</th>)}</tr>
                  </thead>
                  <tbody>
                    {block.rows.map((row, ri) => (
                      <tr key={ri}>{row.map((cell, ci) => <td key={ci}>{renderInline(cell)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          case "p":
            return <p key={idx}>{renderInline(block.text)}</p>;
          default:
            return null;
        }
      })}
    </div>
  );
}

// ── AssistantStreaming ──────────────────────────────────────────────────
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
