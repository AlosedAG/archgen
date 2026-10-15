"use client";

/**
 * The process sidebar: wordmark, the current project, the five-step
 * navigation, then the page guide, Feedback, the signed-in user and the
 * read-only connection badge. Project pages link within the current
 * project (/projects/:id/...).
 */

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { GUIDE } from "@/lib/guide";
import { NAV, hrefFor, type NavIconKind } from "@/lib/nav";

import { useAppSession } from "./AppSession";
import { openFeedback } from "./FeedbackWidget";
import { Glyph } from "./icons";
import { Icon, spring } from "./ui";
import { collapse } from "@/lib/motion";

/** The design's 16px navigation glyphs, drawn from simple shapes in the current colour. */
function NavIcon({ kind }: { kind: NavIconKind }) {
  return (
    <span className={`nav-icon nav-icon-${kind}`} aria-hidden>
      {kind === "doc" && (
        <>
          <span className="nav-icon-outline" />
          <span className="nav-icon-line" style={{ top: 6, width: 6 }} />
          <span className="nav-icon-line" style={{ top: 9, width: 4 }} />
        </>
      )}
      {kind === "grid" && [0, 1, 2, 3].map((i) => <span key={i} className="nav-icon-tile" />)}
      {kind === "list" && (
        <>
          <span className="nav-icon-stem" />
          <span className="nav-icon-bar" style={{ top: 3, width: 7 }} />
          <span className="nav-icon-bar" style={{ top: 7, width: 5 }} />
          <span className="nav-icon-bar" style={{ top: 11, width: 6 }} />
        </>
      )}
    </span>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const { me, signOut, project } = useAppSession();
  const [guideOpen, setGuideOpen] = useState(false);
  const projectId = /^\/projects\/([^/]+)/.exec(pathname)?.[1] ?? null;
  const guide = GUIDE[pathname.split("/").filter(Boolean).at(-1) ?? ""];

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
              Project{project.folder ? ` · ${project.folder}` : ""} · switch
            </span>
            <span className="sidebar-project-name">{project.client_name || project.name}</span>
            <span className="sidebar-project-meta" title={project.lead?.email ?? ""}>
              In charge: <b>{project.lead?.name ?? "nobody yet"}</b>
            </span>
          </Link>
        )}
        <div className="nav-groups">
          {NAV.map(({ group, items }) => (
            <nav key={group} aria-label={group}>
              <div className="nav-group-label">{group}</div>
              <ul className="nav-list">
                {items.map((item) => {
                  const href = hrefFor(item, projectId);
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
                        <NavIcon kind={item.icon} />
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
              className="sidebar-guide-summary"
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
                <motion.div variants={collapse} initial="closed" animate="open" exit="closed" style={{ overflow: "hidden" }}>
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
        <button type="button" className="sidebar-feedback" onClick={openFeedback}>
          <Icon name="message-square" />
          Feedback
        </button>
        <div className="sidebar-user">
        <Link href="/account" className="sidebar-user-name" title="Your profile and account settings" aria-current={pathname === "/account" ? "page" : undefined}>
          <span className="avatar" aria-hidden>
            <Glyph name="user" size={14} />
          </span>
          <span className="sidebar-user-text">
            <span style={{ fontWeight: 600 }}>{me.name || me.email}</span>
            <span className="t-caption">{me.workspace_name}</span>
          </span>
        </Link>
          <button type="button" className="btn-link" onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
        <span
          className="badge badge-connection"
          title="ArchitectureScope only reads from HubSpot — it never creates, edits, or deletes anything."
        >
          <span className="status-dot" aria-hidden />
          Read-only HubSpot connection
        </span>
      </div>
    </aside>
  );
}
