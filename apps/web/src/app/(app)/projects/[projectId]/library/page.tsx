"use client";

/** The project library: every document saved from this project's pages, grouped by type. */

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useAppSession } from "@/components/AppSession";
import { PageHeader } from "@/components/PageHeader";
import { Callout, spring } from "@/components/ui";
import { ApiError, deleteDocument, downloadDocument, listDocuments, type LibraryDocument } from "@/lib/api";

function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function ext(filename: string): string {
  return filename.includes(".") ? (filename.split(".").pop() ?? "") : "file";
}

export default function LibraryPage() {
  const { project, me } = useAppSession();
  const [documents, setDocuments] = useState<LibraryDocument[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!project) return;
    listDocuments(project.id)
      .then(setDocuments)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Couldn't load the library."));
  }, [project]);
  useEffect(load, [load]);

  if (!project) return null;
  const groups = new Map<string, LibraryDocument[]>();
  for (const doc of documents ?? []) groups.set(doc.document_type, [...(groups.get(doc.document_type) ?? []), doc]);

  return (
    <>
      <PageHeader
        eyebrow="LIBRARY"
        breadcrumb={`${project.client_name || project.name}  /  ${me.workspace_name}`}
        title="Project Library"
        description="Every document saved from this project, with editable downloads."
      />
      <div className="page-content">
        {error && <Callout tone="error" title="Something went wrong">{error}</Callout>}
        {documents === null ? (
          <div className="skeleton" style={{ height: 160 }} aria-busy="true" />
        ) : documents.length === 0 ? (
          <div className="stack">
            <h2 className="t-section">No saved documents yet</h2>
            <p className="flagged-line">
              Generate a discovery document, then choose Save to Project Library. This client&apos;s documents will
              appear here with editable downloads.
            </p>
            <Link href={`/projects/${project.id}/discovery`} className="btn btn-primary" style={{ width: "fit-content" }}>
              Open Discovery Call Assistant
            </Link>
          </div>
        ) : (
          [...groups.entries()].map(([type, docs]) => (
            <section key={type} className="build-section">
              <div className="heading-row">
                <h2 className="t-section">{type}</h2>
                <span className="badge badge-neutral">
                  {docs.length} file{docs.length === 1 ? "" : "s"}
                </span>
              </div>
              <div className="build-list">
                <AnimatePresence initial={false}>
                  {docs.map((doc) => (
                    <motion.div
                      key={doc.id}
                      className="doc-row"
                      layout
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={spring}
                    >
                      <span className="file-chip">{ext(doc.filename)}</span>
                      <span className="doc-row-body">
                        <span className="doc-row-name" title={doc.filename}>
                          {doc.filename}
                        </span>
                        <span className="t-caption">
                          {new Date(doc.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })} ·{" "}
                          {size(doc.size_bytes)}
                        </span>
                      </span>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => downloadDocument(project.id, doc).catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Download failed."))}
                      >
                        ↓  Download
                      </button>
                      {confirming === doc.id ? (
                        <>
                          <button
                            type="button"
                            className="btn btn-danger"
                            onClick={async () => {
                              try {
                                await deleteDocument(project.id, doc.id);
                                setDocuments((all) => (all ?? []).filter((d) => d.id !== doc.id));
                              } catch (e) {
                                setError(e instanceof ApiError ? e.message : "Couldn't delete it.");
                              }
                              setConfirming(null);
                            }}
                          >
                            Delete
                          </button>
                          <button type="button" className="btn-link" onClick={() => setConfirming(null)}>
                            Cancel
                          </button>
                        </>
                      ) : (
                        <button type="button" className="btn-link" onClick={() => setConfirming(doc.id)}>
                          Delete…
                        </button>
                      )}
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            </section>
          ))
        )}
      </div>
    </>
  );
}
