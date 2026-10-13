"use client";

/**
 * Documentation Generator: the portal's documentation pack from the
 * read-only snapshot — data dictionary, workflow inventory, association
 * map, pipelines & stages, and teams / owners — as Markdown or Word.
 */

import { useState } from "react";

import { DataTable } from "@/components/project/DataTable";
import { PortalPage } from "@/components/project/PortalPage";
import { Stats } from "@/components/project/Stats";
import { ExportFooter } from "@/components/ui";
import { fileStub, snapshotDocument, type PortalSnapshot, type Project } from "@/lib/api";

const yesNo = (v: boolean | undefined) => (v ? "Yes" : "No");

function Documentation({ project, snapshot }: { project: Project; snapshot: PortalSnapshot }) {
  const [open, setOpen] = useState<string | null>(null);
  const schemas = snapshot.object_schemas ?? [];
  const workflows = snapshot.workflows ?? [];
  const pipelines = snapshot.pipelines ?? [];
  const teams = snapshot.teams ?? [];
  const owners = snapshot.owners ?? [];
  const associations = schemas.flatMap((s) => s.associations ?? []);
  const stub = fileStub(project.client_name || project.name, "portal_documentation");

  return (
    <>
      <Stats
        items={[
          ["Objects", schemas.length],
          ["Properties", schemas.reduce((n, s) => n + (s.properties ?? []).length, 0)],
          ["Workflows", workflows.length],
          ["Pipelines", pipelines.length],
          ["Owners", owners.length],
        ]}
      />

      <section className="stack" style={{ gap: 12 }}>
        <h2 className="t-section">Data dictionary</h2>
        {schemas.map((schema) => {
          const key = schema.object_type;
          const props = schema.properties ?? [];
          return (
            <div key={key} className="card" style={{ padding: 0 }}>
              <button
                type="button"
                className="disclosure"
                aria-expanded={open === key}
                onClick={() => setOpen(open === key ? null : key)}
              >
                <span className="t-card-title">{schema.label}</span>
                <span className="t-caption">
                  {schema.is_custom ? "Custom" : "Standard"} · {schema.object_type} · {props.length} properties
                </span>
                <span aria-hidden>{open === key ? "−" : "+"}</span>
              </button>
              {open === key && (
                <div style={{ padding: "0 16px 16px" }}>
                  <DataTable
                    label={`${schema.label} properties`}
                    empty="No properties returned."
                    columns={[
                      { key: "name", label: "Property", width: "minmax(150px, 1.2fr)" },
                      { key: "label", label: "Label", width: "minmax(150px, 1.2fr)" },
                      { key: "type", label: "Type", width: "100px" },
                      { key: "field", label: "Field type", width: "110px" },
                      { key: "group", label: "Group", width: "minmax(120px, 1fr)" },
                      { key: "options", label: "Options", width: "minmax(160px, 1.4fr)" },
                    ]}
                    rows={props.map((p) => ({
                      name: <code>{p.name}</code>,
                      label: p.label,
                      type: p.type,
                      field: p.field_type,
                      group: p.group_name,
                      options: (p.options ?? []).join(", "),
                    }))}
                  />
                </div>
              )}
            </div>
          );
        })}
      </section>

      <section className="stack" style={{ gap: 12 }}>
        <h2 className="t-section">Workflow inventory</h2>
        <DataTable
          label="Workflows"
          empty="No workflows returned."
          columns={[
            { key: "name", label: "Name", width: "minmax(220px, 2fr)" },
            { key: "object", label: "Object type", width: "minmax(110px, 1fr)" },
            { key: "enabled", label: "Enabled", width: "90px" },
            { key: "reenroll", label: "Re-enrollment", width: "120px" },
            { key: "actions", label: "Actions", width: "80px" },
          ]}
          rows={workflows.map((w) => ({
            name: w.name,
            object: w.object_type,
            enabled: yesNo(w.enabled),
            reenroll: yesNo(w.re_enrollment_enabled),
            actions: (w.actions ?? []).length,
          }))}
        />
      </section>

      <section className="stack" style={{ gap: 12 }}>
        <h2 className="t-section">Association map</h2>
        <p className="t-caption">
          From each custom object&apos;s schema. Default associations between standard objects aren&apos;t exposed by this endpoint and are omitted.
        </p>
        <DataTable
          label="Associations"
          empty="None found."
          columns={[
            { key: "from", label: "From", width: "1fr" },
            { key: "to", label: "To (type ID)", width: "1fr" },
            { key: "label", label: "Label", width: "1fr" },
          ]}
          rows={associations.map((a) => ({ from: a.from_object, to: a.to_object, label: a.label || "—" }))}
        />
      </section>

      <section className="stack" style={{ gap: 12 }}>
        <h2 className="t-section">Pipelines &amp; stages</h2>
        {pipelines.length === 0 && <p className="t-caption">No pipelines returned.</p>}
        <div className="grid-2">
          {pipelines.map((pl) => (
            <div key={pl.pipeline_id} className="card stack" style={{ gap: 8 }}>
              <span className="t-card-title">{pl.label}</span>
              <span className="t-caption">{pl.object_type}</span>
              <ol style={{ margin: 0, paddingLeft: 20 }}>
                {[...(pl.stages ?? [])]
                  .sort((a, b) => a.display_order - b.display_order)
                  .map((s) => (
                    <li key={s.stage_id}>{s.label}</li>
                  ))}
              </ol>
            </div>
          ))}
        </div>
      </section>

      <section className="stack" style={{ gap: 12 }}>
        <h2 className="t-section">Roles &amp; permissions</h2>
        <div className="grid-2" style={{ alignItems: "start" }}>
          <DataTable
            label="Teams"
            empty="No teams returned."
            columns={[
              { key: "team", label: "Team", width: "2fr" },
              { key: "members", label: "Members", width: "1fr" },
            ]}
            rows={teams.map((t) => ({ team: t.name, members: t.member_count }))}
          />
          <DataTable
            label="Owners"
            empty="No owners returned."
            columns={[
              { key: "name", label: "Name", width: "minmax(120px, 1fr)" },
              { key: "email", label: "Email", width: "minmax(160px, 1.4fr)" },
              { key: "teams", label: "Teams", width: "minmax(100px, 1fr)" },
              { key: "archived", label: "Archived", width: "80px" },
            ]}
            rows={owners.map((o) => ({
              name: `${o.first_name ?? ""} ${o.last_name ?? ""}`.trim() || "—",
              email: o.email,
              teams: (o.teams ?? []).join(", ") || "—",
              archived: yesNo(o.archived),
            }))}
          />
        </div>
      </section>

      <ExportFooter
        library={{ projectId: project.id, documentType: "Documentation Pack" }}
        actions={(["docx", "md"] as const).map((format) => ({ label: `.${format}`, make: () => snapshotDocument(snapshot, format, stub) }))}
      />
    </>
  );
}

export default function DocumentationPage() {
  return (
    <PortalPage
      eyebrow="STEP 2 / DOCUMENT"
      title="Documentation Generator"
      description="The portal's documentation pack: data dictionary, workflow inventory, association map, pipelines & stages, and teams & owners. Every call is read-only."
    >
      {(project, store) =>
        store.state.snapshot ? (
          <Documentation project={project} snapshot={store.state.snapshot} />
        ) : (
          <p className="t-caption">Pull from HubSpot to generate the documentation pack.</p>
        )
      }
    </PortalPage>
  );
}
