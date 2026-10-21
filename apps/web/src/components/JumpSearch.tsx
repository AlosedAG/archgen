"use client";

/**
 * The top bar's search: jump to any page (in the current project) or any
 * project. "/" focuses it from anywhere that isn't a text field; Up/Down
 * move, Enter opens, Esc closes.
 */

import { AnimatePresence, motion } from "framer-motion";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { listProjects, type Project } from "@/lib/api";
import { hrefFor, searchablePages } from "@/lib/nav";

import { useAppSession } from "./AppSession";
import { NavIcon } from "./NavIcons";
import { dropdown } from "@/lib/motion";

type Result = { key: string; label: string; detail: string; href: string };
const MAX_RESULTS = 8;

function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

export function JumpSearch() {
  const router = useRouter();
  const { me } = useAppSession();
  const pathname = usePathname();
  const projectId = /^\/projects\/([^/]+)/.exec(pathname)?.[1] ?? null;
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [projects, setProjects] = useState<Project[] | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const root = useRef<HTMLDivElement>(null);
  const listId = useId();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "/" && !e.metaKey && !e.ctrlKey && !isTyping(e.target)) {
        e.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const loadProjects = () => {
    if (projects === null) {
      setProjects([]);
      listProjects()
        .then(setProjects)
        .catch(() => setProjects([]));
    }
  };

  const results = useMemo<Result[]>(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    const pages = searchablePages(me.is_admin).map(({ section, item }) => ({
      key: `page:${section.id}:${item.label}`,
      label: item.label,
      detail: item.soon ? `${section.label} · Soon` : section.label,
      href: hrefFor(item, projectId),
    }));
    const found = (projects ?? []).map((p) => ({
      key: `project:${p.id}`,
      label: p.client_name || p.name,
      detail: ["Project", p.folder].filter(Boolean).join(" · "),
      href: `/projects/${p.id}/discovery`,
    }));
    return [...pages, ...found].filter((r) => `${r.label} ${r.detail}`.toLowerCase().includes(q)).slice(0, MAX_RESULTS);
  }, [query, projects, projectId, me.is_admin]);

  const go = (result: Result | undefined) => {
    if (!result) return;
    setQuery("");
    setOpen(false);
    input.current?.blur();
    router.push(result.href);
  };

  return (
    <div className="jump-search" ref={root}>
      <NavIcon name="search" size={16} />
      <input
        ref={input}
        className="jump-search-input"
        role="combobox"
        aria-label="Search pages and projects"
        aria-expanded={open && results.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        placeholder="Search or press /"
        value={query}
        onFocus={() => {
          loadProjects();
          setOpen(true);
        }}
        onBlur={(e) => {
          if (!root.current?.contains(e.relatedTarget as Node | null)) setOpen(false);
        }}
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((i) => Math.min(i + 1, results.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((i) => Math.max(i - 1, 0));
          } else if (e.key === "Enter") {
            e.preventDefault();
            go(results[active]);
          } else if (e.key === "Escape") {
            setQuery("");
            setOpen(false);
            input.current?.blur();
          }
        }}
      />
      <kbd className="jump-search-kbd" aria-hidden>
        /
      </kbd>
      <AnimatePresence>
        {open && query.trim() !== "" && (
          <motion.ul
            id={listId}
            role="listbox"
            className="option-list jump-search-results"
            variants={dropdown}
            initial="hidden"
            animate="visible"
            exit="exit"
          >
            {results.length === 0 ? (
              <li className="option-empty">No pages or projects match.</li>
            ) : (
              results.map((r, i) => (
                <li
                  key={r.key}
                  role="option"
                  aria-selected={i === active}
                  className="option jump-search-option"
                  data-active={i === active}
                  onMouseEnter={() => setActive(i)}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    go(r);
                  }}
                >
                  <span>{r.label}</span>
                  <span className="t-caption">{r.detail}</span>
                </li>
              ))
            )}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
