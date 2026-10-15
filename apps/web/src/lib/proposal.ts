/**
 * The Proposal & SOW Builder's tables (columns over the API's snake_case
 * proposal rows), choice lists that mirror archscope_domain.proposal, and
 * the conversions between proposal rows and editable-table rows.
 */

import type { Column, Row } from "@/components/project/EditableTable";

import type { ProposalDocument } from "./api";

export const DOCUMENT_TYPES = ["Proposal + Statement of Work", "Proposal", "Statement of Work"];
export const SCOPE_STATUSES = ["In Scope", "Out of Scope", "Optional Add-on", "Client Responsibility"] as const;
export const CURRENCIES = ["USD", "CAD", "MXN", "EUR", "GBP"];
const SIDES = ["SonaMation", "Client", "Third Party"];
const LEVELS = ["Low", "Medium", "High"];

/** Switchable sections; the cover, Scope at a Glance and the three volumes always render. */
export const OPTIONAL_SECTIONS: Record<string, string> = {
  executive_summary: "Executive Summary",
  company_overview: "About SonaMation",
  glossary: "Glossary of Terms",
  kpis: "Targeted KPIs",
  risks: "Risk Management",
  addons: "Optional Add-on Services Menu",
  rate_card: "Rate Card (Change Requests)",
  signatures: "Acceptance & Signatures",
};

export const SCOPE_HINTS: Record<string, string> = {
  "In Scope": "Delivered, up to the stated limit.",
  "Out of Scope": "Not included — only via Change Request.",
  "Optional Add-on": "Pre-priced; the client can add it any time.",
  "Client Responsibility": "The client provides this.",
};

export type TableField =
  | "objectives"
  | "requirements"
  | "methodology"
  | "tools"
  | "techniques"
  | "glossary"
  | "scope"
  | "assumptions"
  | "team"
  | "governance"
  | "timeline"
  | "risks"
  | "kpis"
  | "milestones"
  | "addons"
  | "rate_card";

const wide = "minmax(220px, 2fr)";

export const TABLES: Record<TableField, Column[]> = {
  objectives: [
    { key: "objective", label: "Objective", kind: "textarea", width: wide },
    { key: "success_measure", label: "Success measure" },
  ],
  requirements: [
    { key: "id", label: "ID", width: "80px", placeholder: "auto" },
    { key: "requirement", label: "Requirement", kind: "textarea", width: wide },
    { key: "priority", label: "Priority", kind: "select", options: ["Must Have", "Should Have", "Nice to Have", "To Confirm"], width: "150px" },
    { key: "source", label: "Source", width: "minmax(140px, 1fr)" },
  ],
  methodology: [
    { key: "phase", label: "Phase", width: "minmax(140px, 1fr)" },
    { key: "activities", label: "Activities", kind: "textarea", width: wide },
    { key: "outputs", label: "Outputs", kind: "textarea", width: wide },
  ],
  tools: [
    { key: "tool", label: "Tool" },
    { key: "purpose", label: "Purpose", width: "minmax(180px, 1.6fr)" },
    { key: "provided_by", label: "Provided by", kind: "select", options: SIDES, width: "140px" },
  ],
  techniques: [
    { key: "technique", label: "Technique" },
    { key: "how_applied", label: "How it is applied", kind: "textarea", width: wide },
  ],
  glossary: [
    { key: "term", label: "Term", width: "220px" },
    { key: "definition", label: "Definition", kind: "textarea", width: wide },
  ],
  scope: [
    { key: "id", label: "ID", width: "70px", placeholder: "auto" },
    { key: "status", label: "Status", kind: "select", options: [...SCOPE_STATUSES], width: "170px" },
    { key: "workstream", label: "Workstream", width: "140px" },
    { key: "item", label: "Item", kind: "textarea", width: wide },
    { key: "quantity_limit", label: "Quantity / limit", width: "150px" },
    { key: "acceptance_criteria", label: "Acceptance criteria", kind: "textarea", width: wide },
    { key: "requirement_ids", label: "Req. ID", width: "100px", placeholder: "R-1, R-3" },
    { key: "milestone", label: "Milestone", width: "130px" },
    { key: "tools_techniques", label: "Tools / techniques", width: "160px" },
  ],
  assumptions: [{ key: "assumption", label: "Assumption", kind: "textarea", width: "minmax(320px, 1fr)" }],
  team: [
    { key: "side", label: "Side", kind: "select", options: SIDES, width: "140px" },
    { key: "role", label: "Role" },
    { key: "name", label: "Name" },
    { key: "email", label: "Email" },
    { key: "responsibilities", label: "Responsibilities", kind: "textarea", width: wide },
  ],
  governance: [
    { key: "meeting", label: "Meeting" },
    { key: "cadence", label: "Cadence", width: "130px" },
    { key: "participants", label: "Participants" },
    { key: "purpose", label: "Purpose", kind: "textarea", width: wide },
  ],
  timeline: [
    { key: "phase", label: "Phase" },
    { key: "start", label: "Start", width: "130px" },
    { key: "end", label: "End", width: "130px" },
    { key: "key_deliverables", label: "Key deliverables", kind: "textarea", width: wide },
  ],
  risks: [
    { key: "risk", label: "Risk", kind: "textarea", width: "minmax(180px, 1.4fr)" },
    { key: "likelihood", label: "Likelihood", kind: "select", options: LEVELS, width: "120px" },
    { key: "impact", label: "Impact", kind: "select", options: LEVELS, width: "120px" },
    { key: "mitigation", label: "Mitigation", kind: "textarea", width: wide },
    { key: "owner", label: "Owner", width: "130px" },
  ],
  kpis: [
    { key: "type", label: "Type", kind: "select", options: ["Primary", "Secondary"], width: "130px" },
    { key: "kpi", label: "KPI" },
    { key: "definition", label: "Definition", kind: "textarea", width: wide },
    { key: "target", label: "Target", width: "140px" },
  ],
  milestones: [
    { key: "milestone", label: "Milestone" },
    { key: "deliverables", label: "Deliverables", kind: "textarea", width: wide },
    { key: "start_on_or_before", label: "Start on/before", width: "140px" },
    { key: "due_on_or_before", label: "Due on/before", width: "140px" },
    { key: "fee", label: "Fee", kind: "number", width: "120px" },
  ],
  addons: [
    { key: "service", label: "Service" },
    { key: "includes", label: "Includes", kind: "textarea", width: wide },
    { key: "cost", label: "Cost", kind: "number", width: "110px" },
    { key: "billing", label: "Billing", kind: "select", options: ["One Time", "Monthly", "Per Unit", "Per Year", "Hourly"], width: "130px" },
    { key: "add_to_total", label: "Add to total", kind: "checkbox", width: "110px" },
  ],
  rate_card: [
    { key: "role", label: "Role", width: "minmax(180px, 2fr)" },
    { key: "hourly_rate", label: "Hourly rate", kind: "number", width: "140px" },
  ],
};

