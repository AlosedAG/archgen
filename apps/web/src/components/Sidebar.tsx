"use client";

/**
 * The process sidebar: wordmark, the current project, the five-step
 * navigation with its rails, the page guide, and the signed-in user.
 * Project pages link within the current project (/projects/:id/...).
 */

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { GUIDE } from "@/lib/guide";

import { useAppSession } from "./AppSession";
import { Icon, spring } from "./ui";

/** `page` = a project page at /projects/:id/<page>; `href` = a fixed route. */
type NavItem = { label: string; page?: string; href?: string };

const NAV: { group: string; rail: boolean; items: NavItem[] }[] = [
  {
    group: "Start here",
    rail: false,
    items: [{ label: "Projects", href: "/projects" }, { label: "Setup & API keys", href: "/settings" }, { label: "User guide", href: "/guide" }],
  },
  {
    group: "Step 1 · Discover",
    rail: true,
    items: [
      { label: "Discovery Call Assistant", page: "discovery" },
      { label: "Deal Stage Planner", page: "stage-planner" },
      { label: "Requirements Document", page: "requirements" },
      { label: "Joint Evaluation Plan", page: "evaluation-plan" },
    ],
  },
  {
    group: "Step 2 · Assess current portal",
    rail: true,
    items: [
      { label: "Portal Auditor", page: "portal-audit" },
      { label: "Property Audit", page: "property-audit" },
      { label: "Documentation Generator", page: "documentation" },
      { label: "Executive Report", page: "executive-report" },
    ],
  },
  { group: "Step 3 · Design", rail: true, items: [{ label: "Architecture Generator", page: "architecture" }, { label: "Architecture Diagram", page: "diagram" }] },
  { group: "Step 4 · Propose", rail: true, items: [{ label: "Proposal & SOW Builder", page: "proposal" }] },
  { group: "Step 5 · Deliver & test", rail: true, items: [{ label: "Test Case Document", page: "test-cases" }] },
  { group: "Library", rail: false, items: [{ label: "Project Library", page: "library" }] },
];


export function Sidebar() {
  const pathname = usePathname();
  const { me, signOut, project } = useAppSession();
  const [guideOpen, setGuideOpen] = useState(false);
  const projectId = /^\/projects\/([^/]+)/.exec(pathname)?.[1] ?? null;
  const guide = GUIDE[pathname.split("/").filter(Boolean).at(-1) ?? ""];

  const hrefFor = (item: NavItem): string | null => {
    if (item.href) return item.href;
    if (item.page) return projectId ? `/projects/${projectId}/${item.page}` : "/projects";
    return null;
  };

  return (
    <aside className="sidebar" aria-label="Main navigation">
      <div className="nav">
        <Link href="/projects" className="wordmark">
          <span className="wordmark-name">ArchitectureScope</span>
          <span className="wordmark-tagline">SOLUTIONS ARCHITECT WORKSPACE</span>
        </Link>
        {projectId && project && (
          <Link href="/projects" className="sidebar-project" title="Switch project">
            <span className="sidebar-project-label">
              Project{project.folder ? ` · ${project.folder}` : ""} · switch ↗
            </span>
            <span className="sidebar-project-name">{project.client_name || project.name}</span>
            <span className="sidebar-project-meta" title={project.lead?.email ?? ""}>
              In charge: <b>{project.lead?.name ?? "nobody yet"}</b>
            </span>
            <span className="sidebar-project-meta" title={new Date(project.updated_at).toLocaleString()}>
              Last edit: {project.last_edited_by?.name ?? "—"} ·{" "}
              {new Date(project.updated_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}
            </span>
          </Link>
        )}
        <div className="nav-groups">
          {NAV.map(({ group, rail, items }) => (
            <nav key={group} aria-label={group}>
              <div className="nav-group-label">{group}</div>
              <ul className="nav-list" data-rail={rail}>
                {items.map((item) => {
                  const href = hrefFor(item);
                  if (!href) {
                    return (
                      <li key={item.label}>
                        <span className="nav-item nav-item-soon" aria-disabled="true" title="Coming soon to the web app">
                          <span className="nav-label">{item.label}</span>
                          <span className="nav-soon">Soon</span>
                        </span>
                      </li>
                    );
                  }
                  const active = item.page
                    ? Boolean(projectId) && pathname.startsWith(`/projects/${projectId}/${item.page}`)
                    : pathname === href;
                  return (
                    <li key={item.label}>
                      <Link href={href} className="nav-item" aria-current={active ? "page" : undefined}>
                        {active && (
                          <>
                            <motion.span layoutId="nav-active-bg" className="nav-active-bg" transition={spring} />
                            <motion.span layoutId="nav-active-bar" className="nav-active-bar" transition={spring} />
                          </>
                        )}
                        <span className="nav-label">{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </nav>
          ))}
        </div>
      </div>

      <div className="sidebar-utilities">
        {guide && (
          <div className="sidebar-guide">
            <button
              type="button"
              className="accordion-summary"
              aria-expanded={guideOpen}
              onClick={() => setGuideOpen((open) => !open)}
            >
              <motion.span animate={{ rotate: guideOpen ? 90 : 0 }} transition={spring} style={{ display: "inline-flex" }}>
                <Icon name="chevron-right" />
              </motion.span>
              Guide for this page
            </button>
            <AnimatePresence initial={false}>
              {guideOpen && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  style={{ overflow: "hidden" }}
                >
                  <div className="sidebar-guide-body">
                    {guide.map((line) => (
                      <p key={line}>{line}</p>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
        <div className="sidebar-user">
          <span className="sidebar-user-name">
            <span style={{ fontWeight: 600 }}>{me.name || me.email}</span>
            <span className="t-caption">{me.workspace_name}</span>
          </span>
          <button type="button" className="btn-link" onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
        <span
          className="badge badge-connection"
          title="ArchitectureScope only reads from HubSpot — it never creates, edits, or deletes anything."
        >
          ● Read-only HubSpot connection
        </span>
      </div>
    </aside>
  );
}
