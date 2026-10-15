"use client";

/**
 * Required tasks, in the two forms the design uses: the full checklist
 * panel (on the section whose answers triggered them) and a compact
 * snapshot (on other sections, so the list stays in view without taking
 * over the page).
 */

import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import type { FlaggedTask } from "@/lib/api";
import type { DiscoveryStore } from "@/lib/discovery-state";

import { AnimatedNumber, Checkbox, Icon, Reveal, spring } from "../ui";
import { highlight, offset, springs, tween } from "@/lib/motion";

function Heading({ tasks, store, badge }: { tasks: FlaggedTask[]; store: DiscoveryStore; badge: string }) {
  const done = tasks.filter((t) => store.state.tasksDone.includes(t.task.id)).length;
  return (
    <div className="heading-row">
      <h2 className="t-card-title" aria-live="polite">
        Required tasks (<AnimatedNumber value={done} /> of <AnimatedNumber value={tasks.length} /> done)
      </h2>
      <span className="badge badge-keep">{badge}</span>
    </div>
  );
}

/** Why a task is required, collapsed under it (design: "Source details"). */
function SourceDetails({ reasons, detail }: { reasons: string[]; detail?: string | null }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="task-source">
      <button type="button" className="task-source-toggle" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <motion.span animate={{ rotate: open ? 90 : 0 }} transition={spring} style={{ display: "inline-flex" }}>
          <Icon name="chevron-right" />
        </motion.span>
        Source details
      </button>
      <Reveal show={open}>
        <p className="task-reason">
          Because: {reasons.join(" · ")}
          {detail ? ` — ${detail}` : ""}
        </p>
      </Reveal>
    </div>
  );
}

export function RequiredTasksPanel({ tasks, store }: { tasks: FlaggedTask[]; store: DiscoveryStore }) {
  return (
    <motion.section className="panel" layout transition={spring} aria-label="Required tasks">
      <Heading tasks={tasks} store={store} badge="Updated from your answers" />
      {tasks.length === 0 ? (
        <p className="t-description">
          None yet. Some answers — e.g. EU / UK contacts, or more than one location — add follow-up questions and
          required tasks here.
        </p>
      ) : (
        <ul className="task-list">
          <AnimatePresence initial={false}>
            {tasks.map((flagged) => {
              const done = store.state.tasksDone.includes(flagged.task.id);
              return (
                <motion.li
                  key={flagged.task.id}
                  className="task-row"
                  data-done={done}
                  layout
                  initial={{ opacity: 0, x: -offset.item, backgroundColor: highlight.from }}
                  animate={{ opacity: 1, x: 0, backgroundColor: highlight.to }}
                  exit={{ opacity: 0, x: -offset.item, transition: tween.fast }}
                  transition={{ ...springs.snappy, backgroundColor: highlight.transition }}
                >
                  <Checkbox checked={done} onChange={() => store.toggleIn("tasksDone", flagged.task.id)}>
                    {flagged.task.label}
                  </Checkbox>
                  <SourceDetails reasons={flagged.reasons} detail={flagged.task.detail} />
                </motion.li>
              );
            })}
          </AnimatePresence>
        </ul>
      )}
      {tasks.length > 0 && <p className="t-caption">Tasks update as you answer. Completed tasks stay checked.</p>}
    </motion.section>
  );
}

const SNAPSHOT_TASKS = 3;

export function RequiredTasksSnapshot({ tasks, store }: { tasks: FlaggedTask[]; store: DiscoveryStore }) {
  const shown = tasks.slice(0, SNAPSHOT_TASKS);
  const more = tasks.length - shown.length;
  const reasons = [...new Set(shown.flatMap((t) => t.reasons))];
  return (
    <motion.section className="panel panel-compact" layout transition={spring} aria-label="Required tasks summary">
      <Heading tasks={tasks} store={store} badge="Shared across discovery" />
      <p className="flagged-line">
        {shown.map((t) => t.task.label).join(" · ")}
        {more > 0 && ` · +${more} more`}
      </p>
      <p className="t-caption">Because: {reasons.join("; ")}</p>
    </motion.section>
  );
}
