"use client";

/**
 * The "Sales pipeline stages" answer as an editable, reorderable list, like
 * HubSpot's pipeline editor: each row is a stage name and a win probability.
 * Drag a row by its handle (or focus the handle and use the arrow keys) to
 * reorder. The answer is still stored as text — "Stage (20%) → Next (40%)",
 * the format the Deal Stage Planner writes — so the AI, exports and the
 * planner keep reading it as before.
 */

import { Reorder, useDragControls } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { springs } from "@/lib/motion";

import { Glyph } from "../icons";

type Stage = { id: string; name: string; pct: number | null };

const PROBABILITIES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];

/** HubSpot's default sales pipeline, as a starting point. */
const HUBSPOT_DEFAULT: [string, number][] = [
  ["Appointment scheduled", 20],
  ["Qualified to buy", 40],
  ["Presentation scheduled", 60],
  ["Decision maker bought-in", 80],
  ["Contract sent", 90],
  ["Closed won", 100],
  ["Closed lost", 0],
];

let nextId = 0;
const rowId = () => `stage-${++nextId}`;

/** "Consult (20%) → Booked (100%)", one per line, or comma-separated free text, into rows. */
export function parseStages(text: string): Stage[] {
  const trimmed = text.trim();
  if (!trimmed) return [];
  const parts = /→|\n/.test(trimmed) ? trimmed.split(/→|\n/) : trimmed.split(",");
  return parts
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const m = /^(.*?)\s*(?:\(\s*(\d{1,3}(?:\.\d+)?)\s*%\s*\)|[—–-]\s*(\d{1,3}(?:\.\d+)?)\s*%)\s*$/.exec(part);
      const pct = m ? Number(m[2] ?? m[3]) : null;
      return { id: rowId(), name: (m ? m[1]! : part).trim(), pct: pct !== null && pct >= 0 && pct <= 100 ? pct : null };
    });
}

export function formatStages(stages: Stage[]): string {
  return stages
    .filter((s) => s.name.trim())
    .map((s) => (s.pct === null ? s.name.trim() : `${s.name.trim()} (${s.pct}%)`))
    .join(" → ");
}

function StageRow({
  stage,
  index,
  count,
  onChange,
  onRemove,
  onMove,
}: {
  stage: Stage;
  index: number;
  count: number;
  onChange: (patch: Partial<Stage>) => void;
  onRemove: () => void;
  onMove: (to: number) => void;
}) {
  const controls = useDragControls();
  return (
    <Reorder.Item value={stage} dragListener={false} dragControls={controls} className="pipeline-row" transition={springs.snappy} whileDrag={{ scale: 1.01, boxShadow: "0 6px 16px rgb(42 32 88 / 12%)" }}>
      <button
        type="button"
        className="pipeline-handle"
        aria-label={`Move ${stage.name || "stage"} (drag, or use the arrow keys)`}
        title="Drag to reorder"
        onPointerDown={(e) => controls.start(e)}
        onKeyDown={(e) => {
          if (e.key === "ArrowUp" && index > 0) {
            e.preventDefault();
            onMove(index - 1);
          } else if (e.key === "ArrowDown" && index < count - 1) {
            e.preventDefault();
            onMove(index + 1);
          }
        }}
      >
        <span aria-hidden className="pipeline-grip" />
      </button>
      <span className="pipeline-order" aria-hidden>
        {index + 1}
      </span>
      <input className="input input-soft" aria-label={`Stage ${index + 1} name`} placeholder="Stage name" value={stage.name} onChange={(e) => onChange({ name: e.target.value })} />
      <select
        className="select select-soft pipeline-pct"
        aria-label={`Stage ${index + 1} win probability`}
        value={stage.pct === null ? "" : String(stage.pct)}
        onChange={(e) => onChange({ pct: e.target.value === "" ? null : Number(e.target.value) })}
      >
        <option value="">Probability</option>
        {stage.pct !== null && !PROBABILITIES.includes(stage.pct) && <option value={stage.pct}>{stage.pct}%</option>}
        {PROBABILITIES.map((p) => (
          <option key={p} value={p}>
            {p}%
          </option>
        ))}
      </select>
      <button type="button" className="icon-btn" aria-label={`Remove stage ${stage.name || index + 1}`} onClick={onRemove}>
        <Glyph name="x" size={14} />
      </button>
    </Reorder.Item>
  );
}

export function PipelineStagesInput({ value, onChange, labelId }: { value: string; onChange: (text: string) => void; labelId: string }) {
  const [stages, setStages] = useState<Stage[]>(() => parseStages(value));
  // The text this editor last wrote; anything else arriving (e.g. a planner import) is re-read.
  const emitted = useRef(value);
  useEffect(() => {
    if (value !== emitted.current) {
      emitted.current = value;
      setStages(parseStages(value));
    }
  }, [value]);

  const update = (next: Stage[]) => {
    setStages(next);
    const text = formatStages(next);
    emitted.current = text;
    onChange(text);
  };
  const move = (from: number, to: number) => {
    const next = [...stages];
    const [row] = next.splice(from, 1);
    next.splice(to, 0, row!);
    update(next);
  };

  return (
    <div className="pipeline-editor" role="group" aria-labelledby={labelId}>
      {stages.length > 0 && (
        <Reorder.Group axis="y" values={stages} onReorder={update} className="pipeline-list" as="ol">
          {stages.map((stage, i) => (
            <StageRow
              key={stage.id}
              stage={stage}
              index={i}
              count={stages.length}
              onChange={(patch) => update(stages.map((s) => (s.id === stage.id ? { ...s, ...patch } : s)))}
              onRemove={() => update(stages.filter((s) => s.id !== stage.id))}
              onMove={(to) => move(i, to)}
            />
          ))}
        </Reorder.Group>
      )}
      <div className="row">
        <button type="button" className="btn btn-secondary" onClick={() => update([...stages, { id: rowId(), name: "", pct: null }])}>
          <Glyph name="plus" /> Add stage
        </button>
        {stages.length === 0 && (
          <button type="button" className="btn-link" onClick={() => update(HUBSPOT_DEFAULT.map(([name, pct]) => ({ id: rowId(), name, pct })))}>
            Start from HubSpot&apos;s default stages
          </button>
        )}
      </div>
    </div>
  );
}
