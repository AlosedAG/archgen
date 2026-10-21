/**
 * Hubzy's tunable behaviour. Times are milliseconds; each range is
 * [shortest, longest] and a random value in between is used every time, so
 * nothing ticks like a metronome. What he says lives here too, so the copy can
 * be edited without touching the components.
 */

/** The small one-off expressions he pulls now and then. */
export type HubzyExpression = "smile" | "wiggle" | "hop" | "tilt";

export const HUBZY_TIMING = {
  /** Time between blinks; some blinks come as a quick double. */
  blinkEvery: [2600, 6800] as const,
  blinkLength: 140,
  doubleBlinkChance: 0.18,

  /** Time between glances (left, right, or toward the cursor). */
  glanceEvery: [2800, 7000] as const,
  /** How long a glance holds before the eyes drift back to centre. */
  glanceHold: [900, 2200] as const,
  /** A glance goes toward the cursor if it moved within this long. */
  cursorFreshFor: 4000,

  /** Time between small expressions. */
  expressionEvery: [9000, 20000] as const,
  /** How long each expression lasts (matches its CSS animation). */
  expressionLength: { smile: 1100, wiggle: 900, hop: 600, tilt: 1400 } satisfies Record<HubzyExpression, number>,
} as const;

/** How far the pupils can move, in the SVG's units (the eye radius is 7.5). */
export const LOOK_RANGE = { x: 3.5, y: 2.5 };

export const EXPRESSIONS: HubzyExpression[] = ["smile", "wiggle", "hop", "tilt"];

/** Dragging: how far a press must travel before it counts as a drag, and the screen margin he stays inside. */
export const HUBZY_DRAG = {
  storageKey: "hubzy:position",
  threshold: 5,
  margin: 8,
  /** Arrow keys move him this far (Shift moves four times as far). */
  keyStep: 16,
};

/** The speech bubble's layout: the gap left for its tail, and the screen margin it never crosses. */
export const HUBZY_BUBBLE = {
  gap: 12,
  margin: 10,
  /** The tail stays at least this far from the bubble's corners. */
  tailInset: 22,
};

/** What a quick-reply button under a bubble does. */
export type HubzyAction = "tour" | "start-project" | "dismiss";
export type HubzyReply = { label: string; action: HubzyAction };

export const HUBZY_GREETING = {
  /** Shown once per browser session, this long after the app loads. */
  delay: 1400,
  sessionKey: "hubzy:greeted",
  /** Used when the signed-in user has no name on their account. */
  fallbackName: "Human",
  text: (name: string) => `Hey ${name}, need a hand? I'll be right here if you do.`,
  replies: [
    { label: "Show me around", action: "tour" },
    { label: "Start a project", action: "start-project" },
    { label: "No thanks", action: "dismiss" },
  ] satisfies HubzyReply[],
};

export const HUBZY_TOUR = {
  text:
    "Everything lives in the rail on the left. RevOps walks a client from discovery to delivery, " +
    "Implementation holds your projects and tasks, and the question mark at the bottom opens help and a short guide for the page you're on. " +
    "Hover any icon to see what's inside.",
  replies: [
    { label: "Start a project", action: "start-project" },
    { label: "Got it", action: "dismiss" },
  ] satisfies HubzyReply[],
};

/**
 * Ambient HubSpot facts: Hubzy offers one now and then while you're idle.
 * "Idle" = no typing, clicking or scrolling for `idleFor`; never while a text
 * field has focus, another bubble is open, or the tab is hidden.
 */
export const HUBZY_FACT_TIMING = {
  /** Time between facts (the first one too). */
  every: [60_000, 120_000] as const,
  idleFor: 30_000,
  /** How often the conditions are checked. */
  checkEvery: 1_000,
  /** A fact stays up this long plus a little per character, within these bounds. */
  showFor: { base: 5_000, perChar: 55, min: 8_000, max: 14_000 },
  /** He talks (mouth moving) this long as a fact appears. */
  talkFor: 1_400,
  /** The order still to come, so no fact repeats until all have been shown. */
  storageKey: "hubzy:facts-queue",
};

export const HUBZY_FACT_LABEL = "HubSpot tip";

/** Edit freely: add, remove or reword. Keep them short, true and friendly. */
export const HUBZY_FACTS: string[] = [
  "HubSpot was founded in 2006 by Brian Halligan and Dharmesh Shah, who met at MIT.",
  "HubSpot's founders popularised the term \"inbound marketing\": attract people with useful content instead of interrupting them.",
  "Every HubSpot tool shares one CRM, so marketing, sales and service all see the same contact record.",
  "Contacts, companies, deals and tickets are HubSpot's four standard CRM objects. Enterprise accounts can add custom objects too.",
  "Associations link records together, like a contact to their company. Association labels say how, for example \"Decision maker\".",
  "HubSpot's default lifecycle stages run Subscriber, Lead, MQL, SQL, Opportunity, Customer, Evangelist (plus Other).",
  "Automation can only move a lifecycle stage forward. To move one back, clear the property first, then set it again.",
  "A property's label can be renamed any time, but its internal name is fixed once it's created, so name it carefully.",
  "HubSpot spots duplicate contacts by email address and duplicate companies by domain name.",
  "Each deal pipeline has its own stages, and every stage carries a win probability used for weighted forecasts.",
  "Tickets work like deals: they move through pipelines with stages you define, which is handy for support processes.",
  "Active lists update themselves as records match the filters; static lists only change when you add or remove records.",
  "Workflow re-enrollment is off by default, so a record goes through a workflow once unless you switch it on.",
  "Sales sequences stop automatically when a contact replies, so nobody gets a follow-up after they've answered.",
  "Breeze is HubSpot's AI layer, with a copilot that helps inside the tools and agents that can take on whole tasks.",
  "Enterprise accounts come with a standard sandbox, a safe copy of the portal for testing changes before going live.",
  "HubSpot Academy offers free courses and certifications, a quick way to get a client's team up to speed.",
];

/** The help panel (click Hubzy): pick a question, he answers from the workspace's Hubzy Answers table. */
export const HUBZY_PANEL = {
  hello: (name: string) => `Hi ${name}! Pick a question below and I'll answer it.`,
  /** When the answers can't be loaded (server asleep or unreachable). */
  unreachable: "Hmm, I couldn't reach my brain just now — try again?",
  retry: "Try again",
  empty: "I don't have any answers yet. An admin can add some under Help > Hubzy Answers.",
  helloDelay: 240,
  /** He "types" for a random time in this range before answering. */
  typingFor: [650, 1100] as const,
  /** His mouth moves this long once an answer appears. */
  talkFor: 1_700,
  /** Give up loading after this long and show `unreachable`. */
  loadTimeout: 15_000,
  /** Group headings for the question buttons. */
  pageGroup: "About this page",
  generalGroup: "HubSpot & The Hub Zone",
};
