"use client";

/**
 * Proposal & SOW Builder: turns the Requirements Document and Joint
 * Evaluation Plan into a seller's proposal and/or Statement of Work —
 * technical approach, scope (every item In / Out / Optional / Client),
 * management approach and cost — then a branded PDF. The proposal is
 * saved to the project; all merge, pricing and coverage logic is the
 * API's. Commercial sections (executive summary at a glance, workstream
 * pricing, recurring fees, payment schedule, responsibilities, a week-based
 * timeline, acceptance evidence, data-quality issues, the subscription-tier
 * assumption) can be pre-filled from earlier steps, and the SOW can only be
 * marked "Ready to send" once the API's readiness checks pass.
 */

import { useEffect, useId, useState } from "react";

import { useAppSession } from "@/components/AppSession";
import { AssistButton } from "@/components/AssistButton";
import { IndustryTemplatePicker } from "@/components/IndustryTemplatePicker";
import { TokenSelect } from "@/components/discovery/QuestionCard";
import { DataTable } from "@/components/project/DataTable";
import { EditableTable } from "@/components/project/EditableTable";
import { ProjectHeader } from "@/components/project/ProjectHeader";
import { ProposalTemplatesBar } from "@/components/project/ProposalTemplatesBar";
import { SaveBanner } from "@/components/project/SaveBanner";
import { Stats } from "@/components/project/Stats";
import { normalizeDocument } from "@/components/project/TableDocument";
import { TermsTab } from "@/components/project/TermsTab";
import { TimelinePreview } from "@/components/project/TimelinePreview";
import { Callout, Checkbox, ExportFooter, TabPanel, Tabs } from "@/components/ui";
import {
  addLibraryAddons,
  addScopeLibraryItems,
  analyseProposal,
  ApiError,
  applyIndustryProposalTemplate,
  assistProposal,
  defaultProposal,
  downloadFile,
  draftScopeFromRequirements,
  getModuleState,
  importJepIntoProposal,
  prefillProposal,
  importWrdIntoProposal,
  proposalLibraries,
  proposalPdf,
  proposalTemplate,
  textFile,
  type Project,
  type ProposalAnalysis,
  type ProposalDocument,
  type ProposalLibraries,
  type ScopeStatus,
} from "@/lib/api";
import { projectContext } from "@/lib/assist";
import { JOINT_EVALUATION_PLAN, REQUIREMENTS_DOCUMENT } from "@/lib/documents";
import { useModuleState, type ModuleStore } from "@/lib/module-state";
import {
  assignIds,
  CURRENCIES,
  DOCUMENT_TYPES,
  DUE_TERMS,
  fromRows,
  INVOICING_OPTIONS,
  money,
  OPTIONAL_SECTIONS,
  SCOPE_HINTS,
  SCOPE_STATUSES,
  STATUS_READY,
  TABLES,
  toRows,
  type TableField,
} from "@/lib/proposal";
import { Glyph } from "@/components/icons";

type ProposalState = { doc: ProposalDocument | null };
const normalizeProposal = (raw: unknown): ProposalState => ({ doc: ((raw as ProposalState | null)?.doc ?? null) as ProposalDocument | null });

/** The proposal addressed to ``company`` (every party field kept, blanks filled). */
function addressedTo(doc: ProposalDocument, company: string): ProposalDocument {
  const c = doc.client;
  return { ...doc, client: { address: c?.address ?? "", contact: c?.contact ?? "", email: c?.email ?? "", phone: c?.phone ?? "", company } };
}

type TabId = "setup" | "technical" | "scope" | "management" | "cost" | "terms" | "review";
type Store = ModuleStore<ProposalState>;
type Props = { doc: ProposalDocument; set: (patch: Partial<ProposalDocument>) => void };

const TEXT_FIELDS = [
  "executive_summary",
  "exec_key_risks",
  "exec_dependencies",
  "tier_assumption",
  "timeline_buffer_label",
  "company_overview",
  "problem_statement",
  "current_state",
  "solution_overview",
  "change_process",
  "acceptance_process",
  "payment_terms",
  "expenses",
  "confidentiality",
  "title",
  "reference_number",
] as const;
type TextField = (typeof TEXT_FIELDS)[number];

function Text({ doc, set, field, label, rows, placeholder, help }: Props & { field: TextField; label: string; rows?: number; placeholder?: string; help?: string }) {
  const value = String(doc[field] ?? "");
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {rows ? (
        <textarea className="textarea" rows={rows} placeholder={placeholder} value={value} onChange={(e) => set({ [field]: e.target.value })} />
      ) : (
        <input className="input" placeholder={placeholder} value={value} onChange={(e) => set({ [field]: e.target.value })} />
      )}
      {help && <span className="t-caption">{help}</span>}
    </label>
  );
}

