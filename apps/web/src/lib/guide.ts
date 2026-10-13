/**
 * The web app's user guide: an overview, then one entry per page in
 * sidebar order. The sidebar shows a page's ``steps`` under "Guide for this
 * page" (keyed by the page's last path segment); /guide shows everything.
 */

export type GuidePage = { key: string; title: string; step: string; summary: string; steps: string[] };

export const QUICK_START: string[] = [
  "Create an account (or sign in), then create a project for each client engagement under Projects.",
  "An admin adds the workspace's HubSpot private app token (read-only scopes) and an AI key (Gemini or Anthropic) under Setup & API keys — once, for everyone.",
  "Open the project and work left to right through the five steps in the sidebar. Every page saves to the project as you go; there is no Save button.",
  "Anything you export can also be filed in the project's library with “Save to Project Library”.",
];

export const PROCESS: { step: string; text: string }[] = [
  { step: "1 · Discover", text: "Run the discovery call, plan the deal stages, and write up requirements and the joint evaluation plan." },
  { step: "2 · Assess current portal", text: "Pull a read-only snapshot of the client's HubSpot, audit it, rate every property, document it, and report on it." },
  { step: "3 · Design", text: "Generate the target architecture and draw it." },
  { step: "4 · Propose", text: "Turn the requirements and plan into a proposal and Statement of Work." },
  { step: "5 · Deliver & test", text: "Track QA and UAT against the requirements." },
];

