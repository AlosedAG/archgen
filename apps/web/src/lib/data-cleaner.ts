/**
 * Data Migration: turn a client's messy CSV / Excel export into a CSV that
 * imports into HubSpot without errors. Everything runs in the browser, so
 * client data never leaves the user's computer.
 *
 * For each column the user picks the HubSpot format it will be imported as
 * (a format is suggested from the header and the values). Every cell is then
 * checked against that format and, where possible, corrected: numbers lose
 * currency symbols and stray letters, dates become YYYY-MM-DD, emails are
 * trimmed and lower-cased, phones keep only digits and a leading +, yes/no
 * values become true/false, dropdown values are matched to the allowed
 * options. A value that can't be made valid is left blank (HubSpot rejects
 * the whole row otherwise) and listed in the issues report, as are the
 * placeholder values clients use for "nothing" (N/A, TBD, test@test.com…).
 */

export type FormatId =
  | "text"
  | "name"
  | "number"
  | "date"
  | "datetime"
  | "email"
  | "phone"
  | "boolean"
  | "dropdown"
  | "multi"
  | "url"
  | "domain"
  | "skip";

export const FORMATS: { id: FormatId; label: string; hint: string }[] = [
  { id: "text", label: "Single-line text", hint: "Trimmed; extra spaces and hidden characters removed." },
  { id: "name", label: "Name", hint: "Trimmed and capitalised: “ana MARÍA” becomes “Ana María”." },
  { id: "number", label: "Number", hint: "Digits only: currency symbols, thousands separators and letters removed." },
  { id: "date", label: "Date", hint: "Written as YYYY-MM-DD." },
  { id: "datetime", label: "Date and time", hint: "Written as YYYY-MM-DD HH:MM." },
  { id: "email", label: "Email", hint: "Trimmed, lower-case; invalid addresses are left blank." },
  { id: "phone", label: "Phone number", hint: "Digits with an optional leading +; extensions removed." },
  { id: "boolean", label: "Single checkbox (true / false)", hint: "Yes / Sí / Y / 1 / X become true; No / N / 0 become false." },
  { id: "dropdown", label: "Dropdown select", hint: "Matched to the allowed options you list." },
  { id: "multi", label: "Multiple checkboxes", hint: "Values separated by ; and matched to the allowed options." },
  { id: "url", label: "URL", hint: "Starts with https:// when the scheme is missing." },
  { id: "domain", label: "Company domain", hint: "Just the domain: no https://, www. or path." },
  { id: "skip", label: "Don't import", hint: "Left out of the cleaned file." },
];

export type ColumnSpec = {
  /** The header in the cleaned file (HubSpot maps it to a property). */
  name: string;
  format: FormatId;
  /** Allowed values for dropdown / multiple checkboxes, one per line or comma-separated. */
  options: string;
};

export type DateOrder = "auto" | "dmy" | "mdy";

export type CleanOptions = {
  /** How to read ambiguous dates like 03/04/2025. */
  dateOrder: DateOrder;
  /** Added to phone numbers without one, e.g. "+52". */
  countryCode: string;
  removeDuplicates: boolean;
};

export type Table = { headers: string[]; rows: string[][] };

export type Issue = { row: number; column: string; original: string; result: string; note: string };

export type ColumnReport = {
  name: string;
  format: FormatId;
  fixed: number;
  blanked: number;
  /** For dates: the order used for ambiguous values. */
  detail?: string;
};

export type CleanResult = {
  headers: string[];
  rows: string[][];
  /** For each output row, which cells changed (same shape as rows). */
  changed: boolean[][];
  /** For each output row, its row number in the file (the header is row 1). */
  sources: number[];
  columns: ColumnReport[];
  issues: Issue[];
  stats: { rowsIn: number; rowsOut: number; emptyRows: number; duplicates: number; fixed: number; blanked: number };
};

// ---- Reading files ------------------------------------------------------------------------

