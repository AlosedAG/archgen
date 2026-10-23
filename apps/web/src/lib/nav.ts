/**
 * The app's navigation tree — one config drives the icon rail and its
 * flyouts, the breadcrumb, and the top-bar search.
 *
 * A link is one of:
 *   `page` — a project page at /projects/:id/<page> (needs an open project);
 *   `href` — a fixed route;
 *   `soon` — not built yet: links to its "Coming soon" page at /soon/<soon>
 *            and wears a "Soon" tag in the flyout.
 */

import type { NavIconName } from "@/components/NavIcons";

/** `adminOnly` items are hidden from members who aren't workspace owners or admins. */
export type NavItem = { label: string; icon: NavIconName; page?: string; href?: string; soon?: string; adminOnly?: boolean };
export type NavGroup = { label: string; items: NavItem[] };
export type NavSection = {
  id: string;
  label: string;
  icon: NavIconName;
  /** Small pill beside the flyout title. */
  tag?: string;
  /** Project-scoped sections: their pages need an open project. */
  scoped?: boolean;
  groups: NavGroup[];
};

export const NAV: NavSection[] = [
  {
    id: "revops",
    label: "RevOps",
    icon: "trend",
    tag: "SCOPE",
    scoped: true,
    groups: [
      {
        label: "1 · Discover",
        items: [
          { label: "Discovery Call Assistant", icon: "chat", page: "discovery" },
          { label: "Deal Stage Planner", icon: "cols", page: "stage-planner" },
          { label: "Requirements Document", icon: "doc", page: "requirements" },
          { label: "Joint Evaluation Plan", icon: "clip", page: "evaluation-plan" },
        ],
      },
      {
        label: "2 · Assess",
        items: [
          { label: "Portal Auditor", icon: "gauge", page: "portal-audit" },
          { label: "Property Audit", icon: "list", page: "property-audit" },
          { label: "Documentation Generator", icon: "files", page: "documentation" },
          { label: "Executive Report", icon: "chart", page: "executive-report" },
        ],
      },
      {
        label: "3 · Design",
        items: [
          { label: "Architecture Generator", icon: "cube", page: "architecture" },
          { label: "Architecture Diagram", icon: "share", page: "diagram" },
        ],
      },
      { label: "4 · Propose", items: [{ label: "Proposal & SOW Builder", icon: "sign", page: "proposal" }] },
      {
        label: "5 · Deliver",
        items: [
          { label: "QA Reports", icon: "shield", page: "test-cases" },
          { label: "Schedule Planner", icon: "cal", page: "schedule-planner" },
        ],
      },
    ],
  },
  {
    id: "implementation",
    label: "Implementation",
    icon: "layers",
    groups: [
      {
        label: "",
        items: [
          { label: "Projects", icon: "grid", href: "/projects" },
          { label: "Tasks", icon: "check", page: "tasks" },
          { label: "Project Library", icon: "files", page: "library" },
          { label: "Dashboard", icon: "layout", soon: "implementation-dashboard" },
          { label: "Schedule", icon: "cal", soon: "schedule" },
          { label: "Review & Feedback", icon: "chat", soon: "review-feedback" },
        ],
      },
    ],
  },
  {
    id: "data",
    label: "Data",
    icon: "database",
    groups: [
      {
        label: "",
        items: [
          { label: "Database", icon: "db", soon: "database" },
          { label: "Data Documentation", icon: "files", soon: "data-documentation" },
          { label: "AI Guide", icon: "spark", soon: "ai-guide" },
          { label: "Management", icon: "sliders", soon: "data-management" },
        ],
      },
    ],
  },
  {
    id: "service",
    label: "Service",
    icon: "lifebuoy",
    groups: [
      {
        label: "",
        items: [
          { label: "Customer Success", icon: "heart", soon: "customer-success" },
          { label: "Knowledge Base", icon: "book", soon: "knowledge-base" },
          { label: "Subscriptions & Memberships", icon: "card", soon: "subscriptions" },
        ],
      },
    ],
  },
  {
    id: "marketing",
    label: "Marketing",
    icon: "megaphone",
    groups: [
      {
        label: "",
        items: [
          { label: "Marketing Dashboard", icon: "layout", soon: "marketing-dashboard" },
          { label: "Leads", icon: "userplus", soon: "leads" },
          { label: "Studio", icon: "wand", soon: "studio" },
          { label: "Social", icon: "share", soon: "social" },
        ],
      },
    ],
  },
  {
    id: "developers",
    label: "Developers",
    icon: "code",
    groups: [
      {
        label: "",
        items: [
          { label: "API Keys", icon: "key", href: "/settings" },
          { label: "Integrations", icon: "plug", soon: "integrations" },
          { label: "Webhooks", icon: "share", soon: "webhooks" },
          { label: "Logs", icon: "term", soon: "logs" },
        ],
      },
    ],
  },
];

