/**
 * Data Migration summary report: a page or two on what was found in a file
 * and what was done about it, as PDF or Word. Built in the browser like the
 * rest of the page, so client data still never leaves the computer; the PDF
 * and Word libraries load only when a report is downloaded.
 *
 * buildReport() decides the content once; reportPdf() and reportDocx() lay
 * the same blocks out in each format.
 */

import type { Paragraph as DocParagraph, Table as DocTable, TableRow as DocTableRow } from "docx";

import { FORMATS, type CleanResult } from "./data-cleaner";
import type { DupGroup, DupOutcome } from "./data-duplicates";
import type { Decision, ReviewItem } from "./data-review";

export type ReportBlock =
  | { kind: "heading"; text: string }
  | { kind: "text"; text: string }
  | { kind: "facts"; items: [string, string][] }
  | { kind: "bullets"; items: string[] }
  | { kind: "table"; headers: string[]; widths: number[]; rows: string[][] };

export type Report = { title: string; subtitle: string; blocks: ReportBlock[]; footer: string };

export type ReportInput = {
  fileName: string;
  sheet?: string;
  /** Rows in the file, empty ones included. */
  rowsIn: number;
  /** The cleaned file before duplicates were handled (column results, exact duplicates). */
  cleaned: CleanResult;
  /** What's downloaded. */
  final: CleanResult & { dups: DupOutcome };
  items: ReviewItem[];
  decisions: Record<string, Decision>;
  groups: DupGroup[];
  keys: string[];
  skipped: string[];
};

const FORMAT_LABEL = Object.fromEntries(FORMATS.map((f) => [f.id, f.label])) as Record<string, string>;

const n = (v: number) => v.toLocaleString("en-US");
const plural = (v: number, one: string, many = `${one}s`) => `${n(v)} ${v === 1 ? one : many}`;
const short = (v: string) => (v ? (v.length > 34 ? `${v.slice(0, 33)}…` : v) : "(blank)");

/** The value an entry ends up as, given the user's decision. */
function used(it: ReviewItem, d: Decision | undefined): string {
  if (!d) return it.review ? it.found : it.recommended;
  return d.choice === "rec" ? it.recommended : d.choice === "mine" ? d.mine.trim() : it.found;
}