/** Parse CSV text (comma, semicolon, tab or pipe separated, quotes per RFC 4180). */
export function parseCsv(text: string): Table {
  const source = text.replace(/^﻿/, "");
  const firstLine = source.slice(0, source.search(/\r?\n|$/));
  const delimiter = [",", ";", "\t", "|"]
    .map((d) => ({ d, n: firstLine.split(d).length }))
    .sort((a, b) => b.n - a.n)[0]!.d;
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < source.length; i++) {
    const ch = source[i]!;
    if (quoted) {
      if (ch === '"') {
        if (source[i + 1] === '"') {
          cell += '"';
          i++;
        } else quoted = false;
      } else cell += ch;
    } else if (ch === '"' && cell === "") quoted = true;
    else if (ch === delimiter) {
      row.push(cell);
      cell = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && source[i + 1] === "\n") i++;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else cell += ch;
  }
  if (cell !== "" || row.length) {
    row.push(cell);
    rows.push(row);
  }
  return toTable(rows);
}

/** A sheet's cells (as read from Excel) as text: real dates become ISO dates. */
export function sheetToTable(data: unknown[][]): Table {
  const text = (v: unknown): string => {
    if (v == null) return "";
    if (v instanceof Date) {
      if (Number.isNaN(v.getTime())) return "";
      const iso = v.toISOString();
      return iso.endsWith("T00:00:00.000Z") ? iso.slice(0, 10) : `${iso.slice(0, 10)} ${iso.slice(11, 16)}`;
    }
    if (typeof v === "number") return Number.isInteger(v) ? String(v) : String(Number(v.toPrecision(15)));
    return String(v);
  };
  return toTable(data.map((r) => r.map(text)));
}

function toTable(raw: string[][]): Table {
  const rows = raw.filter((r) => r.some((c) => c.trim() !== ""));
  const header = rows.shift() ?? [];
  const width = Math.max(header.length, ...rows.map((r) => r.length), 0);
  const seen = new Map<string, number>();
  const headers = Array.from({ length: width }, (_, i) => {
    const base = (header[i] ?? "").trim() || `Column ${i + 1}`;
    const n = (seen.get(base) ?? 0) + 1;
    seen.set(base, n);
    return n > 1 ? `${base} (${n})` : base;
  });
  return { headers, rows: rows.map((r) => headers.map((_, i) => r[i] ?? "")) };
}

// ---- Placeholders ("nothing was entered") -------------------------------------------------

const NULLS = new Set([
  "n/a", "na", "n.a.", "null", "none", "nil", "nan", "undefined", "-", "--", "---", "?", "??", ".",
  "tbd", "tbc", "unknown", "not available", "not applicable", "no data", "no info", "pending", "empty", "blank",
  "sin dato", "s/d", "sd", "vacio", "vacío", "pendiente", "desconocido", "no aplica", "ninguno", "ninguna",
  "sin correo", "no email", "sin telefono", "sin teléfono", "no phone",
  "0000000000", "00000", "0000000", "000-000-0000", "1111111111", "9999999999",
  "test@test.com", "test@example.com", "example@example.com", "noemail@noemail.com", "no@email.com",
  "email@email.com", "correo@correo.com", "xxx", "xxxx", "aaa",
]);

export const isPlaceholder = (v: string) => NULLS.has(v.trim().toLowerCase());

// ---- Format suggestions ---------------------------------------------------------------------

const has = (header: string, ...words: string[]) => words.some((w) => header.includes(w));
/** A word in the header that starts with one of ``words``: "count" in "Guest Count", not in "Account". */
const hasWord = (header: string, ...words: string[]) => words.some((w) => new RegExp(`(^|[^\\p{L}])${w}`, "u").test(header));

