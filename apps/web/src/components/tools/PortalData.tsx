"use client";

/**
 * Database and Data Documentation (first versions): read a project's saved,
 * read-only HubSpot snapshot (pulled by the Portal Auditor) and show its
 * objects, pipelines and owners, or a property dictionary for one object.
 * Nothing here calls HubSpot.
 */

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { DataTable } from "@/components/project/DataTable";
import { Stats } from "@/components/project/Stats";
import { Callout } from "@/components/ui";
import { ApiError, downloadFile, getModuleState, listProjects, textFile, type PortalSnapshot, type Project } from "@/lib/api";
import { normalizePortal } from "@/lib/portal-state";

function useSnapshot() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [projectId, setProjectId] = useState("");
  const [snapshot, setSnapshot] = useState<PortalSnapshot | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listProjects()
      .then((list) => {
        setProjects(list);
        if (list[0]) setProjectId(list[0].id);
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Couldn't load the projects."));
  }, []);

  useEffect(() => {
    if (!projectId) return;
    setSnapshot(undefined);
    getModuleState(projectId, "portal")
      .then((saved) => setSnapshot(normalizePortal(saved.data).snapshot))
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Couldn't load the snapshot."));
  }, [projectId]);

  return { projects, projectId, setProjectId, snapshot, error };
}