export function buildReport(input: ReportInput): Report {
  const { cleaned, final, items, decisions, groups } = input;
  const review = items.filter((i) => i.review);
  const auto = items.filter((i) => !i.review);
  const decided = review.filter((i) => decisions[i.key]);
  const undone = auto.filter((i) => decisions[i.key]?.choice === "keep").length;
  const autoCells = auto.reduce((t, i) => t + (decisions[i.key] ? 0 : i.rows.length), 0);
  const dupRows = final.dups.merged + final.dups.removed;
  const blocks: ReportBlock[] = [];

  blocks.push({
    kind: "facts",
    items: [
      ["Rows in the file", n(input.rowsIn)],
      ["Rows ready to import", n(final.rows.length)],
      ["Columns imported", `${n(cleaned.headers.length)} of ${n(cleaned.headers.length + input.skipped.length)}`],
      ["Cells fixed automatically", n(autoCells)],
      ["Values reviewed", `${n(decided.length)} of ${n(review.length)}`],
      ["Duplicate rows merged or removed", n(dupRows + cleaned.stats.duplicates)],
    ],
  });

  blocks.push({ kind: "heading", text: "What was cleaned automatically" });
  blocks.push({
    kind: "text",
    text:
      `Each column was checked against the HubSpot format it will be imported as, and formatting HubSpot needs was applied ` +
      `to ${plural(autoCells, "cell")}: phone numbers written as digits, emails lower-cased, amounts without currency symbols, ` +
      `dates written as YYYY-MM-DD, extra spaces removed.` +
      (undone ? ` ${plural(undone, "automatic fix was", "automatic fixes were")} undone on request.` : "") +
      (cleaned.stats.emptyRows ? ` ${plural(cleaned.stats.emptyRows, "empty row was", "empty rows were")} removed.` : "") +
      (cleaned.stats.duplicates ? ` ${plural(cleaned.stats.duplicates, "row was an exact copy", "rows were exact copies")} of another row and removed.` : ""),
  });
  const touched = cleaned.columns.filter((c) => c.fixed || c.blanked);
  if (touched.length) {
    blocks.push({
      kind: "table",
      headers: ["Column", "Imported as", "Cells changed", "Left blank"],
      widths: [0.34, 0.3, 0.18, 0.18],
      rows: touched.map((c) => [c.name, FORMAT_LABEL[c.format] ?? c.format, n(c.fixed), n(c.blanked)]),
    });
  }
  const untouched = cleaned.columns.filter((c) => !c.fixed && !c.blanked).map((c) => c.name);
  if (untouched.length) blocks.push({ kind: "text", text: `No changes were needed in ${untouched.join(", ")}.` });
  if (input.skipped.length) blocks.push({ kind: "text", text: `Left out of the import: ${input.skipped.join(", ")}.` });

  blocks.push({ kind: "heading", text: "Issues found and how they were resolved" });
  if (!review.length) {
    blocks.push({ kind: "text", text: "Nothing in the file needed a judgement call." });
  } else {
    blocks.push({
      kind: "text",
      text:
        `${plural(review.length, "value")} needed a decision (each distinct value once, across ${plural(review.reduce((t, i) => t + i.rows.length, 0), "row")}). ` +
        `For each, a fix was recommended and the reviewer accepted it, entered their own value or kept the original.`,
    });
    const kinds = new Map<string, ReviewItem[]>();
    for (const it of review) for (const k of it.kinds) kinds.set(k, [...(kinds.get(k) ?? []), it]);
    blocks.push({
      kind: "table",
      headers: ["Issue", "Values", "Rows", "Resolved", "Example"],
      widths: [0.2, 0.09, 0.08, 0.3, 0.33],
      rows: [...kinds].map(([kind, list]) => {
        const count = (choice: Decision["choice"] | undefined) => list.filter((i) => decisions[i.key]?.choice === choice).length;
        const resolved = [
          [count("rec"), "recommended fix"],
          [count("mine"), "own value"],
          [count("keep"), "kept as written"],
          [count(undefined), "not reviewed"],
        ]
          .filter(([v]) => v)
          .map(([v, label]) => `${v} ${label}`)
          .join(", ");
        const ex = list.find((i) => decisions[i.key]) ?? list[0]!;
        const example = decisions[ex.key] ? `${short(ex.found)} → ${short(used(ex, decisions[ex.key]))}` : `${short(ex.found)} → ${short(ex.recommended)} (suggested)`;
        return [kind, n(list.length), n(list.reduce((t, i) => t + i.rows.length, 0)), resolved, example];
      }),
    });
  }

  blocks.push({ kind: "heading", text: "Duplicate records" });
  if (!input.keys.length) {
    blocks.push({ kind: "text", text: "Rows were not checked for duplicate records (no matching columns chosen)." });
  } else if (!groups.length) {
    blocks.push({ kind: "text", text: `Rows were matched on ${input.keys.join(", ")}; no two rows were the same record.` });
  } else {
    const parts = [
      final.dups.merged && `${plural(final.dups.merged, "row was", "rows were")} merged into the matching record (blanks filled in, notes combined)`,
      final.dups.removed && `${plural(final.dups.removed, "row was", "rows were")} dropped in favour of the main row`,
      final.dups.separate && `${plural(final.dups.separate, "group was", "groups were")} confirmed as different records`,
      final.dups.pending && `${plural(final.dups.pending, "group was", "groups were")} not reviewed and kept every row`,
    ].filter(Boolean);
    blocks.push({
      kind: "text",
      text: `Rows were matched on ${input.keys.join(", ")}: ${plural(groups.length, "group")} of rows described the same record. ${parts.join("; ")}.`,
    });
  }

  const pending = review.length - decided.length;
  const riskyKept = review.filter(
    (i) => decisions[i.key]?.choice === "keep" && i.kinds.some((k) => /^Not (valid|a date|a number|an option)$/.test(k)),
  ).length;
  const notesRemoved = review.filter((i) => i.kinds.includes("Note in brackets") && decisions[i.key]?.choice === "rec").length;
  const todo = [
    pending && `${plural(pending, "value was", "values were")} not reviewed and kept as written; HubSpot may reject or misread them.`,
    riskyKept && `${plural(riskyKept, "value", "values")} HubSpot may reject ${riskyKept === 1 ? "was" : "were"} kept as written on purpose.`,
    final.dups.pending && `${plural(final.dups.pending, "possible duplicate group was", "possible duplicate groups were")} not reviewed.`,
    notesRemoved && `Notes in brackets were removed from ${plural(notesRemoved, "value")}; check whether any belong in a notes property.`,
    final.stats.blanked && `${plural(final.stats.blanked, "cell was", "cells were")} left blank (placeholders such as N/A or TBD, and values HubSpot would reject).`,
  ].filter((t): t is string => Boolean(t));
  blocks.push({ kind: "heading", text: "Still to check" });
  blocks.push(todo.length ? { kind: "bullets", items: todo } : { kind: "text", text: "Nothing outstanding: every value and possible duplicate was reviewed." });

  return {
    title: "Data cleanup report",
    subtitle: `${input.fileName}${input.sheet ? `, sheet ${input.sheet}` : ""} · ${new Date().toLocaleDateString("en-US", { dateStyle: "long" })}`,
    blocks,
    footer: "Every changed cell is listed, row by row, in the change report (CSV) downloaded with the cleaned file.",
  };
}