/** The format a column most likely needs, from its header and up to 200 of its values. */
export function suggestFormat(header: string, values: string[]): FormatId {
  const h = header.toLowerCase();
  const sample = values.map((v) => v.trim()).filter((v) => v && !isPlaceholder(v)).slice(0, 200);
  const share = (test: (v: string) => boolean) => (sample.length ? sample.filter(test).length / sample.length : 0);

  if (has(h, "email", "e-mail", "correo")) return "email";
  if (has(h, "phone", "mobile", "teléfono", "telefono", "celular", "whatsapp", "fax")) return "phone";
  if (has(h, "website", "url", "linkedin", "sitio web")) return "url";
  if (has(h, "domain", "dominio")) return "domain";
  if (has(h, "first name", "last name", "firstname", "lastname", "nombre", "apellido") || h === "name") return "name";
  if (has(h, "opted", "opt-in", "opt in", "subscribed", "consent", "unsubscribed", "is active", "acepta", "suscrito")) return "boolean";
  if (has(h, "date", "fecha", "birthday", "created", "closed", "since")) return share((v) => /\d{1,2}:\d{2}/.test(v)) > 0.5 ? "datetime" : "date";
  if (share((v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) > 0.8) return "email";
  if (share((v) => parseDate(v, "auto") !== null && /[/\-.]/.test(v)) > 0.8) return "date";
  if (share((v) => /^(true|false|yes|no|y|n|s[ií]|0|1)$/i.test(v)) > 0.9 && new Set(sample.map((v) => v.toLowerCase())).size <= 4)
    return "boolean";
  // Invoice numbers, IDs and codes are text even when they look like numbers.
  if (has(h, "invoice", "folio", " no", "no.", " id", "sku", "zip", "postal", "code", "código")) return "text";
  if (hasWord(h, "amount", "revenue", "price", "total", "count", "number of", "employees", "monto", "precio", "cantidad", "ingresos"))
    return "number";
  if (share((v) => /^[\s$€£(+-]*[\d.,]+\s*%?\)?$/.test(v)) > 0.8 && !has(h, "zip", "postal", "id", "code", "código", "cp")) return "number";
  if (sample.length >= 20 && new Set(sample.map((v) => v.toLowerCase())).size <= Math.max(3, sample.length / 10)) return "dropdown";
  return "text";
}

// ---- Cleaning one value ---------------------------------------------------------------------

export type Outcome = { value: string; note?: string; invalid?: boolean };

export const collapse = (v: string) => v.replace(/[\u0000-\u001F\u007F ​-‍﻿]/g, " ").replace(/\s+/g, " ").trim();

export function cleanNumber(raw: string): Outcome {
  let v = collapse(raw);
  const negative = /^\(.*\)$/.test(v) || /^-/.test(v.replace(/^[^\d-]+/, ""));
  const match = v.match(/\d[\d.,\s]*/);
  if (!match) return { value: "", invalid: true, note: "No number found" };
  let digits = match[0].replace(/\s/g, "");
  const extra = v.replace(match[0], "").replace(/[\s$€£¥()+\-%]/g, "").replace(/^(mxn|usd|eur|cad|gbp)|(mxn|usd|eur|cad|gbp)$/i, "");
  const lastComma = digits.lastIndexOf(",");
  const lastDot = digits.lastIndexOf(".");
  if (lastComma >= 0 && lastDot >= 0) {
    // Both separators: the last one is the decimal point.
    digits = lastComma > lastDot ? digits.replace(/\./g, "").replace(",", ".") : digits.replace(/,/g, "");
  } else if (lastComma >= 0) {
    digits = /^\d{1,3}(,\d{3})+$/.test(digits) ? digits.replace(/,/g, "") : digits.replace(/,(?=\d+$)/, ".").replace(/,/g, "");
  } else if (/^\d{1,3}(\.\d{3}){2,}$/.test(digits)) {
    digits = digits.replace(/\./g, ""); // 1.234.567
  }
  digits = digits.replace(/\.(?=.*\.)/g, "").replace(/\.$/, "");
  if (!/^\d+(\.\d+)?$/.test(digits)) return { value: "", invalid: true, note: "Not a number" };
  // "300k", "1.5M", "2 mil" written as shorthand.
  const suffix = v.slice(v.indexOf(match[0]) + match[0].length).trim().match(/^(k|mil|mm|m|millones|million|bn|b)\b/i)?.[1]?.toLowerCase();
  const factor = suffix ? ({ k: 1e3, mil: 1e3, m: 1e6, mm: 1e6, millones: 1e6, million: 1e6, b: 1e9, bn: 1e9 }[suffix] ?? 1) : 1;
  if (factor !== 1) digits = String(Number((Number(digits) * factor).toPrecision(15)));
  const value = (negative ? "-" : "") + digits.replace(/^0+(?=\d)/, "");
  const removed = suffix ? extra.replace(new RegExp(`${suffix}$`, "i"), "") : extra;
  return { value, note: removed ? `Removed “${removed.slice(0, 20)}”` : undefined };
}

export const MONTHS: Record<string, number> = {
  jan: 1, january: 1, ene: 1, enero: 1, feb: 2, february: 2, febrero: 2, mar: 3, march: 3, marzo: 3,
  apr: 4, april: 4, abr: 4, abril: 4, may: 5, mayo: 5, jun: 6, june: 6, junio: 6, jul: 7, july: 7, julio: 7,
  aug: 8, august: 8, ago: 8, agosto: 8, sep: 9, sept: 9, september: 9, set: 9, septiembre: 9, setiembre: 9,
  oct: 10, october: 10, octubre: 10, nov: 11, november: 11, noviembre: 11, dec: 12, december: 12, dic: 12, diciembre: 12,
};

type DateParts = { y: number; m: number; d: number; hh?: number; mm?: number };

export const year4 = (y: number) => (y < 100 ? (y < 50 ? 2000 + y : 1900 + y) : y);
const real = (p: DateParts): DateParts | null => {
  const t = new Date(Date.UTC(p.y, p.m - 1, p.d));
  return p.y >= 1900 && p.y <= 2100 && t.getUTCMonth() === p.m - 1 && t.getUTCDate() === p.d ? p : null;
};

/** A date in almost any written form, or null. ``order`` settles 03/04/2025. */
export function parseDate(raw: string, order: DateOrder): DateParts | null {
  const v = collapse(raw).toLowerCase().replace(/(\d)(st|nd|rd|th)\b/g, "$1").replace(/,/g, " ").replace(/\s+de\s+/g, " ");
  const time = v.match(/(\d{1,2}):(\d{2})(?::\d{2})?\s*(am|pm|a\.m\.|p\.m\.)?/);
  let hh: number | undefined;
  let mm: number | undefined;
  if (time) {
    hh = Number(time[1]) % 24;
    mm = Number(time[2]);
    if (/p/.test(time[3] ?? "") && hh < 12) hh += 12;
    if (/a/.test(time[3] ?? "") && hh === 12) hh = 0;
  }
  const withTime = (p: DateParts | null) => (p ? { ...p, hh, mm } : null);
  const datePart = v.replace(/t?\d{1,2}:\d{2}(:\d{2})?(\.\d+)?\s*(am|pm|a\.m\.|p\.m\.)?(z|[+-]\d{2}:?\d{2})?/, " ").trim();

  let m = datePart.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/);
  if (m) return withTime(real({ y: +m[1]!, m: +m[2]!, d: +m[3]! }));
  m = datePart.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})$/);
  if (m) {
    const a = +m[1]!;
    const b = +m[2]!;
    const y = year4(+m[3]!);
    const dayFirst = order === "dmy" || (order === "auto" && a > 12);
    return withTime(real(dayFirst ? { y, m: b, d: a } : { y, m: a, d: b }) ?? real(dayFirst ? { y, m: a, d: b } : { y, m: b, d: a }));
  }
  m = datePart.match(/^(\d{1,2})[\s\-/.]+([a-záéíóú]+)\.?[\s\-/.]+(\d{2}|\d{4})$/); // 5 Jan 2024, 05-ene-24
  if (m && MONTHS[m[2]!]) return withTime(real({ y: year4(+m[3]!), m: MONTHS[m[2]!]!, d: +m[1]! }));
  m = datePart.match(/^([a-záéíóú]+)\.?\s+(\d{1,2})\s+(\d{4})$/); // Jan 5 2024
  if (m && MONTHS[m[1]!]) return withTime(real({ y: +m[3]!, m: MONTHS[m[1]!]!, d: +m[2]! }));
  m = datePart.match(/^(\d{4})(\d{2})(\d{2})$/); // 20240105
  if (m) return withTime(real({ y: +m[1]!, m: +m[2]!, d: +m[3]! }));
  m = datePart.match(/^(\d{5})(\.\d+)?$/); // Excel serial day
  if (m && +m[1]! > 20000 && +m[1]! < 80000) {
    const t = new Date(Date.UTC(1899, 11, 30) + +m[1]! * 86_400_000);
    return withTime({ y: t.getUTCFullYear(), m: t.getUTCMonth() + 1, d: t.getUTCDate() });
  }
  return null;
}

