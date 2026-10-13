"use client";

/**
 * Property Audit: rates every property in the snapshot Keep, Review or
 * Remove candidate (sampled fill rate + workflow references) and exports a
 * color-matched workbook and a short PDF so a person checks the calls
 * before anything is deleted in HubSpot. Nothing is changed by this tool.
 */

import { useState } from "react";

import { DataTable } from "@/components/project/DataTable";
import { PortalPage } from "@/components/project/PortalPage";
import { Stats } from "@/components/project/Stats";
import { Callout, ExportFooter } from "@/components/ui";
import { ApiError, exportPropertyAudit, fileStub, runPropertyAudit, type Project, type PropertyAuditResult } from "@/lib/api";
import type { ModuleStore } from "@/lib/module-state";
import { toggle, type PortalState } from "@/lib/portal-state";

type Row = NonNullable<PropertyAuditResult["rows"]>[number];
const RATING_ORDER: Record<string, number> = { "Remove candidate": 0, Review: 1, Keep: 2 };

/** Same as the domain's ``totals``: counts summed, cleanup score over custom properties. */
function totals(result: PropertyAuditResult) {
  const s = result.object_summaries ?? [];
  const sum = (key: "properties_count" | "custom_count" | "remove_count" | "review_count" | "keep_count") => s.reduce((n, o) => n + o[key], 0);
  const custom = sum("custom_count");
  const score = custom === 0 ? 100 : 100 * (1 - (sum("remove_count") + 0.5 * sum("review_count")) / custom);
  return { properties: sum("properties_count"), keep: sum("keep_count"), review: sum("review_count"), remove: sum("remove_count"), score: Math.round(score) };
}

/** Review / Remove candidate rows, worst first — the cleanup worklist. */
function flagged(result: PropertyAuditResult): Row[] {
  return (result.rows ?? [])
    .filter((r) => r.rating !== "Keep")
    .sort(
      (a, b) =>
        (RATING_ORDER[a.rating] ?? 3) - (RATING_ORDER[b.rating] ?? 3) ||
        a.fill_pct - b.fill_pct ||
        a.object_label.localeCompare(b.object_label) ||
        a.property_label.localeCompare(b.property_label),
    );
}

