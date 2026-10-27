"use client";

/**
 * Data Migration step 4: records entered more than once (lib/data-duplicates).
 * The user picks the columns that identify a record; rows sharing a value in
 * any of them are grouped and shown side by side, with the columns that match
 * and the ones that differ. Each group is merged into one row (blanks filled
 * from the others, notes combined), reduced to its main row, or marked as not
 * duplicates. Undecided groups keep every row.
 */

import { useState } from "react";

import { DataTable } from "@/components/project/DataTable";
import type { CleanResult } from "@/lib/data-cleaner";
import { mergeRows, type DupAction, type DupDecision, type DupGroup } from "@/lib/data-duplicates";

const PAGE = 20;

const ACTIONS: { id: DupAction; label: string; title: string }[] = [
  { id: "merge", label: "Merge into one", title: "One row: the main row's values, blanks filled from the others, notes combined" },
  { id: "keep", label: "Keep main row only", title: "Keep the main row and drop the others" },
  { id: "separate", label: "Not duplicates", title: "Keep every row" },
];

type Show = "all" | "open" | "done";

export function DataDuplicates({
  result,
  keys,
  onKeys,
  groups,
  decisions,
  onDecide,
  notes,
}: {
  /** The cleaned file before duplicates are handled. */
  result: CleanResult;
  /** Names of the columns rows are matched on. */
  keys: string[];
  onKeys: (keys: string[]) => void;
  groups: DupGroup[];
  decisions: Record<string, DupDecision>;
  /** Decisions to set; null clears one. */
  onDecide: (changes: Record<string, DupDecision | null>) => void;
  notes: boolean[];
}) {
  const [show, setShow] = useState<Show>("all");
  const [limit, setLimit] = useState(PAGE);
  const done = groups.filter((g) => decisions[g.key]).length;
  const visible = groups.filter((g) => show === "all" || (show === "done") === Boolean(decisions[g.key]));
  const open = visible.filter((g) => !decisions[g.key]);
  const extra = groups.reduce((n, g) => n + g.rows.length - 1, 0);

  return (
    <section className="card stack" style={{ gap: 14 }} aria-labelledby="dm-4">
      <div className="heading-row" style={{ flexWrap: "wrap" }}>
        <h2 id="dm-4" className="t-section">
          4 · Check for duplicate records
        </h2>
        {groups.length > 0 && (
          <span className="t-caption">
            {done} of {groups.length} decided
          </span>
        )}
      </div>
      <p className="t-caption">
        The same person, company or booking entered more than once. HubSpot would update one record with each row in turn, so the
        last row wins and details in the others are lost. Choose the columns that identify a record: rows that share a value in any
        of them are grouped.
      </p>
      <div className="field">
        <span className="field-label" id="dm-keys">
          Match rows on
        </span>
        <div className="choice-chips" role="group" aria-labelledby="dm-keys">
          {result.headers.map((h) => {
            const on = keys.includes(h);
            return (
              <button
                key={h}
                type="button"
                className="choice-chip"
                role="checkbox"
                aria-checked={on}
                onClick={() => {
                  onKeys(on ? keys.filter((k) => k !== h) : [...keys, h]);
                  setLimit(PAGE);
                }}
              >
                {h}
              </button>
            );
          })}
        </div>
      </div>

      {!keys.length ? (
        <p className="t-caption">Choose at least one column to look for duplicates.</p>
      ) : !groups.length ? (
        <p className="t-caption">No duplicates: no two rows share a value in {keys.join(", ")}.</p>
      ) : (
        <>
          <p className="dm-dup-summary">
            {groups.length} {groups.length === 1 ? "group" : "groups"} of rows look like the same record ({extra} extra{" "}
            {extra === 1 ? "row" : "rows"}).
          </p>
          <div className="dm-progress" role="progressbar" aria-label="Groups decided" aria-valuemin={0} aria-valuemax={groups.length} aria-valuenow={done}>
            <span style={{ width: `${(done / groups.length) * 100}%` }} />
          </div>
          <div className="dm-filters">
            <label className="field">
              <span className="field-label">Show</span>
              <select
                className="input"
                value={show}
                onChange={(e) => {
                  setShow(e.target.value as Show);
                  setLimit(PAGE);
                }}
              >
                <option value="all">Every group</option>
                <option value="open">Not decided yet ({groups.length - done})</option>
                <option value="done">Decided ({done})</option>
              </select>
            </label>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={!open.length}
              onClick={() => onDecide(Object.fromEntries(open.map((g) => [g.key, { action: "merge" as const }])))}
            >
              {open.length ? `Merge the ${open.length === 1 ? "group" : `${open.length} groups`} shown` : "All shown groups are decided"}
            </button>
          </div>
          <ol className="dm-dups">
            {visible.slice(0, limit).map((g) => (
              <Group key={g.key} group={g} result={result} decision={decisions[g.key]} notes={notes} onDecide={(d) => onDecide({ [g.key]: d })} />
            ))}
          </ol>
          {visible.length > limit && (
            <button type="button" className="btn btn-secondary" style={{ justifySelf: "start" }} onClick={() => setLimit(limit + PAGE)}>
              Show {Math.min(PAGE, visible.length - limit)} more of {visible.length - limit}
            </button>
          )}
        </>
      )}
    </section>
  );
}

