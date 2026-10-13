"use client";

/**
 * Architecture Generator: answer a few questions about the project and
 * generate a HubSpot blueprint (custom objects, data dictionary,
 * associations, pipelines, naming conventions, suggested workflows). An
 * applied Deal Stage Planner replaces the default deal pipeline and adds
 * its deal properties and workflows. No HubSpot access needed.
 */

import { useId, useState } from "react";

import { useAppSession } from "@/components/AppSession";
import { TokenSelect } from "@/components/discovery/QuestionCard";
import { DataTable } from "@/components/project/DataTable";
import { ProjectHeader } from "@/components/project/ProjectHeader";
import { SaveBanner } from "@/components/project/SaveBanner";
import { Callout, ExportFooter, Icon } from "@/components/ui";
import { ApiError, blueprintMarkdown, fileStub, generateBlueprint, textFile } from "@/lib/api";
import { normalizeArchitecture, type ArchitectureInputs, type ArchitectureState, type Blueprint } from "@/lib/architecture-state";
import { useModuleState } from "@/lib/module-state";

const STANDARD_OBJECTS = ["Contact", "Company", "Deal", "Ticket", "Location", "Child", "Family"];
const CUSTOM_OBJECT_KEYWORDS = ["Membership", "Subscription", "Location", "Event"];
const INTEGRATIONS = ["MyStudio", "Sakari", "Payments Provider", "Other"];
const REGIONS = ["United States", "Canada", "United Kingdom", "European Union", "Australia", "Other"];
const CURRENCIES = ["USD", "CAD", "GBP", "EUR", "AUD", "Other"];
const HUBS = ["Marketing Hub", "Sales Hub", "Service Hub", "CMS Hub", "Operations Hub", "Commerce Hub"];

function MultiField({ label, options, value, onChange, help }: { label: string; options: string[]; value: string[]; onChange: (v: string[]) => void; help?: string }) {
  const id = useId();
  return (
    <div className="field">
      <span className="field-label" id={id}>
        {label}
      </span>
      <TokenSelect choices={options} selected={value} onChange={onChange} labelId={id} />
      {help && <span className="t-caption">{help}</span>}
    </div>
  );
}

function parseVolumes(text: string): Record<string, number> {
  const volumes: Record<string, number> = {};
  for (const line of text.split("\n")) {
    const [obj, count] = line.split(":").map((part) => part?.trim() ?? "");
    const n = Number.parseInt((count ?? "").replace(/,/g, ""), 10);
    if (obj && Number.isFinite(n)) volumes[obj] = n;
  }
  return volumes;
}