/** Which way a column's ambiguous dates (03/04/2025) read: a value with a first part over 12 means day first. */
export function detectDateOrder(values: string[]): "dmy" | "mdy" {
  let dayFirst = 0;
  let monthFirst = 0;
  for (const v of values) {
    const m = v.trim().match(/^(\d{1,2})[-/.](\d{1,2})[-/.]\d{2,4}/);
    if (!m) continue;
    if (+m[1]! > 12) dayFirst++;
    if (+m[2]! > 12) monthFirst++;
  }
  return dayFirst > monthFirst ? "dmy" : "mdy";
}

export const pad = (n: number) => String(n).padStart(2, "0");

const EMAIL_RE = /^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,}$/;
const DOMAIN_TYPOS: Record<string, string> = {
  "gmial.com": "gmail.com", "gmai.com": "gmail.com", "gmail.co": "gmail.com", "gmail.con": "gmail.com", "gamil.com": "gmail.com",
  "hotmial.com": "hotmail.com", "hotmail.con": "hotmail.com", "hotmal.com": "hotmail.com", "yaho.com": "yahoo.com",
  "yahoo.con": "yahoo.com", "outlook.con": "outlook.com", "outlok.com": "outlook.com",
};

export const fold = (v: string) => v.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
export const splitOptions = (options: string) => options.split(/[\n,;]/).map((o) => o.trim()).filter(Boolean);

