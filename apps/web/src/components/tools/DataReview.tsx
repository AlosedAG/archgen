"use client";

/**
 * Data Migration step 3: the values that need a decision (lib/data-review), one
 * row per distinct value with every row it appears on. Each has a recommended
 * value and a box for the user's own; the user picks the recommendation, their
 * value or the original. Automatic fixes are listed underneath, collapsed, so
 * any of them can be undone.
 */

import { useMemo, useState } from "react";

import { DataTable } from "@/components/project/DataTable";
import { Checkbox } from "@/components/ui";
import type { Choice, Decision, ReviewItem } from "@/lib/data-review";

const PAGE = 50;

const CHOICES: { id: Choice; label: string; title: string }[] = [
  { id: "rec", label: "Recommended", title: "Use the recommended value" },
  { id: "mine", label: "Mine", title: "Use the value you typed (empty means blank)" },
  { id: "keep", label: "Original", title: "Keep the value as it is in the file" },
];

type Show = "all" | "open" | "done";

const rowsLabel = (rows: number[]) =>
  rows.length === 1 ? `Row ${rows[0]}` : `Rows ${rows.slice(0, 4).join(", ")}${rows.length > 4 ? ` and ${rows.length - 4} more` : ""}`;

const shown = (v: string) => (v ? v : <em className="dm-blank">(blank)</em>);

/** Each distinct value of ``pick`` across ``items``, with how many items have it. */
function tally(items: ReviewItem[], pick: (i: ReviewItem) => string[]) {
  const counts = new Map<string, number>();
  for (const it of items) for (const v of pick(it)) counts.set(v, (counts.get(v) ?? 0) + 1);
  return [...counts];
}

