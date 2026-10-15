"use client";

/**
 * An AI-drafted document: the generating state (progress, live text), then
 * Preview / Edit text tabs over a document card with its export footer.
 */

import { motion } from "framer-motion";
import { useState } from "react";
import ReactMarkdown from "react-markdown";

import { exportMarkdown, fileStub, textFile } from "@/lib/api";

import { ExportFooter, TabPanel, Tabs } from "../ui";
import { DraftProgress } from "./DraftProgress";

export function DocumentResult({
  markdown,
  streaming,
  onEdit,
  title,
  heading,
  eyebrow,
  status,
  clientName,
  fileSuffix,
  projectId,
  documentType,
  progress,
}: {
  markdown: string;
  streaming: boolean;
  onEdit: (markdown: string) => void;
  /** Export title. */
  title: string;
  /** Section heading above the tabs, e.g. "Business analysis". */
  heading?: string;
  /** Small caps line at the top of the document card. */
  eyebrow: string;
  /** Badge at the top right of the document card. */
  status: { label: string; tone: "keep" | "success" };
  clientName: string;
  fileSuffix: string;
  /** Saving to the library files it under this project and document type. */
  projectId: string;
  documentType: string;
  /** While drafting: sections the document should have, when it started, the latest status note. */
  progress?: { sections: number; startedAt: number; status: string | null };
}) {
  const [view, setView] = useState<"preview" | "edit">("preview");
  if (!markdown && !streaming) return null;
  const stub = fileStub(clientName, fileSuffix);
  const tabs = (
    <Tabs
      label="Document view"
      layoutId={`doc-${fileSuffix}`}
      variant="secondary"
      tabs={[
        { id: "preview", label: "Preview" },
        { id: "edit", label: "Edit text" },
      ]}
      active={streaming ? "preview" : view}
      onChange={(id) => !streaming && setView(id)}
    />
  );

  return (
    <motion.section className="stack" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      {heading && (
        <div className="heading-row">
          <h2 className="t-section">{heading}</h2>
          {!streaming && <span className="badge badge-success">Generated</span>}
        </div>
      )}
      {tabs}
      {streaming ? (
        <div className="stack" aria-busy="true">
          <p className="drafting-label">Drafting your {heading ? heading.toLowerCase() : "document"}…</p>
          <DraftProgress
            text={markdown}
            sections={progress?.sections ?? 1}
            startedAt={progress?.startedAt ?? Date.now()}
            status={progress?.status ?? null}
          />
          <div className="doc">
            <ReactMarkdown>{markdown}</ReactMarkdown>
          </div>
          <span className="caret" aria-hidden />
          <p className="t-caption">The preview updates as the draft arrives. Wait for completion before editing or downloading.</p>
        </div>
      ) : (
        <TabPanel panelKey={view} id={`doc-${fileSuffix}`}>
          {view === "edit" ? (
            <div className="stack">
              <label className="field">
                <span className="field-label">Editable document text</span>
                <textarea
                  className="textarea markdown-editor"
                  value={markdown}
                  onChange={(e) => onEdit(e.target.value)}
                />
              </label>
              <p className="t-caption">Markdown headings, lists, and paragraphs are preserved in your editable exports.</p>
              <ExportActions markdown={markdown} title={title} stub={stub} projectId={projectId} documentType={documentType} />
            </div>
          ) : (
            <article className="doc-card">
              <div className="heading-row">
                <span className="t-eyebrow">{eyebrow}</span>
                <span className={`badge badge-${status.tone}`}>{status.label}</span>
              </div>
              <div className="doc">
                <ReactMarkdown>{markdown}</ReactMarkdown>
              </div>
              <ExportActions markdown={markdown} title={title} stub={stub} projectId={projectId} documentType={documentType} />
            </article>
          )}
        </TabPanel>
      )}
    </motion.section>
  );
}

function ExportActions({
  markdown,
  title,
  stub,
  projectId,
  documentType,
}: {
  markdown: string;
  title: string;
  stub: string;
  projectId: string;
  documentType: string;
}) {
  return (
    <ExportFooter
      actions={[
        { label: ".docx", make: () => exportMarkdown(markdown, title, "docx", stub) },
        { label: ".pdf", make: () => exportMarkdown(markdown, title, "pdf", stub) },
        { label: ".md", make: () => textFile(markdown, `${stub}.md`, "text/markdown") },
      ]}
      library={{ projectId, documentType, title }}
    />
  );
}
