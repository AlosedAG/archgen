"use client";

/**
 * A structured document made of text fields and editable tables (the
 * Requirements Document, Joint Evaluation Plan, Test Case Document), saved
 * to the project and exported in every format. Each document is a
 * definition (see lib/documents.ts); this renders any of them.
 */

import { useCallback } from "react";

import { exportSections, fileStub, type ExportSection, type SectionsFormat } from "@/lib/api";
import { useModuleState, type ModuleStore } from "@/lib/module-state";

import { useAppSession } from "../AppSession";
import { Callout, ExportFooter } from "../ui";
import { EditableTable, blankRow, type Column, type Row } from "./EditableTable";
import { ProjectHeader } from "./ProjectHeader";
import { SaveBanner } from "./SaveBanner";

export type DocumentState = { fields: Record<string, string>; tables: Record<string, Row[]> };

export type FieldDef = { kind: "field"; key: string; label: string; multiline?: boolean; placeholder?: string; help?: string };
export type TableDef = {
  kind: "table";
  key: string;
  title: string;
  caption?: string;
  columns: Column[];
  /** Starting rows for a new document (blank rows if a number). */
  defaults: Row[] | number;
  /** Export only rows with something in one of these columns (default: any column). */
  required?: string[];
  addLabel?: string;
};
export type Block = FieldDef | TableDef | { kind: "heading"; title: string; caption?: string };

export type DocumentDef = {
  module: string;
  title: string;
  eyebrow: string;
  description: string;
  documentType: string;
  fileSuffix: string;
  subtitle: string;
  blocks: Block[];
  exportSections: (state: DocumentState, clientName: string) => ExportSection[];
};

const FORMATS: SectionsFormat[] = ["docx", "xlsx", "csv", "pdf"];

export function normalizeDocument(def: DocumentDef, raw: unknown): DocumentState {
  const stored = (typeof raw === "object" && raw ? raw : {}) as Partial<DocumentState>;
  const tables: Record<string, Row[]> = {};
  const fields: Record<string, string> = {};
  for (const block of def.blocks) {
    if (block.kind === "table") {
      tables[block.key] =
        stored.tables?.[block.key] ??
        (typeof block.defaults === "number"
          ? Array.from({ length: block.defaults }, () => blankRow(block.columns))
          : block.defaults.map((r) => blankRow(block.columns, r)));
    } else if (block.kind === "field") {
      fields[block.key] = stored.fields?.[block.key] ?? "";
    }
  }
  return { fields, tables };
}

export function useDocumentState(def: DocumentDef, projectId: string): ModuleStore<DocumentState> {
  const normalize = useCallback((raw: unknown) => normalizeDocument(def, raw), [def]);
  return useModuleState<DocumentState>(projectId, def.module, normalize);
}

export function TableDocumentPage({
  def,
  top,
  bottom,
}: {
  def: DocumentDef;
  /** Extra content above the blocks (e.g. "load requirements" on Test Cases). */
  top?: (store: ModuleStore<DocumentState>) => React.ReactNode;
  bottom?: (store: ModuleStore<DocumentState>) => React.ReactNode;
}) {
  const { project } = useAppSession();
  const store = useDocumentState(def, project?.id ?? "");
  const { state, change, loaded } = store;
  const client = project?.client_name || project?.name || "";

  if (!project) return null;
  const header = <ProjectHeader eyebrow={def.eyebrow} title={def.title} description={def.description} />;
  if (store.status === "error" && !loaded) {
    return (
      <>
        {header}
        <div className="page-content">
          <Callout tone="error" title="Couldn't load this document">
            {store.error}
          </Callout>
        </div>
      </>
    );
  }
  if (!loaded) {
    return (
      <>
        {header}
        <div className="page-content" aria-busy="true">
          <div className="skeleton" style={{ height: 120 }} />
          <div className="skeleton" style={{ height: 220 }} />
        </div>
      </>
    );
  }

  const title = `${def.title} — ${client}`;
  return (
    <>
      {header}
      <div className="page-content">
        <SaveBanner store={store} />
        {top?.(store)}
        {def.blocks.map((block, i) => {
          if (block.kind === "heading") {
            return (
              <div key={`h${i}`} className="stack" style={{ gap: 4, marginTop: 8 }}>
                <h2 className="t-section">{block.title}</h2>
                {block.caption && <p className="t-description">{block.caption}</p>}
              </div>
            );
          }
          if (block.kind === "field") {
            const props = {
              className: block.multiline ? "textarea" : "input",
              placeholder: block.placeholder,
              value: state.fields[block.key] ?? "",
              onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
                const value = e.target.value;
                change((s) => ({ ...s, fields: { ...s.fields, [block.key]: value } }));
              },
            };
            return (
              <label key={block.key} className="field">
                <span className="field-label">{block.label}</span>
                {block.multiline ? <textarea {...props} /> : <input {...props} />}
                {block.help && <span className="t-caption">{block.help}</span>}
              </label>
            );
          }
          return (
            <section key={block.key} className="stack" style={{ gap: 10 }}>
              <div className="stack" style={{ gap: 4 }}>
                <h3 className="t-card-title">{block.title}</h3>
                {block.caption && <p className="t-description">{block.caption}</p>}
              </div>
              <EditableTable
                label={block.title}
                columns={block.columns}
                rows={state.tables[block.key] ?? []}
                addLabel={block.addLabel}
                onChange={(rows) => change((s) => ({ ...s, tables: { ...s.tables, [block.key]: rows } }))}
              />
            </section>
          );
        })}
        {bottom?.(store)}
        <ExportFooter
          library={{ projectId: project.id, documentType: def.documentType, title }}
          actions={FORMATS.map((format) => ({
            label: `.${format}`,
            make: () => exportSections(title, def.subtitle, def.exportSections(state, client), format, fileStub(client, def.fileSuffix)),
          }))}
        />
      </div>
    </>
  );
}
