"use client";

/**
 * Data Migration: one page to turn a client's export into a CSV HubSpot
 * imports cleanly. 1) Drop a .csv or .xlsx file; 2) each column's HubSpot
 * format is suggested and can be changed (and renamed); 3) the values that
 * need a judgement call are listed once each with a recommended fix, to
 * accept, replace or ignore (DataReview); 4) records entered more than once
 * are grouped to merge or keep apart (DataDuplicates); 5) the cleaned file, a
 * report of every change and a short summary (PDF or Word) update as you go,
 * ready to download. All processing happens in the browser (lib/data-*), so
 * the client's data is never uploaded.
 */

import { useDeferredValue, useMemo, useRef, useState } from "react";

import { DataTable } from "@/components/project/DataTable";
import { DataDuplicates } from "@/components/tools/DataDuplicates";
import { DataReview } from "@/components/tools/DataReview";
import { Stats } from "@/components/project/Stats";
import { NavIcon } from "@/components/NavIcons";
import { Callout, Checkbox } from "@/components/ui";
import { downloadFile, textFile } from "@/lib/api";
import {
  cleanTable,
  FORMATS,
  parseCsv,
  sheetToTable,
  suggestFormat,
  toCsv,
  type CleanOptions,
  type ColumnSpec,
  type FormatId,
  type Table,
} from "@/lib/data-cleaner";
import { applyDuplicates, findDuplicates, notesColumns, suggestKeys, type DupDecision } from "@/lib/data-duplicates";
import { buildReport, reportDocx, reportPdf } from "@/lib/data-report";
import { findItems, overridesFor, type Decision } from "@/lib/data-review";

type Loaded = { fileName: string; sheets: { name: string; table: Table }[]; sheet: number };

const PREVIEW_ROWS = 12;
const ISSUE_ROWS = 100;
const FORMAT_HINT = Object.fromEntries(FORMATS.map((f) => [f.id, f.hint])) as Record<FormatId, string>;

async function readFile(file: File): Promise<Loaded> {
  const name = file.name.toLowerCase();
  if (name.endsWith(".csv") || name.endsWith(".txt") || file.type === "text/csv") {
    return { fileName: file.name, sheets: [{ name: "CSV", table: parseCsv(await file.text()) }], sheet: 0 };
  }
  if (name.endsWith(".xlsx")) {
    const { default: readXlsxFile } = await import("read-excel-file/browser");
    const sheets = await readXlsxFile(file);
    return {
      fileName: file.name,
      sheets: sheets.map((s) => ({ name: s.sheet, table: sheetToTable(s.data as unknown[][]) })),
      sheet: Math.max(0, sheets.findIndex((s) => s.data.length > 1)),
    };
  }
  throw new Error(name.endsWith(".xls") ? "Old .xls files aren't supported: open it in Excel and save as .xlsx or .csv." : "Choose a .csv or .xlsx file.");
}

function specsFor(table: Table): ColumnSpec[] {
  return table.headers.map((h, i) => ({ name: h, format: suggestFormat(h, table.rows.map((r) => r[i] ?? "")), options: "" }));
}

const stem = (fileName: string) => fileName.replace(/\.[^.]+$/, "");

/** Applies ``changes`` to a decisions map; null removes a decision. */
function patch<T>(all: Record<string, T>, changes: Record<string, T | null>): Record<string, T> {
  const next = { ...all };
  for (const [key, d] of Object.entries(changes)) {
    if (d) next[key] = d;
    else delete next[key];
  }
  return next;
}

