"use client";

/**
 * The SOW builder's Terms tab: this SOW's copy of the firm's clause library.
 * Each clause can be switched on or off, edited, and its [[blanks]] filled for
 * this deal; clauses missing from the SOW can be pulled in from the library,
 * and an edited one put back to the firm's text. Confidentiality (a fixed
 * section of every SOW) and the validity / effective dates live here too.
 */

import { useEffect, useState } from "react";

import { Callout, Checkbox } from "@/components/ui";
import { ApiError, listSowClauses, type LibraryClause, type ProposalDocument } from "@/lib/api";
import { clauseBlanks, LEGAL_NOTE, TOKENS } from "@/lib/clauses";

type Clause = NonNullable<ProposalDocument["clauses"]>[number];
type Props = { doc: ProposalDocument; set: (patch: Partial<ProposalDocument>) => void };

const toClause = (c: LibraryClause): Clause => ({ key: c.key, title: c.title, body: c.body, include: c.include_by_default });

export function TermsTab({ doc, set }: Props) {
  const [library, setLibrary] = useState<LibraryClause[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const clauses = doc.clauses ?? [];

  useEffect(() => {
    listSowClauses()
      .then(setLibrary)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Couldn't load the firm's clause library."));
  }, []);

  const byKey = new Map((library ?? []).map((c) => [c.key, c]));
  const missing = (library ?? []).filter((c) => !clauses.some((s) => s.key === c.key));
  const update = (i: number, patch: Partial<Clause>) => set({ clauses: clauses.map((c, j) => (j === i ? { ...c, ...patch } : c)) });

  return (
    <div className="stack" style={{ gap: 20 }}>
      <Callout tone="warning" title="Have your legal team review these terms">
        {LEGAL_NOTE} The firm&apos;s standard set lives under Help &gt; SOW Clause Library (admins).
      </Callout>
      {error && <Callout tone="error" title="Something went wrong">{error}</Callout>}

      <section className="grid-3">
        <label className="field">
          <span className="field-label">Proposal valid until</span>
          <input type="date" className="input" value={String(doc.valid_until ?? "").slice(0, 10)} onChange={(e) => set({ valid_until: e.target.value })} />
        </label>
        <label className="field">
          <span className="field-label">Effective date</span>
          <input type="date" className="input" value={String(doc.effective_date ?? "").slice(0, 10)} onChange={(e) => set({ effective_date: e.target.value })} />
        </label>
      </section>
      <p className="t-caption">
        Write blanks to fill as <code>[[like this]]</code>; the SOW can&apos;t be sent while one is left in a clause that&apos;s switched on.{" "}
        {Object.entries(TOKENS)
          .map(([token, what]) => `{{${token}}} is ${what}`)
          .join(", ")}
        , filled in automatically.
      </p>

      <label className="field">
        <span className="field-label">Confidentiality (always included)</span>
        <textarea className="textarea" rows={3} value={doc.confidentiality ?? ""} onChange={(e) => set({ confidentiality: e.target.value })} />
      </label>

      <div className="row">
        <button type="button" className="btn btn-secondary" disabled={!missing.length} onClick={() => set({ clauses: [...clauses, ...missing.map(toClause)] })}>
          {missing.length ? `Add the firm's ${missing.length} missing clause${missing.length === 1 ? "" : "s"}` : "Every firm clause is here"}
        </button>
        <button
          type="button"
          className="btn-link"
          disabled={!library}
          onClick={() => {
            if (library && window.confirm("Replace this SOW's terms with the firm's current clauses? Edits and filled-in blanks here are lost.")) {
              set({ clauses: library.map(toClause) });
            }
          }}
        >
          Start over from the firm&apos;s clauses
        </button>
      </div>

      <ol className="clause-list">
        {clauses.map((clause, i) => {
          const firm = clause.key ? byKey.get(clause.key) : undefined;
          const edited = firm && (firm.title !== clause.title || firm.body !== clause.body);
          const blanks = clauseBlanks(`${clause.title ?? ""} ${clause.body ?? ""}`, {
            client: doc.client?.company,
            seller: doc.seller?.company,
            valid_until: doc.valid_until,
            effective_date: doc.effective_date,
          });
          return (
            <li key={`${clause.key || "custom"}-${i}`} className={`clause-card${clause.include === false ? " clause-off" : ""}`}>
              <div className="clause-head">
                <Checkbox checked={clause.include !== false} onChange={(on) => update(i, { include: on })}>
                  <span className="visually-hidden">Include {clause.title || `clause ${i + 1}`}</span>
                </Checkbox>
                <input
                  className="input clause-title"
                  aria-label={`Clause ${i + 1} title`}
                  value={clause.title ?? ""}
                  onChange={(e) => update(i, { title: e.target.value })}
                />
                {edited && (
                  <button type="button" className="btn-link" onClick={() => update(i, { title: firm.title, body: firm.body })}>
                    Reset to the firm&apos;s text
                  </button>
                )}
                {!firm && (
                  <button type="button" className="btn-link btn-link-danger" onClick={() => set({ clauses: clauses.filter((_, j) => j !== i) })}>
                    Remove
                  </button>
                )}
              </div>
              <textarea
                className="textarea"
                rows={5}
                aria-label={`${clause.title || `Clause ${i + 1}`} text`}
                value={clause.body ?? ""}
                onChange={(e) => update(i, { body: e.target.value })}
              />
              <span className="t-caption">
                {clause.include === false
                  ? "Not included in this SOW."
                  : blanks.length
                    ? `To fill in: ${blanks.join(", ")}`
                    : edited
                      ? "Edited for this SOW."
                      : "Ready."}
              </span>
            </li>
          );
        })}
      </ol>
      <button
        type="button"
        className="btn-link"
        style={{ width: "fit-content" }}
        onClick={() => set({ clauses: [...clauses, { key: "", title: "New clause", body: "", include: true }] })}
      >
        + Add a clause to this SOW only
      </button>
    </div>
  );
}
