"use client";

/**
 * Tab 1 — the live call form: Required tasks, section tabs of question
 * cards (follow-ups reveal under their trigger), notes, the flagged
 * summary, AI drafting, and backup / restore / reset.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useRef, useState } from "react";

import { downloadFile, fileStub, textFile, type DiscoveryConfig, type Evaluation, type FollowUpQuestion } from "@/lib/api";
import {
  emptyState,
  getAnswer,
  getSection,
  hasAnyNotes,
  isAnswered,
  parseState,
  toDiscoveryNotes,
  type DiscoveryStore,
} from "@/lib/discovery-state";

import { Callout, Icon, Reveal, spring, TabPanel, Tabs } from "../ui";
import { DocumentResult } from "./DocumentResult";
import { QuestionBlock, type QuestionContext } from "./QuestionCard";
import { RequiredTasksPanel, RequiredTasksSnapshot } from "./RequiredTasks";
import { StreamErrorCallout } from "./StreamErrorCallout";
import { ModelPicker, useAiModel } from "./ModelPicker";
import { useDocumentStream } from "./useDocumentStream";

/** The business analysis always has these 12 sections (see the system prompt), so progress can count them. */
const BUSINESS_ANALYSIS_SECTIONS = 12;

export function BusinessAnalysisTab({
  config,
  evaluation,
  store,
}: {
  config: DiscoveryConfig;
  evaluation: Evaluation | null;
  store: DiscoveryStore;
}) {
  const sections = config.question_bank.sections;
  const [active, setActive] = useState(sections[0]?.name ?? "");
  const { state, update, setSectionField } = store;

  const followUpsById = new Map(config.follow_ups.map((f) => [f.id, f]));
  const followUps: Record<string, FollowUpQuestion[]> = {};
  for (const [anchor, ids] of Object.entries(evaluation?.follow_ups ?? {})) {
    followUps[anchor] = ids.map((id) => followUpsById.get(id)).filter((f): f is FollowUpQuestion => f !== undefined);
  }
  const revealed = config.follow_ups.filter((f) => Object.values(followUps).some((list) => list.includes(f)));
  const ctx: QuestionContext = {
    store,
    otherOption: config.question_bank.other_option,
    followUps,
    revealedBy: evaluation?.revealed_by ?? {},
  };

  const onDone = useCallback((text: string) => update({ baOutput: text }), [update]);
  const stream = useDocumentStream("business-analysis", onDone);
  const ai = useAiModel();

  const flagged = sections.flatMap((section) =>
    [...section.questions, ...revealed.filter((f) => f.home_section === section.name)]
      .filter((q) => getAnswer(state, section.name, q.id).flagged)
      .map((q) => ({ section: section.name, label: q.label, note: getAnswer(state, section.name, q.id).notes })),
  );

  const current = sections.find((s) => s.name === active) ?? sections[0];
  const tasks = evaluation?.tasks ?? [];
  const answered = current ? current.questions.filter((q) => isAnswered(getAnswer(state, current.name, q.id))).length : 0;
  const followUpCount = current ? revealed.filter((f) => f.home_section === current.name).length : 0;
  const flaggedHere = current ? flagged.filter((f) => f.section === current.name).length : 0;
  // Full checklist where the tasks were triggered (and before any exist); a snapshot elsewhere.
  const fullTasks = tasks.length === 0 || tasks.some((t) => t.section === current?.name);

  return (
    <>
      {fullTasks ? <RequiredTasksPanel tasks={tasks} store={store} /> : <RequiredTasksSnapshot tasks={tasks} store={store} />}

      <div className="stack" style={{ gap: 24 }}>
        <Tabs
          label="Discovery sections"
          layoutId="section-tabs"
          variant="secondary"
          tabs={sections.map((s) => ({ id: s.name, label: s.name }))}
          active={active}
          onChange={setActive}
        />
        {current && (
          <TabPanel panelKey={current.name} id="section-tabs">
            <div className="stack" style={{ gap: 24 }}>
              <div className="stack" style={{ gap: 24 }}>
                <div className="heading-row" style={{ alignItems: "baseline" }}>
                  <h2 className="t-section">{current.name}</h2>
                  <p className="t-caption">
                    {answered} of {current.questions.length} questions answered
                    {followUpCount > 0 && ` · ↳ ${followUpCount} follow-up${followUpCount === 1 ? "" : "s"}`}
                    {flaggedHere > 0 && ` · ⚑ ${flaggedHere} flagged for follow-up`}
                  </p>
                </div>
                {current.description && <p className="t-intro">{current.description}</p>}
              </div>
              <div className="question-columns">
                {[0, 1].map((column) => (
                  <div key={column} className="question-column">
                    {current.questions
                      .filter((_, i) => i % 2 === column)
                      .map((q) => (
                        <QuestionBlock key={q.id} section={current.name} question={q} ctx={ctx} />
                      ))}
                  </div>
                ))}
              </div>
              <div className="grid-2">
                <label className="field">
                  <span className="field-label">Other notes</span>
                  <textarea
                    className="textarea"
                    placeholder="Anything said that doesn't fit a question above"
                    value={getSection(state, current.name).notes}
                    onChange={(e) => setSectionField(current.name, "notes", e.target.value)}
                  />
                </label>
                <label className="field">
                  <span className="field-label">Edge cases / flags</span>
                  <textarea
                    className="textarea"
                    placeholder="Compliance, multi-location, multi-entity, contradictions…"
                    value={getSection(state, current.name).edge_cases}
                    onChange={(e) => setSectionField(current.name, "edge_cases", e.target.value)}
                  />
                </label>
              </div>
            </div>
          </TabPanel>
        )}
      </div>

      <Reveal show={flagged.length > 0}>
        <section className="panel" aria-label="Flagged for follow-up">
          <h2 className="t-card-title">⚑ Flagged for follow-up ({flagged.length})</h2>
          <AnimatePresence initial={false}>
            {flagged.map((f) => (
              <motion.p
                key={`${f.section}-${f.label}`}
                className="flagged-line"
                layout
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={spring}
              >
                {f.section} · {f.label}
                {f.note.trim() && ` — ${f.note.trim()}`}
              </motion.p>
            ))}
          </AnimatePresence>
        </section>
      </Reveal>

      <div className="stack">
        <div className="row">
          <motion.button
            type="button"
            className={stream.streaming ? "btn btn-primary btn-busy" : "btn btn-primary"}
            disabled={!hasAnyNotes(state) || stream.streaming}
            whileTap={{ scale: 0.97 }}
            onClick={() => stream.start(toDiscoveryNotes(state), ai.model)}
          >
            {!stream.streaming && <Icon name="sparkles" />}
            {stream.streaming ? "Generating…" : state.baOutput ? "Regenerate business analysis" : "Generate business analysis"}
          </motion.button>
          <ModelPicker models={ai.models} value={ai.model} onChange={ai.setModel} disabled={stream.streaming} />
          <p className="t-caption">
            {hasAnyNotes(state)
              ? "Uses captured answers and notes. Review the draft before sharing."
              : "Capture at least one answer or note to enable generating."}
          </p>
        </div>
        {stream.error && (
          <StreamErrorCallout
            error={stream.error}
            lighter={ai.lightest}
            onRetryWith={(id) => {
              ai.setModel(id);
              void stream.start(toDiscoveryNotes(state), id);
            }}
          />
        )}
      </div>

      <DocumentResult
        markdown={stream.streaming ? stream.text : state.baOutput}
        streaming={stream.streaming}
        onEdit={(baOutput) => update({ baOutput })}
        title={`Discovery Business Analysis — ${state.clientName || "Client"}`}
        heading="Business analysis"
        eyebrow={`${state.clientName || "Client"} / Discovery business analysis`}
        status={{ label: "Draft · Consultant review", tone: "keep" }}
        clientName={state.clientName}
        fileSuffix="discovery_business_analysis"
        projectId={store.projectId}
        documentType="Discovery Business Analysis"
        progress={{ sections: BUSINESS_ANALYSIS_SECTIONS, startedAt: stream.startedAt, status: stream.status }}
      />

      <BackupAccordion store={store} />
    </>
  );
}

