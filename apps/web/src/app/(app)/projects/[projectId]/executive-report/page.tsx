"use client";

/**
 * Executive Report: what the portal has, how it's structured and what's
 * worth fixing, from the saved snapshot (and audit findings when run). A
 * polished client version and a full-detail internal version. Makes no
 * HubSpot calls of its own.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { DataTable } from "@/components/project/DataTable";
import { PortalPage } from "@/components/project/PortalPage";
import { Stats } from "@/components/project/Stats";
import { Callout, ExportFooter } from "@/components/ui";
import { ApiError, fileStub, reportContext, reportDocument, type Project, type ReportContext } from "@/lib/api";
import type { ModuleStore } from "@/lib/module-state";
import { SEVERITIES, type PortalState } from "@/lib/portal-state";

function Report({ project, store }: { project: Project; store: ModuleStore<PortalState> }) {
  const { snapshot, findings } = store.state;
  const clientName = project.client_name || project.name;
  const [ctx, setCtx] = useState<ReportContext | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!snapshot) return;
    let live = true;
    reportContext({ snapshot, findings, project_name: clientName })
      .then((c) => live && setCtx(c))
      .catch((e: unknown) => live && setError(e instanceof ApiError ? e.message : "Couldn't build the report."));
    return () => {
      live = false;
    };
  }, [snapshot, findings, clientName]);

  if (!snapshot) {
    return (
      <Callout tone="info" title="No portal snapshot yet">
        Pull one from the{" "}
        <Link className="btn-link" href={`/projects/${project.id}/portal-audit`}>
          Portal Auditor
        </Link>{" "}
        or the{" "}
        <Link className="btn-link" href={`/projects/${project.id}/documentation`}>
          Documentation Generator
        </Link>{" "}
        first.
      </Callout>
    );
  }
  if (error) return <Callout tone="error" title="Couldn't build the report">{error}</Callout>;
  if (!ctx) return <div className="skeleton" style={{ height: 240 }} aria-busy="true" />;

  const body = { snapshot, findings, project_name: clientName };
  return (
    <>
      {!findings && (
        <Callout tone="warning" title="No audit has been run yet">
          The report will describe the portal&apos;s structure, but &ldquo;Things worth fixing&rdquo; stays empty until you{" "}
          <Link className="btn-link" href={`/projects/${project.id}/portal-audit`}>
            run the audit
          </Link>
          .
        </Callout>
      )}
      <Stats
        items={[
          ["Overall health", ctx.rating],
          ["Findings", ctx.audited ? ctx.finding_total : "—"],
          ["Objects / properties", `${ctx.standard_object_count + ctx.custom_object_count} / ${ctx.total_properties}`],
        ]}
      />
      <p className="t-caption">{ctx.rating_reason}</p>

      <section className="stack" style={{ gap: 12 }}>
        <h2 className="t-section">What&apos;s in this portal</h2>
        <DataTable
          label="Objects"
          columns={[
            { key: "object", label: "Object", width: "minmax(130px, 1fr)" },
            { key: "kind", label: "Kind", width: "90px" },
            { key: "props", label: "Properties", width: "100px" },
            { key: "groups", label: "Top data groups", width: "minmax(200px, 2fr)" },
            { key: "links", label: "Connects to", width: "minmax(160px, 1.4fr)" },
          ]}
          rows={ctx.object_summaries.map((o) => ({
            object: o.label,
            kind: o.is_custom ? "Custom" : "Standard",
            props: o.property_count,
            groups: (o.top_groups ?? []).slice(0, 3).map((g) => `${g.name} (${g.count})`).join(", ") || "—",
            links: (o.association_targets ?? []).join(", ") || "—",
          }))}
        />
      </section>

      {ctx.pipeline_summaries.length > 0 && (
        <section className="stack" style={{ gap: 12 }}>
          <h2 className="t-section">Pipelines</h2>
          <DataTable
            label="Pipelines"
            columns={[
              { key: "object", label: "Object", width: "1fr" },
              { key: "pipelines", label: "Pipelines", width: "1fr" },
              { key: "stages", label: "Total stages", width: "1fr" },
            ]}
            rows={ctx.pipeline_summaries.map((p) => ({ object: p.object_type, pipelines: p.pipeline_count, stages: p.total_stage_count }))}
          />
        </section>
      )}

      <section className="stack" style={{ gap: 12 }}>
        <h2 className="t-section">Automation &amp; people</h2>
        <div className="grid-2">
          <p className="t-description">
            <strong>Workflows:</strong> {ctx.workflow_total} total — {ctx.workflow_enabled} enabled, {ctx.workflow_disabled} disabled, {ctx.workflow_unnamed} still using
            HubSpot&apos;s default &ldquo;Unnamed workflow&rdquo; name.
          </p>
          <p className="t-description">
            <strong>Users &amp; teams:</strong> {ctx.owner_total} owners ({ctx.owner_unassigned} not on a team, {ctx.owner_archived} archived), {ctx.team_total} teams ({ctx.team_empty} with no members).
          </p>
        </div>
      </section>

      {ctx.audited && (
        <section className="stack" style={{ gap: 12 }}>
          <h2 className="t-section">Things worth fixing</h2>
          {ctx.finding_groups.length === 0 && (
            <Callout tone="success" title="No issues found in this scan" />
          )}
          {SEVERITIES.map((sev) => {
            const groups = ctx.finding_groups.filter((g) => g.severity === sev);
            if (!groups.length) return null;
            return (
              <div key={sev} className="stack" style={{ gap: 10 }}>
                <h3 className="t-card-title">
                  <span className={`sev sev-${sev}`}>{sev}</span> {groups.reduce((n, g) => n + g.count, 0)} finding(s)
                </h3>
                {groups.map((g) => (
                  <div key={g.area} className="stack" style={{ gap: 6 }}>
                    <span className="field-label">
                      {g.area} ({g.count})
                    </span>
                    <DataTable
                      label={g.area}
                      columns={[
                        { key: "object", label: "Object", width: "minmax(100px, 0.7fr)" },
                        { key: "description", label: "Description", width: "minmax(220px, 2fr)" },
                        { key: "fix", label: "Recommended fix", width: "minmax(220px, 2fr)" },
                      ]}
                      rows={(g.items ?? []).map((f) => ({ object: f.object_type || "—", description: f.description, fix: f.recommended_fix }))}
                    />
                  </div>
                ))}
              </div>
            );
          })}
        </section>
      )}

      <div className="grid-2" style={{ alignItems: "start" }}>
        <div className="card stack" style={{ gap: 8 }}>
          <span className="t-card-title">Client report</span>
          <span className="t-caption">Polished and plain-language — safe to send to the client as-is.</span>
          <ExportFooter
            divider={false}
            library={{ projectId: project.id, documentType: "Executive Report (Client)" }}
            actions={[{ label: ".docx", make: () => reportDocument(body, "client", fileStub(clientName, "portal_report_client")) }]}
          />
        </div>
        <div className="card stack" style={{ gap: 8 }}>
          <span className="t-card-title">Internal report</span>
          <span className="t-caption">Full technical detail — every finding and raw property groups.</span>
          <ExportFooter
            divider={false}
            library={{ projectId: project.id, documentType: "Executive Report (Internal)" }}
            actions={[{ label: ".docx", make: () => reportDocument(body, "internal", fileStub(clientName, "portal_report_internal")) }]}
          />
        </div>
      </div>
    </>
  );
}

export default function ExecutiveReportPage() {
  return (
    <PortalPage
      eyebrow="STEP 2 / REPORT"
      title="Executive Report"
      description="What the portal has, how it's structured, and what's worth fixing — as a polished client version and a full-detail internal version."
      pullBar={false}
    >
      {(project, store) => <Report project={project} store={store} />}
    </PortalPage>
  );
}