function PropertyAudit({ project, store }: { project: Project; store: ModuleStore<PortalState> }) {
  const { state, update } = store;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hidden, setHidden] = useState<string[]>([]);
  const result = state.propertyAudit;
  const clientName = project.client_name || project.name;

  const run = async () => {
    if (!state.snapshot) return;
    setBusy(true);
    setError(null);
    try {
      update({ propertyAudit: await runPropertyAudit(state.snapshot) });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The property audit didn't finish.");
    }
    setBusy(false);
  };

  const worklist = result ? flagged(result) : [];
  const objects = [...new Set(worklist.map((r) => r.object_label))].sort();
  const shown = worklist.filter((r) => !hidden.includes(r.object_label));
  const t = result ? totals(result) : null;

  return (
    <>
      <div className="row">
        <button type="button" className="btn btn-primary" disabled={!state.snapshot || busy} onClick={() => void run()}>
          {busy ? "Sampling records and rating properties…" : result ? "Run the property audit again" : "Run property audit"}
        </button>
        <span className="t-caption">
          {!state.snapshot
            ? "Pull from HubSpot first, then run the property audit."
            : result
              ? `Last run ${new Date(result.generated_at).toLocaleString()} · fill % from up to ${result.sample_size} records per object`
              : "Only custom properties are ever flagged; native HubSpot properties are always Keep."}
        </span>
      </div>
      {error && (
        <Callout tone="error" title="The property audit didn't finish">
          {error}
        </Callout>
      )}

      {result && t && (
        <section className="stack" style={{ gap: 16 }}>
          {(result.warnings ?? []).map((w) => (
            <Callout key={w} tone="warning" title="Heads up">
              {w}
            </Callout>
          ))}
          <Stats
            items={[
              ["Properties audited", t.properties],
              ["Keep", t.keep],
              ["Review", t.review],
              ["Remove candidate", t.remove],
              ["Cleanup score", `${t.score}/100`],
            ]}
          />
          <p className="t-caption">
            &ldquo;Uses&rdquo; counts references in this portal&apos;s workflow actions only — forms, lists, reports and dashboards aren&apos;t pulled, so a property used only there still shows 0.
          </p>

          <h2 className="t-section">Summary by object</h2>
          <DataTable
            label="Summary by object"
            columns={[
              { key: "object", label: "Object", width: "minmax(160px, 1.4fr)" },
              { key: "properties", label: "Properties", width: "100px" },
              { key: "custom", label: "Custom", width: "90px" },
              { key: "remove", label: "Remove candidate", width: "140px" },
              { key: "review", label: "Review", width: "90px" },
              { key: "keep", label: "Keep", width: "90px" },
              { key: "score", label: "Cleanup score", width: "120px" },
            ]}
            rows={(result.object_summaries ?? []).map((s) => ({
              object: s.object_label,
              properties: s.properties_count,
              custom: s.custom_count,
              remove: s.remove_count,
              review: s.review_count,
              keep: s.keep_count,
              score: s.cleanup_score,
            }))}
          />

          <h2 className="t-section">Flagged for action ({worklist.length})</h2>
          {worklist.length === 0 ? (
            <Callout tone="success" title="No custom properties flagged">
              Every custom field is well filled or in active use.
            </Callout>
          ) : (
            <>
              <div className="filter-row" role="group" aria-label="Filter by object">
                <span className="field-label">Object</span>
                {objects.map((o) => (
                  <button key={o} type="button" className="filter-chip" aria-pressed={!hidden.includes(o)} onClick={() => setHidden(toggle(hidden, o))}>
                    {o}
                  </button>
                ))}
              </div>
              <DataTable
                label="Flagged properties"
                empty="No flagged properties for these objects."
                columns={[
                  { key: "object", label: "Object", width: "minmax(110px, 0.8fr)" },
                  { key: "property", label: "Property", width: "minmax(150px, 1.2fr)" },
                  { key: "internal", label: "Internal name", width: "minmax(150px, 1.2fr)" },
                  { key: "type", label: "Type", width: "100px" },
                  { key: "fill", label: "Fill %", width: "70px" },
                  { key: "uses", label: "Uses", width: "60px" },
                  { key: "rating", label: "Rating", width: "140px" },
                  { key: "assessment", label: "Assessment", width: "minmax(220px, 2fr)" },
                ]}
                rows={shown.map((r) => ({
                  object: r.object_label,
                  property: r.property_label,
                  internal: <code>{r.internal_name}</code>,
                  type: r.field_type,
                  fill: `${r.fill_pct}%`,
                  uses: r.uses,
                  rating: <span className={`sev ${r.rating === "Remove candidate" ? "sev-High" : "sev-Medium"}`}>{r.rating}</span>,
                  assessment: r.assessment,
                }))}
              />
            </>
          )}
          <ExportFooter
            library={{ projectId: project.id, documentType: "Property Audit" }}
            actions={(["xlsx", "pdf"] as const).map((format) => ({
              label: `.${format}`,
              make: () => exportPropertyAudit({ result, project_name: clientName }, format, fileStub(clientName, "property_audit")),
            }))}
          />
        </section>
      )}
    </>
  );
}

export default function PropertyAuditPage() {
  return (
    <PortalPage
      title="Property Audit"
      description="Rates every property in the live portal Keep, Review or Remove candidate — from a sampled fill rate and workflow references — so a person can check the calls before anything is deleted in HubSpot. Nothing is changed by this tool."
    >
      {(project, store) => <PropertyAudit project={project} store={store} />}
    </PortalPage>
  );
}