/** Back up, restore, or reset the call — collapsed by default. */
function BackupAccordion({ store }: { store: DiscoveryStore }) {
  const [open, setOpen] = useState(false);
  const [over, setOver] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const { state } = store;

  const restore = async (file: File | undefined) => {
    if (!file) return;
    try {
      store.replace(parseState(await file.text()));
      setMessage({ tone: "success", text: `Restored call notes from ${file.name}.` });
    } catch {
      setMessage({ tone: "error", text: "That file isn't a call-note backup from this page." });
    }
  };

  return (
    <section className="accordion" data-open={open}>
      <button type="button" className="accordion-summary" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <Icon name={open ? "chevron-down-18" : "chevron-right"} />
        Back up, restore, or reset call notes
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            style={{ overflow: "hidden" }}
          >
            <div className="accordion-body">
              <p className="flagged-line">
                Notes save to this project automatically. A backup (.json) contains answers, notes, follow-up flags
                and completed tasks — API keys are never included.
              </p>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() =>
                  downloadFile(
                    textFile(
                      JSON.stringify(state, null, 2),
                      `${fileStub(state.clientName, "discovery_notes")}.json`,
                      "application/json",
                    ),
                  )
                }
              >
                ↓  Download call notes .json
              </button>
              <div className="field" style={{ width: "100%" }}>
                <span className="field-label">Restore a call-note backup</span>
                <div
                  className="drop-zone"
                  data-over={over}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setOver(true);
                  }}
                  onDragLeave={() => setOver(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setOver(false);
                    void restore(e.dataTransfer.files[0]);
                  }}
                >
                  Drop a .json file here, or browse files
                </div>
              </div>
              <button type="button" className="btn btn-secondary" onClick={() => fileInput.current?.click()}>
                Browse files
              </button>
              <input
                ref={fileInput}
                type="file"
                accept="application/json,.json"
                hidden
                onChange={(e) => {
                  void restore(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
              <Callout tone="warning" title="Restoring replaces the current call notes">
                Download a backup first. Documents saved to the Project Library are not affected.
              </Callout>
              {message && (
                <Callout tone={message.tone} title={message.tone === "success" ? "Done" : "Couldn't restore"}>
                  {message.text}
                </Callout>
              )}
              {confirmReset ? (
                <div className="row">
                  <span className="flagged-line">Clear every answer, note and draft?</span>
                  <button
                    type="button"
                    className="btn btn-danger"
                    onClick={() => {
                      store.replace(emptyState());
                      setConfirmReset(false);
                      setMessage({ tone: "success", text: "Started a new call." });
                    }}
                  >
                    Yes, clear everything
                  </button>
                  <button type="button" className="btn-link" onClick={() => setConfirmReset(false)}>
                    Cancel
                  </button>
                </div>
              ) : (
                <button type="button" className="btn btn-danger" onClick={() => setConfirmReset(true)}>
                  <Icon name="rotate-ccw" />
                  Start a new call
                </button>
              )}
              <p className="t-caption">
                Clears this project&apos;s answers and notes only. Download a backup before starting again.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