/** The rail footer's Help section. "Send feedback" opens the feedback panel instead of navigating. */
export const HELP: NavSection = {
  id: "help",
  label: "Help",
  icon: "help",
  groups: [
    {
      label: "",
      items: [
        { label: "User Guide", icon: "book", href: "/guide" },
        { label: "Send Feedback", icon: "chat", href: "#feedback" },
        { label: "Setup & API Keys", icon: "key", href: "/settings" },
        { label: "Hubzy Answers", icon: "chat", href: "/settings/hubzy", adminOnly: true },
        { label: "SOW Clause Library", icon: "sign", href: "/settings/clauses", adminOnly: true },
      ],
    },
  ],
};

/** Copy for each "Coming soon" page, keyed by the item's `soon` slug. */
export const SOON_COPY: Record<string, string> = {
  "implementation-dashboard": "One view of every implementation: progress, blockers and what's due next.",
  schedule: "A calendar of every project's milestones and sessions.",
  "review-feedback": "Collect client reviews and sign-offs on deliverables in one place.",
  database: "Browse the HubSpot objects and records captured in your read-only snapshots.",
  "data-documentation": "A living data dictionary for each portal's objects, properties and associations.",
  "ai-guide": "Ask questions about a portal's data model and get guided answers.",
  "data-management": "Track data-quality issues and clean-up plans across portals.",
  "customer-success": "Health scores, renewals and success plans for each client.",
  "knowledge-base": "Your team's reusable articles, playbooks and how-tos.",
  subscriptions: "Manage client retainers, subscriptions and memberships.",
  "marketing-dashboard": "Marketing performance across your clients at a glance.",
  leads: "Lead sources, routing and qualification for your pipeline.",
  studio: "Draft campaign assets and content with AI.",
  social: "Plan and review social content.",
  integrations: "Connect the other tools your clients use, alongside HubSpot.",
  webhooks: "Get notified in other tools when something changes here.",
  logs: "A record of API calls and background jobs.",
};

const ALL: NavSection[] = [...NAV, HELP];

/** The link for a nav item: project pages need a project (else they go to the project list). */
export function hrefFor(item: NavItem, projectId: string | null): string {
  if (item.soon) return `/soon/${item.soon}`;
  if (item.href) return item.href;
  return projectId ? `/projects/${projectId}/${item.page}` : "/projects";
}

export function itemsOf(section: NavSection): NavItem[] {
  return section.groups.flatMap((g) => g.items);
}

/** Is this item the page being shown? */
export function isCurrent(item: NavItem, pathname: string, projectId: string | null): boolean {
  if (item.soon) return pathname === `/soon/${item.soon}`;
  if (item.page) return Boolean(projectId) && pathname.startsWith(`/projects/${projectId}/${item.page}`);
  return pathname === item.href;
}

/** The section and item for the current page, if it's in the nav (first match wins). */
export function locate(pathname: string, projectId: string | null): { section: NavSection; item: NavItem } | null {
  for (const section of ALL) {
    for (const item of itemsOf(section)) {
      if (isCurrent(item, pathname, projectId)) return { section, item };
    }
  }
  return null;
}

/** Every navigable page, for the search. */
export function searchablePages(isAdmin: boolean): { section: NavSection; item: NavItem }[] {
  return ALL.flatMap((section) =>
    itemsOf(section)
      .filter((item) => !item.href?.startsWith("#") && (isAdmin || !item.adminOnly))
      .map((item) => ({ section, item })),
  );
}
