/**
 * Typed client for the ArchitectureScope API (apps/api). Types come from
 * the API's OpenAPI contract (`npm run gen:api` regenerates api-types.ts),
 * so a contract change shows up here as a type error.
 *
 * Calls are same-origin (`/api/v1/...`): Next.js proxies them to the API
 * (see next.config.ts), so the HttpOnly session cookie is first-party.
 */

import type { components } from "./api-types";

type Schemas = components["schemas"];
export type DiscoveryConfig = Schemas["DiscoveryConfig"];
export type Question = Schemas["Question"];
export type FollowUpQuestion = Schemas["FollowUpQuestion"];
export type EvaluateRequest = Schemas["EvaluateRequest"];
export type Evaluation = Schemas["Evaluation"];
export type DiscoveryNotes = Schemas["DiscoveryNotes"];
export type ExportSection = Schemas["ExportSection"];
export type BuildOrder = Schemas["BuildOrder"];
export type BuildItem = Schemas["BuildItem"];
export type FlaggedTask = Schemas["FlaggedTask"];
export type HubSpotModule = Schemas["ClientExplainerRequest"]["modules"][number];
export type Me = Schemas["Me"];
export type AuthConfig = Schemas["AuthConfig"];
export type Project = Schemas["Project"];
export type ModuleState = Schemas["ModuleState"];
export type LibraryDocument = Schemas["Document"];
export type SecretStatus = Schemas["SecretStatus"];
export type PlannedStage = Schemas["PlannedStage"];
export type StagePlannerImport = Schemas["StagePlannerImport"];

const V1 = "/api/v1";

/** An API failure with the RFC 9457 problem's human-readable message. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly type?: string,
  ) {
    super(message);
  }
}

/** Called on any 401 (session missing / expired), e.g. to send the user to sign-in. */
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const problem = (await response.json()) as { title?: string; detail?: string; type?: string };
    return new ApiError(problem.detail || problem.title || response.statusText, response.status, problem.type);
  } catch {
    return new ApiError(`${response.status} ${response.statusText}`, response.status);
  }
}

// A host that sleeps idle services (Render's free plan) answers 502/503/504
// while the API wakes — measured at over a minute for a cold start. Reads are
// safe to repeat, so they retry through that window instead of failing the page.
export const WAKING = new Set([502, 503, 504]);
const WAKE_RETRY_MS = 180_000;

function pause(ms: number, signal?: AbortSignal | null): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });
}

async function request(path: string, init: RequestInit = {}, { auth = true } = {}): Promise<Response> {
  const retryable = (init.method ?? "GET").toUpperCase() === "GET";
  const giveUpAt = Date.now() + WAKE_RETRY_MS;
  let delay = 2_000;
  let response: Response | undefined;
  for (;;) {
    response = undefined;
    try {
      response = await fetch(`${V1}${path}`, {
        credentials: "same-origin",
        ...init,
        headers: { "Content-Type": "application/json", ...init.headers },
      });
    } catch (error) {
      if ((error as Error).name === "AbortError") throw error;
    }
    const waking = response === undefined || WAKING.has(response.status);
    if (!(waking && retryable && Date.now() + delay < giveUpAt)) break;
    await pause(delay, init.signal);
    delay = Math.min(delay * 2, 10_000);
  }
  if (response === undefined) {
    throw new ApiError("Can't reach The Hub Zone service. Check your connection and try again.");
  }
  if (!response.ok) {
    if (response.status === 401 && auth) onUnauthorized?.();
    throw await toApiError(response);
  }
  return response;
}

async function json<T>(path: string, init: RequestInit = {}, options?: { auth?: boolean }): Promise<T> {
  return (await (await request(path, init, options)).json()) as T;
}

const post = <T>(path: string, body: unknown, signal?: AbortSignal) =>
  json<T>(path, { method: "POST", body: JSON.stringify(body), signal });

// ---- Auth ---------------------------------------------------------------------

export const getAuthConfig = () => json<AuthConfig>("/auth/config", {}, { auth: false });
export const getMe = () => json<Me>("/auth/me", {}, { auth: false });
export const signIn = (email: string, password: string) =>
  json<Me>("/auth/sign-in", { method: "POST", body: JSON.stringify({ email, password }) }, { auth: false });
export async function signOut(): Promise<void> {
  await request("/auth/sign-out", { method: "POST" }, { auth: false });
}

// Your own account (the profile page).
export type Account = Schemas["Account"];
export const getAccount = () => json<Account>("/auth/account");
export const updateAccount = (name: string) => json<Account>("/auth/account", { method: "PATCH", body: JSON.stringify({ name }) });
export const changePassword = (current_password: string, new_password: string) =>
  post<Account>("/auth/account/password", { current_password, new_password });
