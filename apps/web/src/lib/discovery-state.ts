"use client";

/**
 * Discovery call notes for a project, saved on the server via
 * useModuleState (debounced autosave, version-checked).
 */

import { useCallback, useEffect, useState } from "react";

import type { DiscoveryNotes, HubSpotModule, PlannedStage } from "./api";
import { useModuleState } from "./module-state";

export type Answer = { selected: string[]; other: string; notes: string; flagged: boolean };
export type SectionNotes = { answers: Record<string, Answer>; notes: string; edge_cases: string };

export type DiscoveryState = {
  version: 1;
  clientName: string;
  businessType: string;
  /** The client's website; its homepage is read for the business analysis. */
  clientWebsite: string;
  sections: Record<string, SectionNotes>;
  /** Required-task ids ticked on the Business analysis tab. */
  tasksDone: string[];
  /** Build-order item ids ticked as built. */
  buildDone: string[];
  projectType: string;
  baOutput: string;
  ceOutput: string;
  ceModules: HubSpotModule[];
  /** Stages of a Deal Stage Planner applied to the build order (null = none). */
  stagePlanner: PlannedStage[] | null;
};

const MODULE = "discovery";
/** Where the browser-only version kept notes; offered for a one-time import. */
const LEGACY_STORAGE_KEY = "archscope.discovery.v1";

export const EMPTY_ANSWER: Answer = { selected: [], other: "", notes: "", flagged: false };
const EMPTY_SECTION: SectionNotes = { answers: {}, notes: "", edge_cases: "" };

export function emptyState(clientName = ""): DiscoveryState {
  return {
    version: 1,
    clientName,
    businessType: "",
    clientWebsite: "",
    sections: {},
    tasksDone: [],
    buildDone: [],
    projectType: "",
    baOutput: "",
    ceOutput: "",
    ceModules: [],
    stagePlanner: null,
  };
}

/** A stored, restored or uploaded state with any missing fields filled in. */
export function normalizeState(raw: unknown, clientName = ""): DiscoveryState {
  if (typeof raw !== "object" || raw === null) return emptyState(clientName);
  return { ...emptyState(clientName), ...(raw as Partial<DiscoveryState>), version: 1 };
}

/** Parse a JSON backup. Throws if it isn't one. */
export function parseState(text: string): DiscoveryState {
  const raw = JSON.parse(text) as Partial<DiscoveryState>;
  if (typeof raw !== "object" || raw === null || raw.version !== 1) throw new Error("Not a discovery notes backup.");
  return normalizeState(raw);
}

export function getSection(state: DiscoveryState, section: string): SectionNotes {
  return state.sections[section] ?? EMPTY_SECTION;
}

export function getAnswer(state: DiscoveryState, section: string, questionId: string): Answer {
  return getSection(state, section).answers[questionId] ?? EMPTY_ANSWER;
}

/** Anything captured — options, "Other" text, or notes (text questions keep their answer in notes). */
export function isAnswered(answer: Answer): boolean {
  return answer.selected.length > 0 || answer.notes.trim() !== "" || answer.other.trim() !== "";
}

export function hasAnyNotes(state: DiscoveryState): boolean {
  return Object.values(state.sections).some(
    (s) => Object.values(s.answers).some(isAnswered) || s.notes.trim() !== "" || s.edge_cases.trim() !== "",
  );
}

/** The notes in the API's DiscoveryNotes shape. */
export function toDiscoveryNotes(state: DiscoveryState): DiscoveryNotes {
  return { client_name: state.clientName, business_type: state.businessType, client_website: state.clientWebsite, sections: state.sections };
}

function readLegacyNotes(): DiscoveryState | null {
  try {
    const stored = window.localStorage.getItem(LEGACY_STORAGE_KEY);
    const state = stored ? parseState(stored) : null;
    return state && hasAnyNotes(state) ? state : null;
  } catch {
    return null;
  }
}

/** A project's discovery notes, loaded from and autosaved to the server. */
export function useDiscoveryState(projectId: string, defaultClientName: string) {
  const normalize = useCallback((raw: unknown) => normalizeState(raw, defaultClientName), [defaultClientName]);
  const store = useModuleState<DiscoveryState>(projectId, MODULE, normalize);
  const { change, replace, version, loaded } = store;
  const [legacy, setLegacy] = useState<DiscoveryState | null>(null);

  // Notes from the browser-only version, offered once for an empty project.
  useEffect(() => {
    setLegacy(loaded && version === 0 ? readLegacyNotes() : null);
    // Only when first loaded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded]);

  const setAnswer = useCallback(
    (section: string, questionId: string, patch: Partial<Answer>) => {
      change((s) => {
        const current = getSection(s, section);
        const answer = { ...(current.answers[questionId] ?? EMPTY_ANSWER), ...patch };
        return {
          ...s,
          sections: { ...s.sections, [section]: { ...current, answers: { ...current.answers, [questionId]: answer } } },
        };
      });
    },
    [change],
  );

  const setSectionField = useCallback(
    (section: string, field: "notes" | "edge_cases", value: string) => {
      change((s) => ({ ...s, sections: { ...s.sections, [section]: { ...getSection(s, section), [field]: value } } }));
    },
    [change],
  );

  const toggleIn = useCallback(
    (field: "tasksDone" | "buildDone", id: string) => {
      change((s) => ({ ...s, [field]: s[field].includes(id) ? s[field].filter((x) => x !== id) : [...s[field], id] }));
    },
    [change],
  );

  const importLegacy = useCallback(() => {
    if (!legacy) return;
    replace({ ...legacy, clientName: legacy.clientName || defaultClientName });
    try {
      window.localStorage.removeItem(LEGACY_STORAGE_KEY);
    } catch {
      // ignore
    }
    setLegacy(null);
  }, [legacy, replace, defaultClientName]);

  return {
    ...store,
    legacy,
    importLegacy,
    dismissLegacy: () => setLegacy(null),
    setAnswer,
    setSectionField,
    toggleIn,
  };
}

export type DiscoveryStore = ReturnType<typeof useDiscoveryState>;