export function DataReview({
  items,
  decisions,
  onDecide,
}: {
  items: ReviewItem[];
  decisions: Record<string, Decision>;
  /** Decisions to set; null clears one. */
  onDecide: (changes: Record<string, Decision | null>) => void;
}) {
  const review = useMemo(() => items.filter((i) => i.review), [items]);
  const auto = useMemo(() => items.filter((i) => !i.review), [items]);
  const [column, setColumn] = useState("");
  const [kind, setKind] = useState("");
  const [show, setShow] = useState<Show>("all");
  const [limit, setLimit] = useState(PAGE);
  const [autoLimit, setAutoLimit] = useState(PAGE);

  const done = review.filter((i) => decisions[i.key]).length;
  const columns = useMemo(() => tally(review, (i) => [i.column]), [review]);
  const kinds = useMemo(() => tally(review, (i) => i.kinds), [review]);
  const visible = review.filter(
    (i) =>
      (!column || i.column === column) &&
      (!kind || i.kinds.includes(kind)) &&
      (show === "all" || (show === "done") === Boolean(decisions[i.key])),
  );
  const open = visible.filter((i) => !decisions[i.key]);
  const decide = (it: ReviewItem, choice: Choice, mine?: string) =>
    onDecide({ [it.key]: { choice, mine: mine ?? decisions[it.key]?.mine ?? "" } });
  const filter = (apply: () => void) => {
    apply();
    setLimit(PAGE);
  };

  return (
    <section className="card stack" style={{ gap: 14 }} aria-labelledby="dm-3">
      <div className="heading-row" style={{ flexWrap: "wrap" }}>
        <h2 id="dm-3" className="t-section">
          3 · Review what needs a decision
        </h2>
        {review.length > 0 && (
          <span className="t-caption">
            {done} of {review.length} reviewed
          </span>
        )}
      </div>

      {review.length === 0 ? (
        <p className="t-caption">Nothing needs a decision: every change is automatic and listed below.</p>
      ) : (
        <>
          <p className="t-caption">
            Each row is one value as written in the file, decided once for every row it appears on. Use the recommended value, type
            your own, or keep the original. Values you haven&apos;t reviewed keep their original value in the download.
          </p>
          <div className="dm-progress" role="progressbar" aria-label="Values reviewed" aria-valuemin={0} aria-valuemax={review.length} aria-valuenow={done}>
            <span style={{ width: `${(done / review.length) * 100}%` }} />
          </div>
          <div className="dm-filters">
            <label className="field">
              <span className="field-label">Column</span>
              <select className="input" value={column} onChange={(e) => filter(() => setColumn(e.target.value))}>
                <option value="">All columns ({review.length})</option>
                {columns.map(([c, n]) => (
                  <option key={c} value={c}>
                    {c} ({n})
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field-label">Issue</span>
              <select className="input" value={kind} onChange={(e) => filter(() => setKind(e.target.value))}>
                <option value="">All issues</option>
                {kinds.map(([k, n]) => (
                  <option key={k} value={k}>
                    {k} ({n})
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field-label">Show</span>
              <select className="input" value={show} onChange={(e) => filter(() => setShow(e.target.value as Show))}>
                <option value="all">Everything</option>
                <option value="open">Not reviewed yet ({review.length - done})</option>
                <option value="done">Reviewed ({done})</option>
              </select>
            </label>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={!open.length}
              onClick={() => onDecide(Object.fromEntries(open.map((i) => [i.key, { choice: "rec" as const, mine: "" }])))}
            >
              {open.length ? `Accept the ${open.length === 1 ? "recommendation" : `${open.length} recommendations`} shown` : "All shown values are reviewed"}
            </button>
          </div>
          <DataTable
            label="Values to review"
            empty="Nothing matches these filters."
            columns={[
              { key: "column", label: "Column", width: "minmax(120px, 0.8fr)" },
              { key: "found", label: "Found", width: "minmax(170px, 1.2fr)" },
              { key: "issue", label: "Issue", width: "minmax(220px, 1.7fr)" },
              { key: "rec", label: "Recommended", width: "minmax(140px, 1fr)" },
              { key: "mine", label: "Your value", width: "minmax(150px, 1fr)" },
              { key: "use", label: "Use", width: "250px" },
            ]}
            rows={visible.slice(0, limit).map((it) => {
              const d = decisions[it.key];
              return {
                column: <span className="dm-cell-strong">{it.column}</span>,
                found: (
                  <span className="dm-found">
                    <span className="dm-value">{it.found}</span>
                    <span className="t-caption">{rowsLabel(it.rows)}</span>
                  </span>
                ),
                issue: (
                  <span className="dm-found">
                    <span className="dm-kinds">{it.kinds.join(" · ")}</span>
                    <span className="t-caption">{it.issue}</span>
                  </span>
                ),
                rec: <span className="dm-value">{shown(it.recommended)}</span>,
                mine: (
                  <input
                    className="input dm-mine"
                    value={d?.mine ?? ""}
                    placeholder="Type a value"
                    aria-label={`Your value for ${it.found}`}
                    onChange={(e) => decide(it, "mine", e.target.value)}
                  />
                ),
                use: (
                  <span className="dm-choice" role="radiogroup" aria-label={`What to use for ${it.found}`}>
                    {CHOICES.map((c) => (
                      <button
                        key={c.id}
                        type="button"
                        role="radio"
                        aria-checked={d?.choice === c.id}
                        title={c.title}
                        className={`dm-choice-btn${!d && c.id === "rec" ? " dm-choice-suggested" : ""}`}
                        onClick={() => decide(it, c.id)}
                      >
                        {c.label}
                      </button>
                    ))}
                  </span>
                ),
              };
            })}
          />
          {visible.length > limit && (
            <button type="button" className="btn btn-secondary" style={{ justifySelf: "start" }} onClick={() => setLimit(limit + PAGE)}>
              Show {Math.min(PAGE, visible.length - limit)} more of {visible.length - limit}
            </button>
          )}
        </>
      )}

      {auto.length > 0 && (
        <details className="dm-auto">
          <summary>
            Automatic fixes: {auto.length} {auto.length === 1 ? "value" : "values"}, no decision needed
          </summary>
          <p className="t-caption">Formatting HubSpot needs, applied to every row. Tick “Keep original” to undo one.</p>
          <DataTable
            label="Automatic fixes"
            columns={[
              { key: "column", label: "Column", width: "minmax(120px, 0.8fr)" },
              { key: "found", label: "Found", width: "minmax(170px, 1.2fr)" },
              { key: "rec", label: "Becomes", width: "minmax(150px, 1fr)" },
              { key: "issue", label: "Why", width: "minmax(200px, 1.5fr)" },
              { key: "undo", label: "Undo", width: "150px" },
            ]}
            rows={auto.slice(0, autoLimit).map((it) => ({
              column: <span className="dm-cell-strong">{it.column}</span>,
              found: (
                <span className="dm-found">
                  <span className="dm-value">{it.found}</span>
                  <span className="t-caption">{rowsLabel(it.rows)}</span>
                </span>
              ),
              rec: <span className="dm-value">{shown(it.recommended)}</span>,
              issue: <span className="t-caption">{it.issue}</span>,
              undo: (
                <Checkbox
                  checked={decisions[it.key]?.choice === "keep"}
                  onChange={(on) => onDecide({ [it.key]: on ? { choice: "keep", mine: "" } : null })}
                >
                  Keep original
                </Checkbox>
              ),
            }))}
          />
          {auto.length > autoLimit && (
            <button type="button" className="btn btn-secondary" style={{ justifySelf: "start" }} onClick={() => setAutoLimit(autoLimit + PAGE)}>
              Show {Math.min(PAGE, auto.length - autoLimit)} more of {auto.length - autoLimit}
            </button>
          )}
        </details>
      )}
    </section>
  );
}
