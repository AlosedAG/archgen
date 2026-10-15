/**
 * The process navigation, shared by the sidebar and the top-bar search.
 * `page` = a project page at /projects/:id/<page>; `href` = a fixed route.
 * `icon` is the design's navigation glyph: a document outline, a 2×2 grid,
 * or a list.
 */

export type NavIconKind = "doc" | "grid" | "list";
export type NavItem = { label: string; icon: NavIconKind; page?: string; href?: string };
export type NavGroup = { group: string; crumb: string; items: NavItem[] };

export const NAV: NavGroup[] = [
  {
    group: "Start here",
    crumb: "Start here",
    items: [
      { label: "Projects", icon: "grid", href: "/projects" },
      { label: "Setup & API keys", icon: "doc", href: "/settings" },
      { label: "User guide", icon: "grid", href: "/guide" },
    ],
  },
  {
    group: "Step 1 · Discover",
    crumb: "Discovery",
    items: [
      { label: "Discovery Call Assistant", icon: "list", page: "discovery" },
      { label: "Deal Stage Planner", icon: "list", page: "stage-planner" },
      { label: "Requirements Document", icon: "doc", page: "requirements" },
      { label: "Joint Evaluation Plan", icon: "grid", page: "evaluation-plan" },
    ],
  },
  {
    group: "Step 2 · Assess current portal",
    crumb: "Assessment",
    items: [
      { label: "Portal Auditor", icon: "list", page: "portal-audit" },
      { label: "Property Audit", icon: "doc", page: "property-audit" },
      { label: "Documentation Generator", icon: "grid", page: "documentation" },
      { label: "Executive Report", icon: "list", page: "executive-report" },
    ],
  },
  {
    group: "Step 3 · Design",
    crumb: "Design",
    items: [
      { label: "Architecture Generator", icon: "doc", page: "architecture" },
      { label: "Architecture Diagram", icon: "grid", page: "diagram" },
    ],
  },
  { group: "Step 4 · Propose", crumb: "Proposal", items: [{ label: "Proposal & SOW Builder", icon: "list", page: "proposal" }] },
  { group: "Step 5 · Deliver & test", crumb: "Delivery", items: [{ label: "Test Case Document", icon: "doc", page: "test-cases" }] },
  { group: "Library", crumb: "Library", items: [{ label: "Project Library", icon: "grid", page: "library" }] },
];

/** The link for a nav item: project pages need a project (else they go to the project list). */
export function hrefFor(item: NavItem, projectId: string | null): string {
  if (item.href) return item.href;
  return projectId ? `/projects/${projectId}/${item.page}` : "/projects";
}

/** The nav group (breadcrumb label) a path belongs to, if any. */
export function crumbFor(pathname: string): string | null {
  const last = pathname.split("/").filter(Boolean).at(-1) ?? "";
  for (const group of NAV) {
    for (const item of group.items) {
      if (item.page === last || item.href === pathname) return group.crumb === "Start here" ? null : group.crumb;
    }
  }
  return null;
}
