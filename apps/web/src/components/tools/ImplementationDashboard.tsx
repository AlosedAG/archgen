"use client";

/**
 * Implementation Dashboard (first version): every project's stage, scoping
 * progress, portal health and open tasks in one table, from the same
 * figures the Projects cards use (/projects/insights).
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { DataTable } from "@/components/project/DataTable";
import { Stats } from "@/components/project/Stats";
import { Callout } from "@/components/ui";
import { ApiError, listProjectInsights, listProjects, type Project, type ProjectInsight } from "@/lib/api";

const HEALTH: Record<ProjectInsight["health"]["status"], string> = {
  healthy: "Healthy",
  needs_review: "Needs review",
  not_started: "Not started",
};

export function ImplementationDashboard() {
  const [data, setData] = useState<{ projects: Project[]; insights: Map<string, ProjectInsight> } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listProjects(), listProjectInsights()])
      .then(([projects, insights]) => setData({ projects, insights: new Map(insights.map((i) => [i.project_id, i])) }))
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Couldn't load the projects."));
  }, []);

  if (error) return <Callout tone="error" title="Couldn't load the dashboard">{error}</Callout>;
  if (!data) return <div className="skeleton" style={{ height: 280 }} aria-busy="true" />;

  const rows = data.projects.map((p) => ({ p, i: data.insights.get(p.id) }));
  const known = rows.flatMap((r) => (r.i ? [r.i] : []));
  const average = known.length ? Math.round(known.reduce((s, i) => s + i.progress, 0) / known.length) : 0;

  return (
    <>
      <Stats
        items={[
          ["Projects", data.projects.length],
          ["In progress", known.filter((i) => i.progress > 0 && i.progress < 100).length],
          ["Average progress", `${average}%`],
          ["Needs review", known.filter((i) => i.health.status === "needs_review").length],
          ["Open tasks", known.reduce((s, i) => s + i.open_tasks, 0)],
        ]}
      />
      <DataTable
        label="Implementations"
        empty="No projects yet: create one under Projects."
        columns={[
          { key: "project", label: "Project", width: "minmax(180px, 1.4fr)" },
          { key: "lead", label: "In charge", width: "minmax(130px, 1fr)" },
          { key: "stage", label: "Stage", width: "110px" },
          { key: "progress", label: "Progress", width: "100px" },
          { key: "health", label: "Portal health", width: "140px" },
          { key: "tasks", label: "Open tasks", width: "100px" },
          { key: "edited", label: "Last edited", width: "130px" },
        ]}
        rows={rows.map(({ p, i }) => ({
          project: <Link href={`/projects/${p.id}`}>{p.client_name || p.name}</Link>,
          lead: p.lead?.name ?? "Nobody yet",
          stage: i?.stage ?? "…",
          progress: i ? `${i.progress}%` : "…",
          health: i ? `${HEALTH[i.health.status]}${i.health.score != null ? ` (${i.health.score})` : ""}` : "…",
          tasks: i?.open_tasks ?? "…",
          edited: new Date(p.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
        }))}
      />
    </>
  );
}