export const GUIDE_PAGES: GuidePage[] = [
  {
    key: "projects",
    title: "Projects",
    step: "Start here",
    summary: "Each client engagement is a project; everything you write is saved to it.",
    steps: ["Create a project per client engagement, then open it to work on its discovery call and documents."],
  },
  {
    key: "settings",
    title: "Setup & API keys",
    step: "Start here",
    summary: "Workspace-wide connections, stored encrypted.",
    steps: [
      "The HubSpot token and AI keys are stored encrypted for the whole workspace; only admins can change them.",
      "Use a HubSpot private app with read-only scopes — ArchitectureScope never creates, changes or deletes anything in HubSpot.",
    ],
  },
  {
    key: "discovery",
    title: "Discovery Call Assistant",
    step: "Step 1 · Discover",
    summary: "Live notes during the discovery call, with follow-ups, required tasks, a checklist and a build order.",
    steps: [
      "Answer under Goals, Data, Processes and Solutions Design in any order — blanks become follow-up questions, never guesses.",
      "Some answers reveal follow-ups under them and add required tasks; tick tasks off as they're covered.",
      "After the call, generate the business analysis, then the client explainer, checklist and build order.",
    ],
  },
  {
    key: "stage-planner",
    title: "Deal Stage Planner",
    step: "Step 1 · Discover",
    summary: "A spreadsheet the client fills in before the call, imported back to shape discovery and the architecture.",
    steps: ["Send the client the planner before the call; import the filled-out copy, review it, then apply it."],
  },
  {
    key: "requirements",
    title: "Requirements Document",
    step: "Step 1 · Discover",
    summary: "HubSpot's Written Requirements Document structure.",
    steps: ["Purpose, goals, numbered requirements, terms, risks, plan and questions. Saves to the project as you type."],
  },
  {
    key: "evaluation-plan",
    title: "Joint Evaluation Plan",
    step: "Step 1 · Discover",
    summary: "What needs to happen, when, and who's involved during the evaluation.",
    steps: ["Milestones, team, technical and business needs, and questions for the evaluation. Saves as you type."],
  },
  {
    key: "portal-audit",
    title: "Portal Auditor",
    step: "Step 2 · Assess current portal",
    summary: "Best-practice checks against a read-only snapshot of the client's portal.",
    steps: [
      "Pull from HubSpot once — the snapshot is saved to the project and shared by every Step 2 page and the diagram.",
      "Run the audit, then filter findings by severity and area. Findings feed the Executive Report and the diagram.",
      "Record-level checks sample records per object rather than reading everything, and say so in each finding.",
    ],
  },
  {
    key: "property-audit",
    title: "Property Audit",
    step: "Step 2 · Assess current portal",
    summary: "Keep / Review / Remove candidate for every property, from fill rate and workflow use.",
    steps: [
      "Run it on the saved snapshot; only custom properties are ever flagged.",
      "Export the color-matched workbook for the client to confirm before anything is deleted — this tool never deletes.",
    ],
  },
  {
    key: "documentation",
    title: "Documentation Generator",
    step: "Step 2 · Assess current portal",
    summary: "The portal's data dictionary, workflows, associations, pipelines, teams and owners.",
    steps: ["Pull from HubSpot, review each section, then download Word or Markdown or save it to the library."],
  },
  {
    key: "executive-report",
    title: "Executive Report",
    step: "Step 2 · Assess current portal",
    summary: "A plain-language report: what the portal has and what's worth fixing.",
    steps: [
      "Uses the saved snapshot and audit findings — run the Portal Auditor first for the “Things worth fixing” section.",
      "The client version is safe to send as-is; the internal version has every finding.",
    ],
  },
  {
    key: "architecture",
    title: "Architecture Generator",
    step: "Step 3 · Design",
    summary: "A HubSpot blueprint from a few project questions.",
    steps: [
      "Pick objects, pipelines, integrations, regions and hubs; an applied Deal Stage Planner replaces the default deal pipeline.",
      "Generate the blueprint, review it, and export or save it. No HubSpot access needed.",
    ],
  },
  {
    key: "diagram",
    title: "Architecture Diagram",
    step: "Step 3 · Design",
    summary: "An editable map of objects and connections, with findings highlighted.",
    steps: [
      "Build it from the blueprint or the live snapshot, then fix anything in the Objects and Connections tables.",
      "Focus on a few objects to narrow the drawing; download .drawio for drag-and-drop editing in diagrams.net.",
    ],
  },
  {
    key: "proposal",
    title: "Proposal & SOW Builder",
    step: "Step 4 · Propose",
    summary: "A proposal and Statement of Work: technical, scope, management and cost.",
    steps: [
      "Import the Requirements Document and Joint Evaluation Plan in Setup — imports only fill blanks and append rows.",
      "Put every scope item in exactly one bucket; the coverage table shows requirements no scope item addresses.",
      "Review & generate checks for gaps before you download the PDF.",
    ],
  },
  {
    key: "test-cases",
    title: "Test Case Document",
    step: "Step 5 · Deliver & test",
    summary: "QA and UAT test cases against the requirements.",
    steps: ["Load the Requirements Document's requirements as a starting point, then record QA and UAT results."],
  },
  {
    key: "library",
    title: "Project Library",
    step: "Library",
    summary: "Every document saved from this project's pages.",
    steps: ["Newest first. Download or delete them here."],
  },
];

export const TROUBLESHOOTING: { problem: string; fix: string }[] = [
  { problem: "“HubSpot isn't connected”", fix: "An admin adds the HubSpot private app token under Setup & API keys." },
  { problem: "Part of the portal couldn't be read", fix: "The private app is missing a read scope for that area. Add it in HubSpot and pull again." },
  { problem: "“This was changed somewhere else”", fix: "Someone saved the same page in another tab. Reload the saved version, then redo your last edit." },
  { problem: "AI drafts don't start", fix: "The workspace needs a Gemini or Anthropic API key under Setup & API keys. On Gemini's free tier, a quota message means today's free runs are used up." },
  { problem: "No verification email", fix: "Check spam, wait a minute and use “Send a new code”. Codes expire after 15 minutes." },
];

/** Sidebar guide lines by the page's last path segment. */
export const GUIDE: Record<string, string[]> = Object.fromEntries(GUIDE_PAGES.map((p) => [p.key, p.steps]));
