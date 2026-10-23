/**
 * SOW clause helpers shared by the builder's Terms tab and the admin clause
 * library: finding the [[blanks]] left to fill and the {{tokens}} that fill
 * from the SOW (the same rules as archscope_domain.sow_clauses).
 */

export const BLANK_RE = /\[\[([^\]]*)\]\]/g;

export const TOKENS: Record<string, string> = {
  client: "the client's company",
  seller: "SonaMation's company name",
  valid_until: "the proposal-valid-until date",
  effective_date: "the effective date",
};

/** The distinct [[blanks]] in a text, as written. */
export function blanksIn(text: string): string[] {
  return [...new Set([...text.matchAll(BLANK_RE)].map((m) => m[0]))];
}

export const LEGAL_NOTE =
  "These clauses are editable placeholder templates, not legal advice. Your firm's legal counsel should review and approve the standard set, and any change made to it in a SOW, before anything is signed.";

// A token whose SOW value is empty is a blank too (same names as the API uses).
const TOKEN_BLANKS: Record<string, string> = {
  client: "[[client name]]",
  seller: "[[SonaMation's legal name]]",
  valid_until: "[[proposal validity date]]",
  effective_date: "[[effective date]]",
};

/** What's still to fill in a SOW clause: its [[blanks]], plus {{tokens}} whose SOW value is empty. */
export function clauseBlanks(text: string, values: Record<string, string | null | undefined>): string[] {
  const empty = [...text.matchAll(/\{\{\s*(\w+)\s*\}\}/g)]
    .map((m) => m[1]!)
    .filter((name) => name in TOKEN_BLANKS && !String(values[name] ?? "").trim())
    .map((name) => TOKEN_BLANKS[name]!);
  return [...new Set([...blanksIn(text), ...empty])];
}
