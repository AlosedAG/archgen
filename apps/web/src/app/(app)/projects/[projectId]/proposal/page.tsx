"use client";

/**
 * Proposal & SOW Builder: turns the Requirements Document and Joint
 * Evaluation Plan into a seller's proposal and/or Statement of Work —
 * technical approach, scope (every item In / Out / Optional / Client),
 * management approach and cost — then a branded PDF. The proposal is
 * saved to the project; all merge, pricing and coverage logic is the
 * API's.
 */

import { useEffect, useId, useState } from "react";

import { useAppSession } from "@/components/AppSession";
import { TokenSelect } from "@/components/discovery/QuestionCard";
import { DataTable } from "@/components/project/DataTable";
import { EditableTable } from "@/components/project/EditableTable";
import { ProjectHeader } from "@/components/project/ProjectHeader";
import { SaveBanner } from "@/components/project/SaveBanner";
import { Stats } from "@/components/project/Stats";
import { normalizeDocument } from "@/components/project/TableDocument";
import { Callout, Checkbox, ExportFooter, TabPanel, Tabs } from "@/components/ui";
import {
  addLibraryAddons,
  addScopeLibraryItems,
  analyseProposal,
  ApiError,
  defaultProposal,
  downloadFile,
  draftScopeFromRequirements,
  getModuleState,
  importJepIntoProposal,
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
import { JOINT_EVALUATION_PLAN, REQUIREMENTS_DOCUMENT } from "@/lib/documents";
import { useModuleState, type ModuleStore } from "@/lib/module-state";
import { CURRENCIES, DOCUMENT_TYPES, fromRows, money, OPTIONAL_SECTIONS, SCOPE_HINTS, SCOPE_STATUSES, TABLES, toRows, type TableField } from "@/lib/proposal";

type ProposalState = { doc: ProposalDocument | null };
const normalizeProposal = (raw: unknown): ProposalState => ({ doc: ((raw as ProposalState | null)?.doc ?? null) as ProposalDocument | null });

/** The proposal addressed to ``company`` (every party field kept, blanks filled). */
function addressedTo(doc: ProposalDocument, company: string): ProposalDocument {
  const c = doc.client;
  return { ...doc, client: { address: c?.address ?? "", contact: c?.contact ?? "", email: c?.email ?? "", phone: c?.phone ?? "", company } };
}

type TabId = "setup" | "technical" | "scope" | "management" | "cost" | "review";
type Store = ModuleStore<ProposalState>;
type Props = { doc: ProposalDocument; set: (patch: Partial<ProposalDocument>) => void };

const TEXT_FIELDS = [
  "executive_summary",
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
        rows={toRows(doc, field)}
        onChange={(rows) => set({ [field]: fromRows(field, rows) } as Partial<ProposalDocument>)}
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

// ---- Setup ----------------------------------------------------------------------------

const PARTY_FIELDS = [
  ["company", "Company"],
  ["contact", "Primary contact"],
  ["address", "Address"],
  ["phone", "Phone"],
  ["email", "Email"],
] as const;

function Setup({ doc, set, project, apply, busy }: Props & { project: Project; apply: (label: string, work: () => Promise<ProposalDocument>) => void; busy: boolean }) {
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
        <span className="t-caption">
          Imports merge: blank fields are filled and rows are appended — nothing typed here is overwritten. Requirements become the proposal&apos;s requirement list; the JEP&apos;s team, milestones and needs flow into Management and Technical.
        </span>
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

      <section className="stack" style={{ gap: 12 }}>
        <h2 className="t-section">Document</h2>
        <div className="grid-3">
          <Select label="Document type" value={doc.document_type || DOCUMENT_TYPES[0]} options={DOCUMENT_TYPES} onChange={(v) => set({ document_type: v as ProposalDocument["document_type"] })} />
          <Text doc={doc} set={set} field="title" label="Engagement title" />
          <Text doc={doc} set={set} field="reference_number" label="Reference / SOW number" />
        </div>
        <div className="grid-4">
          <DateField doc={doc} set={set} field="issue_date" label="Issue date" />
          <DateField doc={doc} set={set} field="effective_date" label="Effective date" />
          <DateField doc={doc} set={set} field="expiration_date" label="Expiration date" />
          <DateField doc={doc} set={set} field="valid_until" label="Proposal valid until" />
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
        <h2 className="t-section">Introduction</h2>
        <Text doc={doc} set={set} field="executive_summary" label="Executive summary" rows={4} placeholder="Two or three sentences: the client's problem, what SonaMation will deliver, and the outcome." />
        <Text doc={doc} set={set} field="company_overview" label="About SonaMation (standard text)" rows={4} />
      </section>
    </div>
  );
}

// ---- Scope --------------------------------------------------------------------------

function ScopeTab({ doc, set, analysis, apply, busy }: Props & { analysis: ProposalAnalysis | null; apply: (label: string, work: () => Promise<ProposalDocument>) => void; busy: boolean }) {
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
      <Callout tone="info" title="Scope is the section clients misread most">
        Put every item a client might ask about into exactly one bucket. Give each In Scope item a quantity limit and acceptance criteria, and list common requests you are not doing as Out of Scope — that&apos;s what prevents disputes later.
      </Callout>

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
        caption="IDs (S-01, S-02…) are assigned automatically. 'Req. ID' links an item to the requirements it satisfies (comma-separated, e.g. R-01, R-03)."
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
  const props = { doc, set };
  const currency = doc.currency || "USD";
  const pricing = analysis?.pricing;
  const stub = `${(doc.client?.company || clientName || "Client").trim()}_${doc.document_type || "Proposal"}`.replace(/\s+/g, "_").replace(/\+/g, "and");
  const count = (s: string) => analysis?.scope_by_status?.[s]?.length ?? 0;

  return (
    <>
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
          { id: "review", label: "6 · Review & generate" },
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
        {tab === "setup" && <Setup {...props} project={project} apply={apply} busy={busy} />}

        {tab === "technical" && (
          <div className="stack" style={{ gap: 24 }}>
            <Callout tone="info" title="Volume I — Technical approach">
              Show that SonaMation understands the problem, and exactly how it will be solved: the tools, techniques and procedures used to implement it.
            </Callout>
            <Text {...props} field="problem_statement" label="1.1 Understanding of the problem" rows={5} help="Start lines with '- ' for bullets in the PDF." />
            <Text {...props} field="current_state" label="Current state (optional)" rows={3} />
            <Table {...props} field="objectives" title="1.2 Objectives" addLabel="+ Add objective" />
            <Table {...props} field="requirements" title="1.3 Requirements" caption="IDs (R-01, R-02…) are assigned automatically if left blank; scope items cite them in the Scope tab." addLabel="+ Add requirement" />
            <Text {...props} field="solution_overview" label="1.4 Proposed solution" rows={6} help="How the requirements will be met. Start lines with '- ' for bullets." />
            <Table {...props} field="methodology" title="1.5 Methodology" addLabel="+ Add phase" />
            <Table {...props} field="tools" title="1.6 Tools & platforms" addLabel="+ Add tool" />
            <Table {...props} field="techniques" title="1.7 Techniques & procedures" addLabel="+ Add technique" />
            <Table {...props} field="glossary" title="Glossary of terms" addLabel="+ Add term" />
          </div>
        )}

        {tab === "scope" && <ScopeTab {...props} analysis={analysis} apply={apply} busy={busy} />}

        {tab === "management" && (
          <div className="stack" style={{ gap: 24 }}>
            <Callout tone="info" title="Volume II — Management approach">
              How SonaMation will manage contract performance.
            </Callout>
            <Table {...props} field="team" title="2.1 Project team & roles" addLabel="+ Add team member" />
            <Table {...props} field="governance" title="2.2 Governance & communication" addLabel="+ Add meeting" />
            <Table {...props} field="timeline" title="2.3 Schedule" addLabel="+ Add phase" />
            <Table {...props} field="risks" title="Risk management" addLabel="+ Add risk" />
            <Table {...props} field="kpis" title="Targeted KPIs" caption="Primary: value drivers tied to ROI. Secondary: operational / marketing improvement." addLabel="+ Add KPI" />
            <Text {...props} field="acceptance_process" label="Acceptance process (standard text)" rows={5} />
          </div>
        )}

        {tab === "cost" && (
          <div className="stack" style={{ gap: 24 }}>
            <Callout tone="info" title="Volume III — Cost & pricing">
              Milestone fees, the add-on menu, and the rate for anything beyond scope.
            </Callout>
            <div className="grid-4">
              <Select label="Currency" value={currency} options={CURRENCIES} onChange={(v) => set({ currency: v })} />
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
            <Table {...props} field="milestones" title="3.1 Deliverables & milestone schedule" caption="What's delivered, when it can start, when it's due, and the fee due on acceptance." addLabel="+ Add milestone" />
            <Table {...props} field="addons" title="Optional add-on services menu" caption="Tick 'Add to total' for add-ons the client has already chosen." addLabel="+ Add service" />
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
                {Object.entries(pricing.recurring ?? {}).map(([billing, amount]) => (
                  <span key={billing} className="t-caption">
                    Plus selected recurring add-ons: {money(Number(amount), currency)} ({billing}).
                  </span>
                ))}
              </>
            )}
            <Text {...props} field="payment_terms" label="Payment terms (standard text)" rows={4} />
            <Text {...props} field="expenses" label="Expenses (standard text)" rows={3} />
            <Text {...props} field="confidentiality" label="Confidentiality (standard text)" rows={3} />
          </div>
        )}

        {tab === "review" && (
          <div className="stack" style={{ gap: 24 }}>
            <section className="stack" style={{ gap: 10 }}>
              <h2 className="t-section">Sections to include</h2>
              <span className="t-caption">The cover, Scope at a Glance, and the Technical, Management and Cost volumes are always included.</span>
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
                ↓ Download as a reusable template (.json)
              </button>
              <span className="t-caption">Keeps only the reusable parts — SonaMation details, methodology, tools, governance, add-on menu, rate card, standard terms. Load it in Setup to start the next proposal.</span>
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
        description="Build a seller's proposal and Statement of Work from the Requirements Document and Joint Evaluation Plan — technical approach, management approach and cost — with a scope that states plainly what is included, what isn't, and what can be added."
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