export default function ArchitecturePage() {
  const { project } = useAppSession();
  const store = useModuleState<ArchitectureState>(project?.id ?? "", "architecture", normalizeArchitecture);
  const { state, change, loaded } = store;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!project) return null;
  const client = project.client_name || project.name;
  const inputs = state.inputs;
  const set = (patch: Partial<ArchitectureInputs>) => change((s) => ({ ...s, inputs: { ...s.inputs, ...patch } }));
  const planner = state.stagePlanner;
  const pipelineChoices = ["Deal", "Ticket", ...inputs.customObjectKeywords];

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      const blueprint = await generateBlueprint({
        project_name: client || "Untitled Project",
        standard_objects: inputs.standardObjects,
        custom_object_keywords: inputs.customObjectKeywords,
        custom_object_notes: inputs.customObjectNotes,
        pipelines_required: inputs.pipelinesRequired.filter((p) => pipelineChoices.includes(p)),
        regions: inputs.regions,
        currencies: inputs.currencies,
        integrations: inputs.integrations,
        other_integration_notes: inputs.otherIntegrationNotes,
        record_volumes: parseVolumes(inputs.recordVolumes),
        hubs_in_scope: inputs.hubsInScope,
        pipeline_overrides: planner ? { Deal: planner.stages } : {},
        additional_properties: planner ? { Deal: planner.properties } : {},
        additional_workflows: planner ? planner.workflows : [],
      });
      change((s) => ({ ...s, blueprint, generatedAt: new Date().toISOString() }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't generate the blueprint.");
    }
    setBusy(false);
  };

  return (
    <>
      <ProjectHeader
        eyebrow="STEP 3 / DESIGN"
        title="Architecture Generator"
        description="Answer a few questions about the project and get a HubSpot architecture blueprint. No HubSpot access required."
      />
      <div className="page-content">
        {!loaded ? (
          <div className="skeleton" style={{ height: 320 }} aria-busy="true" />
        ) : (
          <>
            <SaveBanner store={store} />
            {planner && (
              <Callout tone="info" title={`Using the Deal Stage Planner applied on ${planner.appliedOn}`}>
                {planner.stages.length} deal pipeline stages, {planner.properties.length} deal properties and {planner.workflows.length}{" "}
                suggested workflows are included.{" "}
                <button type="button" className="btn-link" onClick={() => change((s) => ({ ...s, stagePlanner: null }))}>
                  Stop using it
                </button>
              </Callout>
            )}

            <section className="stack">
              <h2 className="t-section">Project inputs</h2>
              <div className="grid-2">
                <MultiField label="Standard objects in scope" options={STANDARD_OBJECTS} value={inputs.standardObjects} onChange={(v) => set({ standardObjects: v })} />
                <MultiField
                  label="Custom object keywords"
                  options={CUSTOM_OBJECT_KEYWORDS}
                  value={inputs.customObjectKeywords}
                  onChange={(v) => set({ customObjectKeywords: v })}
                  help="Known patterns become custom objects with their properties and associations."
                />
                <MultiField
                  label="Pipelines required"
                  options={pipelineChoices}
                  value={inputs.pipelinesRequired.filter((p) => pipelineChoices.includes(p))}
                  onChange={(v) => set({ pipelinesRequired: v })}
                  help={planner ? "The Deal pipeline comes from the Stage Planner." : "Objects that need a pipeline."}
                />
                <MultiField label="Integrations" options={INTEGRATIONS} value={inputs.integrations} onChange={(v) => set({ integrations: v })} />
                <MultiField label="Regions" options={REGIONS} value={inputs.regions} onChange={(v) => set({ regions: v })} />
                <MultiField label="Currencies in scope" options={CURRENCIES} value={inputs.currencies} onChange={(v) => set({ currencies: v })} />
                <MultiField label="Hubs in scope" options={HUBS} value={inputs.hubsInScope} onChange={(v) => set({ hubsInScope: v })} />
                <label className="field">
                  <span className="field-label">Other integration notes</span>
                  <input className="input" placeholder="Name it if you picked Other" value={inputs.otherIntegrationNotes} onChange={(e) => set({ otherIntegrationNotes: e.target.value })} />
                </label>
                <label className="field">
                  <span className="field-label">Custom object notes</span>
                  <textarea className="textarea" placeholder="Anything that isn't covered by the keywords — reviewed manually" value={inputs.customObjectNotes} onChange={(e) => set({ customObjectNotes: e.target.value })} />
                </label>
                <label className="field">
                  <span className="field-label">Estimated record volumes</span>
                  <textarea className="textarea" placeholder={"Contact: 45000\nDeal: 12000"} value={inputs.recordVolumes} onChange={(e) => set({ recordVolumes: e.target.value })} />
                  <span className="t-caption">One per line, as Object: count.</span>
                </label>
              </div>
              <div className="row">
                <button type="button" className={busy ? "btn btn-primary btn-busy" : "btn btn-primary"} disabled={busy} onClick={() => void generate()}>
                  {!busy && <Icon name="sparkles" />}
                  {busy ? "Generating…" : state.blueprint ? "Regenerate blueprint" : "Generate blueprint"}
                </button>
                {state.generatedAt && <span className="t-caption">Last generated {new Date(state.generatedAt).toLocaleString()}</span>}
              </div>
              {error && <Callout tone="error" title="The blueprint wasn't generated">{error}</Callout>}
            </section>

            {state.blueprint && <BlueprintView blueprint={state.blueprint} projectId={project.id} client={client} />}
          </>
        )}
      </div>
    </>
  );
}

