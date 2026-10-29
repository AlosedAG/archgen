/**
 * Data Migration review: the values in a file that need a person's decision
 * before import, with a recommended value for each. There is one entry per
 * distinct value in a column, so "druiz" on 23 rows is decided once.
 *
 * What needs a decision: spelling variants of the same thing (druiz / Derek R.
 * / Derek Ruiz, Calif. / CA, Wed. / Wedding), notes in brackets, ranges and
 * approximate numbers, numbers far larger than the rest of the column, dates
 * whose day and month could be either way round, month-only or season dates,
 * placeholders and values that aren't valid for the column's format.
 * Fixes that need no judgement (phone formatting, lower-case emails, currency
 * symbols) are listed as automatic so any of them can be undone.
 *
 * The recommendation applies unless the user types their own value or keeps
 * the original; overridesFor() turns those choices into the values cleanTable uses.
 */

import {
  cleanNumber,
  cleanValue,
  collapse,
  detectDateOrder,
  fold,
  isPlaceholder,
  MONTHS,
  pad,
  properlyCased,
  splitOptions,
  titleCase,
  year4,
  type CleanOptions,
  type ColumnSpec,
  type FormatId,
  type Override,
  type Table,
} from "./data-cleaner";

export type ReviewItem = {
  /** ``${column}\u0001${value}``: the same key cleanTable looks overrides up by. */
  key: string;
  col: number;
  column: string;
  /** The value as written in the file (spaces tidied). */
  found: string;
  /** Short labels for the kinds of problem, for filtering. */
  kinds: string[];
  /** What was found and why the recommendation. */
  issue: string;
  /** Row numbers as in the file (the header is row 1). */
  rows: number[];
  recommended: string;
  /** False for automatic fixes: applied unless the user undoes them. */
  review: boolean;
};

export type Choice = "rec" | "mine" | "keep";
export type Decision = { choice: Choice; mine: string };

export const itemKey = (col: number, value: string) => `${col}\u0001${value}`;

// ---- Spelling variants ------------------------------------------------------------------------

const STATES: Record<string, string> = {
  alabama: "AL", alaska: "AK", arizona: "AZ", arkansas: "AR", california: "CA", colorado: "CO", connecticut: "CT",
  delaware: "DE", "district of columbia": "DC", florida: "FL", georgia: "GA", hawaii: "HI", idaho: "ID", illinois: "IL",
  indiana: "IN", iowa: "IA", kansas: "KS", kentucky: "KY", louisiana: "LA", maine: "ME", maryland: "MD",
  massachusetts: "MA", michigan: "MI", minnesota: "MN", mississippi: "MS", missouri: "MO", montana: "MT", nebraska: "NE",
  nevada: "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
  "north dakota": "ND", ohio: "OH", oklahoma: "OK", oregon: "OR", pennsylvania: "PA", "rhode island": "RI",
  "south carolina": "SC", "south dakota": "SD", tennessee: "TN", texas: "TX", utah: "UT", vermont: "VT", virginia: "VA",
  washington: "WA", "west virginia": "WV", wisconsin: "WI", wyoming: "WY",
  // Common written abbreviations.
  ala: "AL", ariz: "AZ", ark: "AR", cal: "CA", calif: "CA", colo: "CO", conn: "CT", del: "DE", fla: "FL", ill: "IL",
  ind: "IN", kan: "KS", mass: "MA", mich: "MI", minn: "MN", miss: "MS", mont: "MT", neb: "NE", nev: "NV", okla: "OK",
  ore: "OR", penn: "PA", tenn: "TN", tex: "TX", wash: "WA", wis: "WI", wisc: "WI", wyo: "WY",
};
const STATE_CODES = new Set(Object.values(STATES));

/** "Harborline Biotech Inc.": the full stop belongs there. */
const COMPANY_ENDING = /\b(inc|co|corp|ltd|llc|llp|plc|jr|sr|bros|intl|dept|s\.a|s\.c|c\.v)\.$/i;