export const signOutOtherBrowsers = () => post<{ signed_out: number }>("/auth/account/sign-out-others", {});

const noAuthPost = <T>(path: string, body: unknown) =>
  json<T>(path, { method: "POST", body: JSON.stringify(body) }, { auth: false });

/** Start sign-up: emails a 6-digit code. */
export const signUp = (name: string, email: string, password: string) =>
  noAuthPost<{ message: string }>("/auth/sign-up", { name, email, password });
export const resendSignUpCode = (email: string) => noAuthPost<{ message: string }>("/auth/sign-up/resend", { email });
/** Confirm the code: creates the account and signs in. */
export const verifySignUp = (email: string, code: string) => noAuthPost<Me>("/auth/sign-up/verify", { email, code });
export const requestPasswordReset = (email: string) => noAuthPost<{ message: string }>("/auth/password-reset", { email });
export const confirmPasswordReset = (email: string, code: string, password: string) =>
  noAuthPost<Me>("/auth/password-reset/confirm", { email, code, password });

// ---- Projects, saved state, library ------------------------------------------------

export const listProjects = (includeArchived = false) =>
  json<Project[]>(`/projects${includeArchived ? "?include_archived=true" : ""}`);
export const createProject = (name: string, extra: { client_name?: string; folder?: string; lead_user_id?: string | null } = {}) =>
  post<Project>("/projects", { name, client_name: "", ...extra });
export const getProject = (id: string) => json<Project>(`/projects/${id}`);
export const updateProject = (id: string, patch: Schemas["ProjectUpdate"]) =>
  json<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
/** Delete a project with all its saved work and library documents. */
export async function deleteProject(id: string): Promise<void> {
  await request(`/projects/${id}`, { method: "DELETE" });
}

export type Member = Schemas["Member"];
export type Person = Schemas["Person"];
export const listMembers = () => json<Member[]>("/workspace/members");

// ---- Feedback ---------------------------------------------------------------------------

export type FeedbackRequest = Schemas["FeedbackRequest"];
/** Email a bug report, idea or question (with screenshots) to the app owner. */
export const sendFeedback = (body: FeedbackRequest) => post<{ message: string }>("/feedback", body);

// ---- Suggestions from earlier steps ("Fill from earlier steps" / "Suggest") ------------

export type AssistContext = Schemas["AssistContext"];
export type ArchitectureAssistInputs = Schemas["ArchitectureInputs"];
export const assistStagePlanner = (context: AssistContext, stages: PlannedStage[]) =>
  post<Schemas["StagePlannerAssistResponse"]>("/assist/stage-planner", { context, stages });
export const assistArchitecture = (context: AssistContext, inputs: ArchitectureAssistInputs) =>
  post<Schemas["ArchitectureAssistResponse"]>("/assist/architecture", { context, inputs });
export const assistProposal = (context: AssistContext, proposal: ProposalDocument) =>
  post<Schemas["ProposalAssistResponse"]>("/assist/proposal", { context, proposal });

export type SuggestedTask = Schemas["SuggestedTask"];
export const assistProjectTasks = (context: AssistContext, tasks: { stage: string; title: string }[]) =>
  post<Schemas["ProjectTasksAssistResponse"]>("/assist/project-tasks", { context, tasks });
export type ScheduleSettingsPayload = Schemas["ScheduleSettings"];
export type MeetingStub = Schemas["MeetingStub"];
export type SuggestedMeeting = Schemas["SuggestedMeeting"];
export type MeetingContent = Schemas["MeetingContent"];
export const assistSchedule = (context: AssistContext, settings: ScheduleSettingsPayload, meetings: MeetingStub[]) =>
  post<Schemas["ScheduleAssistResponse"]>("/assist/schedule", { context, settings, meetings });
export const assistScheduleMeeting = (
  context: AssistContext,
  settings: ScheduleSettingsPayload,
  meeting: Schemas["MeetingToPrepare"],
  other_meetings: MeetingStub[],
) => post<Schemas["ScheduleMeetingAssistResponse"]>("/assist/schedule-meeting", { context, settings, meeting, other_meetings });
export type CompanyOverview = Schemas["CompanyOverview"];
export const companyOverview = (website: string, client_name: string, business_type: string) =>
  post<Schemas["CompanyOverviewResponse"]>("/assist/company-overview", { website, client_name, business_type });

// ---- Industry templates -------------------------------------------------------------------

