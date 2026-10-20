"use client";

/**
 * One meeting, in a side panel. Preview shows it the way the client will
 * read the invite; Edit changes anything. "Suggest content" drafts the
 * purpose, agenda, preparation, review points, what to explain, attendees,
 * follow-ups and notes from the project (only adding to what's there).
 * Copy the invite text, download it as .ics, mark it done, or step to the
 * previous / next meeting.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { assistScheduleMeeting, ApiError, type AssistContext } from "@/lib/api";
import {
  DURATIONS,
  MEETING_TYPES,
  PHASES,
  STATUSES,
  downloadFile,
  durationLabel,
  fromLines,
  inviteText,
  prettyDate,
  safeUrl,
  settingsPayload,
  stubs,
  timeRange,
  toIcs,
  toLines,
  warningsFor,
  type Meeting,
  type MeetingStatus,
  type MeetingType,
  type Phase,
  type ScheduleSettings,
} from "@/lib/schedule-state";

import { Glyph } from "../icons";
import { Callout, Tabs } from "../ui";

import { TypeTag } from "./MeetingList";

type Mode = "preview" | "edit";

const LIST_FIELDS: { key: "agenda" | "prepare" | "review" | "attendees" | "followUps"; label: string; preview: string; hint: string }[] = [
  { key: "agenda", label: "Agenda", preview: "Agenda", hint: "One item per line, e.g. “10 min – Recap of goals”" },
  { key: "prepare", label: "What to prepare", preview: "Please have ready", hint: "What the team and the client need ready beforehand" },
  { key: "review", label: "What to review", preview: "We'll review", hint: "What gets reviewed or decided in the meeting" },
  { key: "attendees", label: "Attendees", preview: "Attendees", hint: "Names or roles, one per line" },
  { key: "followUps", label: "Follow-ups", preview: "Follow-ups after the meeting", hint: "What to send or do afterwards" },
];

const CHANGED_LABELS: Record<string, string> = {
  purpose: "purpose",
  agenda: "agenda",
  prepare: "preparation",
  review: "review points",
  explain: "what to explain",
  attendees: "attendees",
  follow_ups: "follow-ups",
  notes: "notes",
};

export function MeetingDrawer({
  meeting,
  meetings,
  settings,
  client,
  onClose,
  onUpdate,
  onRemove,
  onNavigate,
  context,
}: {
  meeting: Meeting | null;
  meetings: Meeting[];
  settings: ScheduleSettings;
  client: string;
  onClose: () => void;
  onUpdate: (id: string, patch: Partial<Meeting>) => void;
  onRemove: (id: string) => void;
  onNavigate: (id: string) => void;
  context: () => Promise<AssistContext>;
}) {
  const [mode, setMode] = useState<Mode>("preview");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ tone: "success" | "info" | "error"; text: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const id = meeting?.id ?? null;

  // A fresh meeting opens in Edit; one with content opens in Preview.
  useEffect(() => {
    if (!meeting) return;
    setMode(meeting.purpose || meeting.agenda.length ? "preview" : "edit");
    setResult(null);
    setCopied(false);
    panel.current?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (!meeting) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [meeting, onClose]);

  const ordered = [...meetings].sort((a, b) => (a.date || "9999").localeCompare(b.date || "9999") || (a.time || "").localeCompare(b.time || ""));
  const index = meeting ? ordered.findIndex((m) => m.id === meeting.id) : -1;
  const prev = index > 0 ? ordered[index - 1] : null;
  const next = index >= 0 && index < ordered.length - 1 ? ordered[index + 1] : null;

  const set = (patch: Partial<Meeting>) => meeting && onUpdate(meeting.id, patch);

  const suggest = async () => {
    if (!meeting) return;
    setBusy(true);
    setResult(null);
    try {
      const res = await assistScheduleMeeting(
        await context(),
        settingsPayload(settings),
        {
          title: meeting.title || "Meeting",
          type: meeting.type,
          date: meeting.date,
          time: meeting.time,
          duration_minutes: meeting.duration,
          purpose: meeting.purpose,
          agenda: meeting.agenda,
          prepare: meeting.prepare,
          review: meeting.review,
          explain: meeting.explain,
          attendees: meeting.attendees,
          follow_ups: meeting.followUps,
          notes: meeting.notes,
        },
        stubs(meetings, meeting.id),
      );
      const c = res.meeting;
      onUpdate(meeting.id, {
        purpose: c.purpose ?? "",
        agenda: c.agenda ?? [],
        prepare: c.prepare ?? [],
        review: c.review ?? [],
        explain: c.explain ?? "",
        attendees: c.attendees ?? [],
        followUps: c.follow_ups ?? [],
        notes: c.notes ?? "",
      });
      setResult(
        res.changed.length
          ? { tone: "success", text: `Added ${res.changed.map((k) => CHANGED_LABELS[k] ?? k).join(", ")} (${res.model}).` }
          : { tone: "info", text: "Nothing to add — this meeting already covers what the project suggests." },
      );
    } catch (e) {
      setResult({ tone: "error", text: e instanceof ApiError ? e.message : "The suggestions didn't arrive. Try again." });
    }
    setBusy(false);
  };

  const copyInvite = async () => {
    if (!meeting) return;
    try {
      await navigator.clipboard.writeText(inviteText(meeting, settings, client));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setResult({ tone: "error", text: "Couldn't copy — your browser blocked the clipboard." });
    }
  };

  const url = meeting ? safeUrl(meeting.link) : null;
  const warnings = meeting ? warningsFor(meeting, meetings, settings) : [];

  return (
    <AnimatePresence>
      {meeting && (
        <>
          <motion.div
            className="drawer-backdrop"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.16 }}
          />
          <motion.div
            ref={panel}
            className="drawer"
            role="dialog"
            aria-modal="true"
            aria-label={meeting.title || "Meeting"}
            tabIndex={-1}
            data-type={meeting.type}
            initial={{ x: 40, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 40, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.2, 0.7, 0.2, 1] }}
          >
            <header className="drawer-head">
              <div className="drawer-nav">
                <button type="button" className="icon-btn" aria-label="Previous meeting" disabled={!prev} onClick={() => prev && onNavigate(prev.id)}>
                  <Glyph name="arrow-right" size={15} className="flip" />
                </button>
                <span className="t-caption">
                  {index + 1} of {ordered.length}
                </span>
                <button type="button" className="icon-btn" aria-label="Next meeting" disabled={!next} onClick={() => next && onNavigate(next.id)}>
                  <Glyph name="arrow-right" size={15} />
                </button>
              </div>
              <button type="button" className="icon-btn" aria-label="Close" onClick={onClose}>
                <Glyph name="x" size={16} />
              </button>
            </header>

            <div className="drawer-title">
              <div className="row" style={{ gap: 8 }}>
                <TypeTag type={meeting.type} />
                <span className="sched-status-text" data-status={meeting.status}>
                  {!meeting.date && meeting.status === "tentative" ? "to schedule" : meeting.status}
                </span>
              </div>
              <h2>{meeting.title || "Untitled meeting"}</h2>
              <p className="drawer-when">
                {meeting.date ? (
                  <>
                    <b>{prettyDate(meeting.date, { weekday: "long", month: "long", day: "numeric", year: "numeric" })}</b> · {timeRange(meeting)}
                    {settings.timezone && <span className="t-caption"> ({settings.timezone.replace(/_/g, " ")})</span>}
                  </>
                ) : (
                  "No date yet"
                )}
              </p>
              <div className="row" style={{ gap: 8 }}>
                {url && (
                  <a className="btn btn-primary btn-sm" href={url} target="_blank" rel="noopener noreferrer">
                    <Glyph name="external-link" size={14} />
                    Join meeting
                  </a>
                )}
                <button type="button" className={`btn btn-secondary btn-sm${busy ? " btn-busy" : ""}`} disabled={busy} onClick={() => void suggest()}>
                  <Glyph name="sparkles" size={14} />
                  {busy ? "Reading the project…" : "Suggest content"}
                </button>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => void copyInvite()}>
                  <Glyph name={copied ? "check" : "file"} size={14} />
                  {copied ? "Copied" : "Copy invite"}
                </button>
                {meeting.date && (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => downloadFile(`${meeting.title || "meeting"}.ics`, toIcs([meeting], settings, client))}
                  >
                    <Glyph name="download" size={14} />
                    .ics
                  </button>
                )}
              </div>
              {result && (
                <Callout tone={result.tone} title={result.tone === "error" ? "No suggestions" : result.text}>
                  {result.tone === "error" ? result.text : undefined}
                </Callout>
              )}
              {warnings.map((w) => (
                <p key={w} className="sched-pop-warn">
                  <Glyph name="alert-triangle" size={13} />
                  {w}
                </p>
              ))}
            </div>

            <Tabs<Mode>
              tabs={[
                { id: "preview", label: "Preview" },
                { id: "edit", label: "Edit" },
              ]}
              active={mode}
              onChange={setMode}
              layoutId="meeting-drawer-tabs"
              variant="secondary"
              label="Meeting"
            />

            <div className="drawer-body" id="panel-meeting-drawer-tabs" role="tabpanel">
              {mode === "preview" ? (
                <div className="sched-preview">
                  {meeting.purpose ? (
                    <section>
                      <h3>Purpose</h3>
                      <p>{meeting.purpose}</p>
                    </section>
                  ) : null}
                  {LIST_FIELDS.slice(0, 3).map((f) =>
                    meeting[f.key].length ? (
                      <section key={f.key}>
                        <h3>{f.preview}</h3>
                        <ul>
                          {meeting[f.key].map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      </section>
                    ) : null,
                  )}
                  {meeting.explain && (
                    <section>
                      <h3>What we&apos;ll walk through</h3>
                      <p>{meeting.explain}</p>
                    </section>
                  )}
                  {LIST_FIELDS.slice(3).map((f) =>
                    meeting[f.key].length ? (
                      <section key={f.key}>
                        <h3>{f.preview}</h3>
                        <ul>
                          {meeting[f.key].map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      </section>
                    ) : null,
                  )}
                  {meeting.location && (
                    <section>
                      <h3>Where</h3>
                      <p>{meeting.location}</p>
                    </section>
                  )}
                  {meeting.notes && (
                    <section className="sched-preview-notes">
                      <h3>Internal notes</h3>
                      <p>{meeting.notes}</p>
                    </section>
                  )}
                  {!meeting.purpose && !meeting.agenda.length && !meeting.explain && !meeting.notes && (
                    <div className="sched-empty">
                      <p>Nothing here yet.</p>
                      <p className="t-caption">Use Suggest content to draft it from the project, or switch to Edit.</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="stack">
                  <label className="field">
                    <span className="field-label">Title</span>
                    <input className="input" value={meeting.title} onChange={(e) => set({ title: e.target.value })} />
                  </label>
                  <div className="grid-2" style={{ gap: 12 }}>
                    <label className="field">
                      <span className="field-label">Type</span>
                      <select className="select" value={meeting.type} onChange={(e) => set({ type: e.target.value as MeetingType })}>
                        {MEETING_TYPES.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span className="field-label">Phase</span>
                      <select className="select" value={meeting.phase} onChange={(e) => set({ phase: e.target.value as Phase })}>
                        <option value="">No phase</option>
                        {PHASES.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span className="field-label">Date</span>
                      <input type="date" className="input" value={meeting.date} onChange={(e) => set({ date: e.target.value })} />
                    </label>
                    <label className="field">
                      <span className="field-label">Start time</span>
                      <input type="time" className="input" step={900} value={meeting.time} onChange={(e) => set({ time: e.target.value })} />
                    </label>
                    <label className="field">
                      <span className="field-label">Length</span>
                      <select className="select" value={meeting.duration} onChange={(e) => set({ duration: Number(e.target.value) })}>
                        {[...new Set([...DURATIONS, meeting.duration])].sort((a, b) => a - b).map((d) => (
                          <option key={d} value={d}>
                            {durationLabel(d)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span className="field-label">Status</span>
                      <select className="select" value={meeting.status} onChange={(e) => set({ status: e.target.value as MeetingStatus })}>
                        {STATUSES.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <label className="field">
                    <span className="field-label">Meeting link</span>
                    <input type="url" className="input" placeholder="https://…" value={meeting.link} onChange={(e) => set({ link: e.target.value })} />
                    {meeting.link && !url && <span className="t-caption">That doesn&apos;t look like a web link yet.</span>}
                  </label>
                  <label className="field">
                    <span className="field-label">Location or dial-in (optional)</span>
                    <input className="input" value={meeting.location} onChange={(e) => set({ location: e.target.value })} />
                  </label>
                  <label className="field">
                    <span className="field-label">Purpose</span>
                    <textarea className="textarea" value={meeting.purpose} onChange={(e) => set({ purpose: e.target.value })} />
                  </label>
                  {LIST_FIELDS.slice(0, 3).map((f) => (
                    <ListField key={f.key} label={f.label} hint={f.hint} items={meeting[f.key]} onChange={(items) => set({ [f.key]: items })} />
                  ))}
                  <label className="field">
                    <span className="field-label">What to explain</span>
                    <textarea
                      className="textarea"
                      placeholder="What to walk the client through, and why it matters to them"
                      value={meeting.explain}
                      onChange={(e) => set({ explain: e.target.value })}
                    />
                  </label>
                  {LIST_FIELDS.slice(3).map((f) => (
                    <ListField key={f.key} label={f.label} hint={f.hint} items={meeting[f.key]} onChange={(items) => set({ [f.key]: items })} />
                  ))}
                  <label className="field">
                    <span className="field-label">Internal notes</span>
                    <textarea
                      className="textarea"
                      placeholder="Only for your team — not included in the invite"
                      value={meeting.notes}
                      onChange={(e) => set({ notes: e.target.value })}
                    />
                  </label>
                </div>
              )}
            </div>

            <footer className="drawer-foot">
              {meeting.status !== "done" ? (
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => set({ status: "done" })}>
                  <Glyph name="check-circle" size={14} />
                  Mark done
                </button>
              ) : (
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => set({ status: "confirmed" })}>
                  Reopen
                </button>
              )}
              <button
                type="button"
                className="btn-link btn-link-danger"
                onClick={() => {
                  if (window.confirm(`Delete “${meeting.title || "this meeting"}”?`)) onRemove(meeting.id);
                }}
              >
                Delete meeting
              </button>
            </footer>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

/** A list edited as one item per line (kept as typed until you leave the field). */
function ListField({ label, hint, items, onChange }: { label: string; hint: string; items: string[]; onChange: (items: string[]) => void }) {
  const [text, setText] = useState(toLines(items));
  const editing = useRef(false);
  useEffect(() => {
    if (!editing.current) setText(toLines(items));
  }, [items]);
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <textarea
        className="textarea"
        placeholder={hint}
        value={text}
        onFocus={() => (editing.current = true)}
        onChange={(e) => {
          setText(e.target.value);
          onChange(fromLines(e.target.value));
        }}
        onBlur={() => {
          editing.current = false;
          setText(toLines(fromLines(text)));
        }}
      />
    </label>
  );
}