const YES = new Set(["yes", "y", "si", "s", "true", "1", "x"]);
const NO = new Set(["no", "n", "false", "0"]);

const words = (v: string) => fold(v).split(/[^a-z0-9]+/).filter(Boolean);
const letters = (v: string) => words(v).join("");

/** Values with the same key are the same thing written differently. */
function variantKey(v: string, stateColumn: boolean): string {
  const w = words(v).join(" ");
  if (YES.has(w)) return "\u0001yes";
  if (NO.has(w)) return "\u0001no";
  if (stateColumn) {
    const code = STATES[w] ?? (STATE_CODES.has(w.toUpperCase()) ? w.toUpperCase() : undefined);
    if (code) return `\u0002${code}`;
  }
  return w.replace(/ /g, "");
}

/** "Derek R." in "Derek Ruiz", "Wed." in "Wedding", "Harborline Biotech" in "Harborline Biotech Inc.". */
function shortFormOf(short: string[], long: string[]): boolean {
  if (!short.length || short.length > long.length || long.length > short.length + 2 || long.length > 6) return false;
  return short.every((t, i) => long[i] === t || (long[i]!.startsWith(t) && (t.length >= 3 || (i > 0 && t.length === 1))));
}

/** One letter added, removed or changed. */
function oneEditApart(a: string, b: string): boolean {
  if (Math.abs(a.length - b.length) > 1 || a === b) return false;
  let i = 0;
  while (i < a.length && a[i] === b[i]) i++;
  return a.slice(i + (a.length >= b.length ? 1 : 0)) === b.slice(i + (b.length >= a.length ? 1 : 0));
}

type Variant = { v: string; key: string; words: string[] };

function related(a: Variant, b: Variant): boolean {
  if (a.key === b.key) return true;
  if (shortFormOf(a.words, b.words) || shortFormOf(b.words, a.words)) return true;
  // "druiz" for "Derek Ruiz".
  const [one, many] = a.words.length === 1 ? [a, b] : [b, a];
  if (one.words.length === 1 && many.words.length >= 2 && one.words[0] === many.words[0]![0]! + many.words.at(-1)!) return true;
  return Math.min(a.key.length, b.key.length) >= 6 && /^[a-z]+$/.test(a.key + b.key) && oneEditApart(a.key, b.key);
}

/**
 * For each value that's a variant of another, the value to use instead. With dropdown
 * options, values map to the options; otherwise to the most common spelling in the group,
 * written in its best-cased form ("Rehearsal Dinner" over "Rehearsal dinner").
 */
function variantMap(counts: Map<string, number>, allowed: string[], stateColumn: boolean): Map<string, string> {
  const info = (v: string): Variant => ({ v, key: variantKey(v, stateColumn), words: words(v) });
  const map = new Map<string, string>();
  if (allowed.length) {
    const options = allowed.map(info);
    for (const v of counts.keys()) {
      const a = info(v);
      const match = options.find((o) => o.key === a.key) ?? options.find((o) => related(a, o));
      if (match && match.v !== v) map.set(v, match.v);
    }
    return map;
  }
  const byUse = [...counts.keys()].sort(
    (a, b) => counts.get(b)! - counts.get(a)! || Number(properlyCased(b)) - Number(properlyCased(a)) || b.length - a.length,
  );
  const groups: (Variant & { members: string[] })[] = [];
  for (const v of byUse) {
    const a = info(v);
    // Groups are in order of use, so a value joins the most common one it matches.
    const group = groups.find((g) => g.key === a.key) ?? groups.find((g) => related(a, g));
    if (group) group.members.push(v);
    else groups.push({ ...a, members: [v] });
  }
  for (const g of groups) {
    const all = [g.v, ...g.members];
    const display = all
      .filter((m) => letters(m) === letters(g.v))
      .sort((a, b) => Number(properlyCased(b)) - Number(properlyCased(a)) || counts.get(b)! - counts.get(a)!)[0]!;
    for (const m of all) if (m !== display) map.set(m, display);
  }
  return map;
}

