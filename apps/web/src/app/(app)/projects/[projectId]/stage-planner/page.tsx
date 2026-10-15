"use client";

/**
 * Deal Stage Planner — the pre-call template out, a filled-out planner in.
 *
 * 1. Download the template (or save it to the library) to send the client.
 * 2. Import their filled-out copy: it's parsed by the API, shown with
 *    anything odd the parser skipped, and editable.
 * 3. A live preview shows what each target gets; Apply writes to the
 *    chosen targets only, confirming before replacing earlier work.
 * Input ingestion only — nothing is sent to HubSpot.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { useAppSession } from "@/components/AppSession";
import { AssistButton } from "@/components/AssistButton";
import { DataTable } from "@/components/project/DataTable";
import { EditableTable, type Column, type Row } from "@/components/project/EditableTable";
import { ProjectHeader } from "@/components/project/ProjectHeader";
import { SaveBanner } from "@/components/project/SaveBanner";
import { Callout, Checkbox, ExportFooter, TabPanel, Tabs } from "@/components/ui";
import {
  ApiError,
  assistStagePlanner,
  getModuleState,
  importStagePlanner,
  previewStagePlanner,
  stagePlannerTemplate,
  type PlannedStage,
  type StagePlannerImport,
} from "@/lib/api";
import { normalizeArchitecture, type ArchitectureState } from "@/lib/architecture-state";
import { projectContext } from "@/lib/assist";
import { normalizeState as normalizeDiscovery, type DiscoveryState } from "@/lib/discovery-state";
import { updateModuleState, useModuleState } from "@/lib/module-state";
import { Glyph } from "@/components/icons";

type Target = "discovery" | "build_order" | "architecture";
const TARGETS: Record<Target, string> = {
  discovery: "Discovery Call Assistant — Processes (pipeline stages + notes)",
  build_order: "Build order — pipeline, properties, automations, rep tasks",
  architecture: "Architecture Generator — deal pipeline, deal properties, workflows",
};

type PlannerState = {
  rows: Row[];
  warnings: string[];
  source: string;
  applied: { targets: Target[]; appliedOn: string } | null;
};

const COLUMNS: Column[] = [
  { key: "name", label: "Stage", width: "200px" },
  { key: "forecast", label: "Forecast %", kind: "number", width: "110px" },
  { key: "entry_criteria", label: "Entry criteria", kind: "textarea", width: "220px" },
  { key: "exit_criteria", label: "Exit criteria", kind: "textarea", width: "220px" },
  { key: "actions", label: "Desired actions", kind: "textarea", width: "240px" },
  { key: "automations", label: "Automations", kind: "textarea", width: "240px" },
  { key: "fields", label: "Required fields (comma-separated)", kind: "textarea", width: "240px" },
];

const NOTES_START = "[Deal Stage Planner]";
const NOTES_END = "[/Deal Stage Planner]";

function normalize(raw: unknown): PlannerState {
  const s = (typeof raw === "object" && raw ? raw : {}) as Partial<PlannerState>;
  return { rows: s.rows ?? [], warnings: s.warnings ?? [], source: s.source ?? "", applied: s.applied ?? null };
}

function toRows(stages: PlannedStage[]): Row[] {
  return stages.map((s) => ({
    name: s.name,
    forecast: s.forecast == null ? "" : String(s.forecast),
    entry_criteria: s.entry_criteria ?? "",
    exit_criteria: s.exit_criteria ?? "",
    actions: s.actions ?? "",
    automations: s.automations ?? "",
    fields: (s.fields ?? []).join(", "),
  }));
}

function toStages(rows: Row[]): PlannedStage[] {
  return rows
    .filter((r) => String(r.name ?? "").trim())
    .map((r) => {
      const forecast = Number.parseFloat(String(r.forecast ?? ""));
      return {
        name: String(r.name).trim(),
        forecast: Number.isFinite(forecast) ? forecast : null,
        entry_criteria: String(r.entry_criteria ?? "").trim(),
        exit_criteria: String(r.exit_criteria ?? "").trim(),
        actions: String(r.actions ?? "").trim(),
        automations: String(r.automations ?? "").trim(),
        fields: String(r.fields ?? "")
          .split(",")
          .map((f) => f.trim())
          .filter(Boolean),
      };
    });
}

/** Put the planner block into a notes field, replacing an earlier one. */
function mergeNotes(existing: string, block: string): string {
  const start = existing.indexOf(NOTES_START);
  const end = existing.indexOf(NOTES_END);
  if (start !== -1 && end > start) return existing.slice(0, start) + block + existing.slice(end + NOTES_END.length);
  return existing.trim() ? `${existing.trimEnd()}\n\n${block}` : block;
}

