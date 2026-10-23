"use client";

/**
 * A project's dashboard data: one request, one object. The board header,
 * workstream cards, donut, documents-by-stage chart, team list and activity
 * feed all read from what this returns; the figures are derived on the
 * server from the project's saved work (services/project_insights.py).
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError, getProjectDashboard, type ProjectDashboard } from "./api";

export type DashboardState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: ProjectDashboard };

export function useProjectDashboard(projectId: string): DashboardState & { reload: () => void } {
  const [state, setState] = useState<DashboardState>({ status: "loading" });

  const reload = useCallback(() => {
    setState({ status: "loading" });
    getProjectDashboard(projectId)
      .then((data) => setState({ status: "ready", data }))
      .catch((e: unknown) => setState({ status: "error", message: e instanceof ApiError ? e.message : "Couldn't load the dashboard." }));
  }, [projectId]);

  useEffect(() => reload(), [reload]);
  return { ...state, reload };
}

/** "2 h ago", "Yesterday", "Oct 18". */
export function ago(iso: string): string {
  const then = new Date(iso);
  const minutes = Math.round((Date.now() - then.getTime()) / 60000);
  if (Number.isNaN(minutes)) return "";
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 24 * 60) return `${Math.round(minutes / 60)} h ago`;
  if (minutes < 48 * 60) return "Yesterday";
  return then.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