function DateField({ doc, set, field, label }: Props & { field: "issue_date" | "effective_date" | "expiration_date" | "valid_until"; label: string }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <input type="date" className="input" value={String(doc[field] ?? "").slice(0, 10)} onChange={(e) => set({ [field]: e.target.value })} />
    </label>
  );
}

function Table({ doc, set, field, title, caption, addLabel }: Props & { field: TableField; title: string; caption?: string; addLabel?: string }) {
  return (
    <div className="stack" style={{ gap: 8 }}>
      <h3 className="t-card-title">{title}</h3>
      {caption && <span className="t-caption">{caption}</span>}
      <EditableTable
        columns={TABLES[field]}
        rows={assignIds(field, toRows(doc, field))}
        onChange={(rows) => set({ [field]: fromRows(field, assignIds(field, rows)) } as Partial<ProposalDocument>)}
        label={title}
        addLabel={addLabel}
      />
    </div>
  );
}

function Select({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o}>{o}</option>
        ))}
      </select>
    </label>
  );
}

type PaymentSchedule = { deposit_type: "Percent" | "Amount"; deposit_value: number; invoicing: string; due_terms: string; notes: string };

/** The payment schedule with every field present (older proposals may lack it). */
function schedule(doc: ProposalDocument): PaymentSchedule {
  const p = doc.payment_schedule;
  return {
    deposit_type: p?.deposit_type ?? "Percent",
    deposit_value: p?.deposit_value ?? 0,
    invoicing: p?.invoicing ?? "",
    due_terms: p?.due_terms ?? "",
    notes: p?.notes ?? "",
  };
}

/** A text field with suggestions (any value can be typed). */
function ChoiceInput({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  const id = useId();
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <input className="input" list={id} value={value} placeholder="Choose or type" onChange={(e) => onChange(e.target.value)} />
      <datalist id={id}>
        {options.map((o) => (
          <option key={o} value={o} />
        ))}
      </datalist>
    </label>
  );
}

// ---- Setup ----------------------------------------------------------------------------

const PARTY_FIELDS = [
  ["company", "Company"],
  ["contact", "Primary contact"],
  ["address", "Address"],
  ["phone", "Phone"],
  ["email", "Email"],
] as const;

const SUGGESTED_PARTS: Record<string, string> = {
  executive_summary: "executive summary",
  problem_statement: "problem statement",
  current_state: "current state",
  solution_overview: "proposed solution",
  objectives: "objectives",
  scope: "scope items",
  assumptions: "assumptions",
  risks: "risks",
  kpis: "KPIs",
  glossary: "glossary",
  exec_key_risks: "key risks",
  exec_dependencies: "dependencies",
  client_responsibilities: "client responsibilities",
  vendor_responsibilities: "SonaMation responsibilities",
  data_quality: "data-quality issues",
  timeline: "timeline",
};

/** The fees shown up front: one-time, then each recurring period (never added together). */
function investment(analysis: ProposalAnalysis | null, currency: string): string {
  const pricing = analysis?.pricing;
  if (!pricing) return "…";
  const recurring = Object.entries(pricing.recurring ?? {}).map(([period, amount]) => ` + ${money(Number(amount), currency)} ${period.toLowerCase()}`);
  return `${money(pricing.total, currency)} one-time${recurring.join("")}`;
}