export type IndustryTemplates = Schemas["IndustryTemplates"];
export const listIndustryTemplates = () => json<IndustryTemplates>("/industry-templates");
export const applyIndustryDiscoveryTemplate = (industry: string, size: string | null, notes: DiscoveryNotes) =>
  post<Schemas["IndustryDiscoveryResponse"]>("/industry-templates/discovery", { industry, size, notes });
export const applyIndustryProposalTemplate = (industry: string, size: string | null, proposal: ProposalDocument) =>
  post<Schemas["IndustryProposalResponse"]>("/industry-templates/proposal", { industry, size, proposal });

export const getModuleState = (projectId: string, module: string) =>
  json<ModuleState>(`/projects/${projectId}/state/${module}`);
export const saveModuleState = (projectId: string, module: string, data: object, version: number) =>
  json<ModuleState>(`/projects/${projectId}/state/${module}`, { method: "PUT", body: JSON.stringify({ data, version }) });

export const listDocuments = (projectId: string) => json<LibraryDocument[]>(`/projects/${projectId}/documents`);
export async function deleteDocument(projectId: string, documentId: string): Promise<void> {
  await request(`/projects/${projectId}/documents/${documentId}`, { method: "DELETE" });
}
export async function downloadDocument(projectId: string, doc: LibraryDocument): Promise<void> {
  const response = await request(`/projects/${projectId}/documents/${doc.id}`);
  saveBlob(await response.blob(), doc.filename);
}

/** A file produced in the browser or by an export endpoint. */
export type GeneratedFile = { blob: Blob; filename: string };

export async function saveToLibrary(projectId: string, documentType: string, file: GeneratedFile, title = ""): Promise<LibraryDocument> {
  const params = new URLSearchParams({ document_type: documentType, filename: file.filename, title: title || file.filename });
  const response = await request(`/projects/${projectId}/documents?${params}`, {
    method: "POST",
    body: file.blob,
    headers: { "Content-Type": file.blob.type || "application/octet-stream" },
  });
  return (await response.json()) as LibraryDocument;
}

// ---- Workspace settings ------------------------------------------------------------

export const listSecrets = () => json<SecretStatus[]>("/workspace/secrets");
export const setSecret = (name: string, value: string) =>
  json<SecretStatus[]>(`/workspace/secrets/${name}`, { method: "PUT", body: JSON.stringify({ value }) });
export async function deleteSecret(name: string): Promise<void> {
  await request(`/workspace/secrets/${name}`, { method: "DELETE" });
}

// ---- Architecture ---------------------------------------------------------------

export type BlueprintInputBody = Schemas["BlueprintInput"];
export type BlueprintBody = Schemas["Blueprint"];
export type DiagramBody = Schemas["Diagram"];

export const generateBlueprint = (input: BlueprintInputBody) => post<BlueprintBody>("/blueprints", input);

export async function blueprintMarkdown(blueprint: BlueprintBody): Promise<string> {
  const response = await request("/blueprints/markdown", { method: "POST", body: JSON.stringify(blueprint) });
  return response.text();
}

export const diagramFromBlueprint = (body: Schemas["DiagramFromBlueprintRequest"]) =>
  post<DiagramBody>("/diagrams/from-blueprint", body);
export const diagramFromSnapshot = (body: Schemas["DiagramFromSnapshotRequest"]) =>
  post<DiagramBody>("/diagrams/from-snapshot", body);

export async function renderDiagram(
  body: Schemas["DiagramRenderRequest"],
  format: "png" | "dot" | "drawio",
  fileStub: string,
): Promise<GeneratedFile> {
  const response = await request(`/diagrams/render?format=${format}`, { method: "POST", body: JSON.stringify(body) });
  return { blob: await response.blob(), filename: filenameFrom(response, `${fileStub}.${format}`) };
}

// ---- Portal (read-only HubSpot) -----------------------------------------------------

export type PortalSnapshot = Schemas["PortalSnapshot"];
export type Finding = Schemas["Finding"];
export type AuditResult = Schemas["AuditResult"];
export type PropertyAuditResult = Schemas["PropertyAuditResult"];
export type ReportContext = Schemas["ReportContext"];

/** Pull a read-only snapshot with the workspace's stored HubSpot token. */
export const pullSnapshot = () => post<PortalSnapshot>("/portal/snapshot", {});
export const runAudit = (snapshot: PortalSnapshot) => post<AuditResult>("/audits", { snapshot });
export const runPropertyAudit = (snapshot: PortalSnapshot) => post<PropertyAuditResult>("/property-audits", { snapshot });