function ProjectPicker({ projects, value, onChange }: { projects: Project[]; value: string; onChange: (id: string) => void }) {
  return (
    <label className="field" style={{ maxWidth: 360 }}>
      <span className="field-label">Project</span>
      <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        {projects.map((p) => (
          <option key={p.id} value={p.id}>
            {p.client_name || p.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function NoSnapshot({ projectId }: { projectId: string }) {
  return (
    <Callout tone="info" title="No portal snapshot for this project yet">
      Pull one (read-only) in the project&apos;s <Link href={`/projects/${projectId}/portal-audit`}>Portal Auditor</Link>, then come back.
    </Callout>
  );
}

function Frame({ children, state }: { children: (snapshot: PortalSnapshot) => React.ReactNode; state: ReturnType<typeof useSnapshot> }) {
  const { projects, projectId, setProjectId, snapshot, error } = state;
  if (error) return <Callout tone="error" title="Something went wrong">{error}</Callout>;
  if (!projects) return <div className="skeleton" style={{ height: 240 }} aria-busy="true" />;
  if (!projects.length) return <Callout tone="info" title="No projects yet">Create a project under Projects first.</Callout>;
  return (
    <>
      <ProjectPicker projects={projects} value={projectId} onChange={setProjectId} />
      {snapshot === undefined ? (
        <div className="skeleton" style={{ height: 240 }} aria-busy="true" />
      ) : snapshot === null ? (
        <NoSnapshot projectId={projectId} />
      ) : (
        <>
          {Number.isFinite(Date.parse(snapshot.pulled_at)) && (
            <p className="t-caption">Snapshot pulled {new Date(snapshot.pulled_at).toLocaleString()}.</p>
          )}
          {children(snapshot)}
        </>
      )}
    </>
  );
}

export function DatabaseTool() {
  const state = useSnapshot();
  return (
    <Frame state={state}>
      {(s) => {
        const objects = s.object_schemas ?? [];
        return (
          <>
            <Stats
              items={[
                ["Objects", objects.length],
                ["Custom objects", objects.filter((o) => o.is_custom).length],
                ["Properties", objects.reduce((n, o) => n + (o.properties?.length ?? 0), 0)],
                ["Pipelines", s.pipelines?.length ?? 0],
                ["Owners", s.owners?.length ?? 0],
              ]}
            />
            <h2 className="t-section">Objects</h2>
            <DataTable
              label="Objects"
              columns={[
                { key: "label", label: "Object", width: "minmax(160px, 1.2fr)" },
                { key: "kind", label: "Kind", width: "110px" },
                { key: "properties", label: "Properties", width: "110px" },
                { key: "custom", label: "Custom properties", width: "150px" },
                { key: "assoc", label: "Associations", width: "120px" },
              ]}
              rows={objects.map((o) => ({
                label: o.label || o.object_type,
                kind: o.is_custom ? "Custom" : "Standard",
                properties: o.properties?.length ?? 0,
                custom: (o.properties ?? []).filter((p) => !p.hubspot_defined).length,
                assoc: o.associations?.length ?? 0,
              }))}
            />
            <h2 className="t-section">Pipelines</h2>
            <DataTable
              label="Pipelines"
              empty="No pipelines in this snapshot."
              columns={[
                { key: "label", label: "Pipeline", width: "minmax(160px, 1fr)" },
                { key: "object", label: "Object", width: "130px" },
                { key: "stages", label: "Stages", width: "minmax(220px, 2fr)" },
              ]}
              rows={(s.pipelines ?? []).map((p) => ({
                label: p.label,
                object: p.object_type,
                stages: [...(p.stages ?? [])].sort((a, b) => a.display_order - b.display_order).map((st) => st.label).join(" › "),
              }))}
            />
            <h2 className="t-section">Owners</h2>
            <DataTable
              label="Owners"
              empty="No owners in this snapshot."
              columns={[
                { key: "name", label: "Name", width: "minmax(160px, 1fr)" },
                { key: "email", label: "Email", width: "minmax(200px, 1.4fr)" },
                { key: "status", label: "Status", width: "110px" },
              ]}
              rows={(s.owners ?? []).map((o) => ({
                name: `${o.first_name ?? ""} ${o.last_name ?? ""}`.trim() || "—",
                email: o.email ?? "",
                status: o.archived ? "Archived" : "Active",
              }))}
            />
          </>
        );
      }}
    </Frame>
  );
}

export function DataDocumentationTool() {
  const state = useSnapshot();
  const [objectType, setObjectType] = useState("");
  const [query, setQuery] = useState("");
  const objects = useMemo(() => state.snapshot?.object_schemas ?? [], [state.snapshot]);
  const current = objects.find((o) => o.object_type === objectType) ?? objects[0];

  return (
    <Frame state={state}>
      {() => {
        if (!current) return <Callout tone="info" title="This snapshot has no objects" />;
        const q = query.trim().toLowerCase();
        const props = (current.properties ?? []).filter(
          (p) => !q || [p.label, p.name, p.group_name, p.description].some((v) => (v ?? "").toLowerCase().includes(q)),
        );
        const csv = () => {
          const cell = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
          const lines = [["Label", "Internal name", "Type", "Field type", "Group", "Defined by", "Description"].map(cell).join(",")];
          for (const p of current.properties ?? []) {
            lines.push([p.label, p.name, p.type, p.field_type, p.group_name, p.hubspot_defined ? "HubSpot" : "Custom", p.description].map(cell).join(","));
          }
          downloadFile(textFile(lines.join("\n"), `${current.label || current.object_type}_data_dictionary.csv`, "text/csv"));
        };
        return (
          <>
            <div className="grid-3" style={{ alignItems: "end" }}>
              <label className="field">
                <span className="field-label">Object</span>
                <select className="input" value={current.object_type} onChange={(e) => setObjectType(e.target.value)}>
                  {objects.map((o) => (
                    <option key={o.object_type} value={o.object_type}>
                      {o.label || o.object_type}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="field-label">Search properties</span>
                <input className="input" type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Label, name, group…" />
              </label>
              <button type="button" className="btn btn-secondary" style={{ width: "fit-content" }} onClick={csv}>
                Download as CSV
              </button>
            </div>
            <Stats
              items={[
                ["Properties", current.properties?.length ?? 0],
                ["Custom", (current.properties ?? []).filter((p) => !p.hubspot_defined).length],
                ["Without a description", (current.properties ?? []).filter((p) => !(p.description ?? "").trim()).length],
              ]}
            />
            <DataTable
              label={`${current.label || current.object_type} properties`}
              empty="No properties match."
              columns={[
                { key: "label", label: "Label", width: "minmax(160px, 1.2fr)" },
                { key: "name", label: "Internal name", width: "minmax(160px, 1.2fr)" },
                { key: "type", label: "Type", width: "120px" },
                { key: "group", label: "Group", width: "minmax(130px, 1fr)" },
                { key: "by", label: "Defined by", width: "110px" },
                { key: "description", label: "Description", width: "minmax(220px, 2fr)" },
              ]}
              rows={props.map((p) => ({
                label: p.label,
                name: <code>{p.name}</code>,
                type: `${p.type}${p.field_type ? ` / ${p.field_type}` : ""}`,
                group: p.group_name,
                by: p.hubspot_defined ? "HubSpot" : "Custom",
                description: p.description || "—",
              }))}
            />
          </>
        );
      }}
    </Frame>
  );
}
