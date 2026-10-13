"use client";

/** A read-only table for previews and results: columns by label, rows as objects. */

import { tableMinWidth } from "./EditableTable";

export function DataTable({
  columns,
  rows,
  label,
  empty = "Nothing to show.",
}: {
  columns: { key: string; label: string; width?: string }[];
  rows: Record<string, React.ReactNode>[];
  label: string;
  empty?: string;
}) {
  if (!rows.length) return <p className="t-caption">{empty}</p>;
  const template = columns.map((c) => c.width ?? "minmax(140px, 1fr)").join(" ");
  const minWidth = tableMinWidth(columns.map((c) => c.width ?? "minmax(140px, 1fr)"));
  return (
    <div className="etable" role="table" aria-label={label}>
      <div className="etable-scroll">
        <div className="etable-row etable-head" role="row" style={{ gridTemplateColumns: template, minWidth }}>
          {columns.map((c) => (
            <span key={c.key} role="columnheader">
              {c.label}
            </span>
          ))}
        </div>
        {rows.map((row, i) => (
          <div key={i} className="etable-row" role="row" style={{ gridTemplateColumns: template, minWidth }}>
            {columns.map((c) => (
              <span key={c.key} role="cell" className="dtable-cell">
                {row[c.key]}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