const ID_PREFIX: Partial<Record<TableField, string>> = { requirements: "R", scope: "S" };
const ID_RE = /^\s*([A-Za-z]+)\s*-\s*0*(\d+)\s*$/;

/**
 * Give every requirement / scope row without an ID the next free R-N / S-N
 * (after the numbers already used, so existing references never change) —
 * the same rule the API uses when it numbers rows for the PDF.
 */
export function assignIds(field: TableField, rows: Row[]): Row[] {
  const prefix = ID_PREFIX[field];
  if (!prefix) return rows;
  const used = new Set<number>();
  for (const row of rows) {
    const m = ID_RE.exec(String(row.id ?? ""));
    if (m && m[1]?.toUpperCase() === prefix) used.add(Number(m[2]));
  }
  let n = 0;
  return rows.map((row) => {
    if (String(row.id ?? "").trim()) return row;
    n += 1;
    while (used.has(n)) n += 1;
    used.add(n);
    return { ...row, id: `${prefix}-${n}` };
  });
}

/** Proposal rows → editable rows (numbers shown as text, missing cells blank). */
export function toRows(doc: ProposalDocument, field: TableField): Row[] {
  const rows = (doc[field] ?? []) as Record<string, unknown>[];
  return rows.map((r) =>
    Object.fromEntries(
      TABLES[field].map((c) => [c.key, c.kind === "checkbox" ? r[c.key] === true : r[c.key] == null ? "" : String(r[c.key])]),
    ),
  );
}

/** Editable rows → proposal rows (number columns parsed; blanks become 0). */
export function fromRows(field: TableField, rows: Row[]): Record<string, unknown>[] {
  return rows.map((r) =>
    Object.fromEntries(
      TABLES[field].map((c) => {
        const v = r[c.key];
        if (c.kind === "number") {
          const n = Number.parseFloat(String(v ?? "").replace(/[,$]/g, ""));
          return [c.key, Number.isFinite(n) ? n : 0];
        }
        return [c.key, c.kind === "checkbox" ? v === true : String(v ?? "")];
      }),
    ),
  );
}

export function money(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: currency || "USD" }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}
