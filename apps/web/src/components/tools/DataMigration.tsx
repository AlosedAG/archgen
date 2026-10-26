"use client";

/**
 * Data Migration: one page to turn a client's export into a CSV HubSpot
 * imports cleanly. 1) Drop a .csv or .xlsx file; 2) each column's HubSpot
 * format is suggested and can be changed (and renamed); 3) the cleaned file
 * and a report of every fix and every value left blank update as you go,
 * ready to download. All processing happens in the browser (lib/data-cleaner),
 * so the client's data is never uploaded.
 */

import { useDeferredValue, useMemo, useRef, useState } from "react";

import { DataTable } from "@/components/project/DataTable";
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

export function DataMigration() {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [specs, setSpecs] = useState<ColumnSpec[]>([]);
  const [options, setOptions] = useState<CleanOptions>({ dateOrder: "auto", countryCode: "", removeDuplicates: true });
  const [error, setError] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const table = loaded?.sheets[loaded.sheet]?.table ?? null;

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
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't read that file.");
    }
    setReading(false);
  };

  // Re-cleaning runs as you change formats; deferred so typing stays smooth on big files.
  const deferredSpecs = useDeferredValue(specs);
  const deferredOptions = useDeferredValue(options);
  const result = useMemo(
    () => (table && deferredSpecs.length === table.headers.length ? cleanTable(table, deferredSpecs, deferredOptions) : null),
    [table, deferredSpecs, deferredOptions],
  );
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
                  Remove duplicate rows
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

          {/* 3 · Results */}
          {result && (
            <section className="card stack" style={{ gap: 14 }} aria-labelledby="dm-3">
              <div className="heading-row" style={{ flexWrap: "wrap" }}>
                <h2 id="dm-3" className="t-section">
                  3 · Download the cleaned file
                </h2>
                <div className="row" style={{ flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!result.headers.length}
                    onClick={() => downloadFile(textFile(toCsv(result.headers, result.rows), `${stem(loaded!.fileName)}_hubspot.csv`, "text/csv"))}
                  >
                    Download cleaned CSV
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={!result.issues.length}
                    onClick={() =>
                      downloadFile(
                        textFile(
                          toCsv(
                            ["Row in your file", "Column", "Original value", "Cleaned value", "What happened"],
                            result.issues.map((x) => [String(x.row), x.column, x.original, x.result, x.note]),
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
              <Stats
                items={[
                  ["Rows ready to import", result.stats.rowsOut.toLocaleString()],
                  ["Cells fixed", result.stats.fixed.toLocaleString()],
                  ["Values left blank", result.stats.blanked.toLocaleString()],
                  ["Duplicate rows removed", result.stats.duplicates.toLocaleString()],
                  ["Empty rows removed", result.stats.emptyRows.toLocaleString()],
                ]}
              />
              {result.stats.blanked > 0 && (
                <Callout tone="warning" title="Some values couldn't be fixed and were left blank">
                  HubSpot rejects a row with an invalid value, so these cells are emptied instead; the rest of each row still imports.
                  Check the change report to fill them in by hand if they matter.
                </Callout>
              )}
              <h3 className="t-card-title">Preview (first {Math.min(PREVIEW_ROWS, result.rows.length)} rows; changed cells highlighted)</h3>
              <DataTable
                label="Cleaned preview"
                empty="No rows left after cleaning."
                columns={result.headers.map((h, k) => ({ key: String(k), label: h, width: "minmax(140px, 1fr)" }))}
                rows={result.rows.slice(0, PREVIEW_ROWS).map((r, ri) =>
                  Object.fromEntries(r.map((v, k) => [String(k), result.changed[ri]?.[k] ? <mark className="dm-changed">{v || "(blank)"}</mark> : v])),
                )}
              />
              <h3 className="t-card-title">
                Changes and problems{" "}
                <span className="t-caption">
                  {result.issues.length > ISSUE_ROWS ? `(first ${ISSUE_ROWS} of ${result.issues.length.toLocaleString()}; all are in the report)` : `(${result.issues.length})`}
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
                rows={result.issues.slice(0, ISSUE_ROWS).map((x) => ({ ...x, row: x.row, result: x.result || "(blank)" }))}
              />
            </section>
          )}
        </>
      )}
    </div>
  );
}