function matchOption(value: string, allowed: string[]): string | null {
  const key = fold(value);
  return allowed.find((o) => fold(o) === key) ?? allowed.find((o) => fold(o).replace(/[^a-z0-9]/g, "") === key.replace(/[^a-z0-9]/g, "")) ?? null;
}

const CONNECTORS = new Set(["at", "of", "the", "and", "for", "on", "in", "de", "del", "la", "las", "los", "el", "y", "e", "da", "do", "dos", "di", "du", "van", "von", "der", "le"]);

/**
 * Every word starts with a capital (or is a connector like "de", "at") and none is
 * shouting: keeps "McDonald", "O'Neil", "María de la Cruz", "Poway HS".
 */
export const properlyCased = (v: string) =>
  !(/\p{L}{2}/u.test(v) && v === v.toLocaleUpperCase()) &&
  v.split(/\s+/).every((w, i) => (i > 0 && CONNECTORS.has(w)) || (/^\p{Lu}/u.test(w) && !(/\p{L}{4}/u.test(w) && w === w.toLocaleUpperCase())));

export const titleCase = (v: string) =>
  v.toLocaleLowerCase().replace(/(^|[\s\-'’])(\p{L})/gu, (_m, sep: string, ch: string) => sep + ch.toLocaleUpperCase());

/** One cell cleaned to ``format``. ``order`` is the column's date order. */
export function cleanValue(format: FormatId, raw: string, spec: ColumnSpec, options: CleanOptions, order: "dmy" | "mdy"): Outcome {
  const v = collapse(raw);
  if (!v) return { value: "" };
  if (isPlaceholder(v)) return { value: "", note: `Placeholder “${v}” left blank` };

  switch (format) {
    case "skip":
    case "text":
      return { value: v };
    case "name":
      return { value: properlyCased(v) ? v : titleCase(v) };
    case "number":
      return cleanNumber(v);
    case "date":
    case "datetime": {
      const p = parseDate(v, options.dateOrder === "auto" ? order : options.dateOrder);
      if (!p) return { value: "", invalid: true, note: "Not a recognisable date" };
      const date = `${p.y}-${pad(p.m)}-${pad(p.d)}`;
      return { value: format === "date" ? date : `${date} ${pad(p.hh ?? 0)}:${pad(p.mm ?? 0)}` };
    }
    case "email": {
      let e = v.toLowerCase().replace(/^mailto:/, "");
      const inside = e.match(/<([^>]+)>/) ?? e.match(/[^\s<>,;]+@[^\s<>,;]+/);
      if (inside) e = (inside[1] ?? inside[0]).trim();
      e = e.replace(/\s+/g, "").replace(/[.,;]+$/, "");
      const [user, domain] = e.split("@");
      let note: string | undefined;
      if (domain && DOMAIN_TYPOS[domain]) {
        e = `${user}@${DOMAIN_TYPOS[domain]}`;
        note = `Fixed typo in “${domain}”`;
      }
      if (!EMAIL_RE.test(e)) return { value: "", invalid: true, note: "Not a valid email" };
      return { value: e, note };
    }
    case "phone": {
      const main = v.split(/\s*(?:ext\.?|extension|x|#)\s*\d+\s*$/i)[0]!;
      let digits = main.replace(/[^\d+]/g, "");
      const plus = digits.startsWith("+") || digits.startsWith("00");
      digits = digits.replace(/\D/g, "").replace(/^00/, "");
      if (digits.length < 7 || digits.length > 15) return { value: "", invalid: true, note: "Too few or too many digits for a phone number" };
      const code = options.countryCode.replace(/\D/g, "");
      const value = plus ? `+${digits}` : code && digits.length <= 10 ? `+${code}${digits}` : digits;
      return { value, note: main !== v ? "Extension removed" : undefined };
    }
    case "boolean": {
      const key = fold(v);
      if (/^(true|yes|y|si|s|1|x|verdadero|checked|on)$/.test(key)) return { value: "true" };
      if (/^(false|no|n|0|falso|unchecked|off)$/.test(key)) return { value: "false" };
      return { value: "", invalid: true, note: "Not a yes / no value" };
    }
    case "dropdown": {
      const allowed = splitOptions(spec.options);
      if (!allowed.length) return { value: v };
      const found = matchOption(v, allowed);
      return found ? { value: found } : { value: "", invalid: true, note: "Not one of the dropdown options" };
    }
    case "multi": {
      const allowed = splitOptions(spec.options);
      const parts = [...new Set(v.split(/[;,|]/).map((p) => p.trim()).filter(Boolean))];
      const mapped = allowed.length ? parts.map((p) => matchOption(p, allowed)) : parts;
      const unknown = parts.filter((_, i) => mapped[i] === null);
      const kept = mapped.filter((p): p is string => p !== null);
      return {
        value: kept.join(";"),
        invalid: kept.length === 0 && unknown.length > 0,
        note: unknown.length ? `Dropped values not in the options: ${unknown.join(", ")}` : undefined,
      };
    }
    case "url": {
      const u = v.replace(/\s+/g, "");
      const withScheme = /^https?:\/\//i.test(u) ? u : `https://${u.replace(/^\/+/, "")}`;
      try {
        const parsed = new URL(withScheme);
        if (!parsed.hostname.includes(".")) throw new Error();
        return { value: withScheme.replace(/^HTTPS?:/i, (s) => s.toLowerCase()) };
      } catch {
        return { value: "", invalid: true, note: "Not a valid web address" };
      }
    }
    case "domain": {
      const d = v.toLowerCase().replace(/\s+/g, "").replace(/^[a-z]+:\/\//, "").replace(/^www\./, "").split(/[/?#]/)[0]!.replace(/^.*@/, "");
      if (!/^[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(d)) return { value: "", invalid: true, note: "Not a valid domain" };
      return { value: d };
    }
  }
}

// ---- Cleaning the whole table ---------------------------------------------------------------

/** A value the user decided in the review (lib/data-review), keyed by ``${column}${value}``. */
export type Override = { value: string; how: string };

export function cleanTable(table: Table, specs: ColumnSpec[], options: CleanOptions, overrides?: Map<string, Override>): CleanResult {
  const keep = specs.map((s, i) => ({ s, i })).filter(({ s }) => s.format !== "skip");
  const orders = specs.map((s, i) => (s.format === "date" || s.format === "datetime" ? detectDateOrder(table.rows.map((r) => r[i] ?? "")) : "mdy"));
  const columns: ColumnReport[] = keep.map(({ s, i }) => ({
    name: s.name,
    format: s.format,
    fixed: 0,
    blanked: 0,
    detail:
      s.format === "date" || s.format === "datetime"
        ? `Ambiguous dates read ${(options.dateOrder === "auto" ? orders[i] : options.dateOrder) === "dmy" ? "day first (dd/mm)" : "month first (mm/dd)"}`
        : undefined,
  }));
  const issues: Issue[] = [];
  const rows: string[][] = [];
  const changed: boolean[][] = [];
  const sources: number[] = [];
  const seen = new Set<string>();
  let emptyRows = 0;
  let duplicates = 0;

  table.rows.forEach((source, r) => {
    const results = keep.map(({ s, i }) => {
      const raw = source[i] ?? "";
      const decided = overrides?.get(`${i}${collapse(raw)}`);
      return {
        raw,
        original: raw.trim(),
        res: decided ? { value: decided.value, note: decided.how } : cleanValue(s.format, raw, s, options, orders[i]!),
      };
    });
    const out = results.map((x) => x.res.value);
    if (out.every((c) => c === "")) {
      emptyRows++;
      return;
    }
    if (options.removeDuplicates) {
      const key = out.join("\u0001");
      if (seen.has(key)) {
        duplicates++;
        return;
      }
      seen.add(key);
    }
    // Only rows that stay in the file count towards fixes and issues.
    results.forEach(({ raw, original, res }, k) => {
      if (res.value !== original) {
        if (original && !res.value) columns[k]!.blanked++;
        else if (res.value !== collapse(raw) || res.note) columns[k]!.fixed++;
      }
      if (res.invalid || res.note || (original && !res.value)) {
        issues.push({ row: r + 2, column: keep[k]!.s.name, original, result: res.value, note: res.note ?? "Left blank" });
      }
    });
    rows.push(out);
    sources.push(r + 2);
    changed.push(results.map((x) => x.res.value !== x.original));
  });

  return {
    headers: keep.map(({ s }) => s.name.trim() || "Column"),
    rows,
    changed,
    sources,
    columns,
    issues,
    stats: {
      rowsIn: table.rows.length,
      rowsOut: rows.length,
      emptyRows,
      duplicates,
      fixed: columns.reduce((n, c) => n + c.fixed, 0),
      blanked: columns.reduce((n, c) => n + c.blanked, 0),
    },
  };
}

/** CSV text HubSpot imports: comma separated, quoted where needed, UTF-8. */
export function toCsv(headers: string[], rows: string[][]): string {
  const cell = (v: string) => (/[",\n\r]/.test(v) || /^\s|\s$/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  return [headers, ...rows].map((r) => r.map(cell).join(",")).join("\r\n") + "\r\n";
}
