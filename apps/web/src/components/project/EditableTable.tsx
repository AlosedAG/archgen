"use client";

/**
 * An editable table: one input per cell (text, multi-line, dropdown,
 * date, or checkbox), add / remove rows, and an optional row limit.
 * Rows are plain objects keyed by column key, so they save and export
 * as-is.
 */

import { AnimatePresence, motion } from "framer-motion";

import { spring } from "../ui";

export type Cell = string | boolean;
export type Row = Record<string, Cell>;

export type Column = {
  key: string;
  label: string;
  kind?: "text" | "textarea" | "select" | "date" | "checkbox" | "number";
  options?: string[];
  /** CSS grid width, e.g. "2fr" or "140px". Default 1fr. */
  width?: string;
  placeholder?: string;
};

/**
 * The narrowest a table may get before it scrolls sideways: the sum of its
 * columns' minimums (px widths as-is, ``minmax(Npx, …)`` → N, anything else
 * 120px). Every row shares it so the columns line up.
 */
export function tableMinWidth(widths: (string | undefined)[], extra = 0): number {
  return widths.reduce((sum, w) => {
    const px = /^(\d+)px$/.exec(w ?? "") ?? /^minmax\((\d+)px/.exec(w ?? "");
    return sum + (px ? Number(px[1]) : 120);
  }, extra);
}

export function blankRow(columns: Column[], overrides: Row = {}): Row {
  const row: Row = {};
  for (const c of columns) row[c.key] = c.kind === "checkbox" ? false : c.kind === "select" ? (c.options?.[0] ?? "") : "";
  return { ...row, ...overrides };
}

export function EditableTable({
  columns,
  rows,
  onChange,
  label,
  addLabel = "+ Add row",
}: {
  columns: Column[];
  rows: Row[];
  onChange: (rows: Row[]) => void;
  label: string;
  addLabel?: string;
}) {
  const template = `${columns.map((c) => c.width ?? "minmax(120px, 1fr)").join(" ")} 36px`;
  const minWidth = tableMinWidth(columns.map((c) => c.width), 36);
  const setCell = (index: number, key: string, value: Cell) =>
    onChange(rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)));

  return (
    <div className="etable" role="table" aria-label={label}>
      <div className="etable-scroll">
        <div className="etable-row etable-head" role="row" style={{ gridTemplateColumns: template, minWidth }}>
          {columns.map((c) => (
            <span key={c.key} role="columnheader">
              {c.label}
            </span>
          ))}
          <span aria-hidden />
        </div>
        <AnimatePresence initial={false}>
          {rows.map((row, index) => (
            <motion.div
              // Rows have no ids; index keys are fine because rows are only appended or removed.
              key={index}
              className="etable-row"
              role="row"
              style={{ gridTemplateColumns: template, minWidth }}
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, height: 0 }}
              transition={spring}
            >
              {columns.map((c) => (
                <span key={c.key} role="cell" className="etable-cell">
                  <CellInput column={c} value={row[c.key] ?? ""} onChange={(v) => setCell(index, c.key, v)} rowLabel={`${label} row ${index + 1}`} />
                </span>
              ))}
              <button
                type="button"
                className="etable-remove"
                aria-label={`Remove ${label} row ${index + 1}`}
                title="Remove row"
                onClick={() => onChange(rows.filter((_, i) => i !== index))}
              >
                ×
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      <button type="button" className="btn-link etable-add" onClick={() => onChange([...rows, blankRow(columns)])}>
        {addLabel}
      </button>
    </div>
  );
}

function CellInput({ column, value, onChange, rowLabel }: { column: Column; value: Cell; onChange: (v: Cell) => void; rowLabel: string }) {
  const aria = `${column.label} (${rowLabel})`;
  switch (column.kind) {
    case "checkbox":
      return <input type="checkbox" aria-label={aria} checked={value === true} onChange={(e) => onChange(e.target.checked)} />;
    case "select":
      return (
        <select className="etable-input" aria-label={aria} value={String(value)} onChange={(e) => onChange(e.target.value)}>
          {(column.options ?? []).map((o) => (
            <option key={o}>{o}</option>
          ))}
        </select>
      );
    case "date":
      return <input type="date" className="etable-input" aria-label={aria} value={String(value)} onChange={(e) => onChange(e.target.value)} />;
    case "textarea":
      return (
        <textarea
          className="etable-input etable-textarea"
          aria-label={aria}
          rows={2}
          placeholder={column.placeholder}
          value={String(value)}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case "number":
      return (
        <input type="number" className="etable-input" aria-label={aria} value={String(value)} onChange={(e) => onChange(e.target.value)} />
      );
    default:
      return (
        <input className="etable-input" aria-label={aria} placeholder={column.placeholder} value={String(value)} onChange={(e) => onChange(e.target.value)} />
      );
  }
}

/** Export form of a table: drop rows where every ``required`` column is blank; booleans → Yes/No. */
export function cleanRows(columns: Column[], rows: Row[], required?: string[]): Record<string, string>[] {
  const keys = required && required.length ? required : columns.map((c) => c.key);
  return rows
    .filter((row) => keys.some((k) => String(row[k] ?? "").trim() !== "" && row[k] !== false))
    .map((row) => Object.fromEntries(columns.map((c) => [c.label, typeof row[c.key] === "boolean" ? (row[c.key] ? "Yes" : "No") : String(row[c.key] ?? "")])));
}
