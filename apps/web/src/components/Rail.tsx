"use client";

/**
 * The dark icon rail: one icon per section (from lib/nav), each opening a
 * flyout of its pages on hover, keyboard focus or tap. Esc closes and returns
 * focus to the icon; Up/Down move through a flyout's links. The section
 * holding the current page gets the accent bar, and the page is highlighted
 * in its flyout. Help sits at the foot: guide, feedback, setup, and the
 * current page's short guide.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { GUIDE } from "@/lib/guide";
import { HELP, NAV, hrefFor, isCurrent, locate, type NavSection } from "@/lib/nav";

import { useAppSession } from "./AppSession";
import { openFeedback } from "./FeedbackWidget";
import { NavIcon } from "./NavIcons";

const CLOSE_DELAY_MS = 120;

export function Rail() {
  const pathname = usePathname();
  const { me, project } = useAppSession();
  const projectId = /^\/projects\/([^/]+)/.exec(pathname)?.[1] ?? null;
  const activeId = locate(pathname, projectId)?.section.id ?? null;
  const guide = GUIDE[pathname.split("/").filter(Boolean).at(-1) ?? ""];

  const [openId, setOpenId] = useState<string | null>(null);
  const closeTimer = useRef<number | undefined>(undefined);
  const skipFocusOpen = useRef(false);
  const rail = useRef<HTMLElement>(null);

  // A page change closes whatever was open and lets go of focus held inside a now-hidden flyout.
  useEffect(() => {
    setOpenId(null);
    const focused = document.activeElement;
    if (focused instanceof HTMLElement && rail.current?.contains(focused)) focused.blur();
  }, [pathname]);
  useEffect(() => () => window.clearTimeout(closeTimer.current), []);

  const open = (id: string) => {
    window.clearTimeout(closeTimer.current);
    setOpenId(id);
  };
  const closeSoon = (id: string) => {
    window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setOpenId((cur) => (cur === id ? null : cur)), CLOSE_DELAY_MS);
  };

  const focusButton = (item: HTMLElement) => {
    skipFocusOpen.current = true;
    item.querySelector<HTMLButtonElement>(".ibtn")?.focus();
    skipFocusOpen.current = false;
  };

  const onKeyDown = (id: string) => (e: React.KeyboardEvent<HTMLDivElement>) => {
    const item = e.currentTarget;
    const links = Array.from(item.querySelectorAll<HTMLElement>(".flyout .litem"));
    const at = links.indexOf(document.activeElement as HTMLElement);
    if (e.key === "Escape") {
      e.preventDefault();
      setOpenId(null);
      focusButton(item);
    } else if (e.key === "ArrowDown" || (e.key === "ArrowRight" && at < 0)) {
      e.preventDefault();
      open(id);
      // The flyout becomes focusable once it's visible on the next frame.
      requestAnimationFrame(() => links[Math.min(at + 1, links.length - 1)]?.focus());
    } else if (e.key === "ArrowUp" && at >= 0) {
      e.preventDefault();
      if (at === 0) focusButton(item);
      else links[at - 1]?.focus();
    } else if (e.key === "ArrowLeft" && at >= 0) {
      e.preventDefault();
      setOpenId(null);
      focusButton(item);
    }
  };

  const renderSection = (section: NavSection, place: "top" | "bottom") => {
    const isOpen = openId === section.id;
    const flyoutId = `flyout-${section.id}`;
    const needsProject = section.scoped && !projectId;
    return (
      <div
        key={section.id}
        className="rail-item"
        data-open={isOpen}
        data-active={activeId === section.id}
        data-place={place}
        onPointerEnter={(e) => e.pointerType === "mouse" && open(section.id)}
        onPointerLeave={(e) => e.pointerType === "mouse" && closeSoon(section.id)}
        onFocus={() => !skipFocusOpen.current && open(section.id)}
        onBlur={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node | null)) closeSoon(section.id);
        }}
        onKeyDown={onKeyDown(section.id)}
      >
        <button
          type="button"
          className="ibtn"
          aria-label={section.label}
          aria-expanded={isOpen}
          aria-controls={flyoutId}
          aria-current={activeId === section.id ? "true" : undefined}
          // Opens only: a mouse click lands right after hover has already opened it.
          onClick={() => open(section.id)}
        >
          <NavIcon name={section.icon} size={21} />
        </button>
        <div className="flyout" id={flyoutId} role="group" aria-label={section.label}>
          <div className="fly-title">
            {section.label}
            {section.tag && <span className="fly-tag">{section.tag}</span>}
          </div>
          {section.scoped && (
            <p className="fly-note">
              {projectId && project ? (
                <>
                  <NavIcon name="folder" size={13} />
                  {project.client_name || project.name}
                </>
              ) : (
                "Open a project first — these pages work inside one."
              )}
            </p>
          )}
          {section.groups.map((group) => (
            <div key={group.label || "items"} className="fly-section">
              {group.label && <div className="fly-group">{group.label}</div>}
              {group.items.filter((item) => me.is_admin || !item.adminOnly).map((item) => {
                const content = (
                  <>
                    <NavIcon name={item.icon} size={17} />
                    <span className="litem-label">{item.label}</span>
                    {item.soon && <span className="soon-tag">Soon</span>}
                  </>
                );
                if (item.href === "#feedback") {
                  return (
                    <button
                      key={item.label}
                      type="button"
                      className="litem"
                      tabIndex={isOpen ? 0 : -1}
                      onClick={() => {
                        setOpenId(null);
                        openFeedback();
                      }}
                    >
                      {content}
                    </button>
                  );
                }
                const current = isCurrent(item, pathname, projectId);
                return (
                  <Link
                    key={item.label}
                    href={hrefFor(item, projectId)}
                    className="litem"
                    data-soon={Boolean(item.soon)}
                    data-dim={needsProject || undefined}
                    aria-current={current ? "page" : undefined}
                    tabIndex={isOpen ? 0 : -1}
                  >
                    {content}
                  </Link>
                );
              })}
            </div>
          ))}
          {section.id === HELP.id && guide && (
            <details className="fly-section fly-guide-wrap">
              <summary className="litem" tabIndex={isOpen ? 0 : -1}>
                <NavIcon name="list" size={17} />
                <span className="litem-label">Guide for this page</span>
                <NavIcon name="chevron-down" size={15} className="fly-guide-chevron" />
              </summary>
              <ol className="fly-guide">
                {guide.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ol>
            </details>
          )}
        </div>
      </div>
    );
  };

  return (
    <nav className="rail" aria-label="Primary" ref={rail}>
      <div className="rail-group">{NAV.map((s) => renderSection(s, "top"))}</div>
      <div className="rail-spacer" />
      <div className="rail-group">{renderSection(HELP, "bottom")}</div>
    </nav>
  );
}
