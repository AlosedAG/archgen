"use client";

/**
 * The white top bar over every signed-in page: breadcrumb (Workspace /
 * section / page) and the search. It lives in the app layout, outside the
 * page transition, so it stays still while pages change beneath it.
 */

import { usePathname } from "next/navigation";

import { NAV, crumbFor } from "@/lib/nav";

import { JumpSearch } from "./JumpSearch";

const EXTRA_TITLES: Record<string, string> = { account: "Profile & account" };

function pageTitle(pathname: string): string {
  const last = pathname.split("/").filter(Boolean).at(-1) ?? "";
  for (const group of NAV) {
    for (const item of group.items) {
      if (item.page === last || item.href === pathname) return item.label;
    }
  }
  return EXTRA_TITLES[last] ?? "";
}

export function Topbar() {
  const pathname = usePathname();
  const crumb = crumbFor(pathname);
  const title = pageTitle(pathname);
  return (
    <div className="topbar">
      <nav className="topbar-crumbs" aria-label="Breadcrumb">
        <span>Workspace</span>
        {crumb && (
          <>
            <span aria-hidden>/</span>
            <span>{crumb}</span>
          </>
        )}
        {title && (
          <>
            <span aria-hidden>/</span>
            <span className="topbar-crumb-current" aria-current="page">
              {title}
            </span>
          </>
        )}
      </nav>
      <JumpSearch />
    </div>
  );
}
