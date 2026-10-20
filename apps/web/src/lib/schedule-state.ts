/**
 * The Schedule Planner (saved as the "schedule" module state): how the
 * client meetings should be scheduled, and the meetings themselves — each
 * with its date and time, link, agenda, what to prepare / review / explain,
 * notes and follow-ups. Also the helpers the page needs: placing meetings
 * on the calendar, spotting clashes, and exporting invites (.ics / text).
 */

import type { MeetingStub, ScheduleSettingsPayload, SuggestedMeeting } from "./api";

// ---- vocabularies ---------------------------------------------------------------

export const MEETING_TYPES = [
  { id: "kickoff", label: "Kickoff" },
  { id: "discovery", label: "Discovery deep-dive" },
  { id: "requirements", label: "Requirements review" },
  { id: "design", label: "Design review" },
  { id: "build", label: "Build check-in" },
  { id: "data", label: "Data & migration" },
  { id: "training", label: "Training" },
  { id: "uat", label: "UAT / testing" },
  { id: "go_live", label: "Go-live" },
  { id: "review", label: "Retrospective / handover" },
  { id: "other", label: "Other" },
] as const;
export type MeetingType = (typeof MEETING_TYPES)[number]["id"];

export const PHASES = [
  { id: "discover", label: "Discover" },
  { id: "assess", label: "Assess" },
  { id: "design", label: "Design" },
  { id: "propose", label: "Propose" },
  { id: "build", label: "Build" },
  { id: "launch", label: "Test & launch" },
] as const;
export type Phase = (typeof PHASES)[number]["id"] | "";

export const STATUSES = [
  { id: "tentative", label: "Tentative" },
  { id: "confirmed", label: "Confirmed" },
  { id: "done", label: "Done" },
  { id: "cancelled", label: "Cancelled" },
] as const;
export type MeetingStatus = (typeof STATUSES)[number]["id"];

export const CADENCES = [
  { id: "weekly", label: "Weekly", gapDays: 7 },
  { id: "twice_weekly", label: "Twice a week", gapDays: 3 },
  { id: "biweekly", label: "Every two weeks", gapDays: 14 },
  { id: "monthly", label: "Monthly", gapDays: 28 },
  { id: "milestones", label: "At each milestone", gapDays: 7 },
] as const;
export type Cadence = (typeof CADENCES)[number]["id"];

export const PLATFORMS = ["Zoom", "Google Meet", "Microsoft Teams", "HubSpot meetings link", "Phone", "In person"] as const;
export const DURATIONS = [15, 30, 45, 60, 90, 120] as const;
export const DAYS = [
  { id: "mon", label: "Mon", long: "Monday" },
  { id: "tue", label: "Tue", long: "Tuesday" },
  { id: "wed", label: "Wed", long: "Wednesday" },
  { id: "thu", label: "Thu", long: "Thursday" },
  { id: "fri", label: "Fri", long: "Friday" },
  { id: "sat", label: "Sat", long: "Saturday" },
  { id: "sun", label: "Sun", long: "Sunday" },
] as const;
export type DayId = (typeof DAYS)[number]["id"];

export const TIMEZONES = [
  "America/Los_Angeles",
  "America/Denver",
  "America/Chicago",
  "America/New_York",
  "America/Mexico_City",
  "America/Bogota",
  "America/Sao_Paulo",
  "Europe/London",
  "Europe/Madrid",
  "Europe/Berlin",
  "Asia/Dubai",
  "Asia/Kolkata",
  "Asia/Singapore",
  "Australia/Sydney",
  "UTC",
];

export function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

// ---- state -----------------------------------------------------------------------

export type ScheduleSettings = {
  startDate: string;
  goLiveDate: string;
  cadence: Cadence;
  preferredDays: DayId[];
  defaultTime: string;
  duration: number;
  timezone: string;
  platform: string;
  defaultLink: string;
  meetingCount: number | null;
  attendees: string;
  notes: string;
};

export type Meeting = {
  id: string;
  title: string;
  type: MeetingType;
  phase: Phase;
  status: MeetingStatus;
  /** yyyy-mm-dd, or "" while it still needs a date. */
  date: string;
  /** HH:MM (24-hour), or "". */
  time: string;
  duration: number;
  /** The suggested week (1-based from the start date), used to place it. */
  week: number | null;
  link: string;
  location: string;
  purpose: string;
  agenda: string[];
  prepare: string[];
  review: string[];
  explain: string;
  attendees: string[];
  followUps: string[];
  notes: string;
  origin: "manual" | "ai";
  createdAt: string;
};

export type ScheduleState = { settings: ScheduleSettings; meetings: Meeting[] };

