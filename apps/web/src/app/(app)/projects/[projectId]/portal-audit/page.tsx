"use client";

/**
 * Portal Auditor: checks the project's read-only HubSpot snapshot against
 * best practice (duplicate / unused / missing-required properties, orphaned
 * records, risky workflows, team anomalies, naming drift). Findings are
 * saved to the project for the Executive Report and the diagram.
 */

import { useState } from "react";

import { DataTable } from "@/components/project/DataTable";
import { PortalPage } from "@/components/project/PortalPage";
import { Stats } from "@/components/project/Stats";
import { Callout, ExportFooter } from "@/components/ui";
import { ApiError, exportSections, fileStub, runAudit, textFile, type Finding, type Project } from "@/lib/api";
import type { ModuleStore } from "@/lib/module-state";
import { bySeverity, SEVERITIES, toggle, type PortalState } from "@/lib/portal-state";

function findingsMarkdown(findings: Finding[]): string {
  const lines = ["# Portal audit findings", ""];
  for (const sev of SEVERITIES) {
    const group = findings.filter((f) => f.severity === sev);
    if (!group.length) continue;
    lines.push(`## ${sev} (${group.length})`, "");
    for (const f of group) {
      lines.push(`- **${f.area}**${f.object_type ? ` (${f.object_type})` : ""}: ${f.description}  `, `  _Fix:_ ${f.recommended_fix}`);
    }
    lines.push("");
  }
  return lines.join("\n");
}

const exportRows = (findings: Finding[]) =>
  findings.map((f) => ({
    Severity: f.severity,
    Area: f.area,
    Object: f.object_type ?? "",
    Description: f.description,
    "Recommended Fix": f.recommended_fix,
  }));

function Audit({ project, store }: { project: Project; store: ModuleStore<PortalState> }) {
  const { state, update } = store;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [severities, setSeverities] = useState<string[]>([...SEVERITIES]);
  const [hiddenAreas, setHiddenAreas] = useState<string[]>([]);

  const findings = state.findings;
  const areas = [...new Set((findings ?? []).map((f) => f.area))].sort();
  const filtered = (findings ?? []).filter((f) => severities.includes(f.severity) && !hiddenAreas.includes(f.area)).sort(bySeverity);
  const clientName = project.client_name || project.name;
  const stub = fileStub(clientName, "audit_findings");

  const audit = async () => {
    if (!state.snapshot) return;
    setBusy(true);
    setError(null);
    try {
      const result = await runAudit(state.snapshot);
      update({ findings: result.findings, auditedAt: new Date().toISOString() });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The audit didn't finish.");
    }
    setBusy(false);
  };

  return (
    <>
      <div className="row">
        <button type="button" className="btn btn-primary" disabled={!state.snapshot || busy} onClick={() => void audit()}>
          {busy ? "Running checks…" : findings ? "Run the audit again" : "Run audit"}
        </button>
        <span className="t-caption">
          {!state.snapshot
            ? "Pull from HubSpot first, then run the audit."
            : state.auditedAt
              ? `Last run ${new Date(state.auditedAt).toLocaleString()}`
              : "Record-level checks sample records per object rather than pulling everything, and say so in each finding."}
        </span>
      </div>
      {error && (
        <Callout tone="error" title="The audit didn't finish">
          {error}
        </Callout>
      )}

      {findings && (
        <section className="stack" style={{ gap: 16 }}>
          <h2 className="t-section">Findings ({findings.length})</h2>
          {findings.length === 0 ? (
            <Callout tone="success" title="No findings">
              The portal looks clean against the checks this tool runs.
            </Callout>
          ) : (
            <>
              <Stats items={SEVERITIES.map((s) => [s, findings.filter((f) => f.severity === s).length])} />
              <div className="filter-row" role="group" aria-label="Filter by severity">
                <span className="field-label">Severity</span>
                {SEVERITIES.map((s) => (
                  <button key={s} type="button" className="filter-chip" aria-pressed={severities.includes(s)} onClick={() => setSeverities(toggle(severities, s))}>
                    {s}
                  </button>
                ))}
              </div>
              <div className="filter-row" role="group" aria-label="Filter by area">
                <span className="field-label">Area</span>
                {areas.map((a) => (
                  <button key={a} type="button" className="filter-chip" aria-pressed={!hiddenAreas.includes(a)} onClick={() => setHiddenAreas(toggle(hiddenAreas, a))}>
                    {a}
                  </button>
                ))}
              </div>
              <DataTable
                label="Audit findings"
                empty="No findings match these filters."
                columns={[
                  { key: "severity", label: "Severity", width: "96px" },
                  { key: "area", label: "Area", width: "minmax(140px, 1fr)" },
                  { key: "object", label: "Object", width: "minmax(100px, 0.7fr)" },
                  { key: "description", label: "Description", width: "minmax(220px, 2fr)" },
                  { key: "fix", label: "Recommended fix", width: "minmax(220px, 2fr)" },
                ]}
                rows={filtered.map((f) => ({
                  severity: <span className={`sev sev-${f.severity}`}>{f.severity}</span>,
                  area: f.area,
                  object: f.object_type || "—",
                  description: f.description,
                  fix: f.recommended_fix,
                }))}
              />
              <ExportFooter
                library={{ projectId: project.id, documentType: "Portal Audit Findings" }}
                actions={[
                  { label: ".xlsx", make: () => exportSections("Portal audit findings", clientName, [{ title: "Findings", rows: exportRows(filtered) }], "xlsx", stub) },
                  { label: ".csv", make: () => exportSections("Portal audit findings", clientName, [{ title: "Findings", rows: exportRows(filtered) }], "csv", stub) },
                  { label: ".md", make: () => textFile(findingsMarkdown(filtered), `${stub}.md`, "text/markdown") },
                ]}
              />
            </>
          )}
        </section>
      )}
    </>
  );
}

export default function PortalAuditPage() {
  return (
    <PortalPage
      title="Portal Auditor"
      description="Checks the live portal against best practice — duplicate and unused properties, missing required data, orphaned records, risky workflows, team anomalies and naming drift. Every call is read-only."
    >
      {(project, store) => <Audit project={project} store={store} />}
    </PortalPage>
  );
}