/** "SAN MARCOS": capitals throughout, five letters or more (so "CA", "BBQ" are fine). */
const shouting = (v: string) => (v.match(/\p{L}/gu)?.length ?? 0) >= 5 && v === v.toLocaleUpperCase() && v !== v.toLocaleLowerCase();

/** "Smith wedding (gate code 4412)" → the value without the note, and the note. */
function bracketNote(v: string): { value: string; note: string } | null {
  const m = v.match(/^(.*?)\s*[([]([^)\]]+)[)\]]\s*(.*)$/);
  if (!m) return null;
  const value = collapse(`${m[1]} ${m[3]}`);
  return value ? { value, note: m[2]!.trim() } : null;
}

// ---- Numbers and dates -----------------------------------------------------------------------

const RANGE = /^[^\d]*?(\d[\d.,]*)\s*(?:-|–|—|to|a|hasta|or)\s*[$€£]?\s*(\d[\d.,]*)[^\d]*$/i;

const plain = (n: number) => String(Number(n.toFixed(2)));

const SEASONS: Record<string, number> = {
  spring: 3, primavera: 3, summer: 6, verano: 6, fall: 9, autumn: 9, otono: 9, winter: 12, invierno: 12,
};

/** "Oct 2026", "Spring 2027", "Q3 2026", "2027": the first day it could mean, and what it was. */
function partialDate(v: string): { y: number; m: number; kind: string } | null {
  const w = fold(v).replace(/[.,]/g, " ").replace(/\s+de\s+/g, " ").replace(/\s+/g, " ").trim();
  let m = w.match(/^([a-z]+)[\s\-/]+(\d{4})$/);
  if (m && MONTHS[m[1]!]) return { y: +m[2]!, m: MONTHS[m[1]!]!, kind: "Month and year only" };
  if (m && SEASONS[m[1]!]) return { y: +m[2]!, m: SEASONS[m[1]!]!, kind: "A season, not a date" };
  m = w.match(/^q([1-4])[\s\-/]+(\d{4})$/);
  if (m) return { y: +m[2]!, m: (+m[1]! - 1) * 3 + 1, kind: "A quarter, not a date" };
  m = w.match(/^(\d{1,2})[/\-](\d{4})$/);
  if (m && +m[1]! >= 1 && +m[1]! <= 12) return { y: +m[2]!, m: +m[1]!, kind: "Month and year only" };
  m = w.match(/^((?:19|20)\d{2})$/);
  if (m) return { y: +m[1]!, m: 1, kind: "Year only" };
  return null;
}

const NUMERIC_DATE = /^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})\b/;
/**
 * 05/09/2026 and 5/9/2026 are often typed by different people with different habits,
 * so each habit is read its own way. 10/12/2026 shows neither.
 */
const dateStyle = (m: RegExpMatchArray) =>
  m[1]!.startsWith("0") || m[2]!.startsWith("0") ? "padded" : m[1]!.length === 1 || m[2]!.length === 1 ? "plain" : "neither";

const AUTO_NOTE: Partial<Record<FormatId, string>> = {
  name: "Capitalised",
  number: "Written as a plain number",
  date: "Written as YYYY-MM-DD",
  datetime: "Written as YYYY-MM-DD HH:MM",
  email: "Lower-cased and trimmed",
  phone: "Written as digits only",
  boolean: "Written as true / false",
  dropdown: "Matched to the option's spelling",
  multi: "Matched to the options' spelling",
  url: "https:// added",
  domain: "Reduced to the domain",
};

// ---- Finding what needs a decision -------------------------------------------------------------

type Finding = { kinds: string[]; issues: string[]; value: string; note?: string };

