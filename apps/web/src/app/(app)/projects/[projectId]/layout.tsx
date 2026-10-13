"use client";

/** Loads the project for every page under /projects/:id and shares it with the shell. */

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAppSession } from "@/components/AppSession";
import { Callout } from "@/components/ui";
import { ApiError, getProject } from "@/lib/api";

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const { projectId } = useParams<{ projectId: string }>();
  const { project, setProject } = useAppSession();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    getProject(projectId)
      .then(setProject)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Couldn't load this project."));
  }, [projectId, setProject]);

  if (error) {
    return (
      <div className="page-content">
        <Callout tone="error" title="Can't open this project">
          {error}
        </Callout>
        <a className="btn btn-secondary" style={{ width: "fit-content" }} href="/projects">
          Back to projects
        </a>
      </div>
    );
  }
  if (!project || project.id !== projectId) {
    return (
      <div className="page-content" aria-busy="true">
        <div className="skeleton" style={{ height: 160 }} />
      </div>
    );
  }
  return <>{children}</>;
}