function BlueprintView({ blueprint, projectId, client }: { blueprint: Blueprint; projectId: string; client: string }) {
  const dictionary = [
    ...Object.entries(blueprint.standard_object_properties ?? {}).flatMap(([obj, props]) => props.map((p) => ({ obj, p }))),
    ...(blueprint.custom_objects ?? []).flatMap((co) => (co.properties ?? []).map((p) => ({ obj: co.name, p }))),
  ];
  const stub = fileStub(client, "blueprint");
  return (
    <section className="stack" style={{ gap: 24 }}>
      <div className="heading-row">
        <h2 className="t-section">Blueprint: {blueprint.project_name}</h2>
        <span className="badge badge-success">Generated</span>
      </div>
      {(blueprint.warnings ?? []).map((w) => (
        <Callout key={w} tone="warning" title="Check this">
          {w}
        </Callout>
      ))}

      <h3 className="t-card-title">Custom objects</h3>
      <DataTable
        label="Custom objects"
        empty="None suggested."
        columns={[
          { key: "name", label: "Name", width: "180px" },
          { key: "plural", label: "Plural label", width: "180px" },
          { key: "description", label: "Description" },
        ]}
        rows={(blueprint.custom_objects ?? []).map((o) => ({ name: o.name, plural: o.plural_label, description: o.description }))}
      />

      <h3 className="t-card-title">Data dictionary ({dictionary.length})</h3>
      <DataTable
        label="Data dictionary"
        columns={[
          { key: "obj", label: "Object", width: "130px" },
          { key: "name", label: "Property", width: "200px" },
          { key: "label", label: "Label" },
          { key: "type", label: "Type", width: "120px" },
          { key: "required", label: "Required", width: "100px" },
          { key: "description", label: "Description" },
        ]}
        rows={dictionary.map(({ obj, p }) => ({
          obj,
          name: p.name,
          label: p.label,
          type: p.field_type || p.type,
          required: p.required ? "Yes" : "",
          description: p.description ?? "",
        }))}
      />

      <h3 className="t-card-title">Association model</h3>
      <DataTable
        label="Associations"
        empty="No associations."
        columns={[
          { key: "from", label: "From" },
          { key: "to", label: "To" },
          { key: "label", label: "Label" },
          { key: "cardinality", label: "Cardinality", width: "150px" },
        ]}
        rows={(blueprint.associations ?? []).map((a) => ({ from: a.from_object, to: a.to_object, label: a.label, cardinality: a.cardinality ?? "" }))}
      />

      <h3 className="t-card-title">Pipelines &amp; stages</h3>
      {(blueprint.pipelines ?? []).length === 0 && <p className="t-caption">None requested.</p>}
      {(blueprint.pipelines ?? []).map((pl) => (
        <div key={pl.name} className="stack" style={{ gap: 8 }}>
          <p className="field-label">
            {pl.name} ({pl.object_type})
          </p>
          <DataTable
            label={pl.name}
            columns={[
              { key: "order", label: "Order", width: "80px" },
              { key: "stage", label: "Stage", width: "220px" },
              { key: "probability", label: "Probability", width: "110px" },
              { key: "closed", label: "Closed", width: "90px" },
              { key: "description", label: "Description" },
            ]}
            rows={[...(pl.stages ?? [])]
              .sort((a, b) => a.order - b.order)
              .map((s) => ({
                order: s.order,
                stage: s.name,
                probability: s.probability == null ? "" : `${Math.round(s.probability * 100)}%`,
                closed: s.is_won ? "Won" : s.is_closed ? "Lost" : "",
                description: s.description ?? "",
              }))}
          />
        </div>
      ))}

      <h3 className="t-card-title">Naming conventions</h3>
      <DataTable
        label="Naming conventions"
        columns={[
          { key: "k", label: "Applies to", width: "240px" },
          { key: "v", label: "Convention" },
        ]}
        rows={Object.entries(blueprint.naming_conventions ?? {}).map(([k, v]) => ({ k: k.replace(/_/g, " "), v: String(v) }))}
      />
      <p className="flagged-line">{blueprint.base_currency_note || "No currencies specified."}</p>

      <h3 className="t-card-title">Suggested workflows ({(blueprint.workflows ?? []).length})</h3>
      <DataTable
        label="Suggested workflows"
        columns={[
          { key: "name", label: "Name" },
          { key: "trigger", label: "Trigger" },
          { key: "action", label: "Action" },
          { key: "risk", label: "Overwrite risk", width: "150px" },
        ]}
        rows={(blueprint.workflows ?? []).map((w) => ({
          name: w.name,
          trigger: w.trigger,
          action: w.action_summary,
          risk: w.overwrite_risk ? <span className="badge badge-review" title={w.risk_reason ?? ""}>Overwrite risk</span> : "",
        }))}
      />

      <ExportFooter
        library={{ projectId, documentType: "Architecture Blueprint", title: `Architecture Blueprint — ${client}` }}
        actions={[
          { label: ".md", make: async () => textFile(await blueprintMarkdown(blueprint), `${stub}.md`, "text/markdown") },
          { label: ".json", make: () => textFile(JSON.stringify(blueprint, null, 2), `${stub}.json`, "application/json") },
        ]}
      />
    </section>
  );
}