export function findItems(table: Table, specs: ColumnSpec[], options: CleanOptions): ReviewItem[] {
  const items: ReviewItem[] = [];
  specs.forEach((spec, col) => {
    if (spec.format === "skip") return;
    const rowsOf = new Map<string, number[]>();
    table.rows.forEach((r, i) => {
      const v = collapse(r[col] ?? "");
      if (!v) return;
      const list = rowsOf.get(v);
      if (list) list.push(i + 2);
      else rowsOf.set(v, [i + 2]);
    });
    const values = [...rowsOf.keys()];
    const header = (spec.name || table.headers[col] || "").toLowerCase();
    const format = spec.format;
    const order = options.dateOrder === "auto" ? detectDateOrder(values) : options.dateOrder;
    const base = new Map(values.map((v) => [v, cleanValue(format, v, spec, options, order)]));
    const found = new Map<string, Finding>(values.map((v) => [v, { kinds: [], issues: [], value: base.get(v)!.value }]));
    const flag = (v: string, kind: string, issue: string, value: string) => {
      const f = found.get(v)!;
      f.kinds.push(kind);
      f.issues.push(issue);
      f.value = value;
    };
    const real = values.filter((v) => !isPlaceholder(v));
    for (const v of values) if (isPlaceholder(v)) flag(v, "Placeholder", `“${v}” stands for “nothing”, so it's left blank`, "");

    if (format === "text" || format === "name" || format === "dropdown") {
      // Notes in brackets, stray full stops, two people in one name, letters on an ID.
      const firstNames = /first|given|nombre|forename/.test(header);
      const idColumn = format === "text" && real.length >= 5 && real.filter((v) => /^\d{4,}$/.test(v)).length / real.length >= 0.8;
      for (const v of real) {
        const f = found.get(v)!;
        let value = format === "dropdown" ? v : f.value;
        const note = bracketNote(value);
        if (note) {
          value = format === "name" ? cleanValue("name", note.value, spec, options, order).value : note.value;
          flag(v, "Note in brackets", `Has the note “${note.note}” in brackets; move it to a notes column if it matters`, value);
        }
        if (format === "name") {
          if (/\p{L}{2}\.$/u.test(value) && !COMPANY_ENDING.test(value)) flag(v, "Stray punctuation", "Ends with a full stop", (value = value.replace(/\.+$/, "")));
          const people = value.split(/\s+(?:&|and|y|\+)\s+|\s*\/\s*/i).filter(Boolean);
          if (firstNames && people.length > 1) flag(v, "More than one name", "Looks like more than one person; a HubSpot contact holds one", (value = people[0]!));
        }
        if (idColumn && /\d{4,}/.test(value) && !/^\d+$/.test(value)) {
          const id = value.match(/\d{4,}/)![0];
          flag(v, "Extra text in an ID", `“${collapse(value.replace(id, " ").replace(/^[\s\-_#/]+|[\s\-_#/]+$/g, ""))}” is added to the ID`, (value = id));
        }
        f.value = value;
      }

      // Spelling variants, for columns that hold a short list of values (not names, titles or notes).
      const allowed = format === "dropdown" ? splitOptions(spec.options) : [];
      const filled = real.reduce((n, v) => n + rowsOf.get(v)!.length, 0);
      const listLike = real.length > 0 && real.length <= 80 && real.length <= Math.max(5, filled * 0.6);
      if (format !== "name" && (allowed.length || listLike)) {
        const counts = new Map<string, number>();
        for (const v of real) {
          const value = found.get(v)!.value;
          if (value) counts.set(value, (counts.get(value) ?? 0) + rowsOf.get(v)!.length);
        }
        const variants = variantMap(counts, allowed, /\b(state|province|estado|region)\b/.test(header));
        const capsRare = real.filter(shouting).length / real.length < 0.3;
        for (const v of real) {
          const f = found.get(v)!;
          const to = variants.get(f.value);
          if (to) {
            const uses = counts.get(to);
            flag(
              v,
              allowed.length ? "Matched to an option" : "Spelling variant",
              allowed.length ? `Closest dropdown option is “${to}”` : `${uses} ${uses === 1 ? "row writes" : "rows write"} it “${to}”`,
              to,
            );
          } else if (!allowed.length && capsRare && shouting(f.value)) {
            flag(v, "All capitals", "Written in capitals, unlike the rest of the column", titleCase(f.value));
          }
          if (allowed.length && f.value && !allowed.includes(f.value)) {
            flag(v, "Not an option", `Not one of the dropdown options; left blank unless you type one`, "");
          }
        }
      } else if (format === "text") {
        const capsRare = real.filter(shouting).length / Math.max(1, real.length) < 0.3;
        for (const v of real) if (capsRare && shouting(found.get(v)!.value)) flag(v, "All capitals", "Written in capitals, unlike the rest of the column", titleCase(found.get(v)!.value));
      }
    }

    if (format === "number") {
      const numbers: number[] = [];
      for (const v of real) {
        const range = v.match(RANGE);
        if (range) {
          const a = Number(cleanNumber(range[1]!).value);
          const b = Number(cleanNumber(range[2]!).value);
          if (Number.isFinite(a) && Number.isFinite(b) && a !== b) {
            const mid = Number.isInteger(a) && Number.isInteger(b) ? String(Math.round((a + b) / 2)) : plain((a + b) / 2);
            flag(v, "Range", `A range (${plain(a)} to ${plain(b)}); the midpoint is suggested`, mid);
            continue;
          }
        }
        const res = base.get(v)!;
        if (res.invalid) {
          flag(v, "Not a number", `${res.note ?? "Not a number"}; left blank unless you type one`, "");
          continue;
        }
        const extra = v
          .replace(/[\d.,\s$€£¥()%\-]/g, "")
          .replace(/^(mxn|usd|eur|cad|gbp)|(mxn|usd|eur|cad|gbp)$/i, "")
          .replace(/^(k|m|mm|mil|bn|b|million|millones)$/i, "");
        if (extra) flag(v, "Approximate", `Written as an estimate (“${extra}”); the number is suggested`, res.value);
        numbers.push(Number(res.value));
      }
      // A value ten times the usual top of the column is usually a typo (5200 guests for 52).
      const sorted = numbers.filter(Number.isFinite).sort((a, b) => a - b);
      const p90 = sorted[Math.floor(0.9 * (sorted.length - 1))] ?? 0;
      if (sorted.length >= 10 && p90 > 0) {
        const ceiling = Math.max(...sorted.filter((n) => n < 10 * p90));
        for (const v of real) {
          const f = found.get(v)!;
          const n = Number(f.value);
          if (!f.value || !Number.isFinite(n) || n < 10 * p90) continue;
          const smaller = [10, 100, 1000].map((d) => n / d).find((x) => x <= ceiling);
          flag(
            v,
            "Unusually large",
            `Far larger than the rest of the column (90% are ${plain(p90)} or less)${smaller === undefined ? "; check it" : ""}`,
            smaller === undefined ? f.value : plain(smaller),
          );
        }
      }
    }

    if (format === "date" || format === "datetime") {
      // Which way round each writing style reads, from the dates that can only be read one way.
      const evidence = { padded: { dmy: 0, mdy: 0 }, plain: { dmy: 0, mdy: 0 }, neither: { dmy: 0, mdy: 0 } };
      for (const v of real) {
        const m = v.match(NUMERIC_DATE);
        if (!m) continue;
        if (+m[1]! > 12) evidence[dateStyle(m)].dmy++;
        if (+m[2]! > 12) evidence[dateStyle(m)].mdy++;
      }
      const all = Object.values(evidence);
      const mixed = all.some((e) => e.dmy) && all.some((e) => e.mdy);
      const time = format === "datetime" ? " 00:00" : "";
      for (const v of real) {
        const partial = partialDate(v);
        if (partial) {
          const when = `${partial.y}-${pad(partial.m)}-01`;
          flag(v, partial.kind, `${partial.kind}; HubSpot needs a full date, so the first day it could mean is suggested`, when + time);
          continue;
        }
        const res = base.get(v)!;
        if (res.invalid) {
          flag(v, "Not a date", "Not a recognisable date; left blank unless you type one", "");
          continue;
        }
        const m = v.match(NUMERIC_DATE);
        if (!m || !mixed || options.dateOrder !== "auto") continue;
        const a = +m[1]!;
        const b = +m[2]!;
        if (a > 12 || b > 12 || a === b) continue;
        const y = year4(+m[3]!);
        const style = dateStyle(m);
        const e = evidence[style];
        const byStyle = style === "neither" ? null : e.dmy && !e.mdy ? "dmy" : e.mdy && !e.dmy ? "mdy" : null;
        const read = byStyle ?? order;
        const dayFirst = `${y}-${pad(b)}-${pad(a)}`;
        const monthFirst = `${y}-${pad(a)}-${pad(b)}`;
        const written = style === "padded" ? "with a leading zero (05/09)" : "without leading zeros (5/9)";
        if (byStyle && e[byStyle] >= 3) {
          // Plenty of dates in this style can only be read one way: read this one the same way.
          const f = found.get(v)!;
          f.value = (read === "dmy" ? dayFirst : monthFirst) + res.value.slice(10);
          f.note = `Read ${read === "dmy" ? "day first" : "month first"}, like the other dates written ${written} in this column`;
          continue;
        }
        const why = byStyle
          ? `the few other dates written ${written} in this column are ${read === "dmy" ? "day first" : "month first"}`
          : `most dates in this column are ${read === "dmy" ? "day first" : "month first"}`;
        flag(
          v,
          "Day and month unclear",
          `Could be ${dayFirst} (day first) or ${monthFirst} (month first); this column mixes both, and ${why}`,
          (read === "dmy" ? dayFirst : monthFirst) + res.value.slice(10),
        );
      }
    }

    if (format === "email" || format === "phone" || format === "boolean" || format === "url" || format === "domain" || format === "multi") {
      for (const v of real) {
        const res = base.get(v)!;
        if (res.invalid) flag(v, "Not valid", `${res.note ?? "Not valid for this format"}; left blank unless you type one`, "");
        else if (format === "email" && res.note) flag(v, "Possible typo", res.note, res.value);
        else if (format === "multi" && res.note) flag(v, "Not an option", res.note, res.value);
      }
    }

    for (const v of values) {
      const f = found.get(v)!;
      const column = spec.name || table.headers[col]!;
      const rows = rowsOf.get(v)!;
      if (f.kinds.length) {
        items.push({ key: itemKey(col, v), col, column, found: v, kinds: [...new Set(f.kinds)], issue: f.issues.join(". "), rows, recommended: f.value, review: true });
      } else if (f.value !== v) {
        const res = base.get(v)!;
        items.push({ key: itemKey(col, v), col, column, found: v, kinds: ["Automatic"], issue: f.note ?? res.note ?? AUTO_NOTE[format] ?? "Tidied", rows, recommended: f.value, review: false });
      }
    }
  });
  return items;
}

/** The values cleanTable uses for each entry: the user's choice, else the recommended fix. */
export function overridesFor(items: ReviewItem[], decisions: Record<string, Decision>): Map<string, Override> {
  const map = new Map<string, Override>();
  for (const it of items) {
    const d = decisions[it.key];
    const what = it.kinds.join(", ");
    if (!d) {
      map.set(it.key, { value: it.recommended, how: it.review ? `Recommended fix, not checked (${what})` : it.issue });
    } else if (d.choice === "keep") {
      map.set(it.key, { value: it.found, how: it.review ? `Original kept (${what})` : "Automatic fix undone, original kept" });
    } else if (d.choice === "mine") {
      map.set(it.key, { value: collapse(d.mine), how: `Your value (${what})` });
    } else {
      map.set(it.key, { value: it.recommended, how: it.review ? `Recommended fix (${what})` : it.issue });
    }
  }
  return map;
}
