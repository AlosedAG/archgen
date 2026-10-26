"use client";

/**
 * A module's working state for a project (Discovery notes, the
 * Requirements Document, the proposal, …), loaded from and autosaved to
 * the server.
 *
 * Saves are debounced and serialized (one in flight; changes made during
 * a save trigger another). Each save sends the version it was based on;
 * if someone else saved in between the server refuses (409) and autosave
 * stops with status "conflict" so the page can offer a reload instead of
 * overwriting their work.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, getModuleState, getWorkspaceState, saveModuleState, saveWorkspaceState } from "./api";

export type SaveStatus = "loading" | "saved" | "saving" | "error" | "conflict";

const AUTOSAVE_MS = 900;

export function useModuleState<T extends object>(
  projectId: string,
  module: string,
  /** Turn stored data (or null when nothing is saved yet) into a full state. */
  normalize: (raw: unknown) => T,
  /** A workspace-wide tool's state instead of a project's (projectId is ignored). */
  { workspace = false }: { workspace?: boolean } = {},
) {
  const [state, setState] = useState<T>(() => normalize(null));
  const [loaded, setLoaded] = useState(false);
  const [status, setStatus] = useState<SaveStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [version, setVersionState] = useState(0);
  const versionRef = useRef(0);
  const dirty = useRef(false);
  const saving = useRef(false);
  const latest = useRef(state);
  latest.current = state;
  const normalizeRef = useRef(normalize);
  normalizeRef.current = normalize;

  const setVersion = (v: number) => {
    versionRef.current = v;
    setVersionState(v);
  };

  const load = useCallback(async () => {
    setStatus("loading");
    setError(null);
    try {
      const saved = await (workspace ? getWorkspaceState(module) : getModuleState(projectId, module));
      setVersion(saved.version ?? 0);
      setState(normalizeRef.current(saved.data && Object.keys(saved.data).length ? saved.data : null));
      setSavedAt(saved.updated_at ? new Date(saved.updated_at) : null);
      dirty.current = false;
      setLoaded(true);
      setStatus("saved");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't load this project's data.");
      setStatus("error");
    }
  }, [projectId, module, workspace]);

  useEffect(() => {
    void load();
  }, [load]);

  const flush = useCallback(async () => {
    if (saving.current || !dirty.current) return;
    saving.current = true;
    dirty.current = false;
    setStatus("saving");
    try {
      const saved = await (workspace
        ? saveWorkspaceState(module, latest.current, versionRef.current)
        : saveModuleState(projectId, module, latest.current, versionRef.current));
      setVersion(saved.version ?? versionRef.current + 1);
      setSavedAt(new Date());
      setStatus(dirty.current ? "saving" : "saved");
      setError(null);
    } catch (e) {
      saving.current = false;
      if (e instanceof ApiError && e.status === 409) {
        setStatus("conflict");
        setError(e.message);
        return; // stop autosaving until reloaded
      }
      dirty.current = true;
      setStatus("error");
      setError(e instanceof ApiError ? e.message : "Couldn't save. Your changes are kept here and will retry.");
      return;
    }
    saving.current = false;
    if (dirty.current) void flush();
  }, [projectId, module, workspace]);

  useEffect(() => {
    if (!loaded || status === "conflict" || !dirty.current) return;
    const timer = window.setTimeout(() => void flush(), AUTOSAVE_MS);
    return () => window.clearTimeout(timer);
  }, [state, loaded, status, flush]);

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty.current || saving.current) e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);

  const change = useCallback((updater: (s: T) => T) => {
    dirty.current = true;
    setState(updater);
  }, []);
  const replace = useCallback((next: T) => change(() => next), [change]);
  const update = useCallback((patch: Partial<T>) => change((s) => ({ ...s, ...patch })), [change]);

  return { projectId, module, state, loaded, status, error, savedAt, version, reload: load, change, replace, update };
}

export type ModuleStore<T extends object> = ReturnType<typeof useModuleState<T>>;

/**
 * Change another module's saved state from outside its page (e.g. the
 * Stage Planner applying to Discovery): load, apply ``updater``, save with
 * the loaded version — retrying once if someone saved in between.
 */
export async function updateModuleState<T>(
  projectId: string,
  module: string,
  updater: (current: T | null) => T,
): Promise<void> {
  for (let attempt = 0; attempt < 2; attempt++) {
    const saved = await getModuleState(projectId, module);
    const current = saved.data && Object.keys(saved.data).length ? (saved.data as T) : null;
    try {
      await saveModuleState(projectId, module, updater(current) as object, saved.version ?? 0);
      return;
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 409) || attempt === 1) throw e;
    }
  }
}
