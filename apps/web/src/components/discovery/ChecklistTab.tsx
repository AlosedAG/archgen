"use client";

/** Tab 3 — required tasks + scope items, each with why it's there and a blank Status / Notes column. */

import { AnimatePresence, motion } from "framer-motion";

import { exportSections, fileStub, type Evaluation, type SectionsFormat } from "@/lib/api";
import type { DiscoveryStore } from "@/lib/discovery-state";

import { Callout, ExportFooter } from "../ui";
import { highlight, tween } from "@/lib/motion";

const FORMATS: SectionsFormat[] = ["docx", "xlsx", "csv", "pdf"];

export function ChecklistTab({
  evaluation,
  store,
  onBack,
}: {
  evaluation: Evaluation | null;
  store: DiscoveryStore;
  onBack: () => void;
}) {
  const sections = (evaluation?.checklist ?? []).map((s) => ({ title: s.title, rows: s.rows ?? [] }));
  const client = store.state.clientName;
  const total = sections.reduce((n, s) => n + s.rows.length, 0);

  if (total === 0) {
    return (
      <>
        <h2 className="t-section">Required tasks (0)</h2>
        <Callout tone="info" title="No required tasks yet">
          Answer discovery questions about data regions, locations, compliance, and integrations to populate this
          checklist.
        </Callout>
        <h2 className="t-section">Scope items (0)</h2>
        <p className="flagged-line">No scope items yet. Confirm goals and integrations during the call to build your first scope list.</p>
        <button type="button" className="btn btn-secondary" style={{ width: "fit-content" }} onClick={onBack}>
          Return to business analysis
        </button>
      </>
    );
  }

  const now = new Date();
  const stamp = `${now.toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" })}, ${now.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`;
  const title = `${client || "Client"} — Discovery Checklist`;

  return (
    <>
      <div className="stack" style={{ gap: 24 }}>
        <div className="heading-row">
          <h2 className="t-section">{title}</h2>
          <span className="badge badge-keep">{total} items · Ready to review</span>
        </div>
      </div>

      {sections.map((section) => {
        const columns = Object.keys(section.rows[0] ?? { Task: "", "Why it's required": "", "Status / Notes": "" });
        return (
          <section key={section.title} className="stack" style={{ gap: 24 }}>
            <h2 className="t-section">
              {section.title} ({section.rows.length})
            </h2>
            {section.rows.length > 0 && (
              <div className="table" role="table" aria-label={section.title}>
                <div className="table-row table-head" role="row">
                  {columns.map((c) => (
                    <span key={c} role="columnheader">
                      {c}
                    </span>
                  ))}
                </div>
                <AnimatePresence initial={false}>
                  {section.rows.map((row) => (
                    <motion.div
                      key={row[columns[0] ?? ""]}
                      className="table-row"
                      role="row"
                      layout
                      initial={{ opacity: 0, backgroundColor: highlight.from }}
                      animate={{ opacity: 1, backgroundColor: highlight.to }}
                      exit={{ opacity: 0, transition: tween.fast }}
                      transition={highlight.transition}
                    >
                      {columns.map((c) => (
                        <span key={c} role="cell">
                          {row[c]}
                        </span>
                      ))}
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}
          </section>
        );
      })}

      <p className="t-caption">Generated from the current discovery answers · {stamp} · Blank status cells are intended.</p>
      <ExportFooter
        library={{ projectId: store.projectId, documentType: "Discovery Checklist", title }}
        actions={FORMATS.map((format) => ({
          label: `.${format}`,
          make: () =>
            exportSections(
              title,
              `From the discovery call · ${now.toISOString().slice(0, 10)}`,
              sections,
              format,
              fileStub(client, "discovery_checklist"),
            ),
        }))}
      />
    </>
  );
}
