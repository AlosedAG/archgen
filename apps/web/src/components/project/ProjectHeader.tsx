"use client";

import { useAppSession } from "../AppSession";
import { PageHeader } from "../PageHeader";

/** The page banner for a project page: step eyebrow, "Client / Workspace" breadcrumb. */
export function ProjectHeader({ eyebrow, title, description, meta }: { eyebrow: string; title: string; description?: string; meta?: React.ReactNode }) {
  const { project, me } = useAppSession();
  return (
    <PageHeader
      eyebrow={eyebrow}
      breadcrumb={`${project?.client_name || project?.name || "Project"}  /  ${me.workspace_name}`}
      title={title}
      description={description}
      meta={meta}
    />
  );
}
