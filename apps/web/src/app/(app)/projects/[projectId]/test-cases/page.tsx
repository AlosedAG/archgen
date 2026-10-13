"use client";

/** Test cases, optionally seeded from this project's Requirements Document. */

import { useState } from "react";

import { blankRow, type Row } from "@/components/project/EditableTable";
import { TableDocumentPage, type DocumentState } from "@/components/project/TableDocument";
import { AnimatedNumber, Callout } from "@/components/ui";
import { ApiError, getModuleState } from "@/lib/api";
import { TEST_CASE_COLUMNS, TEST_CASE_DOCUMENT } from "@/lib/documents";
import type { ModuleStore } from "@/lib/module-state";

function LoadRequirements({ store }: { store: ModuleStore<DocumentState> }) {
  const [message, setMessage] = useState<{ tone: "success" | "warning"; text: string } | null>(null);
  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="row">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={async () => {
            try {
              const saved = await getModuleState(store.projectId, "requirements");
              const rows = ((saved.data as Partial<DocumentState>).tables?.requirements ?? []).filter((r) =>
                String(r.requirement ?? "").trim(),
              );
              if (!rows.length) {
                setMessage({ tone: "warning", text: "This project's Requirements Document has no requirements yet." });
                return;
              }
              const added: Row[] = rows.map((r, i) =>
                blankRow(TEST_CASE_COLUMNS, { requirement: `Customer Requirement ${i + 1}: ${String(r.requirement)}` }),
              );
              store.change((s) => {
                const existing = (s.tables.cases ?? []).filter((r) => String(r.requirement ?? "").trim() || String(r.description ?? "").trim());
                return { ...s, tables: { ...s.tables, cases: [...existing, ...added] } };
              });
              setMessage({ tone: "success", text: `Added ${added.length} test case${added.length === 1 ? "" : "s"} from the Requirements Document.` });
            } catch (e) {
              setMessage({ tone: "warning", text: e instanceof ApiError ? e.message : "Couldn't read the Requirements Document." });
            }
          }}
        >
          Load requirements from the Requirements Document
        </button>
        <span className="t-caption">Adds one test case per customer requirement, ready for steps and expected results.</span>
      </div>
      {message && (
        <Callout tone={message.tone} title={message.tone === "success" ? "Requirements loaded" : "Nothing to load"}>
          {message.text}
        </Callout>
      )}
    </div>
  );
}

function Results({ store }: { store: ModuleStore<DocumentState> }) {
  const cases = (store.state.tables.cases ?? []).filter((r) => String(r.requirement ?? "").trim() || String(r.description ?? "").trim());
  const count = (result: string) => cases.filter((r) => r.actual === result).length;
  return (
    <div className="stats">
      {[
        ["Test cases", cases.length],
        ["Met expectations", count("Met Expectations")],
        ["Issues identified", count("Issues Identified")],
        ["Not tested yet", count("Not Tested")],
      ].map(([label, value]) => (
        <div key={label} className="stat">
          <span className="stat-label">{label}</span>
          <span className="stat-value">
            <AnimatedNumber value={value as number} />
          </span>
        </div>
      ))}
    </div>
  );
}

export default function TestCasesPage() {
  return (
    <TableDocumentPage
      def={TEST_CASE_DOCUMENT}
      top={(store) => <LoadRequirements store={store} />}
      bottom={(store) => <Results store={store} />}
    />
  );
}