function Setup({
  doc,
  set,
  project,
  apply,
  busy,
  suggest,
  applyTemplate,
  analysis,
}: Props & {
  analysis: ProposalAnalysis | null;
  project: Project;
  apply: (label: string, work: () => Promise<ProposalDocument>) => void;
  busy: boolean;
  suggest: () => Promise<string>;
  applyTemplate: (industry: string, size: string | null) => Promise<string>;
}) {
  const clientName = project.client_name || project.name;
  const sections = async (def: typeof REQUIREMENTS_DOCUMENT) => {
    const saved = await getModuleState(project.id, def.module);
    const rows = def.exportSections(normalizeDocument(def, saved.data && Object.keys(saved.data).length ? saved.data : null), clientName);
    const filled = rows.filter((s) => (s.rows ?? []).length);
    if (!filled.length) throw new ApiError(`This project's ${def.title} is empty — fill it in first.`);
    return Object.fromEntries(filled.map((s) => [s.title, s.rows ?? []]));
  };
  const [fileError, setFileError] = useState<string | null>(null);

  return (
    <div className="stack" style={{ gap: 24 }}>
      <div className="card stack" style={{ gap: 12 }}>
        <span className="t-card-title">Start from existing work</span>
        <AssistButton label="Suggest a starting point" variant="primary" run={suggest} disabled={busy} />
        <IndustryTemplatePicker apply={applyTemplate} disabled={busy} />
        <div className="row">
          <button
            type="button"
            className="btn btn-secondary"
            disabled={busy}
            onClick={() =>
              apply("Imported the Requirements Document", async () => {
                const merged = await importWrdIntoProposal(doc, await sections(REQUIREMENTS_DOCUMENT));
                return merged.client?.company ? merged : addressedTo(merged, clientName);
              })
            }
          >
            Import Requirements Document
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={busy}
            onClick={() => apply("Imported the Joint Evaluation Plan", async () => importJepIntoProposal(doc, await sections(JOINT_EVALUATION_PLAN), clientName))}
          >
            Import Joint Evaluation Plan
          </button>
          <button
            type="button"
            className="btn-link"
            disabled={busy}
            onClick={() => {
              if (window.confirm("Replace this proposal with SonaMation's defaults? Everything typed here is cleared.")) {
                apply("Reset to SonaMation defaults", async () => {
                  return addressedTo(await defaultProposal(), clientName);
                });
              }
            }}
          >
            Reset to SonaMation defaults
          </button>
        </div>
        <label className="field">
          <span className="field-label">Or load a saved proposal / template (.json)</span>
          <input
            type="file"
            accept="application/json,.json"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (!file) return;
              setFileError(null);
              try {
                const loaded = JSON.parse(await file.text()) as ProposalDocument;
                apply(`Loaded ${file.name}`, async () => {
                  await analyseProposal(loaded); // validates the shape before it replaces anything
                  return loaded;
                });
              } catch {
                setFileError("That file isn't a proposal saved from this builder.");
              }
            }}
          />
        </label>
        {fileError && <Callout tone="error" title="Couldn't load the file">{fileError}</Callout>}
      </div>

      <section className="card commercial-settings" aria-label="Commercial settings">
        <div className="grid-3">
          <label className="field">
            <span className="field-label">Client / project</span>
            <input
              className="input"
              value={doc.client?.company ?? ""}
              onChange={(e) => set({ client: { address: "", contact: "", email: "", phone: "", ...doc.client, company: e.target.value } })}
            />
          </label>
          <Select label="Document type" value={doc.document_type || DOCUMENT_TYPES[0]} options={DOCUMENT_TYPES} onChange={(v) => set({ document_type: v as ProposalDocument["document_type"] })} />
          <Text doc={doc} set={set} field="title" label="Proposal title" />
        </div>
        <div className="grid-3">
          <Select label="Currency" value={doc.currency || "USD"} options={CURRENCIES} onChange={(v) => set({ currency: v })} />
          <Text doc={doc} set={set} field="reference_number" label="Reference / SOW number" />
          <DateField doc={doc} set={set} field="valid_until" label="Proposal valid until" />
        </div>
        <div className="grid-3">
          <DateField doc={doc} set={set} field="issue_date" label="Issue date" />
          <DateField doc={doc} set={set} field="effective_date" label="Effective date" />
          <DateField doc={doc} set={set} field="expiration_date" label="Expiration date" />
        </div>
        <div className="stack" style={{ gap: 4 }}>
          <Checkbox checked={analysis?.is_migration ?? doc.is_migration === true} onChange={(on) => set({ is_migration: on })}>
            This project includes a data migration
          </Checkbox>
          <span className="t-caption">
            {doc.is_migration == null
              ? analysis?.migration_items.length
                ? `Suggested from the scope (${analysis.migration_items.join(", ")} mentions a migration or import).`
                : "Suggested from the scope: no scope item mentions a migration or import."
              : "Set by hand."}{" "}
            Migration projects need at least one data-quality issue (Management tab) before the SOW can be sent.
            {doc.is_migration != null && (
              <>
                {" "}
                <button type="button" className="btn-link" onClick={() => set({ is_migration: null })}>
                  Follow the scope again
                </button>
              </>
            )}
          </span>
        </div>
      </section>

      <section className="stack" style={{ gap: 12 }}>
        <h2 className="t-section">Addresses and contacts for notices</h2>
        <div className="grid-2" style={{ alignItems: "start" }}>
          {(["client", "seller"] as const).map((party) => (
            <div key={party} className="stack" style={{ gap: 10 }}>
              <span className="t-card-title">{party === "client" ? "Client" : "SonaMation"}</span>
              {PARTY_FIELDS.map(([key, label]) => (
                <label key={key} className="field">
                  <span className="field-label">{label}</span>
                  <input className="input" value={doc[party]?.[key] ?? ""} onChange={(e) => set({ [party]: { address: "", company: "", contact: "", email: "", phone: "", ...doc[party], [key]: e.target.value } })} />
                </label>
              ))}
            </div>
          ))}
        </div>
      </section>

      <section className="stack" style={{ gap: 12 }}>
        <h2 className="t-section">Executive summary</h2>
        <span className="t-caption">The first page a non-technical approver reads: plain language, no jargon.</span>
        <Text doc={doc} set={set} field="executive_summary" label="What's being done" rows={4} placeholder="Two or three sentences: the client's problem, what SonaMation will deliver, and the outcome." />
        <div className="grid-2" style={{ alignItems: "start" }}>
          <Text doc={doc} set={set} field="exec_key_risks" label="Key risks" rows={3} help="Left blank, the PDF lists the top risks from the Management tab." />
          <Text doc={doc} set={set} field="exec_dependencies" label="What delivery depends on" rows={3} help="Left blank, the PDF lists the first client responsibilities." />
        </div>
        <p className="t-caption">
          Total investment (from the Cost tab): <b>{investment(analysis, doc.currency || "USD")}</b>
        </p>
        <Text doc={doc} set={set} field="company_overview" label="About SonaMation (standard text)" rows={4} />
      </section>
    </div>
  );
}

