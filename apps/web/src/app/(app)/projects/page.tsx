"use client";

/** The workspace's client projects: open one, or start a new one. */

import { motion } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAppSession } from "@/components/AppSession";
import { PageHeader } from "@/components/PageHeader";
import { Callout } from "@/components/ui";
import { ApiError, createProject, listProjects, type Project } from "@/lib/api";

function when(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export default function ProjectsPage() {
  const router = useRouter();
  const { me, setProject } = useAppSession();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setProject(null);
    listProjects()
      .then(setProjects)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Couldn't load projects."));
  }, [setProject]);

  return (
    <>
      <PageHeader
        eyebrow="WORKSPACE / PROJECTS"
        breadcrumb={`${me.workspace_name}  /  ${me.name || me.email}`}
        title="Projects"
        description="Each client engagement is a project. Its discovery call, documents and build order live inside it."
      />
      <div className="page-content">
        <form
          className="inline-form"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!name.trim()) return;
            setBusy(true);
            setError(null);
            try {
              const project = await createProject(name.trim());
              router.push(`/projects/${project.id}/discovery`);
            } catch (err) {
              setError(err instanceof ApiError ? err.message : "Couldn't create the project.");
              setBusy(false);
            }
          }}
        >
          <label className="field">
            <span className="field-label">New client / project</span>
            <input className="input" placeholder="e.g. Bright Smiles" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <button type="submit" className="btn btn-primary" disabled={busy || !name.trim()}>
            {busy ? "Creating…" : "Create project"}
          </button>
        </form>
        {error && <Callout tone="error" title="Something went wrong">{error}</Callout>}

        {projects === null ? (
          <div className="project-grid" aria-busy="true">
            <div className="skeleton" style={{ height: 110 }} />
            <div className="skeleton" style={{ height: 110 }} />
            <div className="skeleton" style={{ height: 110 }} />
          </div>
        ) : projects.length === 0 ? (
          <Callout tone="info" title="No projects yet">
            Create your first client project above to start a discovery call.
          </Callout>
        ) : (
          <div className="project-grid">
            {projects.map((p, i) => (
              <motion.div key={p.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0, transition: { delay: i * 0.03 } }}>
                <Link href={`/projects/${p.id}/discovery`} className="project-card">
                  <span className="project-card-name">{p.client_name || p.name}</span>
                  {p.client_name && p.client_name !== p.name && <span className="t-description">{p.name}</span>}
                  <span className="t-caption">
                    Updated {when(p.updated_at)} · {p.document_count ?? 0} saved document{p.document_count === 1 ? "" : "s"}
                  </span>
                </Link>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
