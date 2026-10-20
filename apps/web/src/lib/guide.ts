/**
 * The web app's user guide: an overview, then one entry per page in
 * sidebar order. The sidebar shows a page's ``steps`` under "Guide for this
 * page" (keyed by the page's last path segment); /guide shows everything.
 */

export type GuidePage = { key: string; title: string; step: string; summary: string; steps: string[] };

export const QUICK_START: string[] = [
  "Create an account (or sign in), then create a project for each client engagement under Projects.",
  "An admin adds the workspace's HubSpot private app token (read-only scopes) and an AI key (Gemini or Anthropic) under Setup & API keys — once, for everyone.",
  "Open the project and work left to right through the five RevOps steps in the left rail. Every page saves to the project as you go; there is no Save button.",
  "Anything you export can also be filed in the project's library with “Save to Project Library”.",
  "Found a bug or have an idea? Use the Feedback button (bottom right of every page) — attach screenshots with + or paste them.",
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
    steps: [
      "Create a project per client engagement, optionally in a folder (e.g. one folder per client), then open it.",
      "Search by name, client, folder or person, or filter by folder and by who is in charge.",
      "Each card shows who is in charge and who edited it last. Edit changes the name, client, folder or person in charge; Delete (for the person in charge, the creator or an admin) removes the project and its saved documents after a confirmation.",
      "Rename a folder with the pencil next to its name; every project in it moves to the new name.",
    ],
  },
  {
    key: "settings",
    title: "Setup & API keys",
    step: "Start here",
    summary: "Workspace-wide connections, stored encrypted.",
    steps: [
      "The HubSpot token and AI keys are stored encrypted for the whole workspace; only admins can change them.",
      "Use a HubSpot private app with read-only scopes — The Hub Zone never creates, changes or deletes anything in HubSpot.",
      "Gemini keys are free from aistudio.google.com/apikey; when one is set, drafting uses Gemini instead of Claude. Anthropic keys start with sk-ant-.",
    ],
  },
  {
    key: "account",
    title: "Profile & account",
    step: "Account",
    summary: "Your name, your password and the browsers signed in to your account.",
    steps: [
      "Change your display name; it's what teammates see on projects you lead or edit.",
      "Changing your password signs out every other browser; this one stays signed in.",
      "Lost a laptop or used a shared computer? Sign out other browsers.",
    ],
  },
  {
    key: "tasks",
    title: "Tasks & progress",
    step: "Project",
    summary: "The team's internal checklist for this project, grouped by stage, with owners, dates and progress.",
    steps: [
      "Fill the list with “Suggest tasks with AI” (reads everything the project holds so far) or “Pull from discovery” (the discovery call's required tasks and build order, under Build). Add your own under any stage.",
      "Ticking a task records when and by whom. Open “Source details” to see why it's needed, “Add notes” to keep decisions and context, and “Attach file” to keep documents with it (they're also saved to the Project Library).",
      "Each stage starts the day its first task is checked and finishes when its last one is; set who is in charge and adjust the dates whenever you need.",
      "Download the progress report for the client — stages, owners, dates and what's done. Task notes stay out unless you tick “Include task notes”.",
    ],
  },
  {
    key: "discovery",
    title: "Discovery Call Assistant",
    step: "Step 1 · Discover",
    summary: "Live notes during the discovery call, with follow-ups, required tasks, a checklist and a build order.",
    steps: [
      "Type notes live during the call — shorthand is fine, blanks are fine. Answer under Goals, Data, Processes and Solutions Design in any order; blanks become follow-up questions, never guesses.",
      "Know the client's industry? Apply an industry template to pre-fill typical answers for unanswered questions, then confirm each one on the call.",
      "The client's website is read when you generate the business analysis, for a client snapshot, advantages and upsell ideas.",
      "Some answers reveal follow-ups under them and add required tasks; tick tasks off as they're covered.",
      "After the call, generate the business analysis, then the client explainer, checklist and build order.",
      "Drafting takes a minute or two; the progress bar shows which section is being written. If the AI service is busy, the app retries and switches model automatically — or pick a model yourself in the “AI model” menu next to Generate.",
      "The checklist is a client-ready record of what must be configured; Status / Notes is left blank for the delivery team. Required tasks come from answers — confirm scope, owners and commercial terms before treating it as a statement of work.",
      "Build order: create consent assets and core fields first, then lists, pipelines and record pages. Review each template against the client's legal and operational needs before reuse. The .json export keeps task names, sources, template tags and completion for a task tool.",
      "“Start a new call” clears this project's answers and notes only — download a backup first.",
      "Sales pipeline stages: add each stage with its win probability; drag the handle (or use the arrow keys on it) to reorder. “Start from HubSpot's default stages” fills a starting pipeline.",
      "Optional: “5 · Company overview” reads the client's website and summarises the company — type, offerings, highlights, things to know and questions to ask. It also feeds the other AI suggestions.",
    ],
  },
  {
    key: "stage-planner",
    title: "Deal Stage Planner",
    step: "Step 1 · Discover",
    summary: "A spreadsheet the client fills in before the call, imported back to shape discovery and the architecture.",
    steps: [
      "Send the client the pre-call template: one column per pipeline stage with forecast %, entry and exit criteria, desired actions, automations and the deal properties required at that stage. It starts with HubSpot's default sales stages.",
      "No planner from the client? “Fill from the discovery call” drafts the stages from your call notes; with stages already there, it only fills empty cells.",
      "Import the filled-out copy: rows are matched by their label in column A, so inserted, moved or deleted rows are fine; blank and “Stage name” columns are skipped.",
      "Review and edit the stages (in pipeline order), check what each target gets in the preview, then Apply — nothing is applied or sent to HubSpot until you click it.",
    ],
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
      "“Uses” counts references in workflow actions only — forms, lists, reports and dashboards aren't pulled, so a property used only there still shows 0.",
    ],
  },
  {
    key: "documentation",
    title: "Documentation Generator",
    step: "Step 2 · Assess current portal",
    summary: "The portal's data dictionary, workflows, associations, pipelines, teams and owners.",
    steps: [
      "Pull from HubSpot, review each section, then download Word or Markdown or save it to the library.",
      "The association map comes from each custom object's schema; default associations between standard objects aren't exposed by HubSpot's endpoint and are omitted.",
    ],
  },
  {
    key: "executive-report",
    title: "Executive Report",
    step: "Step 2 · Assess current portal",
    summary: "A plain-language report: what the portal has and what's worth fixing.",
    steps: [
      "Uses the saved snapshot and audit findings — run the Portal Auditor first for the “Things worth fixing” section.",
      "The client version is polished and plain-language, safe to send as-is; the internal version has every finding and the raw property groups.",
    ],
  },
  {
    key: "architecture",
    title: "Architecture Generator",
    step: "Step 3 · Design",
    summary: "A HubSpot blueprint from a few project questions.",
    steps: [
      "“Fill from earlier steps” adds what the discovery call, requirements and plan imply; nothing selected or typed is removed.",
      "Pick objects, pipelines, integrations, regions and hubs. Not in the list? Type it and choose “Add”. Known custom-object keywords come with properties and associations; your own become a generic object to define with the client.",
      "Record volumes go one per line as Object: count. An applied Deal Stage Planner replaces the default deal pipeline.",
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
      "Choosing a source again resets your edits. Run the Portal Auditor first to highlight findings on a snapshot diagram.",
      "Colors: filled purple = custom object, white = standard, dashed grey = activity object; the border shows the worst finding (red High, orange Medium, yellow Low).",
      "Connections are drawn only when From / To match an object name in the Objects table.",
      "Focus on a few objects to narrow the drawing; the .drawio file opens in diagrams.net (free, no login) for drag-and-drop editing, and the PNG uses the same layout.",
    ],
  },
  {
    key: "proposal",
    title: "Proposal & SOW Builder",
    step: "Step 4 · Propose",
    summary: "A proposal and Statement of Work: technical, scope, management and cost.",
    steps: [
      "Starting from scratch? “Suggest a starting point” drafts the summary, problem, solution, objectives, scope, assumptions, risks and KPIs from earlier steps — only blanks are filled. Or apply an industry template for typical scope, risks and KPIs by industry and company size.",
      "New proposal for a client like one you've done before? Use “Start from a template” at the top — your team's saved proposals keep everything except the client's details.",
      "Finished a good one? “Save as template” makes it available to everyone in the workspace for similar clients.",
      "Import the Requirements Document and Joint Evaluation Plan in Setup — imports only fill blanks and add rows the proposal doesn't have yet, so importing twice adds nothing.",
      "Technical: show you understand the problem and how it will be solved. Start lines with “- ” for bullets in the PDF. Requirements and scope items get the next ID (R-1, S-1…) automatically.",
      "Scope is the section clients misread most: put every item in exactly one bucket, give In Scope items a quantity limit and acceptance criteria, and list common requests you're not doing as Out of Scope. “Req. ID” links a scope item to the requirements it delivers (e.g. R-1, R-3); the coverage table shows any requirement no scope item addresses.",
      "Management covers team, governance, schedule, risks and KPIs (Primary: value drivers tied to ROI; Secondary: operational or marketing improvements). Cost: milestone fees, the add-on menu (tick “Add to total” for add-ons already chosen) and the rate card for change requests.",
      "Review & generate checks for gaps before you download the PDF. The reusable template download keeps only SonaMation's standard parts (methodology, tools, governance, add-ons, rate card, terms).",
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

/** The rail's "Guide for this page" lines by the page's last path segment. */
export const GUIDE: Record<string, string[]> = Object.fromEntries(GUIDE_PAGES.map((p) => [p.key, p.steps]));