// ---- Scope --------------------------------------------------------------------------

function ScopeTab({ doc, set, analysis, apply, busy, suggest }: Props & { analysis: ProposalAnalysis | null; apply: (label: string, work: () => Promise<ProposalDocument>) => void; busy: boolean; suggest: () => Promise<string> }) {
  const [libraries, setLibraries] = useState<ProposalLibraries | null>(null);
  const [items, setItems] = useState<string[]>([]);
  const [status, setStatus] = useState<ScopeStatus>("In Scope");
  const [addons, setAddons] = useState<string[]>([]);
  const itemsId = useId();
  const addonsId = useId();
  useEffect(() => {
    void proposalLibraries().then(setLibraries);
  }, []);

  const coverage = analysis?.coverage ?? [];
  const gaps = coverage.filter((r) => r.coverage === "Not covered").map((r) => r.id);

  return (
    <div className="stack" style={{ gap: 24 }}>

      {libraries && (
        <div className="card stack" style={{ gap: 12 }}>
          <span className="t-card-title">Add from the preset libraries</span>
          <div className="field">
            <span className="field-label" id={itemsId}>
              Common deliverables (phrased with limits and acceptance criteria)
            </span>
            <TokenSelect choices={libraries.scope.map((i) => i.item)} selected={items} onChange={setItems} labelId={itemsId} />
          </div>
          <div className="row">
            <select className="input" style={{ width: "auto" }} aria-label="Add deliverables as" value={status} onChange={(e) => setStatus(e.target.value as ScopeStatus)}>
              {SCOPE_STATUSES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={!items.length || busy}
              onClick={() => {
                apply(`Added ${items.length} deliverable${items.length === 1 ? "" : "s"} to scope`, () => addScopeLibraryItems(doc, items, status));
                setItems([]);
              }}
            >
              Add deliverables to scope
            </button>
          </div>
          <div className="field">
            <span className="field-label" id={addonsId}>
              Add-on services (added to the Cost menu and listed in scope as Optional Add-ons)
            </span>
            <TokenSelect choices={libraries.addons.map((a) => a.service)} selected={addons} onChange={setAddons} labelId={addonsId} />
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ width: "fit-content" }}
            disabled={!addons.length || busy}
            onClick={() => {
              apply(`Added ${addons.length} add-on service${addons.length === 1 ? "" : "s"}`, () => addLibraryAddons(doc, addons));
              setAddons([]);
            }}
          >
            Add services to the add-on menu
          </button>
        </div>
      )}

      <AssistButton label="Suggest scope from earlier steps" run={suggest} disabled={busy} />
      <div className="row">
        <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => apply("Drafted scope items for uncovered requirements", () => draftScopeFromRequirements(doc))}>
          Draft a scope item for every uncovered requirement
        </button>
      </div>

      <Table
        doc={doc}
        set={set}
        field="scope"
        title="Scope items"
        addLabel="+ Add scope item"
      />

      <section className="stack" style={{ gap: 12 }}>
        <h3 className="t-card-title">Preview — Scope at a Glance</h3>
        <div className="scope-buckets">
          {SCOPE_STATUSES.map((s) => {
            const rows = analysis?.scope_by_status?.[s] ?? [];
            return (
              <div key={s} className="scope-bucket" data-status={s}>
                <div className="scope-bucket-head">
                  {s} ({rows.length})<span>{SCOPE_HINTS[s]}</span>
                </div>
                <ul>
                  {rows.length ? (
                    rows.map((r, i) => (
                      <li key={`${r.id}-${i}`}>
                        <strong>{r.id}</strong> {r.item}
                        {r.quantity_limit && <span className="t-caption"> · {r.quantity_limit}</span>}
                      </li>
                    ))
                  ) : (
                    <li className="t-caption">Nothing listed</li>
                  )}
                </ul>
              </div>
            );
          })}
        </div>
      </section>

      <section className="stack" style={{ gap: 12 }}>
        <h3 className="t-card-title">Requirements coverage</h3>
        {coverage.length ? (
          <>
            <DataTable
              label="Requirements coverage"
              columns={[
                { key: "id", label: "ID", width: "80px" },
                { key: "requirement", label: "Requirement", width: "minmax(220px, 2fr)" },
                { key: "coverage", label: "Coverage", width: "170px" },
                { key: "scope", label: "Scope items", width: "minmax(120px, 1fr)" },
              ]}
              rows={coverage.map((r) => ({ id: r.id, requirement: r.requirement, coverage: r.coverage, scope: r.scope_items || "—" }))}
            />
            {gaps.length ? (
              <Callout tone="warning" title={`Not addressed by any scope item: ${gaps.join(", ")}`}>
                Put the requirement ID in the &lsquo;Req. ID&rsquo; column of the In Scope item that delivers it — or, if you&apos;re not doing it, of an Out of Scope item so the exclusion is stated explicitly.
              </Callout>
            ) : (
              <Callout tone="success" title="Every requirement is addressed by a scope item" />
            )}
          </>
        ) : (
          <span className="t-caption">Add requirements in the Technical tab to check coverage here.</span>
        )}
      </section>

      <Table doc={doc} set={set} field="assumptions" title="Assumptions" addLabel="+ Add assumption" />
      <Text
        doc={doc}
        set={set}
        field="tier_assumption"
        label="Subscription-tier assumption"
        rows={4}
        help="Replace the [[blank]] with the client's HubSpot hubs and tiers. The SOW can't be sent while a [[blank]] is left."
      />
      <Text doc={doc} set={set} field="change_process" label="Change Request process (standard text)" rows={5} />
    </div>
  );
}

