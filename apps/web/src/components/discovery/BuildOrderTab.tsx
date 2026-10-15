"use client";

/**
 * Tab 4 — the implementation team's build order: stats, then items under
 * each configured section, template items grouped first under a green
 * divider and build-from-scratch items after, each tickable as it's built.
 */

import { AnimatePresence, motion } from "framer-motion";

import {
  exportSections,
  fileStub,
  textFile,
  type BuildItem,
  type DiscoveryConfig,
  type Evaluation,
  type SectionsFormat,
} from "@/lib/api";
import type { DiscoveryStore } from "@/lib/discovery-state";

import { AnimatedNumber, Callout, CheckMark, ExportFooter, spring } from "../ui";
import { Glyph } from "@/components/icons";
import { press, springs, tween } from "@/lib/motion";

const FORMATS: SectionsFormat[] = ["docx", "xlsx", "csv", "pdf"];

export function BuildOrderTab({
  config,
  evaluation,
  store,
}: {
  config: DiscoveryConfig;
  evaluation: Evaluation | null;
  store: DiscoveryStore;
}) {
  const { state, update, toggleIn } = store;
  const { project_types: projectTypes, done_status: doneStatus, statuses } = config.build_order;
  const projectType = state.projectType || projectTypes[0] || "";
  // Ticks are applied locally so the check animates instantly, rather than
  // after the next (debounced) evaluate round-trip.
  const doneIds = new Set(state.buildDone);
  const serverOrder = evaluation?.build_order;
  const order = serverOrder && {
    ...serverOrder,
    sections: serverOrder.sections.map((s) => ({
      ...s,
      items: s.items.map((i) => {
        const done = doneIds.has(i.id);
        return { ...i, done, status: done ? doneStatus : (statuses[0] ?? i.status) };
      }),
    })),
  };
  const items = order?.sections.flatMap((s) => s.items) ?? [];
  const templates = items.filter((i) => i.template).length;
  const done = items.filter((i) => i.done).length;

  return (
    <>
      <label className="field">
        <span className="field-label">Project type</span>
        <select className="select select-muted" value={projectType} onChange={(e) => update({ projectType: e.target.value })}>
          {projectTypes.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
        <span className="t-caption">Other project types: {projectTypes.filter((t) => t !== projectType).join(" · ")}</span>
      </label>

      {!order || items.length === 0 ? (
        <Callout tone="info" title="No build items yet">
          They come from the business-analysis answers — e.g. EU / UK contacts (GDPR bundle), more than one location,
          integrations, or must-have features like deal pipelines.
        </Callout>
      ) : (
        <>
          <div className="stack" style={{ gap: 24 }}>
            <motion.h2 key={order.title} className="t-section" initial={{ opacity: 0.4 }} animate={{ opacity: 1 }}>
              {order.title}
            </motion.h2>
            <p className="t-description">
              {items.length} items · {templates} from reusable templates · {items.length - templates} from scratch · {done} done
            </p>
          </div>
          <div className="stats">
            <Stat label="Total build items" value={<AnimatedNumber value={items.length} />} />
            <Stat label="Reusable templates" value={<AnimatedNumber value={templates} />} />
            <Stat label="From scratch" value={<AnimatedNumber value={items.length - templates} />} />
            <Stat
              label="Completed"
              value={
                <>
                  <AnimatedNumber value={done} /> / {items.length}
                </>
              }
            />
          </div>

          {order.sections.map((section) => {
            const fromTemplates = section.items.filter((i) => i.template);
            const fromScratch = section.items.filter((i) => !i.template);
            return (
              <section key={section.id} className="build-section">
                <div className="heading-row">
                  <h2 className="t-section">{section.title}</h2>
                  <span className="badge badge-neutral">
                    {section.items.length} item{section.items.length === 1 ? "" : "s"}
                  </span>
                </div>
                {section.items.length === 0 ? (
                  <p className="t-caption">Nothing for this section from the current answers.</p>
                ) : (
                  <motion.div className="build-list" layout transition={spring}>
                    {fromTemplates.length > 0 && (
                      <>
                        <div className="build-divider build-divider-template">
                          <Glyph name="layers" size={14} /> From templates · {fromTemplates.length} item{fromTemplates.length === 1 ? "" : "s"}
                        </div>
                        <Items items={fromTemplates} onToggle={(id) => toggleIn("buildDone", id)} />
                      </>
                    )}
                    {fromScratch.length > 0 && (
                      <>
                        <div className="build-divider build-divider-scratch">
                          Build from scratch · {fromScratch.length} item{fromScratch.length === 1 ? "" : "s"}
                        </div>
                        <Items items={fromScratch} onToggle={(id) => toggleIn("buildDone", id)} />
                      </>
                    )}
                  </motion.div>
                )}
              </section>
            );
          })}
          <ExportFooter
            library={{ projectId: store.projectId, documentType: "Discovery Build Order", title: order.title }}
            actions={[
              ...FORMATS.map((format) => ({
                label: `.${format}`,
                make: () =>
                  exportSections(
                    order.title,
                    `Generated ${order.generated_on} from the discovery call`,
                    evaluation?.build_order_sections ?? [],
                    format,
                    fileStub(state.clientName, "build_order"),
                  ),
              })),
              {
                label: ".json",
                make: () =>
                  textFile(
                    // The server's copy: ticks reach it with the next evaluate, well before a click here.
                    JSON.stringify(serverOrder, null, 2),
                    `${fileStub(state.clientName, "build_order")}.json`,
                    "application/json",
                  ),
              },
            ]}
          />
        </>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  );
}

function Items({ items, onToggle }: { items: BuildItem[]; onToggle: (id: string) => void }) {
  return (
    <AnimatePresence initial={false}>
      {items.map((item) => (
        <motion.button
          key={item.id}
          type="button"
          role="checkbox"
          aria-checked={item.done}
          className="build-item"
          layout
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, height: 0, transition: tween.fast }}
          transition={springs.snappy}
          whileTap={press}
          onClick={() => onToggle(item.id)}
        >
          <span className="build-item-body">
            <span className="build-item-name">
              <CheckMark checked={item.done} />
              {item.name}
            </span>
            <span className="build-item-source">Source: {item.sources.join("; ")}</span>
          </span>
          {item.template ? (
            <span className="badge badge-success"><Glyph name="layers" size={12} />Template · {item.template_label}</span>
          ) : (
            <span className="badge badge-neutral">Build from scratch</span>
          )}
        </motion.button>
      ))}
    </AnimatePresence>
  );
}
