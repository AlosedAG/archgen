"use client";

/**
 * The line at the top of the workspace: Section › Page, and on project
 * pages the open project (folder, who's in charge) with a link to switch.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

import { locate } from "@/lib/nav";

import { useAppSession } from "./AppSession";
import { NavIcon } from "./NavIcons";

const EXTRA: Record<string, [string, string]> = { "/account": ["Account", "Profile & account"] };

export function ShellCrumbs() {
  const pathname = usePathname();
  const { project } = useAppSession();
  const projectId = /^\/projects\/([^/]+)/.exec(pathname)?.[1] ?? null;
  const found = locate(pathname, projectId);
  const [section, page] = found ? [found.section.label, found.item.label] : (EXTRA[pathname] ?? [null, null]);
  const showProject = projectId && project && project.id === projectId;

  if (!section && !showProject) return null;
  return (
    <div className="shell-crumbs">
      {section && (
        <nav className="crumb" aria-label="Breadcrumb">
          <span>{section}</span>
          <NavIcon name="chevron-right" size={13} />
          <span className="crumb-now" aria-current="page">
            {page}
          </span>
        </nav>
      )}
      {showProject && (
        <Link href="/projects" className="crumb-project" title="Switch project">
          <NavIcon name="folder" size={14} />
          <b>{project.client_name || project.name}</b>
          {project.folder && <span>· {project.folder}</span>}
          <span>· In charge: {project.lead?.name ?? "nobody yet"}</span>
          <span className="crumb-switch">Switch</span>
        </Link>
      )}
    </div>
  );
}
