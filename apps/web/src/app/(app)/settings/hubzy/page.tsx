"use client";

/**
 * Hubzy Answers (admins only): the questions Hubzy offers in his help panel
 * and his answers, edited as one table. Each row can show on every page or
 * on one page only (its "What does this page do?" answer, for example).
 * Changes go live for the whole workspace when saved.
 */

import { useEffect, useMemo, useState } from "react";

import { useAppSession } from "@/components/AppSession";
import { PageHeader } from "@/components/PageHeader";
import { EditableTable, type Column, type Row } from "@/components/project/EditableTable";
import { Callout } from "@/components/ui";
import { ApiError, listHubzyTopics, saveHubzyTopics, type HubzyTopic } from "@/lib/api";
import { GUIDE_PAGES } from "@/lib/guide";

const EVERY_PAGE = "All pages";

/** Page key -> the name shown in the table (and back). */
const PAGE_NAMES: Record<string, string> = Object.fromEntries(GUIDE_PAGES.map((p) => [p.key, p.title]));

function toRows(topics: HubzyTopic[]): Row[] {
  return topics.map((t) => ({ id: t.id, page: t.page ? (PAGE_NAMES[t.page] ?? t.page) : EVERY_PAGE, question: t.question, answer: t.answer }));
}

function pageKeyOf(name: string): string {
  if (name === EVERY_PAGE) return "";
  return Object.entries(PAGE_NAMES).find(([, title]) => title === name)?.[0] ?? name;
}

export default function HubzyAnswersPage() {
  const { me } = useAppSession();
  const [saved, setSaved] = useState<Row[] | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!me.is_admin) return;
    listHubzyTopics()
      .then((topics) => {
        setSaved(toRows(topics));
        setRows(toRows(topics));
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Couldn't load Hubzy's answers."));
  }, [me.is_admin]);

  const dirty = saved !== null && JSON.stringify(rows) !== JSON.stringify(saved);

  // Don't lose edits to a closed tab.
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const columns = useMemo<Column[]>(() => {
    // Keep any page a row already uses, even if it isn't in the guide's list.
    const used = rows.map((r) => String(r.page)).filter((p) => p && p !== EVERY_PAGE && !Object.values(PAGE_NAMES).includes(p));
    return [
      { key: "question", label: "Question", kind: "text", width: "minmax(200px, 1fr)", placeholder: "e.g. What is a SOW?" },
      { key: "answer", label: "Answer", kind: "textarea", width: "minmax(320px, 2fr)", placeholder: "Hubzy's answer" },
      { key: "page", label: "Shows on", kind: "select", width: "190px", options: [EVERY_PAGE, ...Object.values(PAGE_NAMES), ...new Set(used)] },
    ];
  }, [rows]);

  const save = async () => {
    setError(null);
    setNotice(null);
    // Fully blank rows are just dropped; half-filled ones need finishing.
    const filled = rows.filter((r) => String(r.question).trim() || String(r.answer).trim());
    const incomplete = filled.findIndex((r) => !String(r.question).trim() || !String(r.answer).trim());
    if (incomplete >= 0) {
      setError(`Row ${rows.indexOf(filled[incomplete]!) + 1} needs both a question and an answer.`);
      return;
    }
    setBusy(true);
    try {
      const topics = await saveHubzyTopics(
        filled.map((r) => ({
          id: r.id ? String(r.id) : null,
          page: pageKeyOf(String(r.page)),
          question: String(r.question),
          answer: String(r.answer),
        })),
      );
      setSaved(toRows(topics));
      setRows(toRows(topics));
      setNotice(`Saved. Hubzy now knows ${topics.length} answer${topics.length === 1 ? "" : "s"}.`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save Hubzy's answers.");
    }
    setBusy(false);
  };

  return (
    <>
      <PageHeader
        eyebrow="HELP / HUBZY"
        breadcrumb={`${me.workspace_name}  /  ${me.name || me.email}`}
        title="Hubzy Answers"
        description="The questions Hubzy offers when someone clicks him, and his answers. Changes apply to everyone in the workspace once saved."
      />
      <div className="page-content hubzy-answers">
        {!me.is_admin ? (
          <Callout tone="info" title="Only admins can edit Hubzy's answers">
            Ask a workspace owner or admin if an answer needs changing.
          </Callout>
        ) : (
          <>
            {error && <Callout tone="error" title="Something went wrong">{error}</Callout>}
            {notice && <Callout tone="success" title={notice} />}
            {saved === null ? (
              !error && <div className="skeleton" style={{ height: 320 }} aria-busy="true" />
            ) : (
              <>
                <p className="t-description">
                  &ldquo;Shows on&rdquo; picks where a question appears: on every page, or only on one page (it&apos;s listed first
                  there). Rows run in the order shown; add new ones at the bottom.
                </p>
                <EditableTable
                  label="Hubzy answers"
                  columns={columns}
                  rows={rows}
                  onChange={(next) => {
                    setNotice(null);
                    setRows(next);
                  }}
                  addLabel="+ Add question"
                />
                <div className="row">
                  <button type="button" className="btn btn-primary" disabled={!dirty || busy} onClick={save}>
                    {busy ? "Saving…" : "Save changes"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={!dirty || busy}
                    onClick={() => {
                      setError(null);
                      setRows(saved);
                    }}
                  >
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