export function DataMigration() {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [specs, setSpecs] = useState<ColumnSpec[]>([]);
  const [options, setOptions] = useState<CleanOptions>({ dateOrder: "auto", countryCode: "", removeDuplicates: true });
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  /** Columns duplicates are matched on; null until changed, which means the suggested ones. */
  const [dupKeys, setDupKeys] = useState<string[] | null>(null);
  const [dupDecisions, setDupDecisions] = useState<Record<string, DupDecision>>({});
  const [reporting, setReporting] = useState<"pdf" | "docx" | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const table = loaded?.sheets[loaded.sheet]?.table ?? null;

  const startOver = () => {
    setDecisions({});
    setDupKeys(null);
    setDupDecisions({});
    setReportError(null);
  };

  const open = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    setReading(true);
    try {
      const next = await readFile(file);
      const t = next.sheets[next.sheet]?.table;
      if (!t || !t.headers.length) throw new Error("That file has no rows to clean.");
      setLoaded(next);
      setSpecs(specsFor(t));
      startOver();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't read that file.");
    }
    setReading(false);
  };

  // Re-cleaning runs as you change formats and decide values; deferred so typing stays smooth on big files.
  const deferredSpecs = useDeferredValue(specs);
  const deferredOptions = useDeferredValue(options);
  const deferredDecisions = useDeferredValue(decisions);
  const ready = Boolean(table && deferredSpecs.length === table.headers.length);
  const items = useMemo(() => (table && ready ? findItems(table, deferredSpecs, deferredOptions) : []), [table, ready, deferredSpecs, deferredOptions]);
  const overrides = useMemo(() => overridesFor(items, deferredDecisions), [items, deferredDecisions]);
  const result = useMemo(
    () => (table && ready ? cleanTable(table, deferredSpecs, deferredOptions, overrides) : null),
    [table, ready, deferredSpecs, deferredOptions, overrides],
  );
  const pending = items.filter((i) => i.review && !decisions[i.key]).length;
  const decide = (changes: Record<string, Decision | null>) => setDecisions((all) => patch(all, changes));

  // Duplicates are found on the cleaned values, after the decisions above.
  const keys = result ? (dupKeys ?? suggestKeys(result)).filter((k) => result.headers.includes(k)) : [];
  const keysKey = keys.join("\u0001");
  const groups = useMemo(
    () => (result && keysKey ? findDuplicates(result, keysKey.split("\u0001").map((k) => result.headers.indexOf(k))) : []),
    [result, keysKey],
  );
  const notes = useMemo(() => (result ? notesColumns(result) : []), [result]);
  const deferredDupDecisions = useDeferredValue(dupDecisions);
  const final = useMemo(
    () => (result ? applyDuplicates(result, groups, deferredDupDecisions, notes) : null),
    [result, groups, deferredDupDecisions, notes],
  );
  const pendingDups = groups.filter((g) => !dupDecisions[g.key]).length;

  const downloadReport = async (format: "pdf" | "docx") => {
    if (!loaded || !result || !final) return;
    setReporting(format);
    setReportError(null);
    try {
      const report = buildReport({
        fileName: loaded.fileName,
        sheet: loaded.sheets.length > 1 ? loaded.sheets[loaded.sheet]?.name : undefined,
        rowsIn: result.stats.rowsIn,
        cleaned: result,
        final,
        items,
        decisions,
        groups,
        keys,
        skipped: specs.filter((s) => s.format === "skip").map((s) => s.name),
      });
      const blob = format === "pdf" ? await reportPdf(report) : await reportDocx(report);
      downloadFile({ blob, filename: `${stem(loaded.fileName)}_cleanup_report.${format}` });
    } catch {
      setReportError("Couldn't create the report. Try again, or download the change report (CSV) instead.");
    }
    setReporting(null);
  };
  // Each column's result, by its position in the file (skipped columns have none).
  const reports = new Map<number, NonNullable<typeof result>["columns"][number]>();
  let kept = 0;
  deferredSpecs.forEach((s, i) => {
    const report = s.format === "skip" ? undefined : result?.columns[kept++];
    if (report) reports.set(i, report);
  });
  const setSpec = (i: number, patch: Partial<ColumnSpec>) => setSpecs((all) => all.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const distinct = (i: number) =>
    [...new Set((table?.rows ?? []).map((r) => (r[i] ?? "").trim()).filter(Boolean))].slice(0, 60).join("\n");

  return (
    <div className="stack" style={{ gap: 20 }}>
      {/* 1 · Upload */}
      <section className="card stack" style={{ gap: 12 }} aria-labelledby="dm-1">
        <h2 id="dm-1" className="t-section">
          1 · Upload the file to import
        </h2>
        <div
          className={`dm-drop${dragging ? " dm-drop-over" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            void open(e.dataTransfer.files[0]);
          }}
        >
          <NavIcon name="files" size={26} />
          <div>
            <b>{loaded ? loaded.fileName : "Drop a .csv or .xlsx file here"}</b>
            <span className="t-caption">
              {loaded && table
                ? `${table.rows.length.toLocaleString()} rows · ${table.headers.length} columns. Drop another file to start over.`
                : "It stays on your computer: the cleaning runs in your browser."}
            </span>
          </div>
          <button type="button" className="btn btn-secondary" disabled={reading} onClick={() => input.current?.click()}>
            {reading ? "Reading…" : loaded ? "Choose another file" : "Choose a file"}
          </button>
          <input
            ref={input}
            type="file"
            accept=".csv,.txt,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            hidden
            onChange={(e) => {
              void open(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </div>
        {loaded && loaded.sheets.length > 1 && (
          <label className="field" style={{ maxWidth: 320 }}>
            <span className="field-label">Sheet</span>
            <select
              className="input"
              value={loaded.sheet}
              onChange={(e) => {
                const sheet = Number(e.target.value);
                setLoaded({ ...loaded, sheet });
                setSpecs(specsFor(loaded.sheets[sheet]!.table));
                startOver();
              }}
            >
              {loaded.sheets.map((s, i) => (
                <option key={s.name} value={i}>
                  {s.name} ({s.table.rows.length} rows)
                </option>
              ))}
            </select>
          </label>
        )}
        {error && <Callout tone="error" title="Couldn't read the file">{error}</Callout>}
      </section>

      {table && (
        <>
          {/* 2 · Formats */}
          <section className="card stack" style={{ gap: 12 }} aria-labelledby="dm-2">
            <h2 id="dm-2" className="t-section">
              2 · Choose how each column will be imported
            </h2>
            <p className="t-caption">
              Formats are suggested from the headers and values; change any that are wrong. Rename a column to the HubSpot property it
              maps to so the import matches it automatically.
            </p>
            <div className="grid-3">
              <label className="field">
                <span className="field-label">Dates like 03/04/2025 are</span>
                <select className="input" value={options.dateOrder} onChange={(e) => setOptions({ ...options, dateOrder: e.target.value as CleanOptions["dateOrder"] })}>
                  <option value="auto">Detected per column</option>
                  <option value="mdy">Month first (03 = March)</option>
                  <option value="dmy">Day first (03 = 3rd)</option>
                </select>
              </label>
              <label className="field">
                <span className="field-label">Country code for phones without one</span>
                <input className="input" placeholder="e.g. +52 (optional)" value={options.countryCode} onChange={(e) => setOptions({ ...options, countryCode: e.target.value })} />
              </label>
              <div className="field" style={{ justifyContent: "end" }}>
                <Checkbox checked={options.removeDuplicates} onChange={(on) => setOptions({ ...options, removeDuplicates: on })}>
                  Remove rows that are exact copies
                </Checkbox>
              </div>
            </div>
            <ol className="dm-columns">
              {specs.map((spec, i) => {
                const report = reports.get(i);
                const samples = table.rows.map((r) => (r[i] ?? "").trim()).filter(Boolean).slice(0, 3);
                const needsOptions = spec.format === "dropdown" || spec.format === "multi";
                return (
                  <li key={table.headers[i]} className={`dm-col${spec.format === "skip" ? " dm-col-skip" : ""}`}>
                    <div className="dm-col-main">
                      <span className="dm-col-source" title="Column in your file">
                        {table.headers[i]}
                      </span>
                      <span className="dm-col-samples">{samples.length ? samples.join(" · ") : "(empty column)"}</span>
                    </div>
                    <label className="field">
                      <span className="field-label">Name in the cleaned file</span>
                      <input className="input" value={spec.name} onChange={(e) => setSpec(i, { name: e.target.value })} />
                    </label>
                    <label className="field">
                      <span className="field-label">HubSpot format</span>
                      <select className="input" value={spec.format} onChange={(e) => setSpec(i, { format: e.target.value as FormatId })}>
                        {FORMATS.map((f) => (
                          <option key={f.id} value={f.id}>
                            {f.label}
                          </option>
                        ))}
                      </select>
                      <span className="t-caption">{FORMAT_HINT[spec.format]}</span>
                    </label>
                    <div className="dm-col-result">
                      {spec.format === "skip" ? (
                        <span className="pill pill-idle">Not imported</span>
                      ) : report ? (
                        <>
                          {report.fixed > 0 && <span className="pill pill-stage">{report.fixed} fixed</span>}
                          {report.blanked > 0 && <span className="pill pill-warn">{report.blanked} left blank</span>}
                          {!report.fixed && !report.blanked && <span className="pill pill-ok">Ready</span>}
                          {report.detail && <span className="t-caption">{report.detail}</span>}
                        </>
                      ) : null}
                    </div>
                    {needsOptions && (
                      <label className="field dm-col-options">
                        <span className="field-label">
                          Allowed options (one per line, as in HubSpot){" "}
                          <button type="button" className="btn-link" onClick={() => setSpec(i, { options: distinct(i) })}>
                            Use the values in the file
                          </button>
                        </span>
                        <textarea className="textarea" rows={3} value={spec.options} onChange={(e) => setSpec(i, { options: e.target.value })} placeholder="Leave empty to keep values as they are" />
                      </label>
                    )}
                  </li>
                );
              })}
            </ol>
          </section>

          {/* 3 · Review */}
          {ready && <DataReview items={items} decisions={decisions} onDecide={decide} />}

          {/* 4 · Duplicates */}
          {result && (
            <DataDuplicates
              result={result}
              keys={keys}
              onKeys={(next) => {
                setDupKeys(next);
                setDupDecisions({});
              }}
              groups={groups}
              decisions={dupDecisions}
              onDecide={(changes) => setDupDecisions((all) => patch(all, changes))}
              notes={notes}
            />
          )}

          {/* 5 · Results */}
          {final && (
            <section className="card stack" style={{ gap: 14 }} aria-labelledby="dm-5">
              <div className="heading-row" style={{ flexWrap: "wrap" }}>
                <h2 id="dm-5" className="t-section">
                  5 · Download the cleaned file
                </h2>
                <div className="row" style={{ flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!final.headers.length}
                    onClick={() => downloadFile(textFile(toCsv(final.headers, final.rows), `${stem(loaded!.fileName)}_hubspot.csv`, "text/csv"))}
                  >
                    Download cleaned CSV
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={!final.issues.length}
                    onClick={() =>
                      downloadFile(
                        textFile(
                          toCsv(
                            ["Row in your file", "Column", "Original value", "Cleaned value", "What happened and why"],
                            final.issues.map((x) => [String(x.row), x.column, x.original, x.result, x.note]),
                          ),
                          `${stem(loaded!.fileName)}_changes.csv`,
                          "text/csv",
                        ),
                      )
                    }
                  >
                    Download the change report
                  </button>
                </div>
              </div>
              <div className="dm-report">
                <div className="dm-found">
                  <b className="dm-cell-strong">Summary report</b>
                  <span className="t-caption">
                    A page or two for the client or the team: what was found, what was corrected and what is still to check.
                  </span>
                </div>
                <div className="row" style={{ flexWrap: "wrap" }}>
                  <button type="button" className="btn btn-secondary" disabled={reporting !== null} onClick={() => void downloadReport("pdf")}>
                    {reporting === "pdf" ? "Creating…" : "Download PDF"}
                  </button>
                  <button type="button" className="btn btn-secondary" disabled={reporting !== null} onClick={() => void downloadReport("docx")}>
                    {reporting === "docx" ? "Creating…" : "Download Word"}
                  </button>
                </div>
              </div>
              {reportError && <Callout tone="error" title="The report wasn't created">{reportError}</Callout>}
              <Stats
                items={[
                  ["Rows ready to import", final.stats.rowsOut.toLocaleString()],
                  ["Cells fixed", final.stats.fixed.toLocaleString()],
                  ["Values left blank", final.stats.blanked.toLocaleString()],
                  ["Duplicate rows merged or removed", (final.stats.duplicates + final.dups.merged + final.dups.removed).toLocaleString()],
                  ["Empty rows removed", final.stats.emptyRows.toLocaleString()],
                ]}
              />
              {pending > 0 && (
                <Callout tone="warning" title={`${pending} ${pending === 1 ? "value hasn't" : "values haven't"} been reviewed`}>
                  They keep their original value in the download, which HubSpot may reject or read wrongly. Review them in step 3, or
                  accept the recommendations there in one click.
                </Callout>
              )}
              {pendingDups > 0 && (
                <Callout tone="warning" title={`${pendingDups} possible ${pendingDups === 1 ? "duplicate hasn't" : "duplicates haven't"} been reviewed`}>
                  Their rows all stay in the download, so HubSpot would update the same record with each. Decide them in step 4.
                </Callout>
              )}
              {final.stats.blanked > 0 && (
                <Callout tone="info" title="Some values are left blank">
                  Placeholders and values HubSpot would reject are emptied, so the rest of each row still imports. The change report
                  lists every one.
                </Callout>
              )}
              <h3 className="t-card-title">Preview (first {Math.min(PREVIEW_ROWS, final.rows.length)} rows; changed cells highlighted)</h3>
              <DataTable
                label="Cleaned preview"
                empty="No rows left after cleaning."
                columns={final.headers.map((h, k) => ({ key: String(k), label: h, width: "minmax(140px, 1fr)" }))}
                rows={final.rows.slice(0, PREVIEW_ROWS).map((r, ri) =>
                  Object.fromEntries(r.map((v, k) => [String(k), final.changed[ri]?.[k] ? <mark className="dm-changed">{v || "(blank)"}</mark> : v])),
                )}
              />
              <h3 className="t-card-title">
                Changes and problems{" "}
                <span className="t-caption">
                  {final.issues.length > ISSUE_ROWS ? `(first ${ISSUE_ROWS} of ${final.issues.length.toLocaleString()}; all are in the report)` : `(${final.issues.length})`}
                </span>
              </h3>
              <DataTable
                label="Changes and problems"
                empty="Nothing needed fixing beyond tidying spaces."
                columns={[
                  { key: "row", label: "Row", width: "80px" },
                  { key: "column", label: "Column", width: "minmax(130px, 1fr)" },
                  { key: "original", label: "Original", width: "minmax(160px, 1.3fr)" },
                  { key: "result", label: "Cleaned", width: "minmax(160px, 1.3fr)" },
                  { key: "note", label: "What happened", width: "minmax(200px, 1.6fr)" },
                ]}
                rows={final.issues.slice(0, ISSUE_ROWS).map((x) => ({ ...x, row: x.row, result: x.result || "(blank)" }))}
              />
            </section>
          )}
        </>
      )}
    </div>
  );
}