// ---- PDF -----------------------------------------------------------------------------------

/** The standard PDF fonts cover Latin-1 only. */
const latin = (s: string) =>
  s
    .replace(/→/g, "->")
    .replace(/[“”]/g, '"')
    .replace(/[‘’]/g, "'")
    .replace(/[–—]/g, "-")
    .replace(/…/g, "...")
    .replace(/·/g, "-")
    .replace(/[^\u0000-ÿ]/g, "?");

export async function reportPdf(report: Report): Promise<Blob> {
  const { jsPDF } = await import("jspdf");
  const doc = new jsPDF({ unit: "pt", format: "letter" });
  const W = doc.internal.pageSize.getWidth();
  const H = doc.internal.pageSize.getHeight();
  const M = 54;
  const width = W - 2 * M;
  const ink: [number, number, number] = [28, 30, 46];
  const muted: [number, number, number] = [104, 108, 128];
  const accent: [number, number, number] = [91, 83, 232];
  let y = M;
  const font = (size: number, style: "normal" | "bold", color = ink) => {
    doc.setFont("helvetica", style);
    doc.setFontSize(size);
    doc.setTextColor(...color);
  };
  const room = (h: number) => {
    if (y + h <= H - M) return false;
    doc.addPage();
    y = M;
    return true;
  };
  const lines = (text: string, w: number) => doc.splitTextToSize(latin(text), w) as string[];

  font(20, "bold");
  doc.text(latin(report.title), M, y + 14);
  y += 32;
  font(10, "normal", muted);
  doc.text(lines(report.subtitle, width), M, y);
  y += 14;
  doc.setDrawColor(...accent);
  doc.setLineWidth(2);
  doc.line(M, y, M + 48, y);
  y += 22;

  for (const b of report.blocks) {
    if (b.kind === "heading") {
      room(44);
      y += 8;
      font(13, "bold");
      doc.text(latin(b.text), M, y);
      y += 16;
    } else if (b.kind === "text") {
      font(10, "normal");
      for (const line of lines(b.text, width)) {
        room(14);
        doc.text(line, M, y);
        y += 14;
      }
      y += 6;
    } else if (b.kind === "bullets") {
      font(10, "normal");
      for (const item of b.items) {
        lines(item, width - 14).forEach((line, i) => {
          room(14);
          if (i === 0) doc.text("-", M + 2, y);
          doc.text(line, M + 14, y);
          y += 14;
        });
        y += 3;
      }
    } else if (b.kind === "facts") {
      const per = 3;
      const cw = width / per;
      for (let i = 0; i < b.items.length; i += per) {
        room(42);
        b.items.slice(i, i + per).forEach(([label, value], k) => {
          doc.setFillColor(245, 245, 250);
          doc.rect(M + k * cw + (k ? 4 : 0), y - 10, cw - 4, 38, "F");
          font(8, "normal", muted);
          doc.text(latin(label), M + k * cw + 10, y + 2);
          font(14, "bold");
          doc.text(latin(value), M + k * cw + 10, y + 20);
        });
        y += 46;
      }
      y += 4;
    } else {
      const cols = b.widths.map((f) => f * width);
      const row = (cells: string[], header: boolean) => {
        font(8.5, header ? "bold" : "normal", header ? muted : ink);
        const wrapped = cells.map((c, i) => lines(c, cols[i]! - 10));
        const h = Math.max(...wrapped.map((w) => w.length)) * 11 + 9;
        return { wrapped, h };
      };
      const draw = (cells: string[], header: boolean) => {
        const { wrapped, h } = row(cells, header);
        if (room(h) && !header) draw(b.headers, true);
        font(8.5, header ? "bold" : "normal", header ? muted : ink);
        if (header) {
          doc.setFillColor(245, 245, 250);
          doc.rect(M, y - 9, width, h, "F");
        }
        let x = M;
        wrapped.forEach((w, i) => {
          doc.text(w, x + 5, y + 1);
          x += cols[i]!;
        });
        doc.setDrawColor(225, 226, 235);
        doc.setLineWidth(0.6);
        doc.line(M, y - 9 + h, M + width, y - 9 + h);
        y += h;
      };
      room(40);
      draw(b.headers, true);
      for (const r of b.rows) draw(r, false);
      y += 12;
    }
  }
  room(30);
  y += 6;
  font(9, "normal", muted);
  doc.text(lines(report.footer, width), M, y);

  const pages = doc.getNumberOfPages();
  for (let p = 1; p <= pages; p++) {
    doc.setPage(p);
    font(8, "normal", muted);
    doc.text(`${latin(report.title)} - page ${p} of ${pages}`, W - M, H - 28, { align: "right" });
  }
  return doc.output("blob");
}

