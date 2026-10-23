"use client";

/**
 * SOW Clause Library (admins only): the firm's standard terms, copied into
 * every new SOW. Admins refine the set once here (titles, text, [[blanks]],
 * which clauses new SOWs include) and every proposal reuses it; each SOW can
 * still switch clauses off or edit them for that deal. The texts are
 * placeholder templates for the firm's counsel to review, not legal advice.
 */

import { useEffect, useState } from "react";

import { useAppSession } from "@/components/AppSession";
import { NavIcon } from "@/components/NavIcons";
import { PageHeader } from "@/components/PageHeader";
import { Callout, Checkbox } from "@/components/ui";
import { ApiError, listSowClauses, saveSowClauses, type LibraryClause } from "@/lib/api";
import { blanksIn, LEGAL_NOTE, TOKENS } from "@/lib/clauses";

type Draft = { id: string | null; key: string; title: string; body: string; include_by_default: boolean };

const toDraft = (c: LibraryClause): Draft => ({ id: c.id, key: c.key, title: c.title, body: c.body, include_by_default: c.include_by_default });

export default function ClauseLibraryPage() {
  const { me } = useAppSession();
  const [saved, setSaved] = useState<Draft[] | null>(null);
  const [rows, setRows] = useState<Draft[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!me.is_admin) return;
    listSowClauses()
      .then((list) => {
        setSaved(list.map(toDraft));
        setRows(list.map(toDraft));
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Couldn't load the clause library."));
  }, [me.is_admin]);

  const dirty = saved !== null && JSON.stringify(rows) !== JSON.stringify(saved);
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const update = (i: number, patch: Partial<Draft>) => {
    setNotice(null);
    setRows((all) => all.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  };
  const move = (i: number, by: number) =>
    setRows((all) => {
      const next = [...all];
      const [row] = next.splice(i, 1);
      next.splice(Math.min(Math.max(i + by, 0), next.length), 0, row!);
      return next;
    });

  const save = async () => {
    setError(null);
    setNotice(null);
    const empty = rows.findIndex((r) => !r.title.trim() || !r.body.trim());
    if (empty >= 0) {
      setError(`Clause ${empty + 1} needs both a title and text (or remove it).`);
      return;
    }
    setBusy(true);
    try {
      const list = await saveSowClauses(rows);
      setSaved(list.map(toDraft));
      setRows(list.map(toDraft));
      setNotice("Saved. New SOWs start from these clauses; existing SOWs can pull in new ones from their Terms tab.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save the clauses.");
    }
    setBusy(false);
  };

  return (
    <>
      <PageHeader
        eyebrow="HELP / SOW CLAUSES"
        breadcrumb={`${me.workspace_name}  /  ${me.name || me.email}`}
        title="SOW Clause Library"
        description="The firm's standard terms: refined once here, copied into every new Proposal & SOW."
      />
      <div className="page-content">
        {!me.is_admin ? (
          <Callout tone="info" title="Only admins can edit the firm's standard clauses">
            You can still switch clauses on or off and fill in their blanks in each SOW&apos;s Terms tab.
          </Callout>
        ) : (
          <>
            <Callout tone="warning" title="Have your legal team review these terms">
              {LEGAL_NOTE}
            </Callout>
            {error && <Callout tone="error" title="Something went wrong">{error}</Callout>}
            {notice && <Callout tone="success" title={notice} />}
            {saved === null ? (
              !error && <div className="skeleton" style={{ height: 320 }} aria-busy="true" />
            ) : (
              <>
                <p className="t-description">
                  Mark what each SOW must fill in as <code>[[a blank]]</code> (cap amount, governing state, notice periods…).{" "}
                  {Object.entries(TOKENS)
                    .map(([token, what]) => `{{${token}}} becomes ${what}`)
                    .join(", ")}
                  .
                </p>
                <ol className="clause-list">
                  {rows.map((row, i) => {
                    const blanks = blanksIn(row.body);
                    return (
                      <li key={row.id ?? `new-${i}`} className="clause-card">
                        <div className="clause-head">
                          <input className="input clause-title" aria-label={`Clause ${i + 1} title`} value={row.title} onChange={(e) => update(i, { title: e.target.value })} />
                          <button type="button" className="icon-btn" aria-label={`Move ${row.title || "clause"} up`} disabled={i === 0} onClick={() => move(i, -1)}>
                            <NavIcon name="chevron-down" size={15} className="icon-flip" />
                          </button>
                          <button type="button" className="icon-btn" aria-label={`Move ${row.title || "clause"} down`} disabled={i === rows.length - 1} onClick={() => move(i, 1)}>
                            <NavIcon name="chevron-down" size={15} />
                          </button>
                          <button type="button" className="btn-link btn-link-danger" onClick={() => setRows((all) => all.filter((_, j) => j !== i))}>
                            Remove
                          </button>
                        </div>
                        <textarea className="textarea" rows={6} aria-label={`${row.title || `Clause ${i + 1}`} text`} value={row.body} onChange={(e) => update(i, { body: e.target.value })} />
                        <div className="clause-foot">
                          <Checkbox checked={row.include_by_default} onChange={(on) => update(i, { include_by_default: on })}>
                            Included in new SOWs
                          </Checkbox>
                          <span className="t-caption">{blanks.length ? `Blanks: ${blanks.join(", ")}` : "No blanks."}</span>
                        </div>
                      </li>
                    );
                  })}
                </ol>
                <button
                  type="button"
                  className="btn-link"
                  style={{ width: "fit-content" }}
                  onClick={() => setRows((all) => [...all, { id: null, key: "", title: "New clause", body: "", include_by_default: true }])}
                >
                  + Add clause
                </button>
                <div className="row">
                  <button type="button" className="btn btn-primary" disabled={!dirty || busy} onClick={save}>
                    {busy ? "Saving…" : "Save changes"}
                  </button>
                  <button type="button" className="btn btn-secondary" disabled={!dirty || busy} onClick={() => setRows(saved)}>
                    Discard changes
                  </button>
                  {dirty && <span className="t-description">Unsaved changes</span>}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </>
  );
}
