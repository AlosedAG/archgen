/**
 * The project context the "Fill from earlier steps" / "Suggest" buttons
 * send: the discovery call notes and business analysis, the Requirements
 * Document and Joint Evaluation Plan (as their export sections), and an
 * applied Deal Stage Planner — whatever the project has so far.
 */

import { normalizeDocument } from "@/components/project/TableDocument";

import { getModuleState, type AssistContext } from "./api";
import { normalizeState, toDiscoveryNotes, hasAnyNotes } from "./discovery-state";
import { JOINT_EVALUATION_PLAN, REQUIREMENTS_DOCUMENT } from "./documents";

const saved = async (projectId: string, module: string): Promise<unknown> => {
  const state = await getModuleState(projectId, module);
  return state.data && Object.keys(state.data).length ? state.data : null;
};

export async function projectContext(projectId: string, clientName: string): Promise<AssistContext> {
  const [discoveryRaw, ...docs] = await Promise.all([
    saved(projectId, "discovery"),
    ...[REQUIREMENTS_DOCUMENT, JOINT_EVALUATION_PLAN].map((def) => saved(projectId, def.module)),
  ]);
  const discovery = normalizeState(discoveryRaw, clientName);
  const documents: AssistContext["documents"] = {};
  [REQUIREMENTS_DOCUMENT, JOINT_EVALUATION_PLAN].forEach((def, i) => {
    if (!docs[i]) return;
    const sections = def.exportSections(normalizeDocument(def, docs[i]), clientName).filter((s) => (s.rows ?? []).length);
    if (sections.length) documents[def.title] = Object.fromEntries(sections.map((s) => [s.title, s.rows ?? []]));
  });
  const overview = discovery.companyOverview?.data;
  if (overview) {
    const rows = Object.entries(overview)
      .map(([field, value]) => ({ Field: field.replace(/_/g, " "), Value: Array.isArray(value) ? value.join("; ") : String(value ?? "") }))
      .filter((r) => r.Value.trim());
    if (rows.length) documents["Company overview (from the website)"] = { Overview: rows };
  }
  return {
    discovery: hasAnyNotes(discovery) ? toDiscoveryNotes(discovery) : null,
    business_analysis: discovery.baOutput ?? "",
    documents,
    stage_planner: discovery.stagePlanner ?? [],
  };
}