export const DEFAULT_SETTINGS: ScheduleSettings = {
  startDate: "",
  goLiveDate: "",
  cadence: "weekly",
  preferredDays: ["tue", "thu"],
  defaultTime: "10:00",
  duration: 60,
  timezone: "",
  platform: "Zoom",
  defaultLink: "",
  meetingCount: null,
  attendees: "",
  notes: "",
};

const strings = (v: unknown): string[] => (Array.isArray(v) ? v.map((x) => String(x ?? "").trim()).filter(Boolean) : []);
const oneOf = <T extends string>(v: unknown, allowed: readonly { id: T }[], fallback: T): T =>
  allowed.some((a) => a.id === v) ? (v as T) : fallback;

export function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `m-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function newMeeting(patch: Partial<Meeting> = {}, settings: ScheduleSettings = DEFAULT_SETTINGS): Meeting {
  return {
    id: newId(),
    title: "",
    type: "other",
    phase: "",
    status: "tentative",
    date: "",
    time: settings.defaultTime,
    duration: settings.duration,
    week: null,
    link: settings.defaultLink,
    location: "",
    purpose: "",
    agenda: [],
    prepare: [],
    review: [],
    explain: "",
    attendees: [],
    followUps: [],
    notes: "",
    origin: "manual",
    createdAt: new Date().toISOString(),
    ...patch,
  };
}

export function normalizeSchedule(raw: unknown): ScheduleState {
  const s = (typeof raw === "object" && raw ? raw : {}) as Partial<ScheduleState>;
  const rs = (s.settings ?? {}) as Partial<ScheduleSettings>;
  const settings: ScheduleSettings = {
    ...DEFAULT_SETTINGS,
    ...rs,
    cadence: oneOf(rs.cadence, CADENCES, DEFAULT_SETTINGS.cadence),
    preferredDays: Array.isArray(rs.preferredDays)
      ? rs.preferredDays.filter((d): d is DayId => DAYS.some((x) => x.id === d))
      : DEFAULT_SETTINGS.preferredDays,
    duration: Number(rs.duration) > 0 ? Number(rs.duration) : DEFAULT_SETTINGS.duration,
    meetingCount: Number(rs.meetingCount) > 0 ? Number(rs.meetingCount) : null,
  };
  const meetings = (Array.isArray(s.meetings) ? s.meetings : [])
    .filter((m): m is Meeting => Boolean(m && typeof m === "object" && (m as Meeting).id))
    .map((m) => {
      const base = newMeeting({}, settings);
      return {
        ...base,
        ...m,
        type: oneOf(m.type, MEETING_TYPES, "other"),
        phase: PHASES.some((p) => p.id === m.phase) ? m.phase : "",
        status: oneOf(m.status, STATUSES, "tentative"),
        duration: Number(m.duration) > 0 ? Number(m.duration) : settings.duration,
        agenda: strings(m.agenda),
        prepare: strings(m.prepare),
        review: strings(m.review),
        attendees: strings(m.attendees),
        followUps: strings(m.followUps),
      };
    });
  return { settings, meetings };
}

// ---- dates -----------------------------------------------------------------------

/** A yyyy-mm-dd string as a local date (noon, so DST shifts never change the day). */
export function parseDay(iso: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12) : null;
}

export function isoDay(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function addDays(d: Date, n: number): Date {
  const out = new Date(d);
  out.setDate(out.getDate() + n);
  return out;
}

export function todayIso(): string {
  return isoDay(new Date());
}

const DAY_BY_INDEX: DayId[] = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
export const dayId = (d: Date): DayId => DAY_BY_INDEX[d.getDay()]!;

export function minutes(time: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(time);
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

export function clock(total: number): string {
  const t = ((total % 1440) + 1440) % 1440;
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}

/** "10:00" -> "10:00 AM" in the viewer's locale style. */
export function prettyTime(time: string): string {
  const mins = minutes(time);
  if (mins === null) return "";
  const d = new Date(2000, 0, 1, Math.floor(mins / 60), mins % 60);
  return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export function timeRange(m: Pick<Meeting, "time" | "duration">): string {
  const start = minutes(m.time);
  if (start === null) return "Time to be set";
  return `${prettyTime(m.time)} – ${prettyTime(clock(start + m.duration))}`;
}

/** 45 -> "45 min", 90 -> "1 h 30 min". */
export function durationLabel(total: number): string {
  if (total < 60) return `${total} min`;
  const h = Math.floor(total / 60);
  return `${h} h${total % 60 ? ` ${total % 60} min` : ""}`;
}

export function prettyDate(iso: string, opts: Intl.DateTimeFormatOptions = { weekday: "short", month: "short", day: "numeric" }): string {
  const d = parseDay(iso);
  return d ? d.toLocaleDateString(undefined, opts) : "";
}

// ---- placing meetings -------------------------------------------------------------

const cadence = (id: Cadence) => CADENCES.find((c) => c.id === id) ?? CADENCES[0];

function overlaps(a: Pick<Meeting, "date" | "time" | "duration">, b: Pick<Meeting, "date" | "time" | "duration">): boolean {
  if (!a.date || a.date !== b.date) return false;
  const as = minutes(a.time);
  const bs = minutes(b.time);
  if (as === null || bs === null) return false;
  return as < bs + b.duration && bs < as + a.duration;
}

/**
 * Give every meeting that has no date one: in list order, from the start
 * date (or today), at the planned cadence, on a preferred weekday, in its
 * suggested week when it has one, and never on top of another meeting.
 * Placed meetings are marked tentative. Returns the meetings and how many
 * were placed.
 */
export function autoSchedule(meetings: Meeting[], settings: ScheduleSettings): { meetings: Meeting[]; placed: number } {
  const start = parseDay(settings.startDate) ?? parseDay(todayIso())!;
  const preferred = new Set<DayId>(settings.preferredDays.length ? settings.preferredDays : ["mon", "tue", "wed", "thu", "fri"]);
  const gap = cadence(settings.cadence).gapDays;
  const taken: Meeting[] = meetings.filter((m) => m.date && m.status !== "cancelled");
  let cursor = start;
  // Start after the last meeting already on the calendar.
  for (const m of taken) {
    const d = parseDay(m.date);
    if (d && d >= cursor) cursor = addDays(d, gap === 3 ? 1 : gap);
  }
  let placed = 0;
  const out = meetings.map((m) => {
    if (m.date || m.status === "cancelled" || m.status === "done") return m;
    let day = cursor;
    if (m.week) {
      const weekStart = addDays(start, (m.week - 1) * 7);
      if (weekStart > day) day = weekStart;
    }
    const time = m.time || settings.defaultTime;
    for (let i = 0; i < 400; i++) {
      const candidate = { date: isoDay(day), time, duration: m.duration };
      if (preferred.has(dayId(day)) && !taken.some((t) => overlaps(t, candidate))) break;
      day = addDays(day, 1);
    }
    const next = { ...m, date: isoDay(day), time, status: "tentative" as const };
    taken.push(next);
    placed++;
    cursor = addDays(day, gap === 3 ? 1 : gap);
    return next;
  });
  return { meetings: out, placed };
}

/** Why a meeting needs a second look (clash, weekend, after go-live, past and not done). */
export function warningsFor(meeting: Meeting, all: Meeting[], settings: ScheduleSettings): string[] {
  if (!meeting.date || meeting.status === "cancelled") return [];
  const out: string[] = [];
  const clash = all.find((o) => o.id !== meeting.id && o.status !== "cancelled" && overlaps(o, meeting));
  if (clash) out.push(`Overlaps “${clash.title || "Untitled meeting"}”`);
  const d = parseDay(meeting.date);
  if (d && (d.getDay() === 0 || d.getDay() === 6) && !settings.preferredDays.includes(dayId(d))) out.push("Falls on a weekend");
  if (settings.goLiveDate && meeting.date > settings.goLiveDate && !["go_live", "review", "training"].includes(meeting.type))
    out.push("After the target go-live");
  if (meeting.date < todayIso() && meeting.status !== "done") out.push("In the past — mark it done or move it");
  return out;
}

// ---- conversions -------------------------------------------------------------------

const CADENCE_LABEL = Object.fromEntries(CADENCES.map((c) => [c.id, c.label]));

export function settingsPayload(s: ScheduleSettings): ScheduleSettingsPayload {
  return {
    start_date: s.startDate,
    go_live_date: s.goLiveDate,
    cadence: CADENCE_LABEL[s.cadence] ?? "",
    preferred_days: s.preferredDays.map((d) => DAYS.find((x) => x.id === d)!.long),
    default_time: s.defaultTime,
    duration_minutes: s.duration,
    timezone: s.timezone || browserTimezone(),
    platform: s.platform,
    meeting_count: s.meetingCount,
    attendees: s.attendees,
    notes: s.notes,
  };
}

export function stubs(meetings: Meeting[], except?: string): MeetingStub[] {
  return meetings.filter((m) => m.id !== except && m.title.trim()).map((m) => ({ title: m.title, type: m.type, date: m.date }));
}

export function fromSuggestion(s: SuggestedMeeting, settings: ScheduleSettings): Meeting {
  return newMeeting(
    {
      title: s.title,
      type: oneOf(s.type, MEETING_TYPES, "other"),
      phase: PHASES.some((p) => p.id === s.stage) ? (s.stage as Phase) : "",
      week: s.week ?? null,
      duration: s.duration_minutes ?? settings.duration,
      purpose: s.purpose ?? "",
      agenda: s.agenda ?? [],
      prepare: s.prepare ?? [],
      review: s.review ?? [],
      explain: s.explain ?? "",
      attendees: s.attendees ?? [],
      origin: "ai",
    },
    settings,
  );
}

export const typeLabel = (id: MeetingType) => MEETING_TYPES.find((t) => t.id === id)?.label ?? "Other";

// ---- invites -----------------------------------------------------------------------

/** The meeting as plain text, ready to paste into an invite or email. */
export function inviteText(m: Meeting, settings: ScheduleSettings, client: string): string {
  const lines: string[] = [];
  lines.push(m.title || "Meeting");
  if (client) lines.push(client);
  if (m.date) lines.push(`${prettyDate(m.date, { weekday: "long", month: "long", day: "numeric", year: "numeric" })} · ${timeRange(m)}${settings.timezone ? ` (${settings.timezone})` : ""}`);
  if (m.link) lines.push(`Join: ${m.link}`);
  if (m.location) lines.push(`Where: ${m.location}`);
  const section = (title: string, items: string[]) => {
    if (!items.length) return;
    lines.push("", title, ...items.map((i) => `• ${i}`));
  };
  if (m.purpose) lines.push("", "Purpose", m.purpose);
  section("Agenda", m.agenda);
  section("Please have ready", m.prepare);
  section("We'll review", m.review);
  if (m.explain) lines.push("", "What we'll walk through", m.explain);
  section("Attendees", m.attendees);
  return lines.join("\n");
}

const icsEscape = (s: string) => s.replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/([,;])/g, "\\$1");
const icsStamp = (d: Date) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
const icsLocal = (date: string, time: string) => `${date.replace(/-/g, "")}T${time.replace(":", "")}00`;

/** An .ics calendar with the given (dated) meetings; times are in the plan's time zone. */
export function toIcs(meetings: Meeting[], settings: ScheduleSettings, client: string): string {
  const tz = settings.timezone || browserTimezone();
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//The Hub Zone//Schedule Planner//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"];
  for (const m of meetings) {
    if (!m.date || m.status === "cancelled") continue;
    const start = minutes(m.time);
    lines.push("BEGIN:VEVENT", `UID:${m.id}@thehubzone`, `DTSTAMP:${icsStamp(new Date())}`);
    if (start === null) {
      const next = isoDay(addDays(parseDay(m.date)!, 1));
      lines.push(`DTSTART;VALUE=DATE:${m.date.replace(/-/g, "")}`, `DTEND;VALUE=DATE:${next.replace(/-/g, "")}`);
    } else {
      const endTotal = start + m.duration;
      const endDate = endTotal >= 1440 ? isoDay(addDays(parseDay(m.date)!, 1)) : m.date;
      lines.push(`DTSTART;TZID=${tz}:${icsLocal(m.date, m.time)}`, `DTEND;TZID=${tz}:${icsLocal(endDate, clock(endTotal))}`);
    }
    lines.push(`SUMMARY:${icsEscape(client ? `${m.title} · ${client}` : m.title)}`);
    lines.push(`DESCRIPTION:${icsEscape(inviteText(m, settings, client))}`);
    if (m.link) lines.push(`URL:${icsEscape(m.link)}`);
    if (m.link || m.location) lines.push(`LOCATION:${icsEscape(m.location || m.link)}`);
    lines.push(`STATUS:${m.status === "confirmed" || m.status === "done" ? "CONFIRMED" : "TENTATIVE"}`, "END:VEVENT");
  }
  lines.push("END:VCALENDAR");
  // RFC 5545 lines end in CRLF.
  return lines.join("\r\n");
}

export function downloadFile(filename: string, text: string, type = "text/calendar"): void {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** List fields are edited as one item per line. */
export const toLines = (items: string[]) => items.join("\n");
export const fromLines = (text: string) =>
  text
    .split("\n")
    .map((l) => l.replace(/^\s*[•\-*]\s*/, "").trimEnd())
    .filter((l) => l.trim());

/** A safe link to open: only http(s), with https:// added to a bare host. */
export function safeUrl(link: string): string | null {
  const t = link.trim();
  if (!t) return null;
  const withScheme = /^https?:\/\//i.test(t) ? t : /^[\w.-]+\.[a-z]{2,}(\/|$)/i.test(t) ? `https://${t}` : null;
  if (!withScheme) return null;
  try {
    const u = new URL(withScheme);
    return u.protocol === "http:" || u.protocol === "https:" ? u.toString() : null;
  } catch {
    return null;
  }
}
