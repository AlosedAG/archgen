"""The questions and answers Hubzy starts with in every workspace. Admins
edit their own copy in the app (Help > Hubzy Answers); this list only seeds
it the first time. ``page`` is a page key (the last part of its URL) or "" for
every page."""

from __future__ import annotations

# (page, question, answer)
DEFAULT_TOPICS: list[tuple[str, str, str]] = [
    (
        "",
        "What is The Hub Zone?",
        "The Hub Zone is your team's workspace for HubSpot implementations. Each client engagement is a project, and the RevOps steps in the left rail take it from the discovery call through the portal audit, the target architecture and the proposal to delivery and testing. Everything you write is saved to the project as you go.",
    ),
    (
        "",
        "How do I start a project?",
        'Go to Projects (Implementation in the left rail), type the client or project name under "New client / project", optionally pick a folder, and press Create project. You land straight in its Discovery Call Assistant.',
    ),
    (
        "",
        "Where are my saved documents?",
        'In the project\'s Project Library (Implementation in the left rail). Anything you export can be filed there with "Save to Project Library", so the whole team finds it in one place.',
    ),
    (
        "",
        "Who can change the HubSpot token and AI keys?",
        "Only workspace owners and admins, under Help > Setup & API Keys. Everyone else can see what's connected, but not change it. Keys are stored encrypted and never shown again after saving.",
    ),
    (
        "",
        "How do I report a bug or share an idea?",
        "Use Send Feedback under Help in the left rail. Pick Bug, Idea or Question, describe it, and attach screenshots with + or by pasting. It goes straight to the app owner with the page and project filled in.",
    ),
    (
        "",
        "What is HubSpot?",
        "HubSpot is a customer platform built around one shared CRM. Its Hubs (Marketing, Sales, Service, Content, Data and Commerce) all read and write the same contacts, companies, deals and tickets, so every team works from the same record.",
    ),
    (
        "",
        "What is Marketing Hub?",
        "Marketing Hub is HubSpot's marketing software: email, forms, landing pages, ads, social, SEO and marketing automation, all tied to the CRM so you can see which campaigns create leads and revenue. It comes in Free, Starter, Professional and Enterprise tiers.",
    ),
    (
        "",
        "What is Sales Hub?",
        "Sales Hub is HubSpot's sales software: deal pipelines, email tracking and templates, sequences, meeting scheduling, quotes, forecasting and sales analytics, all on the shared CRM.",
    ),
    (
        "",
        "What is Service Hub?",
        "Service Hub is HubSpot's customer service software: tickets and help desk, a shared inbox, knowledge base, customer portal and feedback surveys, so support sees the same customer record as sales and marketing.",
    ),
    (
        "",
        "What is Content Hub?",
        "Content Hub (formerly CMS Hub) is HubSpot's website and content tool: website pages, blogs, landing pages and a content library, with personalisation driven by CRM data.",
    ),
    (
        "",
        "What is Data Hub?",
        "Data Hub (formerly Operations Hub) keeps HubSpot's data clean and connected: data sync with other apps, data quality tools, programmable automation and datasets for reporting.",
    ),
    (
        "",
        "What is Commerce Hub?",
        "Commerce Hub brings quotes, invoices, payments and subscriptions into HubSpot, so billing lives next to the deals and customers it belongs to.",
    ),
    (
        "",
        "What is RevOps?",
        "Revenue Operations (RevOps) lines up marketing, sales and service around one revenue process: shared data, shared definitions (like what counts as a qualified lead), connected tools and one set of reports. The Hub Zone's RevOps steps follow that journey for a client.",
    ),
    (
        "",
        "What is a SOW?",
        "A Statement of Work (SOW) pins a project down: scope, deliverables, timeline, who does what, assumptions and price, agreed by both sides before work starts. You build one in Proposal & SOW Builder (RevOps, step 4 Propose).",
    ),
    (
        "",
        "What is a HubSpot portal?",
        "A portal is one HubSpot account, identified by its Hub ID. A client usually has one production portal, and Enterprise accounts can also have sandbox portals for testing.",
    ),
    (
        "",
        "What is a private app token?",
        "A private app is how a HubSpot admin gives another tool access to their portal. It comes with a token and a list of scopes (permissions). The Hub Zone only needs read-only scopes, because it never changes anything in HubSpot.",
    ),
    (
        "",
        "What is a lifecycle stage?",
        "A lifecycle stage says where a contact or company is in its relationship with the business. The defaults run Subscriber, Lead, Marketing qualified lead, Sales qualified lead, Opportunity, Customer and Evangelist, plus Other.",
    ),
    (
        "",
        "What is a deal pipeline?",
        "A deal pipeline is the series of stages a deal moves through, from first contact to closed won or lost. Each stage has a win probability, and a portal can have several pipelines for different sales processes.",
    ),
    (
        "",
        "What is a property?",
        "A property is a field on a HubSpot record, like a contact's email or a deal's amount. Portals come with default properties, and teams add custom ones for their own data.",
    ),
    (
        "",
        "What is a workflow?",
        "A workflow is HubSpot's automation: when a record meets the enrollment triggers, it goes through actions like sending an email, setting a property, creating a task or rotating an owner.",
    ),
    (
        "projects",
        "What does this page do?",
        "Each client engagement is a project; everything you write is saved to it.\n\n• Create a project per client engagement, optionally in a folder (e.g. one folder per client), then open it.\n• Search by name, client, folder or person, or filter by folder and by who is in charge.\n• Each card shows who is in charge and who edited it last. Edit changes the name, client, folder or person in charge; Delete (for the person in charge, the creator or an admin) removes the project and its saved documents after a confirmation.\n• Rename a folder with the pencil next to its name; every project in it moves to the new name.",
    ),
    (
        "settings",
        "What does this page do?",
        "Workspace-wide connections, stored encrypted.\n\n• The HubSpot token and AI keys are stored encrypted for the whole workspace; only admins can change them.\n• Use a HubSpot private app with read-only scopes — The Hub Zone never creates, changes or deletes anything in HubSpot.\n• Gemini keys are free from aistudio.google.com/apikey; when one is set, drafting uses Gemini instead of Claude. Anthropic keys start with sk-ant-.",
    ),
    (
        "hubzy",
        "What does this page do?",
        'The questions Hubzy, the assistant in the corner, offers when someone clicks him, and his answers. Admins only.\n\n• Each row is one question and its answer. Edit any cell, add a question at the bottom, or remove a row with its x.\n• "Shows on" picks where a question appears: on every page, or only on one page, where it\'s listed first.\n• Nothing changes until you press Save changes; Discard changes puts the table back as it was.\n• Every workspace starts with answers about the platform and HubSpot, plus a "What does this page do?" for each page.',
    ),
    (
        "account",
        "What does this page do?",
        "Your name, your password and the browsers signed in to your account.\n\n• Change your display name; it's what teammates see on projects you lead or edit.\n• Changing your password signs out every other browser; this one stays signed in.\n• Lost a laptop or used a shared computer? Sign out other browsers.",
    ),
    (
        "tasks",
        "What does this page do?",
        "The team's internal checklist for this project, grouped by stage, with owners, dates and progress.\n\n• Fill the list with “Suggest tasks with AI” (reads everything the project holds so far) or “Pull from discovery” (the discovery call's required tasks and build order, under Build). Add your own under any stage.\n• Ticking a task records when and by whom. Open “Source details” to see why it's needed, “Add notes” to keep decisions and context, and “Attach file” to keep documents with it (they're also saved to the Project Library).\n• Each stage starts the day its first task is checked and finishes when its last one is; set who is in charge and adjust the dates whenever you need.\n• Download the progress report for the client — stages, owners, dates and what's done. Task notes stay out unless you tick “Include task notes”.",
    ),
    (
        "discovery",
        "What does this page do?",
        "Live notes during the discovery call, with follow-ups, required tasks, a checklist and a build order.\n\n• Type notes live during the call — shorthand is fine, blanks are fine. Answer under Goals, Data, Processes and Solutions Design in any order; blanks become follow-up questions, never guesses.\n• Know the client's industry? Apply an industry template to pre-fill typical answers for unanswered questions, then confirm each one on the call.\n• The client's website is read when you generate the business analysis, for a client snapshot, advantages and upsell ideas.\n• Some answers reveal follow-ups under them and add required tasks; tick tasks off as they're covered.\n• After the call, generate the business analysis, then the client explainer, checklist and build order.\n• Drafting takes a minute or two; the progress bar shows which section is being written. If the AI service is busy, the app retries and switches model automatically — or pick a model yourself in the “AI model” menu next to Generate.\n• The checklist is a client-ready record of what must be configured; Status / Notes is left blank for the delivery team. Required tasks come from answers — confirm scope, owners and commercial terms before treating it as a statement of work.\n• Build order: create consent assets and core fields first, then lists, pipelines and record pages. Review each template against the client's legal and operational needs before reuse. The .json export keeps task names, sources, template tags and completion for a task tool.\n• “Start a new call” clears this project's answers and notes only — download a backup first.\n• Sales pipeline stages: add each stage with its win probability; drag the handle (or use the arrow keys on it) to reorder. “Start from HubSpot's default stages” fills a starting pipeline.\n• Optional: “5 · Company overview” reads the client's website and summarises the company — type, offerings, highlights, things to know and questions to ask. It also feeds the other AI suggestions.",
    ),
    (
        "stage-planner",
        "What does this page do?",
        "A spreadsheet the client fills in before the call, imported back to shape discovery and the architecture.\n\n• Send the client the pre-call template: one column per pipeline stage with forecast %, entry and exit criteria, desired actions, automations and the deal properties required at that stage. It starts with HubSpot's default sales stages.\n• No planner from the client? “Fill from the discovery call” drafts the stages from your call notes; with stages already there, it only fills empty cells.\n• Import the filled-out copy: rows are matched by their label in column A, so inserted, moved or deleted rows are fine; blank and “Stage name” columns are skipped.\n• Review and edit the stages (in pipeline order), check what each target gets in the preview, then Apply — nothing is applied or sent to HubSpot until you click it.",
    ),
    (
        "requirements",
        "What does this page do?",
        "HubSpot's Written Requirements Document structure.\n\n• Purpose, goals, numbered requirements, terms, risks, plan and questions. Saves to the project as you type.",
    ),
    (
        "evaluation-plan",
        "What does this page do?",
        "What needs to happen, when, and who's involved during the evaluation.\n\n• Milestones, team, technical and business needs, and questions for the evaluation. Saves as you type.",
    ),
    (
        "portal-audit",
        "What does this page do?",
        "Best-practice checks against a read-only snapshot of the client's portal.\n\n• Pull from HubSpot once — the snapshot is saved to the project and shared by every Step 2 page and the diagram.\n• Run the audit, then filter findings by severity and area. Findings feed the Executive Report and the diagram.\n• Record-level checks sample records per object rather than reading everything, and say so in each finding.",
    ),
    (
        "property-audit",
        "What does this page do?",
        "Keep / Review / Remove candidate for every property, from fill rate and workflow use.\n\n• Run it on the saved snapshot; only custom properties are ever flagged.\n• Export the color-matched workbook for the client to confirm before anything is deleted — this tool never deletes.\n• “Uses” counts references in workflow actions only — forms, lists, reports and dashboards aren't pulled, so a property used only there still shows 0.",
    ),
    (
        "documentation",
        "What does this page do?",
        "The portal's data dictionary, workflows, associations, pipelines, teams and owners.\n\n• Pull from HubSpot, review each section, then download Word or Markdown or save it to the library.\n• The association map comes from each custom object's schema; default associations between standard objects aren't exposed by HubSpot's endpoint and are omitted.",
    ),
    (
        "executive-report",
        "What does this page do?",
        "A plain-language report: what the portal has and what's worth fixing.\n\n• Uses the saved snapshot and audit findings — run the Portal Auditor first for the “Things worth fixing” section.\n• The client version is polished and plain-language, safe to send as-is; the internal version has every finding and the raw property groups.",
    ),
    (
        "architecture",
        "What does this page do?",
        "A HubSpot blueprint from a few project questions.\n\n• “Fill from earlier steps” adds what the discovery call, requirements and plan imply; nothing selected or typed is removed.\n• Pick objects, pipelines, integrations, regions and hubs. Not in the list? Type it and choose “Add”. Known custom-object keywords come with properties and associations; your own become a generic object to define with the client.\n• Record volumes go one per line as Object: count. An applied Deal Stage Planner replaces the default deal pipeline.\n• Generate the blueprint, review it, and export or save it. No HubSpot access needed.",
    ),
    (
        "diagram",
        "What does this page do?",
        "An editable map of objects and connections, with findings highlighted.\n\n• Build it from the blueprint or the live snapshot, then fix anything in the Objects and Connections tables.\n• Choosing a source again resets your edits. Run the Portal Auditor first to highlight findings on a snapshot diagram.\n• Colors: filled purple = custom object, white = standard, dashed grey = activity object; the border shows the worst finding (red High, orange Medium, yellow Low).\n• Connections are drawn only when From / To match an object name in the Objects table.\n• Focus on a few objects to narrow the drawing; the .drawio file opens in diagrams.net (free, no login) for drag-and-drop editing, and the PNG uses the same layout.",
    ),
    (
        "proposal",
        "What does this page do?",
        "A proposal and Statement of Work: technical, scope, management and cost.\n\n• Starting from scratch? “Suggest a starting point” drafts the summary, problem, solution, objectives, scope, assumptions, risks and KPIs from earlier steps — only blanks are filled. Or apply an industry template for typical scope, risks and KPIs by industry and company size.\n• New proposal for a client like one you've done before? Use “Start from a template” at the top — your team's saved proposals keep everything except the client's details.\n• Finished a good one? “Save as template” makes it available to everyone in the workspace for similar clients.\n• Import the Requirements Document and Joint Evaluation Plan in Setup — imports only fill blanks and add rows the proposal doesn't have yet, so importing twice adds nothing.\n• Technical: show you understand the problem and how it will be solved. Start lines with “- ” for bullets in the PDF. Requirements and scope items get the next ID (R-1, S-1…) automatically.\n• Scope is the section clients misread most: put every item in exactly one bucket, give In Scope items a quantity limit and acceptance criteria, and list common requests you're not doing as Out of Scope. “Req. ID” links a scope item to the requirements it delivers (e.g. R-1, R-3); the coverage table shows any requirement no scope item addresses.\n• Management covers team, governance, schedule, risks and KPIs (Primary: value drivers tied to ROI; Secondary: operational or marketing improvements). Cost: milestone fees, the add-on menu (tick “Add to total” for add-ons already chosen) and the rate card for change requests.\n• Review & generate checks for gaps before you download the PDF. The reusable template download keeps only SonaMation's standard parts (methodology, tools, governance, add-ons, rate card, terms).",
    ),
    (
        "test-cases",
        "What does this page do?",
        "QA and UAT test cases against the requirements.\n\n• Load the Requirements Document's requirements as a starting point, then record QA and UAT results.",
    ),
    (
        "schedule-planner",
        "What does this page do?",
        "Plan the client meetings — what each covers and when — and run them from a calendar.\n\n• Set how you'll meet: first date, target go-live, how often, the days and time that work, length, time zone, platform and a default link.\n• Suggest meetings drafts the series from the discovery call, documents and Tasks timeline — each with its agenda, what to prepare, review and explain. Or add your own.\n• Pick a date and time per meeting, or use Auto-schedule to place them at your cadence (tentative until you confirm).\n• On the Calendar, hover a day to see and adjust its meetings; drag a meeting to move it; drop undated ones from the tray.\n• Open a meeting to preview it as an invite, edit it, suggest its content, add the link and notes, copy the invite or download it (.ics).\n• Warnings flag clashes, weekends, meetings after go-live, and past meetings not yet marked done.",
    ),
    (
        "library",
        "What does this page do?",
        "Every document saved from this project's pages.\n\n• Newest first. Download or delete them here.",
    ),
]