// ---- Word ----------------------------------------------------------------------------------

export async function reportDocx(report: Report): Promise<Blob> {
  const { AlignmentType, BorderStyle, Document, Packer, Paragraph, ShadingType, Table, TableCell, TableRow, TextRun, WidthType } =
    await import("docx");
  const INK = "1C1E2E";
  const MUTED = "686C80";
  const LINE = "E1E2EB";
  const FILL = "F5F5FA";
  const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  const thin = { style: BorderStyle.SINGLE, size: 4, color: LINE };
  const para = (text: string, opts: { size?: number; bold?: boolean; color?: string; after?: number; before?: number } = {}) =>
    new Paragraph({
      spacing: { after: opts.after ?? 120, before: opts.before ?? 0 },
      children: [new TextRun({ text, size: opts.size ?? 20, bold: opts.bold, color: opts.color ?? INK })],
    });
  const cell = (children: DocParagraph[], widthPct: number, shade?: string) =>
    new TableCell({
      width: { size: widthPct, type: WidthType.PERCENTAGE },
      shading: shade ? { type: ShadingType.CLEAR, color: "auto", fill: shade } : undefined,
      margins: { top: 60, bottom: 60, left: 90, right: 90 },
      children,
    });

  const children: (DocParagraph | DocTable)[] = [
    para(report.title, { size: 36, bold: true, after: 60 }),
    para(report.subtitle, { color: MUTED, after: 240 }),
  ];
  for (const b of report.blocks) {
    if (b.kind === "heading") children.push(para(b.text, { size: 26, bold: true, before: 240, after: 100 }));
    else if (b.kind === "text") children.push(para(b.text));
    else if (b.kind === "bullets") {
      for (const item of b.items) children.push(new Paragraph({ bullet: { level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: item, size: 20, color: INK })] }));
    } else if (b.kind === "facts") {
      const rows: DocTableRow[] = [];
      for (let i = 0; i < b.items.length; i += 3) {
        rows.push(
          new TableRow({
            children: b.items.slice(i, i + 3).map(([label, value]) =>
              cell([para(label, { size: 16, color: MUTED, after: 20 }), para(value, { size: 28, bold: true, after: 20 })], 33, FILL),
            ),
          }),
        );
      }
      children.push(
        new Table({
          width: { size: 100, type: WidthType.PERCENTAGE },
          borders: { top: none, bottom: none, left: none, right: none, insideHorizontal: { style: BorderStyle.SINGLE, size: 24, color: "FFFFFF" }, insideVertical: { style: BorderStyle.SINGLE, size: 24, color: "FFFFFF" } },
          rows,
        }),
        para("", { after: 60 }),
      );
    } else {
      const pct = b.widths.map((w) => Math.round(w * 100));
      children.push(
        new Table({
          width: { size: 100, type: WidthType.PERCENTAGE },
          borders: { top: thin, bottom: thin, left: none, right: none, insideHorizontal: thin, insideVertical: none },
          rows: [
            new TableRow({ tableHeader: true, children: b.headers.map((h, i) => cell([para(h, { size: 17, bold: true, color: MUTED, after: 0 })], pct[i]!, FILL)) }),
            ...b.rows.map((r) => new TableRow({ children: r.map((v, i) => cell([para(v, { size: 17, after: 0 })], pct[i]!)) })),
          ],
        }),
        para("", { after: 60 }),
      );
    }
  }
  children.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { before: 200 }, children: [new TextRun({ text: report.footer, size: 18, color: MUTED })] }));

  const doc = new Document({
    styles: { default: { document: { run: { font: "Calibri" } } } },
    sections: [{ properties: { page: { margin: { top: 1080, bottom: 1080, left: 1080, right: 1080 } } }, children }],
  });
  return Packer.toBlob(doc);
}