async function fileFrom(path: string, body: unknown, fallback: string): Promise<GeneratedFile> {
  const response = await request(path, { method: "POST", body: JSON.stringify(body) });
  return { blob: await response.blob(), filename: filenameFrom(response, fallback) };
}

export const exportPropertyAudit = (
  body: { result: PropertyAuditResult; project_name: string },
  format: "xlsx" | "pdf",
  stub: string,
) => fileFrom(`/property-audits/export?format=${format}`, body, `${stub}.${format}`);

export const snapshotDocument = (snapshot: PortalSnapshot, format: "md" | "docx", stub: string) =>
  fileFrom(`/portal/snapshot/document?format=${format}`, snapshot, `${stub}.${format}`);

export const reportContext = (body: { snapshot: PortalSnapshot; findings: Finding[] | null; project_name: string }) =>
  post<ReportContext>("/reports/context", body);
export const reportDocument = (
  body: { snapshot: PortalSnapshot; findings: Finding[] | null; project_name: string },
  audience: "client" | "internal",
  stub: string,
) => fileFrom(`/reports/document?audience=${audience}`, body, `${stub}.docx`);

// ---- Proposal & SOW Builder -----------------------------------------------------------

export type ProposalDocument = Schemas["ProposalDocument"];
export type ProposalAnalysis = Schemas["ProposalAnalysis"];
export type ProposalLibraries = Schemas["ProposalLibraries"];
export type ScopeStatus = Schemas["AddLibraryItemsRequest"]["status"];
type SectionRows = Record<string, Record<string, string>[]>;

export const defaultProposal = () => json<ProposalDocument>("/proposals/default");
export const proposalLibraries = () => json<ProposalLibraries>("/proposals/libraries");
export const analyseProposal = (proposal: ProposalDocument, signal?: AbortSignal) =>
  post<ProposalAnalysis>("/proposals/analysis", { proposal }, signal);
export const importWrdIntoProposal = (proposal: ProposalDocument, wrd: SectionRows) =>
  post<ProposalDocument>("/proposals/import/wrd", { proposal, wrd });
export const importJepIntoProposal = (proposal: ProposalDocument, jep: SectionRows, prospect_name: string) =>
  post<ProposalDocument>("/proposals/import/jep", { proposal, jep, prospect_name });
export const addScopeLibraryItems = (proposal: ProposalDocument, items: string[], status: ScopeStatus) =>
  post<ProposalDocument>("/proposals/scope/library-items", { proposal, items, status });
export const addLibraryAddons = (proposal: ProposalDocument, services: string[]) =>
  post<ProposalDocument>("/proposals/scope/library-addons", { proposal, services });
export const draftScopeFromRequirements = (proposal: ProposalDocument) =>
  post<ProposalDocument>("/proposals/scope/from-requirements", { proposal });
export const proposalTemplate = (proposal: ProposalDocument) => post<ProposalDocument>("/proposals/template", { proposal });
// Shared templates: a filled-in proposal saved (client details cleared) for similar clients.
export type ProposalTemplateSummary = Schemas["ProposalTemplateSummary"];
export const listProposalTemplates = () => json<ProposalTemplateSummary[]>("/proposals/templates");
export const saveProposalTemplate = (body: { name: string; description: string; proposal: ProposalDocument; replace?: boolean }) =>
  post<ProposalTemplateSummary>("/proposals/templates", body);
