"use client";

/**
 * Architecture Diagram: an editable map of the objects in scope and how
 * they connect, seeded from the Architecture Generator blueprint or the
 * live portal snapshot (with audit findings highlighted). Both sources are
 * heuristic, so the Objects / Connections tables are editable and saved to
 * the project; the preview and every export are drawn from them. Makes no
 * HubSpot calls of its own.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAppSession } from "@/components/AppSession";
import { EditableTable, type Column, type Row } from "@/components/project/EditableTable";
import { ProjectHeader } from "@/components/project/ProjectHeader";
import { SaveBanner } from "@/components/project/SaveBanner";
import { Stats } from "@/components/project/Stats";
import { Callout, Checkbox, ExportFooter } from "@/components/ui";
import {
  ApiError,
  diagramFromBlueprint,
  diagramFromSnapshot,
  exportSections,
  fileStub,
  getModuleState,
  renderDiagram,
  textFile,
  type DiagramBody,
  type Project,
} from "@/lib/api";
import { normalizeArchitecture } from "@/lib/architecture-state";
import { useModuleState, type ModuleStore } from "@/lib/module-state";
import { normalizePortal, toggle, type PortalState } from "@/lib/portal-state";

type Source = "snapshot" | "blueprint";

type DiagramState = {
  source: Source | null;
  includeEngagements: boolean;
  nodes: Row[];
  edges: Row[];
  showLabels: boolean;
  focus: string[];
  seededAt: string | null;
};

const normalizeDiagram = (raw: unknown): DiagramState => {
  const s = (typeof raw === "object" && raw ? raw : {}) as Partial<DiagramState>;
  return {
    source: s.source ?? null,
    includeEngagements: s.includeEngagements ?? false,
    nodes: s.nodes ?? [],
    edges: s.edges ?? [],
    showLabels: s.showLabels ?? true,
    focus: s.focus ?? [],
    seededAt: s.seededAt ?? null,
  };
};

const NODE_COLUMNS: Column[] = [
  { key: "name", label: "Name", width: "minmax(150px, 1.4fr)" },
  { key: "kind", label: "Kind", kind: "select", options: ["Standard", "Custom", "Activity"], width: "130px" },
  { key: "property_count", label: "Properties", kind: "number", width: "100px" },
  { key: "risk", label: "Risk", kind: "select", options: ["", "Low", "Medium", "High"], width: "110px" },
  { key: "finding_count", label: "Findings", kind: "number", width: "90px" },
  { key: "notes", label: "Notes", width: "minmax(160px, 1.6fr)" },
];
const EDGE_COLUMNS: Column[] = [
  { key: "source", label: "From", width: "minmax(130px, 1fr)" },
  { key: "target", label: "To", width: "minmax(130px, 1fr)" },
  { key: "label", label: "Label", width: "minmax(130px, 1fr)" },
  { key: "cardinality", label: "Cardinality", kind: "select", options: ["many-to-many", "one-to-one", "one-to-many", "many-to-one"], width: "150px" },
];

const text = (v: unknown) => String(v ?? "").trim();
const num = (v: unknown) => {
  const n = Number.parseInt(String(v ?? ""), 10);
  return Number.isFinite(n) && n > 0 ? n : 0;
};

/** The edited tables (narrowed to the focus, if any) as the API's Diagram. */
function toDiagram(state: DiagramState): DiagramBody {
  const focus = new Set(state.focus);
  const nodes = state.nodes
    .filter((r) => text(r.name))
    .map((r) => ({
      name: text(r.name),
      kind: (text(r.kind) || "Standard") as "Standard" | "Custom" | "Activity",
      property_count: num(r.property_count),
      risk: text(r.risk) as "" | "Low" | "Medium" | "High",
      finding_count: num(r.finding_count),
      notes: text(r.notes),
    }))
    .filter((n) => !focus.size || focus.has(n.name));
  const edges = state.edges
    .filter((r) => text(r.source) && text(r.target))
    .map((r) => ({ source: text(r.source), target: text(r.target), label: text(r.label), cardinality: text(r.cardinality) || "many-to-many" }))
    .filter((e) => !focus.size || (focus.has(e.source) && focus.has(e.target)));
  return { nodes, edges };
}

const asRows = (diagram: DiagramBody) => ({
  nodes: diagram.nodes.map((n) => ({ ...n, property_count: String(n.property_count ?? 0), finding_count: String(n.finding_count ?? 0) }) as Row),
  edges: diagram.edges.map((e) => ({ ...e }) as Row),
});