// ---- Page -------------------------------------------------------------------------------

function Builder({ project, store }: { project: Project; store: Store }) {
  const doc = store.state.doc;
  const [tab, setTab] = useState<TabId>("setup");
  const [analysis, setAnalysis] = useState<ProposalAnalysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const { replace, change } = store;
  const clientName = project.client_name || project.name;

  // A new project starts from SonaMation's boilerplate, addressed to the client.
  useEffect(() => {
    if (doc) return;
    void defaultProposal().then((fresh) => replace({ doc: addressedTo(fresh, clientName) }));
  }, [doc, replace, clientName]);

  // A proposal saved before the commercial sections existed gets their defaults once (nothing typed is touched).
  const missing = doc ? (["client_responsibilities", "vendor_responsibilities", "tier_assumption", "payment_schedule", "timeline_buffer_weeks", "clauses"] as const).filter((k) => doc[k] === undefined) : [];
  useEffect(() => {
    if (!missing.length) return;
    void defaultProposal().then((fresh) =>
      change((s) => ({ doc: { ...Object.fromEntries(missing.map((k) => [k, fresh[k]])), ...(s.doc as ProposalDocument) } as ProposalDocument })),
    );
    // Runs when the set of missing fields changes (i.e. once per old proposal).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [missing.join()]);

  // "Ready to send" only holds while the checks pass; an edit that breaks one puts it back to Draft.
  useEffect(() => {
    if (doc?.status === STATUS_READY && analysis && analysis.readiness.length) {
      change((s) => ({ doc: { ...(s.doc as ProposalDocument), status: "Draft" } }));
    }
  }, [analysis, doc?.status, change]);

  useEffect(() => {
    if (!doc) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      analyseProposal(doc, controller.signal)
        .then(setAnalysis)
        .catch(() => undefined); // the last analysis stays; edits keep saving
    }, 400);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [doc]);

  if (!doc) return <div className="skeleton" style={{ height: 320 }} aria-busy="true" />;

  const set = (patch: Partial<ProposalDocument>) => change((s) => ({ doc: { ...(s.doc as ProposalDocument), ...patch } }));
  const apply = (label: string, work: () => Promise<ProposalDocument>) => {
    setBusy(true);
    setNotice(null);
    work()
      .then((next) => {
        replace({ doc: next });
        setNotice({ tone: "success", text: label });
      })
      .catch((e: unknown) => setNotice({ tone: "error", text: e instanceof ApiError ? e.message : "That didn't work." }))
      .finally(() => setBusy(false));
  };
  /** Draft blank sections from earlier steps; typed text is never replaced and rows already there are skipped. */
  const suggest = async () => {
    const result = await assistProposal(await projectContext(project.id, clientName), doc);
    if (!result.changed.length) return "Nothing to add: the proposal already covers what earlier steps mention.";
    replace({ doc: result.proposal });
    return `Suggested ${result.changed.map((c) => SUGGESTED_PARTS[c] ?? c).join(", ")}. Review and edit them in each tab.`;
  };
  /** Add an industry template's objectives, scope, assumptions, risks, KPIs and glossary (blanks only). */
  const applyTemplate = async (industry: string, size: string | null) => {
    const result = await applyIndustryProposalTemplate(industry, size, doc);
    if (!result.changed.length) return "Nothing to add: the proposal already has this template's rows.";
    replace({ doc: result.proposal });
    return `Added the template's ${result.changed.map((c) => SUGGESTED_PARTS[c] ?? c).join(", ")}.`;
  };
  /** Fill one section from earlier steps (the API merges; nothing typed is replaced). */
  const prefill = (label: string, part: "responsibilities" | "timeline" | "data_quality") =>
    apply(label, async () => {
      if (part !== "data_quality") return prefillProposal(doc, [part]);
      const portal = await getModuleState(project.id, "portal");
      const findings = (portal.data as { findings?: Record<string, unknown>[] } | null)?.findings ?? [];
      if (!findings.length) throw new ApiError("No portal audit findings yet: run the Portal Auditor first.");
      return prefillProposal(doc, ["data_quality"], findings);
    });
  const props = { doc, set };
  const currency = doc.currency || "USD";
  const pricing = analysis?.pricing;
  const stub = `${(doc.client?.company || clientName || "Client").trim()}_${doc.document_type || "Proposal"}`.replace(/\s+/g, "_").replace(/\+/g, "and");
  const count = (s: string) => analysis?.scope_by_status?.[s]?.length ?? 0;

  return (
    <>
      <ProposalTemplatesBar
        doc={doc}
        defaultName={clientName ? `${clientName} — ${doc.document_type || "Proposal"}` : ""}
        onApplied={(next) => replace({ doc: next })}
      />
      <Tabs<TabId>
        label="Proposal & SOW Builder"
        layoutId="proposal-tabs"
        variant="primary"
        tabs={[
          { id: "setup", label: "1 · Setup" },
          { id: "technical", label: "2 · Technical" },
          { id: "scope", label: "3 · Scope" },
          { id: "management", label: "4 · Management" },
          { id: "cost", label: "5 · Cost" },
          { id: "terms", label: "6 · Terms" },
          { id: "review", label: "7 · Review & generate" },
        ]}
        active={tab}
        onChange={(next) => {
          setTab(next);
          setNotice(null);
        }}
      />
      {notice && (
        <Callout tone={notice.tone} title={notice.tone === "success" ? notice.text : "Couldn't apply that"}>
          {notice.tone === "error" ? notice.text : undefined}
        </Callout>
      )}

      <TabPanel panelKey={tab} id="proposal-tabs">
        {tab === "setup" && <Setup {...props} project={project} apply={apply} busy={busy} suggest={suggest} applyTemplate={applyTemplate} analysis={analysis} />}

        {tab === "technical" && (
          <div className="stack" style={{ gap: 24 }}>
            <AssistButton label="Suggest from earlier steps" run={suggest} disabled={busy} />
            <Text {...props} field="problem_statement" label="1.1 Understanding of the problem" rows={5} />
            <Text {...props} field="current_state" label="Current state (optional)" rows={3} />
            <Table {...props} field="objectives" title="1.2 Objectives" addLabel="+ Add objective" />
            <Table {...props} field="requirements" title="1.3 Requirements" addLabel="+ Add requirement" />
            <Text {...props} field="solution_overview" label="1.4 Proposed solution" rows={6} />
            <Table {...props} field="methodology" title="1.5 Methodology" addLabel="+ Add phase" />
            <Table {...props} field="tools" title="1.6 Tools & platforms" addLabel="+ Add tool" />
            <Table {...props} field="techniques" title="1.7 Techniques & procedures" addLabel="+ Add technique" />
            <Table {...props} field="glossary" title="Glossary of terms" addLabel="+ Add term" />
          </div>
        )}

        {tab === "scope" && <ScopeTab {...props} analysis={analysis} apply={apply} busy={busy} suggest={suggest} />}

        {tab === "management" && (
          <div className="stack" style={{ gap: 24 }}>
            <Table {...props} field="team" title="2.1 Project team & roles" addLabel="+ Add team member" />
            <section className="stack" style={{ gap: 10 }}>
              <div className="heading-row">
                <h3 className="t-card-title">Responsibilities</h3>
                <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => prefill("Added the scope's client responsibilities", "responsibilities")}>
                  Add client items from scope
                </button>
              </div>
              <span className="t-caption">What each party commits to; shown side by side in the SOW.</span>
              <div className="grid-2" style={{ alignItems: "start" }}>
                <Table {...props} field="client_responsibilities" title="The client" addLabel="+ Add responsibility" />
                <Table {...props} field="vendor_responsibilities" title="SonaMation" addLabel="+ Add responsibility" />
              </div>
            </section>
            <Table {...props} field="governance" title="Governance & communication" addLabel="+ Add meeting" />
            <section className="stack" style={{ gap: 10 }}>
              <div className="heading-row">
                <h3 className="t-card-title">Schedule</h3>
                <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => prefill("Drafted the schedule from the methodology", "timeline")}>
                  Draft from methodology
                </button>
              </div>
              <span className="t-caption">
                Give each phase a duration in weeks. Leave the start week blank to begin right after the phase before; set it to overlap phases.
              </span>
              <Table {...props} field="timeline" title="Phases" addLabel="+ Add phase" />
              <div className="grid-4">
                <label className="field">
                  <span className="field-label">Buffer / validation (weeks)</span>
                  <input
                    type="number"
                    className="input"
                    min={0}
                    value={doc.timeline_buffer_weeks ?? 0}
                    onChange={(e) => set({ timeline_buffer_weeks: Math.max(0, Number(e.target.value) || 0) })}
                  />
                </label>
                <Text {...props} field="timeline_buffer_label" label="Buffer label" />
              </div>
              {analysis && <TimelinePreview chart={analysis.timeline} />}
            </section>
            <Table {...props} field="risks" title="Risk management" addLabel="+ Add risk" />
            <section className="stack" style={{ gap: 10 }}>
              <div className="heading-row">
                <h3 className="t-card-title">Data quality & known issues</h3>
                <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => prefill("Added the portal audit's High and Medium findings", "data_quality")}>
                  Import from portal audit
                </button>
              </div>
              <span className="t-caption">Each known problem in the client's data, what happens if it isn't fixed, and who owns it. This protects SonaMation when bad source data causes trouble later.</span>
              {analysis?.is_migration && (
                <Callout tone="info" title="Required for this migration project">
                  The SOW can&apos;t be marked ready to send until at least one issue is listed.
                </Callout>
              )}
              <Table {...props} field="data_quality" title="Issues" addLabel="+ Add issue" />
            </section>
            <Table {...props} field="kpis" title="Targeted KPIs" addLabel="+ Add KPI" />
            <Text {...props} field="acceptance_process" label="Acceptance process (standard text)" rows={5} />
          </div>
        )}

        {tab === "cost" && (
          <div className="stack" style={{ gap: 24 }}>
            <div className="grid-4">
              <label className="field">
                <span className="field-label">Discount (%)</span>
                <input
                  type="number"
                  className="input"
                  min={0}
                  max={100}
                  value={doc.discount_pct ?? 0}
                  onChange={(e) => set({ discount_pct: Math.min(100, Math.max(0, Number(e.target.value) || 0)) })}
                />
              </label>
            </div>
            <Table
              {...props}
              field="milestones"
              title="3.1 Deliverables & milestone schedule"
              caption="Group milestones by workstream / phase; the SOW subtotals each group and states its fee basis. Acceptance evidence is what the client receives to accept the milestone."
              addLabel="+ Add milestone"
            />
            {pricing && pricing.workstreams.length > 1 && (
              <DataTable
                label="Fees by workstream"
                columns={[
                  { key: "workstream", label: "Workstream", width: "minmax(140px, 1fr)" },
                  { key: "basis", label: "Fee basis", width: "minmax(200px, 2fr)" },
                  { key: "fee", label: "Fee", width: "130px" },
                ]}
                rows={pricing.workstreams.map((w) => ({ workstream: w.workstream, basis: w.fee_basis || "—", fee: money(w.fee, currency) }))}
              />
            )}
            <Table {...props} field="recurring_fees" title="Recurring fees" caption="Retainers and subscriptions: billed every period for the term, totalled apart from the one-time fees." addLabel="+ Add recurring fee" />
            <Table {...props} field="addons" title="Optional add-on services menu" addLabel="+ Add service" />
            <Table {...props} field="rate_card" title="Rate card (for Change Requests)" addLabel="+ Add role" />
            {pricing && (
              <>
                <Stats
                  items={[
                    ["Milestone fees", money(pricing.milestone_total, currency)],
                    ["Selected add-ons (one-time)", money(pricing.selected_addons_one_time, currency)],
                    ["Discount", money(-pricing.discount, currency)],
                    ["Total one-time fee", money(pricing.total, currency)],
                  ]}
                />
                {Object.keys(pricing.recurring ?? {}).length > 0 && (
                  <Stats
                    items={[
                      ...Object.entries(pricing.recurring ?? {}).map(([period, amount]): [string, string] => [`Recurring, ${period.toLowerCase()}`, money(Number(amount), currency)]),
                      ["Recurring over their terms", money(pricing.recurring_term_total, currency)],
                    ]}
                  />
                )}
              </>
            )}
            <section className="card stack" style={{ gap: 12 }} aria-label="Payment schedule">
              <h3 className="t-card-title">Payment schedule</h3>
              <span className="t-caption">Required before the SOW can be sent.</span>
              <div className="grid-4">
                <Select
                  label="Deposit as"
                  value={doc.payment_schedule?.deposit_type ?? "Percent"}
                  options={["Percent", "Amount"]}
                  onChange={(v) => set({ payment_schedule: { ...schedule(doc), deposit_type: v as "Percent" | "Amount" } })}
                />
                <label className="field">
                  <span className="field-label">{doc.payment_schedule?.deposit_type === "Amount" ? `Deposit (${currency})` : "Deposit (%)"}</span>
                  <input
                    type="number"
                    className="input"
                    min={0}
                    value={doc.payment_schedule?.deposit_value ?? 0}
                    onChange={(e) => set({ payment_schedule: { ...schedule(doc), deposit_value: Math.max(0, Number(e.target.value) || 0) } })}
                  />
                </label>
                <ChoiceInput
                  label="Invoices are raised"
                  value={doc.payment_schedule?.invoicing ?? ""}
                  options={INVOICING_OPTIONS}
                  onChange={(v) => set({ payment_schedule: { ...schedule(doc), invoicing: v } })}
                />
                <ChoiceInput
                  label="Due"
                  value={doc.payment_schedule?.due_terms ?? ""}
                  options={DUE_TERMS}
                  onChange={(v) => set({ payment_schedule: { ...schedule(doc), due_terms: v } })}
                />
              </div>
              <label className="field">
                <span className="field-label">Notes (optional)</span>
                <input className="input" value={doc.payment_schedule?.notes ?? ""} onChange={(e) => set({ payment_schedule: { ...schedule(doc), notes: e.target.value } })} />
              </label>
            </section>
            <Text {...props} field="payment_terms" label="Payment terms (standard text)" rows={4} />
            <Text {...props} field="expenses" label="Expenses (standard text)" rows={3} />
          </div>
        )}

        {tab === "terms" && <TermsTab {...props} />}

        {tab === "review" && (
          <div className="stack" style={{ gap: 24 }}>
            <section className="card stack" style={{ gap: 10 }} aria-label="Status">
              <div className="heading-row">
                <h2 className="t-section">Status: {doc.status === STATUS_READY ? "Ready to send" : "Draft"}</h2>
                {doc.status === STATUS_READY ? (
                  <button type="button" className="btn btn-secondary" onClick={() => set({ status: "Draft" })}>
                    Back to draft
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!analysis || analysis.readiness.length > 0}
                    onClick={() => set({ status: STATUS_READY })}
                  >
                    Mark ready to send
                  </button>
                )}
              </div>
              {analysis && analysis.readiness.length > 0 ? (
                <Callout tone="error" title="Can't be marked ready to send yet">
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {analysis.readiness.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                </Callout>
              ) : (
                <span className="t-caption">
                  {doc.status === STATUS_READY
                    ? "The PDF is final (no DRAFT mark)."
                    : "All checks pass. Until you mark it ready, the PDF is marked DRAFT."}
                </span>
              )}
            </section>
            <section className="stack" style={{ gap: 10 }}>
              <h2 className="t-section">Sections to include</h2>
              <div className="grid-4">
                {Object.entries(OPTIONAL_SECTIONS).map(([key, label]) => (
                  <Checkbox key={key} checked={doc.sections?.[key] !== false} onChange={(on) => set({ sections: { ...doc.sections, [key]: on } })}>
                    {label}
                  </Checkbox>
                ))}
              </div>
            </section>
            <Stats
              items={[
                ["In scope", count("In Scope")],
                ["Out of scope", count("Out of Scope")],
                ["Optional add-ons", count("Optional Add-on")],
                ["Total one-time fee", pricing ? money(pricing.total, currency) : "—"],
              ]}
            />
            {analysis &&
              (analysis.warnings.length ? (
                <Callout tone="warning" title="Before sending, check">
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {analysis.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </Callout>
              ) : (
                <Callout tone="success" title="No gaps found — scope, requirements and pricing all line up" />
              ))}
            <ExportFooter
              library={{ projectId: project.id, documentType: "Proposal & SOW" }}
              actions={[
                { label: ".pdf", make: () => proposalPdf(doc, stub) },
                { label: ".json", make: () => textFile(JSON.stringify(doc, null, 2), `${stub}.json`, "application/json") },
              ]}
            />
            <div className="row">
              <button
                type="button"
                className="btn-link"
                onClick={async () => {
                  downloadFile(textFile(JSON.stringify(await proposalTemplate(doc), null, 2), "SonaMation_proposal_template.json", "application/json"));
                }}
              >
                <Glyph name="download" /> Download as a reusable template (.json)
              </button>
            </div>
          </div>
        )}
      </TabPanel>
    </>
  );
}

export default function ProposalPage() {
  const { project } = useAppSession();
  const store = useModuleState<ProposalState>(project?.id ?? "", "proposal", normalizeProposal);
  if (!project) return null;
  return (
    <>
      <ProjectHeader
        eyebrow="STEP 4 / PROPOSE"
        title="Proposal & SOW Builder"
      />
      <div className="page-content">
        {!store.loaded ? (
          store.status === "error" ? (
            <Callout tone="error" title="Can't load this proposal">
              {store.error}
            </Callout>
          ) : (
            <div className="skeleton" style={{ height: 320 }} aria-busy="true" />
          )
        ) : (
          <>
            <SaveBanner store={store} />
            <Builder project={project} store={store} />
          </>
        )}
      </div>
    </>
  );
}
