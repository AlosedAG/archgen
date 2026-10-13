/**
 * The Architecture Generator's saved state for a project: its inputs, an
 * applied Deal Stage Planner (pipeline, deal properties, workflows), and
 * the last generated blueprint.
 */

import type { components } from "./api-types";

type Schemas = components["schemas"];
export type BlueprintInput = Schemas["BlueprintInput"];
export type Blueprint = Schemas["Blueprint"];
export type StageDef = Schemas["StageDef"];
export type PropertyDef = Schemas["PropertyDef"];
export type WorkflowSuggestion = Schemas["WorkflowSuggestion"];

export type AppliedPlanner = {
  appliedOn: string;
  stages: StageDef[];
  properties: PropertyDef[];
  workflows: WorkflowSuggestion[];
};

export type ArchitectureInputs = {
  standardObjects: string[];
  customObjectKeywords: string[];
  customObjectNotes: string;
  pipelinesRequired: string[];
  regions: string[];
  currencies: string[];
  integrations: string[];
  otherIntegrationNotes: string;
  recordVolumes: string;
  hubsInScope: string[];
};

export type ArchitectureState = {
  inputs: ArchitectureInputs;
  stagePlanner: AppliedPlanner | null;
  blueprint: Blueprint | null;
  generatedAt: string | null;
};

export const DEFAULT_INPUTS: ArchitectureInputs = {
  standardObjects: ["Contact", "Company", "Deal"],
  customObjectKeywords: [],
  customObjectNotes: "",
  pipelinesRequired: [],
  regions: [],
  currencies: ["USD"],
  integrations: [],
  otherIntegrationNotes: "",
  recordVolumes: "",
  hubsInScope: [],
};

export function normalizeArchitecture(raw: unknown): ArchitectureState {
  const stored = (typeof raw === "object" && raw ? raw : {}) as Partial<ArchitectureState>;
  return {
    inputs: { ...DEFAULT_INPUTS, ...(stored.inputs ?? {}) },
    stagePlanner: stored.stagePlanner ?? null,
    blueprint: stored.blueprint ?? null,
    generatedAt: stored.generatedAt ?? null,
  };
}
