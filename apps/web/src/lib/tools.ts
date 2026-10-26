/**
 * The workspace tools behind the rail's Implementation, Data, Service,
 * Marketing and Developers pages (first versions). Most are a tracker: an
 * editable table saved for the whole workspace, with a few headline figures
 * computed from its rows. Three read real project data instead
 * (``dataPage``). Each tool's columns, statuses and figures live here so a
 * page can grow into its own design later without touching the others.
 */

import type { Column, Row } from "@/components/project/EditableTable";

import type { NavIconName } from "@/components/NavIcons";

export type Stat = { label: string; value: (rows: Row[]) => string | number };

export type Tool = {
  slug: string;
  title: string;
  section: string;
  icon: NavIconName;
  description: string;
  /** Read-only pages over real project data, with their own component. */
  dataPage?: "implementation-dashboard" | "database" | "data-documentation" | "data-migration";
  columns?: Column[];
  /** Singular name for the "+ Add …" button. */
  noun?: string;
  stats?: Stat[];
};

const text = (r: Row, k: string) => String(r[k] ?? "").trim();
const num = (r: Row, k: string) => Number.parseFloat(String(r[k] ?? "").replace(/[,$]/g, "")) || 0;
const count = (key: string, ...values: string[]) => (rows: Row[]) => rows.filter((r) => values.includes(text(r, key))).length;
const filled = (key: string) => (rows: Row[]) => rows.filter((r) => text(r, key)).length;
/** Rows whose date column falls within the next ``days`` days (today included). */
const within = (key: string, days: number, unless?: [string, string]) => (rows: Row[]) => {
  const today = new Date(new Date().toDateString()).getTime();
  return rows.filter((r) => {
    if (unless && text(r, unless[0]) === unless[1]) return false;
    const t = Date.parse(text(r, key));
    return Number.isFinite(t) && t >= today && t <= today + days * 86_400_000;
  }).length;
};
const money = (n: number) => new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
const wide = "minmax(220px, 2fr)";

