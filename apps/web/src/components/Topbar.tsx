"use client";

/**
 * The full-width top bar over every signed-in page: the brand, the search,
 * the read-only connection pill, the theme toggle and the signed-in user.
 * It sits outside the page transition, so it stays still while pages change.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAppSession } from "./AppSession";
import { HubZoneBrand } from "./HubZoneLogo";
import { JumpSearch } from "./JumpSearch";
import { NavIcon } from "./NavIcons";
import { ThemeToggle } from "./ThemeToggle";

function initials(name: string): string {
  const parts = name.trim().split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

/** Avatar + name + org; opens Profile and Sign out. */
function UserMenu() {
  const { me, signOut } = useAppSession();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const name = me.name || me.email;

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        root.current?.querySelector<HTMLButtonElement>(".me")?.focus();
      }
    };
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="me-wrap" ref={root}>
      <button type="button" className="me" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className="me-avatar" aria-hidden>
          {initials(name)}
        </span>
        <span className="me-who">
          <b>{name}</b>
          <span>{me.workspace_name}</span>
        </span>
      </button>
      <div className="menu-pop" role="menu" data-open={open}>
        <div className="menu-pop-head">
          <b>{name}</b>
          <span>{me.email}</span>
        </div>
        <Link href="/account" role="menuitem" className="litem" tabIndex={open ? 0 : -1}>
          <NavIcon name="user" />
          <span>Profile &amp; account</span>
        </Link>
        <button type="button" role="menuitem" className="litem" tabIndex={open ? 0 : -1} onClick={() => void signOut()}>
          <NavIcon name="logout" />
          <span>Sign out</span>
        </button>
      </div>
    </div>
  );
}

export function Topbar() {
  return (
    <header className="topbar">
      <Link href="/projects" className="brand-link" aria-label="The Hub Zone — projects">
        <HubZoneBrand />
      </Link>
      <div className="topbar-spacer" />
      <JumpSearch />
      <span className="conn" title="The Hub Zone only reads from HubSpot — it never creates, edits, or deletes anything.">
        <span className="conn-dot" aria-hidden />
        <span className="conn-label">Read-only HubSpot connection</span>
      </span>
      <ThemeToggle />
      <UserMenu />
    </header>
  );
}
