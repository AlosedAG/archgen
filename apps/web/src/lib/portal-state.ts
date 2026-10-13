/**
 * The project's read-only HubSpot snapshot and what's been computed from
 * it (audit findings, property audit), saved under the "portal" module and
 * shared by every Step 2 page and the live-portal diagram.
 */

import type { Finding, PortalSnapshot, PropertyAuditResult } from "./api";

export type PortalState = {
  snapshot: PortalSnapshot | null;
  findings: Finding[] | null;
  auditedAt: string | null;
  propertyAudit: PropertyAuditResult | null;
};

export function normalizePortal(raw: unknown): PortalState {
  const s = (typeof raw === "object" && raw ? raw : {}) as Partial<PortalState>;
  return { snapshot: s.snapshot ?? null, findings: s.findings ?? null, auditedAt: s.auditedAt ?? null, propertyAudit: s.propertyAudit ?? null };
}

export const SEVERITIES = ["High", "Medium", "Low"] as const;
const SEVERITY_ORDER: Record<string, number> = { High: 0, Medium: 1, Low: 2 };

/** Worst first. */
export const bySeverity = (a: Finding, b: Finding) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3);

/** Add or remove ``value`` (filter chips). */
export function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}