export default function StagePlannerPage() {
  const { project } = useAppSession();
  const projectId = project?.id ?? "";
  const store = useModuleState<PlannerState>(projectId, "stage_planner", normalize);
  const { state, change, loaded } = store;
  const [importError, setImportError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [preview, setPreview] = useState<StagePlannerImport | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [tab, setTab] = useState<"pipeline" | "properties" | "workflows" | "build" | "discovery">("pipeline");
  const [targets, setTargets] = useState<Target[]>(["discovery", "build_order", "architecture"]);
  const [overwrites, setOverwrites] = useState<string[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const stages = toStages(state.rows);
  const stagesKey = JSON.stringify(stages);

  // Re-map the (edited) stages, debounced.
  useEffect(() => {
    if (!loaded || !stages.length) {
      setPreview(null);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      previewStagePlanner(stages, controller.signal)
        .then((p) => {
          setPreview(p);
          setPreviewError(null);
        })
        .catch((e: unknown) => {
          if ((e as Error).name !== "AbortError") setPreviewError(e instanceof ApiError ? e.message : "Couldn't map the stages.");
        });
    }, 400);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
    // stagesKey captures the stages' content.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, stagesKey]);

  // What applying would replace, for the chosen targets.
  const checkOverwrites = useCallback(async () => {
    if (!projectId || !preview) return;
    const found: string[] = [];
    const discovery = normalizeDiscovery((await getModuleState(projectId, "discovery")).data, "");
    const answer = discovery.sections.Processes?.answers.sales_pipeline_stages?.notes?.trim() ?? "";
    if (targets.includes("discovery") && answer && answer !== preview.discovery_answer) {
      found.push(`the Discovery "Sales pipeline stages" answer ("${answer.slice(0, 60)}${answer.length > 60 ? "…" : ""}")`);
    }
    if (targets.includes("build_order") && discovery.stagePlanner) found.push("the planner already applied to the build order");
    const architecture = normalizeArchitecture((await getModuleState(projectId, "architecture")).data);
    if (targets.includes("architecture") && architecture.stagePlanner) {
      found.push(`the planner applied to the Architecture Generator on ${architecture.stagePlanner.appliedOn}`);
    }
    setOverwrites(found);
    setConfirmed(false);
  }, [projectId, preview, targets]);
  useEffect(() => {
    void checkOverwrites();
  }, [checkOverwrites]);

  if (!project) return null;

  /** Fill the planner from the discovery call: a whole pipeline when empty, otherwise only blank cells. */
  const fillFromDiscovery = async () => {
    const result = await assistStagePlanner(await projectContext(project.id, project.client_name || project.name), stages);
    if (!result.filled && stages.length) return "Nothing to fill: every cell the discovery call covers is already filled in.";
    const byName = new Map(result.stages.map((s) => [s.name.trim().toLowerCase(), s]));
    change((s) => ({
      ...s,
      rows: stages.length
        ? s.rows.map((r) => {
            const match = byName.get(String(r.name ?? "").trim().toLowerCase());
            return match ? toRows([match])[0]! : r;
          })
        : toRows(result.stages),
      source: s.source || "Discovery call",
    }));
    return stages.length
      ? `Filled ${result.filled} empty cell${result.filled === 1 ? "" : "s"} from the discovery call`
      : `Drafted ${result.stages.length} stages from the discovery call. Review them below.`;
  };

  const apply = async () => {
    if (!preview) return;
    setApplying(true);
    setApplied(null);
    setImportError(null);
    const today = new Date().toISOString().slice(0, 10);
    try {
      if (targets.includes("discovery") || targets.includes("build_order")) {
        await updateModuleState<DiscoveryState>(project.id, "discovery", (current) => {
          const d = normalizeDiscovery(current, project.client_name || project.name);
          const processes = d.sections.Processes ?? { answers: {}, notes: "", edge_cases: "" };
          return {
            ...d,
            stagePlanner: targets.includes("build_order") ? stages : d.stagePlanner,
            sections: targets.includes("discovery")
              ? {
                  ...d.sections,
                  Processes: {
                    ...processes,
                    notes: mergeNotes(processes.notes, preview.discovery_notes),
                    answers: {
                      ...processes.answers,
                      sales_pipeline_stages: { selected: [], other: "", notes: preview.discovery_answer, flagged: false },
                    },
                  },
                }
              : d.sections,
          };
        });
      }
      if (targets.includes("architecture")) {
        await updateModuleState<ArchitectureState>(project.id, "architecture", (current) => {
          const a = normalizeArchitecture(current);
          return {
            ...a,
            stagePlanner: {
              appliedOn: today,
              stages: preview.pipeline.stages ?? [],
              properties: preview.properties.flatMap((p) => (p.definition ? [p.definition] : [])),
              workflows: preview.workflows,
            },
          };
        });
      }
      change((s) => ({ ...s, applied: { targets, appliedOn: today } }));
      setApplied(`Applied ${stages.length} stages to: ${targets.map((t) => TARGETS[t].split(" — ")[0]).join(", ")}. Nothing was sent to HubSpot.`);
      await checkOverwrites();
    } catch (e) {
      setImportError(e instanceof ApiError ? e.message : "Couldn't apply the planner.");
    }
    setApplying(false);
  };

  return (
    <>
      <ProjectHeader
        eyebrow="STEP 1 / DISCOVER"
        title="Deal Stage Planner"
      />
      <div className="page-content">
        <SaveBanner store={store} />

        <section className="stack">
          <h2 className="t-section">1 · Send the pre-call template</h2>
          <ExportFooter
            divider={false}
            actions={[{ label: ".xlsx", make: stagePlannerTemplate }]}
            library={{ projectId: project.id, documentType: "Pre-call Template — HubSpot Deal Stage Planner", title: "HubSpot Deal Stage Planner" }}
          />
        </section>

        <section className="stack">
          <h2 className="t-section">2 · Import a filled-out planner</h2>
          <div className="row">
            <button type="button" className="btn btn-secondary" disabled={importing} onClick={() => fileInput.current?.click()}>
              {importing ? "Reading…" : <><Glyph name="upload" /> Upload the client&apos;s planner (.xlsx)</>}
            </button>
            {state.source && <span className="t-caption">Last imported: {state.source}</span>}
          </div>
          <input
            ref={fileInput}
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            hidden
            onChange={async (e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (!file) return;
              setImporting(true);
              setImportError(null);
              try {
                const parsed = await importStagePlanner(file);
                change((s) => ({ ...s, rows: toRows(parsed.stages), warnings: parsed.warnings, source: file.name }));
              } catch (err) {
                setImportError(err instanceof ApiError ? err.message : "Couldn't read that file.");
              }
              setImporting(false);
            }}
          />
          {importError && <Callout tone="error" title="That didn't work">{importError}</Callout>}
          <AssistButton label={stages.length ? "Fill empty cells from the discovery call" : "Fill from the discovery call"} run={fillFromDiscovery} />
          {state.warnings.length > 0 && (
            <Callout tone="warning" title={`${state.warnings.length} thing${state.warnings.length === 1 ? "" : "s"} to check`}>
              <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                {state.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </Callout>
          )}
        </section>

        {(state.rows.length > 0 || state.source) && (
          <>
            <section className="stack">
              <h2 className="t-section">Review and edit the stages</h2>
              <EditableTable
                label="Stages"
                columns={COLUMNS}
                rows={state.rows}
                addLabel="+ Add stage"
                onChange={(rows) => change((s) => ({ ...s, rows }))}
              />
            </section>

            <section className="stack">
              <h2 className="t-section">What it will populate</h2>
              {previewError && <Callout tone="error" title="Couldn't map the stages">{previewError}</Callout>}
              {preview && (
                <>
                  <Tabs
                    label="Preview"
                    layoutId="planner-preview"
                    variant="secondary"
                    tabs={[
                      { id: "pipeline", label: `Pipeline (${preview.pipeline.stages?.length ?? 0})` },
                      { id: "properties", label: `Deal properties (${preview.properties.length})` },
                      { id: "workflows", label: `Workflows (${preview.workflows.length})` },
                      { id: "build", label: `Build-order items (${preview.build_items.length})` },
                      { id: "discovery", label: "Discovery" },
                    ]}
                    active={tab}
                    onChange={setTab}
                  />
                  <TabPanel panelKey={tab} id="planner-preview">
                    {tab === "pipeline" && (
                      <DataTable
                        label="Pipeline"
                        columns={[
                          { key: "stage", label: "Stage", width: "220px" },
                          { key: "probability", label: "Probability", width: "110px" },
                          { key: "closed", label: "Closed", width: "90px" },
                          { key: "description", label: "Description" },
                        ]}
                        rows={(preview.pipeline.stages ?? []).map((s) => ({
                          stage: s.name,
                          probability: s.probability == null ? "" : `${Math.round(s.probability * 100)}%`,
                          closed: s.is_won ? "Won" : s.is_closed ? "Lost" : "",
                          description: s.description ?? "",
                        }))}
                      />
                    )}
                    {tab === "properties" && (
                      <DataTable
                        label="Deal properties"
                        columns={[
                          { key: "label", label: "Label" },
                          { key: "name", label: "Internal name" },
                          { key: "type", label: "Type", width: "140px" },
                          { key: "stages", label: "Required at" },
                        ]}
                        rows={preview.properties.map((p) => ({
                          label: p.label,
                          name: p.existing || p.definition?.name || "",
                          type: p.existing ? "HubSpot default" : (p.definition?.field_type ?? ""),
                          stages: p.stages.join(", "),
                        }))}
                      />
                    )}
                    {tab === "workflows" && (
                      <DataTable
                        label="Workflows"
                        columns={[
                          { key: "name", label: "Workflow" },
                          { key: "trigger", label: "Trigger" },
                          { key: "risk", label: "Overwrite risk", width: "130px" },
                        ]}
                        rows={preview.workflows.map((w) => ({ name: w.name, trigger: w.trigger, risk: w.overwrite_risk ? "YES" : "" }))}
                      />
                    )}
                    {tab === "build" && (
                      <DataTable
                        label="Build-order items"
                        columns={[
                          { key: "section", label: "Section", width: "150px" },
                          { key: "name", label: "Item" },
                          { key: "source", label: "Source" },
                        ]}
                        rows={preview.build_items.map((i) => ({ section: i.section, name: i.name, source: i.source }))}
                      />
                    )}
                    {tab === "discovery" && (
                      <div className="stack">
                        <p className="field-label">Processes › Sales pipeline stages</p>
                        <pre className="code-block">{preview.discovery_answer || "—"}</pre>
                        <p className="field-label">Processes › Other notes (added, or replaces an earlier planner block)</p>
                        <pre className="code-block">{preview.discovery_notes}</pre>
                      </div>
                    )}
                  </TabPanel>
                </>
              )}
            </section>

            <section className="stack">
              <h2 className="t-section">3 · Apply</h2>
              {(Object.keys(TARGETS) as Target[]).map((t) => (
                <Checkbox
                  key={t}
                  checked={targets.includes(t)}
                  onChange={(on) => setTargets((all) => (on ? [...all, t] : all.filter((x) => x !== t)))}
                >
                  {TARGETS[t]}
                </Checkbox>
              ))}
              {overwrites.length > 0 && (
                <Callout tone="warning" title="Applying will replace earlier work">
                  {overwrites.join("; ")}.
                  <div style={{ marginTop: 8 }}>
                    <Checkbox checked={confirmed} onChange={setConfirmed}>
                      Replace what&apos;s there
                    </Checkbox>
                  </div>
                </Callout>
              )}
              <div className="row">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={applying || !targets.length || !stages.length || !preview || (overwrites.length > 0 && !confirmed)}
                  onClick={() => void apply()}
                >
                  {applying ? "Applying…" : "Apply the planner"}
                </button>
                {state.applied && !applied && (
                  <span className="t-caption">
                    Last applied {state.applied.appliedOn} to {state.applied.targets.map((t) => TARGETS[t].split(" — ")[0]).join(", ")}.
                  </span>
                )}
              </div>
              {applied && <Callout tone="success" title="Applied">{applied}</Callout>}
            </section>
          </>
        )}
      </div>
    </>
  );
}
