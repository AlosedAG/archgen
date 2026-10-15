"use client";

/**
 * The frame shared by the Step 2 portal pages: header, autosave status,
 * the snapshot bar, and the snapshot's warnings. The page body gets the
 * project and the "portal" module store.
 */

import { useAppSession } from "../AppSession";
import { Callout } from "../ui";
import { ProjectHeader } from "./ProjectHeader";
import { SaveBanner } from "./SaveBanner";
import { SnapshotBar } from "./SnapshotBar";

import type { Project } from "@/lib/api";
import { useModuleState, type ModuleStore } from "@/lib/module-state";
import { normalizePortal, type PortalState } from "@/lib/portal-state";

export function usePortalState(projectId: string): ModuleStore<PortalState> {
  return useModuleState<PortalState>(projectId, "portal", normalizePortal);
}

export function PortalPage({
  eyebrow = "STEP 2 / AUDIT",
  title,
  description,
  pullBar = true,
  children,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  /** Show "Pull from HubSpot" (pages that only read the saved snapshot hide it). */
  pullBar?: boolean;
  children: (project: Project, store: ModuleStore<PortalState>) => React.ReactNode;
}) {
  const { project } = useAppSession();
  const store = usePortalState(project?.id ?? "");
  if (!project) return null;
  return (
    <>
      <ProjectHeader eyebrow={eyebrow} title={title} description={description} />
      <div className="page-content">
        {!store.loaded ? (
          store.status === "error" ? (
            <Callout tone="error" title="Can't load this project's portal data">
              {store.error}
            </Callout>
          ) : (
            <div className="skeleton" style={{ height: 88 }} aria-busy="true" />
          )
        ) : (
          <>
            <SaveBanner store={store} />
            {pullBar && <SnapshotBar store={store} />}
            {(store.state.snapshot?.warnings ?? []).map((w) => (
              <Callout key={w} tone="warning" title="Part of the portal couldn't be read">
                {w}
              </Callout>
            ))}
            {children(project, store)}
          </>
        )}
      </div>
    </>
  );
}