function Preview({ diagram, showLabels, stub }: { diagram: DiagramBody; showLabels: boolean; stub: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const key = JSON.stringify([diagram, showLabels]);

  useEffect(() => {
    if (!diagram.nodes.length) return;
    let live = true;
    let objectUrl: string | null = null;
    const timer = window.setTimeout(() => {
      renderDiagram({ diagram, show_labels: showLabels }, "png", stub)
        .then((file) => {
          if (!live) return;
          objectUrl = URL.createObjectURL(file.blob);
          setUrl(objectUrl);
          setError(null);
        })
        .catch((e: unknown) => live && setError(e instanceof ApiError ? e.message : "Couldn't draw the diagram."));
    }, 500);
    return () => {
      live = false;
      window.clearTimeout(timer);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [key]);

  if (!diagram.nodes.length) return <Callout tone="warning" title="No objects to diagram">Add a row to the Objects table, or clear the focus filter.</Callout>;
  if (error) return <Callout tone="error" title="Couldn't draw the diagram">{error}</Callout>;
  return url ? (
    <img className="diagram-preview" src={url} alt="Architecture diagram of the objects and connections below" />
  ) : (
    <div className="skeleton" style={{ height: 320 }} aria-busy="true" />
  );
}

function Diagram({ project, store }: { project: Project; store: ModuleStore<DiagramState> }) {
  const { state, update } = store;
  const [portal, setPortal] = useState<PortalState | null>(null);
  const [hasBlueprint, setHasBlueprint] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([getModuleState(project.id, "portal"), getModuleState(project.id, "architecture")]).then(([p, a]) => {
      setPortal(normalizePortal(p.data));
      setHasBlueprint(Boolean(normalizeArchitecture(a.data).blueprint));
    });
  }, [project.id]);

  const sources: Source[] = [...(portal?.snapshot ? (["snapshot"] as const) : []), ...(hasBlueprint ? (["blueprint"] as const) : [])];

  const seed = async (source: Source, includeEngagements: boolean) => {
    setBusy(true);
    setError(null);
    try {
      let diagram: DiagramBody;
      if (source === "snapshot") {
        const p = portal ?? normalizePortal((await getModuleState(project.id, "portal")).data);
        if (!p.snapshot) throw new ApiError("Pull a portal snapshot first.");
        diagram = await diagramFromSnapshot({ snapshot: p.snapshot, findings: p.findings, include_engagements: includeEngagements });
      } else {
        const blueprint = normalizeArchitecture((await getModuleState(project.id, "architecture")).data).blueprint;
        if (!blueprint) throw new ApiError("Generate a blueprint first.");
        diagram = await diagramFromBlueprint({ blueprint });
      }
      update({ source, includeEngagements, ...asRows(diagram), focus: [], seededAt: new Date().toISOString() });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't build the diagram.");
    }
    setBusy(false);
  };

  if (!portal) return <div className="skeleton" style={{ height: 120 }} aria-busy="true" />;

  if (!sources.length && !state.nodes.length) {
    return (
      <Callout tone="info" title="Nothing to diagram yet">
        Generate a blueprint in the{" "}
        <Link className="btn-link" href={`/projects/${project.id}/architecture`}>
          Architecture Generator
        </Link>
        , or pull a live portal snapshot in the{" "}
        <Link className="btn-link" href={`/projects/${project.id}/portal-audit`}>
          Portal Auditor
        </Link>
        .
      </Callout>
    );
  }

  const diagram = toDiagram(state);
  const names = state.nodes.map((r) => text(r.name)).filter(Boolean);
  const drawn = new Set(diagram.nodes.map((n) => n.name));
  const dangling = state.edges.filter((r) => text(r.source) && text(r.target) && !(drawn.has(text(r.source)) && drawn.has(text(r.target))));
  const clientName = project.client_name || project.name;
  const stub = fileStub(clientName, "architecture_diagram");
  const render = (format: "png" | "dot" | "drawio") => renderDiagram({ diagram, show_labels: state.showLabels }, format, stub);

  return (
    <>
      <section className="stack" style={{ gap: 12 }}>
        <h2 className="t-section">Source</h2>
        <div className="row">
          {sources.map((s) => (
            <button
              key={s}
              type="button"
              className={state.source === s && state.nodes.length ? "btn btn-primary" : "btn btn-secondary"}
              disabled={busy}
              onClick={() => void seed(s, state.includeEngagements)}
            >
              {s === "snapshot" ? "Live portal snapshot" : "Architecture blueprint"}
            </button>
          ))}
          {state.seededAt && (
            <span className="t-caption">
              Built from the {state.source === "snapshot" ? "portal snapshot" : "blueprint"} {new Date(state.seededAt).toLocaleString()} — choosing a source again resets your edits.
            </span>
          )}
        </div>
        {sources.includes("snapshot") && (
          <Checkbox checked={state.includeEngagements} onChange={(checked) => (state.source === "snapshot" ? void seed("snapshot", checked) : update({ includeEngagements: checked }))}>
            Include HubSpot activity objects (Task, Note, Email, Call, Meeting…)
          </Checkbox>
        )}
        {state.source === "snapshot" && !portal.findings && (
          <span className="t-caption">No audit has been run — run one in the Portal Auditor to highlight findings on the diagram.</span>
        )}
        {error && <Callout tone="error" title="Couldn't build the diagram">{error}</Callout>}
      </section>

      {state.nodes.length > 0 && (
        <>
          <section className="stack" style={{ gap: 12 }}>
            <h2 className="t-section">Diagram</h2>
            <div className="filter-row" role="group" aria-label="Focus the diagram on">
              <span className="field-label">Focus on</span>
              {names.map((n) => (
                <button key={n} type="button" className="filter-chip" aria-pressed={state.focus.includes(n)} onClick={() => update({ focus: toggle(state.focus, n) })}>
                  {n}
                </button>
              ))}
              {state.focus.length > 0 && (
                <button type="button" className="btn-link" onClick={() => update({ focus: [] })}>
                  Show everything
                </button>
              )}
            </div>
            <Checkbox checked={state.showLabels} onChange={(checked) => update({ showLabels: checked })}>
            Show connection labels
          </Checkbox>
            <Preview diagram={diagram} showLabels={state.showLabels} stub={stub} />
            {dangling.length > 0 && (
              <Callout tone="warning" title="Some connections aren't drawn">
                They reference an object that isn&apos;t in the table (or is outside the focus):{" "}
                {dangling.map((r) => `${text(r.source)} → ${text(r.target)}`).join("; ")}
              </Callout>
            )}
            <p className="t-caption">
              Filled purple = custom object · white = standard · dashed grey = activity object · border color = worst finding (red High, orange Medium, yellow Low).
            </p>
            <Stats
              items={[
                ["Objects", diagram.nodes.length],
                ["Connections", diagram.edges.length],
                ["Custom objects", diagram.nodes.filter((n) => n.kind === "Custom").length],
                ["Objects with findings", diagram.nodes.filter((n) => n.risk).length],
              ]}
            />
          </section>

          <section className="stack" style={{ gap: 12 }}>
            <h2 className="t-section">Objects</h2>
            <span className="t-caption">Rename, change kind or risk, add or remove rows — the diagram follows.</span>
            <EditableTable columns={NODE_COLUMNS} rows={state.nodes} onChange={(nodes) => update({ nodes })} label="Diagram objects" addLabel="+ Add object" />
            <h2 className="t-section">Connections</h2>
            <span className="t-caption">From / To must match an object name above to be drawn.</span>
            <EditableTable columns={EDGE_COLUMNS} rows={state.edges} onChange={(edges) => update({ edges })} label="Diagram connections" addLabel="+ Add connection" />
          </section>

          <p className="t-caption">
            The .drawio file opens in diagrams.net (free, no login) for drag-and-drop editing. The PNG uses the same layout, ready for a slide or doc.
          </p>
          <ExportFooter
            library={{ projectId: project.id, documentType: "Architecture Diagram" }}
            actions={[
              { label: ".drawio", make: () => render("drawio") },
              { label: ".png", make: () => render("png") },
              { label: ".gv", make: () => render("dot") },
              {
                label: ".xlsx",
                make: () =>
                  exportSections(
                    "Architecture diagram",
                    clientName,
                    [
                      { title: "Objects", rows: diagram.nodes.map((n) => Object.fromEntries(Object.entries(n).map(([k, v]) => [k, String(v ?? "")]))) },
                      { title: "Connections", rows: diagram.edges.map((e) => Object.fromEntries(Object.entries(e).map(([k, v]) => [k, String(v ?? "")]))) },
                    ],
                    "xlsx",
                    stub,
                  ),
              },
              { label: ".json", make: () => textFile(JSON.stringify(diagram, null, 2), `${stub}.json`, "application/json") },
            ]}
          />
        </>
      )}
    </>
  );
}

export default function DiagramPage() {
  const { project } = useAppSession();
  const store = useModuleState<DiagramState>(project?.id ?? "", "diagram", normalizeDiagram);
  if (!project) return null;
  return (
    <>
      <ProjectHeader
        eyebrow="STEP 3 / DESIGN"
        title="Architecture Diagram"
        description="A visual, editable map of the objects in scope and how they connect — from the Architecture Generator blueprint or the live portal snapshot, with audit findings highlighted."
      />
      <div className="page-content">
        {!store.loaded ? (
          <div className="skeleton" style={{ height: 120 }} aria-busy="true" />
        ) : (
          <>
            <SaveBanner store={store} />
            <Diagram project={project} store={store} />
          </>
        )}
      </div>
    </>
  );
}
