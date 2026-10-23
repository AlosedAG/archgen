/** People shown as coloured initials: the same person always gets the same colour. */

// The mockup's avatar hues (indigo, coral, amber, green, violet, blue), deepened
// where needed so white initials keep at least 4.5:1 contrast.
const PALETTE = ["#5B53E8", "#C73E22", "#9A6506", "#14805A", "#6A5BD8", "#3A63C9"];

export function initials(name: string): string {
  return name
    .split(/[\s@.]+/)
    .map((part) => part.replace(/[^\p{L}\p{N}]/gu, ""))
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function avatarColor(id: string): string {
  let hash = 0;
  for (const ch of id) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return PALETTE[hash % PALETTE.length]!;
}