function Group({
  group,
  result,
  decision,
  notes,
  onDecide,
}: {
  group: DupGroup;
  result: CleanResult;
  decision: DupDecision | undefined;
  notes: boolean[];
  onDecide: (d: DupDecision) => void;
}) {
  const main = decision?.main ?? group.main;
  const action = decision?.action;
  // The columns worth comparing: what matched, what differs; a few filled ones when nothing differs.
  const cols = [...new Set([...group.matchedOn, ...group.conflicts])].sort((a, b) => a - b);
  if (cols.length < 3) {
    for (let c = 0; c < result.headers.length && cols.length < 4; c++) if (!cols.includes(c) && result.rows[main]![c]) cols.push(c);
    cols.sort((a, b) => a - b);
  }
  const merged = action !== "keep" && action !== "separate" ? mergeRows(result, group, main, notes).row : null;
  const sample = result.rows[group.rows[0]!]![group.matchedOn[0]!] ?? "";
  const label = `rows ${group.rows.map((i) => result.sources[i]).join(", ")}`;
  const cell = (v: string, c: number, diff: boolean) => (v ? diff && group.conflicts.includes(c) ? <mark className="dm-diff">{v}</mark> : v : <em className="dm-blank">(blank)</em>);

  return (
    <li className="dm-dup">
      <div className="dm-dup-head">
        <div className="dm-found">
          <b className="dm-cell-strong">
            {group.rows.length} rows: {group.matchedOn.map((c) => result.headers[c]).join(" and ")} match
          </b>
          <span className="t-caption">
            {sample}
            {group.conflicts.length > 0 && ` · differ in ${group.conflicts.map((c) => result.headers[c]).join(", ")}`}
          </span>
        </div>
        <span className="dm-choice" role="radiogroup" aria-label={`What to do with ${label}`}>
          {ACTIONS.map((a) => (
            <button
              key={a.id}
              type="button"
              role="radio"
              aria-checked={action === a.id}
              title={a.title}
              className={`dm-choice-btn${!action && a.id === "merge" ? " dm-choice-suggested" : ""}`}
              onClick={() => onDecide({ action: a.id, main })}
            >
              {a.label}
            </button>
          ))}
        </span>
      </div>
      <DataTable
        label={`Duplicate ${label}`}
        columns={[
          { key: "row", label: "Main row", width: "110px" },
          ...cols.map((c) => ({ key: String(c), label: result.headers[c]!, width: "minmax(140px, 1fr)" })),
        ]}
        rows={[
          ...group.rows.map((i) => ({
            row: (
              <label className="dm-main">
                <input
                  type="radio"
                  name={`main-${group.key}`}
                  checked={i === main}
                  onChange={() => onDecide({ action: action ?? "merge", main: i })}
                  aria-label={`Keep row ${result.sources[i]} as the main row`}
                />
                Row {result.sources[i]}
              </label>
            ),
            ...Object.fromEntries(cols.map((c) => [String(c), cell(result.rows[i]![c] ?? "", c, true)])),
          })),
          ...(merged
            ? [
                {
                  row: <span className="dm-kinds">{action ? "Merged row" : "If merged"}</span>,
                  ...Object.fromEntries(cols.map((c) => [String(c), <b key={c}>{cell(merged[c] ?? "", c, false)}</b>])),
                },
              ]
            : []),
        ]}
      />
    </li>
  );
}