export const renameProposalTemplate = (id: string, patch: { name?: string; description?: string }) =>
  json<ProposalTemplateSummary>(`/proposals/templates/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
export async function deleteProposalTemplate(id: string): Promise<void> {
  await request(`/proposals/templates/${id}`, { method: "DELETE" });
}
/** The given proposal restarted from a template (its client details, dates and reference kept). */
export const applyProposalTemplate = (id: string, proposal: ProposalDocument) =>
  post<ProposalDocument>(`/proposals/templates/${id}/apply`, { proposal });
export const proposalPdf =(proposal: ProposalDocument, stub: string) => fileFrom("/proposals/pdf", { proposal }, `${stub}.pdf`);

// ---- Deal Stage Planner ------------------------------------------------------------

export async function stagePlannerTemplate(): Promise<GeneratedFile> {
  const response = await request("/stage-planner/template");
  return { blob: await response.blob(), filename: filenameFrom(response, "HubSpot_Deal_Stage_Planner.xlsx") };
}

/** Parse a filled-out planner (.xlsx) for review. */
export async function importStagePlanner(file: File): Promise<StagePlannerImport> {
  const response = await request("/stage-planner/import", {
    method: "POST",
    body: file,
    headers: { "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
  });
  return (await response.json()) as StagePlannerImport;
}

export const previewStagePlanner = (stages: PlannedStage[], signal?: AbortSignal) =>
  post<StagePlannerImport>("/stage-planner/preview", { stages }, signal);

// ---- Discovery -----------------------------------------------------------------

export type AiModels = Schemas["AiModels"];
/** The AI models drafting can use, most accurate first. */
export const getAiModels = () => json<AiModels>("/discovery/ai-models");

export const getDiscoveryConfig = (signal?: AbortSignal) => json<DiscoveryConfig>("/discovery/config", { signal });

/** What the notes trigger: follow-ups, required tasks, checklist, build order. */
export const evaluateNotes = (body: EvaluateRequest, signal?: AbortSignal) =>
  post<Evaluation>("/discovery/evaluate", body, signal);

export async function suggestModules(businessAnalysisMarkdown: string): Promise<HubSpotModule[]> {
  const body = await post<{ modules: HubSpotModule[] }>("/discovery/suggest-modules", {
    business_analysis_markdown: businessAnalysisMarkdown,
  });
  return body.modules;
}

/**
 * Stream an AI-drafted document (Server-Sent Events: `status` notes and
 * `delta` chunks, then `done` or an `error` problem). Calls `onText` with
 * each chunk and `onStatus` with each progress note (e.g. which model is
 * drafting, or that a busy one is being replaced).
 */
export async function streamDocument(
  kind: "business-analysis" | "client-explainer",
  body: unknown,
  onText: (text: string) => void,
  signal?: AbortSignal,
  onStatus?: (message: string) => void,
  /** A model to try first (from getAiModels); the others stay as fallbacks. */
  model?: string,
): Promise<void> {
  const query = model ? `?model=${encodeURIComponent(model)}` : "";
  const response = await request(`/discovery/${kind}${query}`, { method: "POST", body: JSON.stringify(body), signal });
  const reader = response.body?.getReader();
  if (!reader) throw new ApiError("The service returned an empty stream.");
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = /^event: (.*)$/m.exec(frame)?.[1];
      const data = JSON.parse(/^data: (.*)$/m.exec(frame)?.[1] ?? "{}") as {
        text?: string;
        detail?: string;
        title?: string;
        message?: string;
        status?: number;
        type?: string;
      };
      if (event === "delta" && data.text) onText(data.text);
      else if (event === "status" && data.message) onStatus?.(data.message);
      else if (event === "error") throw new ApiError(data.detail || data.title || "The document was not completed.", data.status, data.type);
      else if (event === "done") return;
    }
  }
}

// ---- Exports -------------------------------------------------------------------

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** Save a generated file to the user's computer. */
export function downloadFile(file: GeneratedFile): void {
  saveBlob(file.blob, file.filename);
}

function filenameFrom(response: Response, fallback: string): string {
  const header = response.headers.get("Content-Disposition") ?? "";
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header)?.[1];
  if (encoded) return decodeURIComponent(encoded);
  return /filename="?([^";]+)"?/i.exec(header)?.[1] ?? fallback;
}

export type SectionsFormat = "docx" | "xlsx" | "csv" | "pdf";
export type MarkdownFormat = "docx" | "pdf";

/** Table sections as a document, via the API's shared exporters. */
export async function exportSections(
  title: string,
  subtitle: string,
  sections: ExportSection[],
  format: SectionsFormat,
  fileStub: string,
): Promise<GeneratedFile> {
  const response = await request(`/exports/sections?format=${format}`, {
    method: "POST",
    body: JSON.stringify({ title, subtitle, sections }),
  });
  return { blob: await response.blob(), filename: filenameFrom(response, `${fileStub}.${format}`) };
}

/** A Markdown document as Word or PDF, via the API's shared exporters. */
export async function exportMarkdown(markdown: string, title: string, format: MarkdownFormat, fileStub: string): Promise<GeneratedFile> {
  const response = await request(`/exports/markdown?format=${format}`, {
    method: "POST",
    body: JSON.stringify({ markdown, title }),
  });
  return { blob: await response.blob(), filename: filenameFrom(response, `${fileStub}.${format}`) };
}

/** A text file generated in the browser (Markdown, JSON). */
export function textFile(content: string, filename: string, mime: string): GeneratedFile {
  return { blob: new Blob([content], { type: mime }), filename };
}

/** "Bright Smiles" -> "Bright_Smiles", for download file names. */
export function fileStub(name: string, suffix: string): string {
  return `${(name.trim() || "client").replace(/\s+/g, "_")}_${suffix}`;
}
