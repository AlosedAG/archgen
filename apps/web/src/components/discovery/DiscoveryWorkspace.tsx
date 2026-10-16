"use client";

/**
 * The Discovery Call Assistant for one project: loads the question bank
 * and settings, keeps the call's notes (saved to the project), and
 * re-evaluates them (debounced) so follow-ups, required tasks, the
 * checklist and the build order update as the specialist types. All rule
 * logic stays in the API.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError, applyIndustryDiscoveryTemplate, evaluateNotes, getDiscoveryConfig, type DiscoveryConfig, type Evaluation, type Project } from "@/lib/api";
import { getAnswer, isAnswered, normalizeSections, toDiscoveryNotes, useDiscoveryState } from "@/lib/discovery-state";

import { useAppSession } from "../AppSession";
import { PageHeader } from "../PageHeader";
import { SaveBanner } from "../project/SaveBanner";
import { IndustryTemplatePicker } from "../IndustryTemplatePicker";
import { Callout, TabPanel, Tabs } from "../ui";
import { BuildOrderTab } from "./BuildOrderTab";
import { BusinessAnalysisTab } from "./BusinessAnalysisTab";
import { ChecklistTab } from "./ChecklistTab";
import { CompanyOverviewTab } from "./CompanyOverviewTab";
import { ExplainerTab } from "./ExplainerTab";
import { Glyph } from "@/components/icons";

type TabId = "analysis" | "explainer" | "checklist" | "build" | "overview";

/** A safe link for the typed website ("acme.com" → "https://acme.com"), or "" if it isn't a web address. */
function websiteHref(raw: string): string {
  const value = raw.trim();
  if (!value) return "";
  try {
    const url = new URL(/^https?:\/\//i.test(value) ? value : `https://${value}`);
    return url.hostname.includes(".") ? url.href : "";
  } catch {
    return "";
  }
}
const EVALUATE_DEBOUNCE_MS = 250;

export function DiscoveryWorkspace({ project }: { project: Project }) {
  const { me } = useAppSession();
  const store = useDiscoveryState(project.id, project.client_name || project.name);
  const { state, loaded, update } = store;
  const [config, setConfig] = useState<DiscoveryConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [evaluateError, setEvaluateError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("analysis");

  const loadConfig = useCallback(() => {
    setConfigError(null);
    getDiscoveryConfig()
      .then(setConfig)
      .catch((e: unknown) => setConfigError(e instanceof ApiError ? e.message : "Couldn't load the discovery questions."));
  }, []);
  useEffect(loadConfig, [loadConfig]);

  // Re-evaluate whenever anything the rules can see changes. The previous
  // result stays on screen until the new one lands, so nothing flickers.
  const { sections, clientName, businessType, projectType, buildDone, stagePlanner } = state;
  useEffect(() => {
    if (!loaded || !config) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      evaluateNotes(
        {
          client_name: clientName,
          business_type: businessType,
          client_website: "", // not used by the rules
          sections,
          project_type: projectType,
          done_build_items: buildDone,
          stage_planner: stagePlanner,
        },
        controller.signal,
      )
        .then((result) => {
          setEvaluation(result);
          setEvaluateError(null);
        })
        .catch((e: unknown) => {
          if ((e as Error).name === "AbortError") return;
          setEvaluateError(e instanceof ApiError ? e.message : "Couldn't update follow-ups and tasks.");
        });
    }, EVALUATE_DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [loaded, config, sections, clientName, businessType, projectType, buildDone, stagePlanner]);

  const TAB_IDS: TabId[] = ["analysis", "explainer", "checklist", "build", "overview"];
  const bank = config?.question_bank.sections ?? [];
  const totalQuestions = bank.reduce((n, s) => n + s.questions.length, 0);
  const answeredQuestions = bank.reduce(
    (n, s) => n + s.questions.filter((q) => isAnswered(getAnswer(state, s.name, q.id))).length,
    0,
  );
  const header = (
    <PageHeader
      eyebrow="STEP 1 / DISCOVER"
      breadcrumb={`${clientName.trim() || project.client_name || project.name}  /  ${me.workspace_name}`}
      title="Discovery Call Assistant"
      meta={
        <>
          <span className="status-chip status-chip-success">
            Step {TAB_IDS.indexOf(tab) + 1} of {TAB_IDS.length}
          </span>
          {totalQuestions > 0 && (
            <span className="status-chip">
              {answeredQuestions} of {totalQuestions} answered
            </span>
          )}
        </>
      }
    />
  );

  if (configError || (store.status === "error" && !loaded)) {
    return (
      <>
        {header}
        <div className="page-content">
          <Callout tone="error" title="Can't load the discovery form">
            {configError ?? store.error}
          </Callout>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ width: "fit-content" }}
            onClick={() => (configError ? loadConfig() : void store.reload())}
          >
            Try again
          </button>
        </div>
      </>
    );
  }

  if (!config || !loaded) {
    return (
      <>
        {header}
        <div className="page-content" aria-busy="true" aria-label="Loading the discovery form">
          <div className="grid-2">
            <div className="skeleton" style={{ height: 72 }} />
            <div className="skeleton" style={{ height: 72 }} />
          </div>
          <div className="skeleton" style={{ height: 52 }} />
          <div className="skeleton" style={{ height: 160 }} />
        </div>
      </>
    );
  }

  return (
    <>
      {header}
      <div className="page-content">
        <SaveBanner store={store} />
        {store.legacy && (
          <Callout tone="info" title="Notes from this browser were found">
            Before notes were saved to projects, they were kept in the browser. Import them into this project?
            <div className="row" style={{ marginTop: 8 }}>
              <button type="button" className="btn btn-secondary" onClick={store.importLegacy}>
                Import into {project.client_name || project.name}
              </button>
              <button type="button" className="btn-link" onClick={store.dismissLegacy}>
                Not now
              </button>
            </div>
          </Callout>
        )}

        <div className="grid-3" style={{ alignItems: "start" }}>
          <label className="field">
            <span className="field-label">Client / project name</span>
            <input
              className="input"
              placeholder="Client or project name…"
              value={state.clientName}
              onChange={(e) => update({ clientName: e.target.value })}
            />
          </label>
          <label className="field">
            <span className="field-label">Client&apos;s business type</span>
            <input
              className="input"
              placeholder="e.g. multi-location dental practice"
              title="Used to tailor the client explainer with one example specific to their business."
              value={state.businessType}
              onChange={(e) => update({ businessType: e.target.value })}
            />
          </label>
          <label className="field">
            <span className="field-label">
              Client&apos;s website
              {websiteHref(state.clientWebsite) && (
                <a className="btn-link website-open" href={websiteHref(state.clientWebsite)} target="_blank" rel="noopener noreferrer">
                  Open <Glyph name="external-link" size={12} />
                </a>
              )}
            </span>
            <input
              className="input"
              type="url"
              inputMode="url"
              placeholder="e.g. brightsmiles.com"
              title="The business analysis reads the homepage for a quick client snapshot, advantages and upsell ideas."
              value={state.clientWebsite}
              onChange={(e) => update({ clientWebsite: e.target.value })}
            />
          </label>
        </div>

        <IndustryTemplatePicker
          apply={async (industry, size) => {
            const result = await applyIndustryDiscoveryTemplate(industry, size, toDiscoveryNotes(state));
            if (!result.filled) return "Nothing to fill: those questions are already answered.";
            update({ businessType: result.notes.business_type, sections: normalizeSections(result.notes.sections) });
            return `Pre-filled ${result.filled} unanswered question${result.filled === 1 ? "" : "s"}. Confirm each one on the call.`;
          }}
        />

        <Tabs<TabId>
          label="Discovery Call Assistant"
          layoutId="discovery-tabs"
          variant="primary"
          tabs={[
            { id: "analysis", label: "1 · Business analysis" },
            { id: "explainer", label: "2 · Client explainer" },
            { id: "checklist", label: "3 · Required-tasks checklist" },
            { id: "build", label: "4 · Build order" },
            { id: "overview", label: "5 · Company overview" },
          ]}
          active={tab}
          onChange={setTab}
        />

        {evaluateError && (
          <Callout tone="warning" title="Follow-ups and tasks aren't updating">
            {evaluateError}
          </Callout>
        )}

        <TabPanel panelKey={tab} id="discovery-tabs">
          {tab === "analysis" && <BusinessAnalysisTab config={config} evaluation={evaluation} store={store} />}
          {tab === "explainer" && <ExplainerTab store={store} />}
          {tab === "checklist" && <ChecklistTab evaluation={evaluation} store={store} onBack={() => setTab("analysis")} />}
          {tab === "build" && <BuildOrderTab config={config} evaluation={evaluation} store={store} />}
          {tab === "overview" && <CompanyOverviewTab store={store} />}
        </TabPanel>
      </div>
    </>
  );
}
