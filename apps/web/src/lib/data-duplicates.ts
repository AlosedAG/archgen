/**
 * Data Migration duplicates: rows that are the same record entered more than
 * once (same email, invoice number, phone…). They're found on the cleaned
 * values, so "ZOE.DELGADO47@GMAIL.COM " and "zoe.delgado47@gmail.com" match,
 * as do "Harborline Biotech" and "Harborline Biotech Inc.".
 *
 * Rows match when any of the chosen columns match, and matches chain: A and B
 * share an email, B and C a phone, so A, B and C are one group. For each group
 * the user merges the rows into one, keeps only the main row, or says they
 * aren't duplicates. Undecided groups are merged, the suggested action.
 */

import { fold, type CleanResult, type FormatId, type Issue } from "./data-cleaner";

export type DupGroup = {
  /** The rows' numbers in the file, joined: stays the same while the same rows match. */
  key: string;
  /** Indexes into the cleaned rows, in file order. */
  rows: number[];
  /** Columns (cleaned file) the rows share a value in. */
  matchedOn: number[];
  /** The most complete row, suggested as the one to keep. */
  main: number;
  /** Columns where the rows have different, non-blank values. */
  conflicts: number[];
};

export type DupAction = "merge" | "keep" | "separate";
export type DupDecision = { action: DupAction; main?: number };

const COMPANY_WORDS = /\b(inc|llc|llp|ltd|corp|co|company|corporation|limited|the)\b/g;

/** The part of a value that identifies a record: digits for phones, letters for names, the address for emails. */
export function matchKey(v: string): string {
  const compact = v.replace(/[\s()+.\-]/g, "");
  const digits = compact.replace(/\D/g, "");
  if (digits.length >= 7 && digits.length >= compact.length * 0.8) return digits.slice(-10);
  const f = fold(v);
  if (f.includes("@")) return f.replace(/\s+/g, "");
  return f.replace(/[^a-z0-9]+/g, " ").replace(COMPANY_WORDS, " ").replace(/\s+/g, "");
}

/**
 * The columns that usually identify a record: an invoice / order number or ID
 * when the file has one (a bookings file lists one client many times), else emails.
 */
export function suggestKeys(result: CleanResult): string[] {
  const ids = result.headers.filter((h) => /invoice|order|folio|\bid\b|n[uú]mero/i.test(h));
  if (ids.length) return ids.slice(0, 1);
  return result.headers.filter((_, i) => result.columns[i]?.format === "email");
}

/** Notes, comments, descriptions: merged rows keep every distinct one. */
export function notesColumns(result: CleanResult): boolean[] {
  return result.headers.map(
    (h, i) => (result.columns[i]?.format as FormatId | undefined) === "text" && /note|comment|descrip|observ|nota|remark/i.test(h),
  );
}

export function findDuplicates(result: CleanResult, keyCols: number[]): DupGroup[] {
  const parent = result.rows.map((_, i) => i);
  const find = (i: number): number => (parent[i] === i ? i : (parent[i] = find(parent[i]!)));
  const links: [number, number, number][] = [];
  for (const col of keyCols) {
    const first = new Map<string, number>();
    result.rows.forEach((row, i) => {
      const k = matchKey(row[col] ?? "");
      if (k.length < 3) return;
      const seen = first.get(k);
      if (seen === undefined) first.set(k, i);
      else {
        parent[find(i)] = find(seen);
        links.push([seen, i, col]);
      }
    });
  }
  const members = new Map<number, number[]>();
  result.rows.forEach((_, i) => {
    const root = find(i);
    members.set(root, [...(members.get(root) ?? []), i]);
  });
  const groups: DupGroup[] = [];
  for (const [root, rows] of members) {
    if (rows.length < 2) continue;
    const matchedOn = [...new Set(links.filter(([a]) => find(a) === root).map(([, , c]) => c))].sort((a, b) => a - b);
    const filled = (i: number) => result.rows[i]!.filter(Boolean).length;
    const main = rows.reduce((best, i) => (filled(i) > filled(best) ? i : best), rows[0]!);
    const conflicts = result.headers
      .map((_, c) => c)
      .filter((c) => new Set(rows.map((i) => fold(result.rows[i]![c] ?? "")).filter(Boolean)).size > 1);
    groups.push({ key: rows.map((i) => result.sources[i]).join("-"), rows, matchedOn, main, conflicts });
  }
  return groups.sort((a, b) => a.rows[0]! - b.rows[0]!);
}

/** One row from a group: the main row's values, blanks filled from the others, notes combined. */
export function mergeRows(result: CleanResult, group: DupGroup, main: number, notes: boolean[]): { row: string[]; changed: boolean[] } {
  const order = [main, ...group.rows.filter((i) => i !== main)];
  const base = result.rows[main]!;
  const row = base.map((value, c) => {
    const values = order.map((i) => result.rows[i]![c] ?? "").filter(Boolean);
    if (notes[c]) {
      const distinct = new Map(values.map((v) => [fold(v), v]));
      return [...distinct.values()].join("; ");
    }
    return value || values[0] || "";
  });
  return { row, changed: row.map((v, c) => Boolean(result.changed[main]?.[c]) || v !== base[c]) };
}

export type DupOutcome = { merged: number; removed: number; separate: number; pending: number };

/** The cleaned file with each group merged, reduced to its main row, or left as it is. */
export function applyDuplicates(
  result: CleanResult,
  groups: DupGroup[],
  decisions: Record<string, DupDecision>,
  notes: boolean[],
): CleanResult & { dups: DupOutcome } {
  const drop = new Set<number>();
  const replace = new Map<number, { row: string[]; changed: boolean[] }>();
  const issues: Issue[] = [];
  const dups: DupOutcome = { merged: 0, removed: 0, separate: 0, pending: 0 };
  for (const g of groups) {
    // Undecided groups are merged: the suggested action, shown selected.
    const d = decisions[g.key] ?? { action: "merge" };
    if (!decisions[g.key]) dups.pending++;
    if (d.action === "separate") {
      dups.separate++;
      continue;
    }
    const main = d.main !== undefined && g.rows.includes(d.main) ? d.main : g.main;
    if (d.action === "merge") replace.set(main, mergeRows(result, g, main, notes));
    for (const other of g.rows) {
      if (other === main) continue;
      drop.add(other);
      if (d.action === "merge") dups.merged++;
      else dups.removed++;
      issues.push({
        row: result.sources[other]!,
        column: "(whole row)",
        original: "",
        result: "",
        note: d.action === "merge" ? `Merged into row ${result.sources[main]} (duplicate)` : `Removed: duplicate of row ${result.sources[main]}`,
      });
    }
  }
  const keep = result.rows.map((_, i) => i).filter((i) => !drop.has(i));
  return {
    ...result,
    rows: keep.map((i) => replace.get(i)?.row ?? result.rows[i]!),
    changed: keep.map((i) => replace.get(i)?.changed ?? result.changed[i]!),
    sources: keep.map((i) => result.sources[i]!),
    issues: [...result.issues, ...issues].sort((a, b) => a.row - b.row),
    stats: { ...result.stats, rowsOut: keep.length },
    dups,
  };
}