export const TOOLS: Tool[] = [
  // ---- Implementation ----
  {
    slug: "implementation-dashboard",
    title: "Implementation Dashboard",
    section: "Implementation",
    icon: "layout",
    description: "Every implementation at a glance: stage, scoping progress, portal health and open tasks.",
    dataPage: "implementation-dashboard",
  },
  {
    slug: "schedule",
    title: "Schedule",
    section: "Implementation",
    icon: "cal",
    description: "Milestones, workshops and go-lives across every project, in one list.",
    noun: "date",
    columns: [
      { key: "date", label: "Date", kind: "date", width: "150px" },
      { key: "project", label: "Project", width: "minmax(140px, 1fr)" },
      { key: "item", label: "What", kind: "textarea", width: wide },
      { key: "type", label: "Type", kind: "select", options: ["Milestone", "Workshop", "Review", "Training", "Go-live"], width: "140px" },
      { key: "owner", label: "Owner", width: "140px" },
      { key: "status", label: "Status", kind: "select", options: ["Planned", "Done", "Moved"], width: "120px" },
    ],
    stats: [
      { label: "Planned", value: count("status", "Planned") },
      { label: "Next 14 days", value: within("date", 14, ["status", "Done"]) },
      { label: "Go-lives", value: count("type", "Go-live") },
      { label: "Done", value: count("status", "Done") },
    ],
  },
  {
    slug: "review-feedback",
    title: "Review & Feedback",
    section: "Implementation",
    icon: "chat",
    description: "Client reviews and sign-offs on deliverables: who's reviewing what, and what they said.",
    noun: "review",
    columns: [
      { key: "project", label: "Project", width: "minmax(140px, 1fr)" },
      { key: "deliverable", label: "Deliverable", width: "minmax(160px, 1.2fr)" },
      { key: "reviewer", label: "Reviewer", width: "140px" },
      { key: "requested", label: "Requested", kind: "date", width: "150px" },
      { key: "status", label: "Status", kind: "select", options: ["Requested", "In review", "Changes requested", "Approved"], width: "170px" },
      { key: "feedback", label: "Feedback", kind: "textarea", width: wide },
    ],
    stats: [
      { label: "Waiting", value: count("status", "Requested", "In review") },
      { label: "Changes requested", value: count("status", "Changes requested") },
      { label: "Approved", value: count("status", "Approved") },
    ],
  },
  // ---- Data ----
  {
    slug: "database",
    title: "Database",
    section: "Data",
    icon: "db",
    description: "Browse the HubSpot objects, pipelines and owners captured in a project's read-only portal snapshot.",
    dataPage: "database",
  },
  {
    slug: "data-documentation",
    title: "Data Documentation",
    section: "Data",
    icon: "files",
    description: "A data dictionary for each portal: every property of an object with its label, internal name, type and group.",
    dataPage: "data-documentation",
  },
  {
    slug: "data-migration",
    title: "Data Migration",
    section: "Data",
    icon: "upload",
    description:
      "Clean a client's CSV or Excel export for a HubSpot import: pick each column's format, and get back a CSV that imports without errors.",
    dataPage: "data-migration",
  },
  {
    slug: "ai-guide",
    title: "AI Guide",
    section: "Data",
    icon: "spark",
    description: "A shared set of questions and answers about clients' data models, so the team stops re-asking the same things.",
    noun: "question",
    columns: [
      { key: "question", label: "Question", kind: "textarea", width: wide },
      { key: "answer", label: "Answer", kind: "textarea", width: wide },
      { key: "object", label: "Object", width: "130px" },
      { key: "client", label: "Client", width: "140px" },
    ],
    stats: [
      { label: "Questions", value: (rows) => rows.length },
      { label: "Answered", value: filled("answer") },
      { label: "Open", value: (rows) => rows.filter((r) => !text(r, "answer")).length },
    ],
  },
  {
    slug: "data-management",
    title: "Data Management",
    section: "Data",
    icon: "sliders",
    description: "Data-quality issues and clean-up plans across clients' portals.",
    noun: "issue",
    columns: [
      { key: "client", label: "Client", width: "140px" },
      { key: "issue", label: "Issue", kind: "textarea", width: wide },
      { key: "object", label: "Object", width: "120px" },
      { key: "severity", label: "Severity", kind: "select", options: ["High", "Medium", "Low"], width: "120px" },
      { key: "owner", label: "Owner", width: "130px" },
      { key: "status", label: "Status", kind: "select", options: ["Open", "In progress", "Resolved"], width: "140px" },
      { key: "plan", label: "Clean-up plan", kind: "textarea", width: wide },
    ],
    stats: [
      { label: "Open", value: count("status", "Open", "In progress") },
      { label: "High severity open", value: (rows) => rows.filter((r) => text(r, "severity") === "High" && text(r, "status") !== "Resolved").length },
      { label: "Resolved", value: count("status", "Resolved") },
    ],
  },
  // ---- Service ----
  {
    slug: "customer-success",
    title: "Customer Success",
    section: "Service",
    icon: "heart",
    description: "Each client's health, renewal date and next step, so nobody is surprised by a renewal.",
    noun: "client",
    columns: [
      { key: "client", label: "Client", width: "minmax(140px, 1fr)" },
      { key: "health", label: "Health", kind: "select", options: ["Healthy", "At risk", "Critical"], width: "130px" },
      { key: "renewal", label: "Renewal", kind: "date", width: "150px" },
      { key: "owner", label: "Owner", width: "130px" },
      { key: "next_step", label: "Next step", kind: "textarea", width: wide },
      { key: "notes", label: "Notes", kind: "textarea", width: wide },
    ],
    stats: [
      { label: "Clients", value: (rows) => rows.length },
      { label: "At risk or critical", value: count("health", "At risk", "Critical") },
      { label: "Renewals in 90 days", value: within("renewal", 90) },
    ],
  },
  {
    slug: "knowledge-base",
    title: "Knowledge Base",
    section: "Service",
    icon: "book",
    description: "The team's reusable articles, playbooks and how-tos.",
    noun: "article",
    columns: [
      { key: "title", label: "Title", width: "minmax(180px, 1.2fr)" },
      { key: "category", label: "Category", kind: "select", options: ["Playbook", "How-to", "Template", "Reference"], width: "140px" },
      { key: "content", label: "Content", kind: "textarea", width: "minmax(300px, 3fr)" },
      { key: "owner", label: "Owner", width: "130px" },
      { key: "updated", label: "Updated", kind: "date", width: "150px" },
    ],
    stats: [
      { label: "Articles", value: (rows) => rows.length },
      { label: "Playbooks", value: count("category", "Playbook") },
      { label: "How-tos", value: count("category", "How-to") },
    ],
  },
  {
    slug: "subscriptions",
    title: "Subscriptions & Memberships",
    section: "Service",
    icon: "card",
    description: "Client retainers, subscriptions and memberships: what each pays, how often, and when it renews.",
    noun: "subscription",
    columns: [
      { key: "client", label: "Client", width: "minmax(140px, 1fr)" },
      { key: "plan", label: "Plan / service", width: "minmax(160px, 1.2fr)" },
      { key: "type", label: "Type", kind: "select", options: ["Retainer", "Subscription", "Membership"], width: "140px" },
      { key: "amount", label: "Amount", kind: "number", width: "120px" },
      { key: "billing", label: "Billing", kind: "select", options: ["Monthly", "Quarterly", "Yearly"], width: "130px" },
      { key: "renews", label: "Renews", kind: "date", width: "150px" },
      { key: "status", label: "Status", kind: "select", options: ["Active", "Paused", "Cancelled"], width: "130px" },
    ],
    stats: [
      { label: "Active", value: count("status", "Active") },
      {
        label: "Monthly recurring",
        value: (rows) =>
          money(
            rows
              .filter((r) => text(r, "status") === "Active")
              .reduce((sum, r) => sum + num(r, "amount") / ({ Quarterly: 3, Yearly: 12 }[text(r, "billing")] ?? 1), 0),
          ),
      },
      { label: "Renewals in 30 days", value: within("renews", 30, ["status", "Cancelled"]) },
    ],
  },
  // ---- Marketing ----
  {
    slug: "marketing-dashboard",
    title: "Marketing Dashboard",
    section: "Marketing",
    icon: "layout",
    description: "Campaign results across clients: leads, MQLs, spend and cost per lead.",
    noun: "campaign",
    columns: [
      { key: "client", label: "Client", width: "minmax(130px, 1fr)" },
      { key: "campaign", label: "Campaign", width: "minmax(160px, 1.2fr)" },
      { key: "channel", label: "Channel", kind: "select", options: ["Email", "Paid", "Social", "SEO", "Events"], width: "120px" },
      { key: "period", label: "Period", width: "120px", placeholder: "e.g. Oct 2026" },
      { key: "leads", label: "Leads", kind: "number", width: "100px" },
      { key: "mqls", label: "MQLs", kind: "number", width: "100px" },
      { key: "spend", label: "Spend", kind: "number", width: "120px" },
    ],
    stats: [
      { label: "Leads", value: (rows) => rows.reduce((s, r) => s + num(r, "leads"), 0) },
      { label: "MQLs", value: (rows) => rows.reduce((s, r) => s + num(r, "mqls"), 0) },
      { label: "Spend", value: (rows) => money(rows.reduce((s, r) => s + num(r, "spend"), 0)) },
      {
        label: "Cost per lead",
        value: (rows) => {
          const leads = rows.reduce((s, r) => s + num(r, "leads"), 0);
          return leads ? money(rows.reduce((s, r) => s + num(r, "spend"), 0) / leads) : "-";
        },
      },
    ],
  },
  {
    slug: "leads",
    title: "Leads",
    section: "Marketing",
    icon: "userplus",
    description: "New business leads: where they came from, who owns them and how far they've got.",
    noun: "lead",
    columns: [
      { key: "name", label: "Name", width: "minmax(140px, 1fr)" },
      { key: "company", label: "Company", width: "minmax(140px, 1fr)" },
      { key: "source", label: "Source", kind: "select", options: ["Referral", "Website", "Event", "Partner", "Outbound"], width: "130px" },
      { key: "owner", label: "Owner", width: "130px" },
      { key: "status", label: "Status", kind: "select", options: ["New", "Working", "Qualified", "Disqualified"], width: "140px" },
      { key: "created", label: "Created", kind: "date", width: "150px" },
      { key: "notes", label: "Notes", kind: "textarea", width: wide },
    ],
    stats: [
      { label: "New", value: count("status", "New") },
      { label: "Working", value: count("status", "Working") },
      { label: "Qualified", value: count("status", "Qualified") },
      { label: "Total", value: (rows) => rows.length },
    ],
  },
  {
    slug: "studio",
    title: "Studio",
    section: "Marketing",
    icon: "wand",
    description: "Campaign assets and content in progress, from idea to approved.",
    noun: "piece",
    columns: [
      { key: "title", label: "Title", width: "minmax(160px, 1.2fr)" },
      { key: "client", label: "Client", width: "140px" },
      { key: "type", label: "Type", kind: "select", options: ["Email", "Landing page", "Blog post", "Ad", "Social post"], width: "140px" },
      { key: "status", label: "Status", kind: "select", options: ["Idea", "Drafting", "In review", "Approved"], width: "130px" },
      { key: "draft", label: "Draft", kind: "textarea", width: "minmax(300px, 3fr)" },
    ],
    stats: [
      { label: "Ideas", value: count("status", "Idea") },
      { label: "In progress", value: count("status", "Drafting", "In review") },
      { label: "Approved", value: count("status", "Approved") },
    ],
  },
  {
    slug: "social",
    title: "Social",
    section: "Marketing",
    icon: "share",
    description: "A social content calendar: what goes out, where, and when.",
    noun: "post",
    columns: [
      { key: "date", label: "Date", kind: "date", width: "150px" },
      { key: "client", label: "Client", width: "140px" },
      { key: "channel", label: "Channel", kind: "select", options: ["LinkedIn", "Instagram", "Facebook", "X", "TikTok"], width: "130px" },
      { key: "copy", label: "Copy", kind: "textarea", width: "minmax(300px, 3fr)" },
      { key: "status", label: "Status", kind: "select", options: ["Draft", "Scheduled", "Posted"], width: "130px" },
    ],
    stats: [
      { label: "Drafts", value: count("status", "Draft") },
      { label: "Scheduled", value: count("status", "Scheduled") },
      { label: "Next 7 days", value: within("date", 7, ["status", "Posted"]) },
      { label: "Posted", value: count("status", "Posted") },
    ],
  },
  // ---- Developers ----
  {
    slug: "integrations",
    title: "Integrations",
    section: "Developers",
    icon: "plug",
    description: "The other systems each client connects to HubSpot, which way data flows, and whether it works.",
    noun: "integration",
    columns: [
      { key: "client", label: "Client", width: "140px" },
      { key: "system", label: "System", width: "minmax(140px, 1fr)" },
      { key: "direction", label: "Direction", kind: "select", options: ["Into HubSpot", "Out of HubSpot", "Two-way"], width: "150px" },
      { key: "objects", label: "Objects synced", width: "minmax(140px, 1fr)" },
      { key: "status", label: "Status", kind: "select", options: ["Planned", "Building", "Live", "Broken"], width: "120px" },
      { key: "owner", label: "Owner", width: "130px" },
      { key: "notes", label: "Notes", kind: "textarea", width: wide },
    ],
    stats: [
      { label: "Live", value: count("status", "Live") },
      { label: "Building", value: count("status", "Planned", "Building") },
      { label: "Broken", value: count("status", "Broken") },
    ],
  },
  {
    slug: "webhooks",
    title: "Webhooks",
    section: "Developers",
    icon: "share",
    description: "Where other tools should hear about changes here. A registry for now: nothing is sent yet.",
    noun: "webhook",
    columns: [
      { key: "name", label: "Name", width: "minmax(140px, 1fr)" },
      {
        key: "event",
        label: "When",
        kind: "select",
        options: ["Project created", "Document saved", "Task completed", "Proposal ready to send"],
        width: "200px",
      },
      { key: "url", label: "Send to (URL)", width: "minmax(220px, 2fr)", placeholder: "https://…" },
      { key: "status", label: "Status", kind: "select", options: ["Paused", "Active"], width: "120px" },
      { key: "notes", label: "Notes", kind: "textarea", width: wide },
    ],
    stats: [
      { label: "Webhooks", value: (rows) => rows.length },
      { label: "Active", value: count("status", "Active") },
    ],
  },
  {
    slug: "logs",
    title: "Logs",
    section: "Developers",
    icon: "term",
    description: "A running log of integration runs, imports and incidents. Entered by hand for now.",
    noun: "entry",
    columns: [
      { key: "date", label: "Date", kind: "date", width: "150px" },
      { key: "source", label: "Source", kind: "select", options: ["API", "Integration", "Import", "Job", "Person"], width: "140px" },
      { key: "event", label: "Event", width: "minmax(180px, 1.5fr)" },
      { key: "status", label: "Status", kind: "select", options: ["Success", "Warning", "Error"], width: "120px" },
      { key: "details", label: "Details", kind: "textarea", width: wide },
    ],
    stats: [
      { label: "Entries", value: (rows) => rows.length },
      { label: "Warnings", value: count("status", "Warning") },
      { label: "Errors", value: count("status", "Error") },
    ],
  },
];

export const toolBySlug = (slug: string) => TOOLS.find((t) => t.slug === slug);
