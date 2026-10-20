"use client";

/**
 * The meeting plan as a list, grouped by phase: status, title, type, and
 * the date / time / length to edit in place. Open a meeting for everything
 * else. Toolbar: add, auto-schedule the ones without a date, confirm the
 * tentative ones, export the lot as an .ics file.
 */

import { NavIcon } from "../NavIcons";
import { Glyph } from "../icons";
import {
  DURATIONS,
  MEETING_TYPES,
  PHASES,
  STATUSES,
  downloadFile,
  durationLabel,
  toIcs,
  typeLabel,
  warningsFor,
  type Meeting,
  type MeetingStatus,
  type MeetingType,
  type ScheduleSettings,
} from "@/lib/schedule-state";

export function StatusPill({ meeting, onChange }: { meeting: Meeting; onChange: (s: MeetingStatus) => void }) {
  const shown = !meeting.date && meeting.status === "tentative" ? "unscheduled" : meeting.status;
  return (
    <span className="sched-status" data-status={shown}>
      <select
        aria-label={`Status of ${meeting.title || "meeting"}`}
        value={meeting.status}
        onChange={(e) => onChange(e.target.value as MeetingStatus)}
      >
        {STATUSES.map((s) => (
          <option key={s.id} value={s.id}>
            {s.id === "tentative" && !meeting.date ? "To schedule" : s.label}
          </option>
        ))}
      </select>
    </span>
  );
}

export function TypeTag({ type }: { type: MeetingType }) {
  return (
    <span className="sched-type" data-type={type}>
      <span className="sched-dot" aria-hidden />
      {typeLabel(type)}
    </span>
  );
}

export function MeetingList({
  meetings,
  settings,
  client,
  onOpen,
  onUpdate,
  onRemove,
  onAdd,
  onAutoSchedule,
  onConfirmAll,
  onShowCalendar,
}: {
  meetings: Meeting[];
  settings: ScheduleSettings;
  client: string;
  onOpen: (id: string) => void;
  onUpdate: (id: string, patch: Partial<Meeting>) => void;
  onRemove: (id: string) => void;
  onAdd: () => void;
  onAutoSchedule: () => void;
  onConfirmAll: () => void;
  onShowCalendar: () => void;
}) {
  const unscheduled = meetings.filter((m) => !m.date && m.status !== "cancelled" && m.status !== "done").length;
  const tentative = meetings.filter((m) => m.date && m.status === "tentative").length;
  const dated = meetings.filter((m) => m.date && m.status !== "cancelled").length;
  const groups = [...PHASES, { id: "" as const, label: "No phase" }]
    .map((p) => ({
      ...p,
      items: meetings
        .filter((m) => m.phase === p.id)
        .sort((a, b) => (a.date || "9999").localeCompare(b.date || "9999") || (a.time || "").localeCompare(b.time || "")),
    }))
    .filter((g) => g.items.length);

  return (
    <section className="card sched-list-card">
      <div className="sched-toolbar">
        <div className="stack" style={{ gap: 2 }}>
          <h2 className="t-card-title">Meetings</h2>
          <p className="t-description">
            {meetings.length
              ? "Pick a date and time for each, or let Auto-schedule place them. Open a meeting to preview and edit its content."
              : "No meetings yet — suggest them above, or add your own."}
          </p>
        </div>
        <div className="sched-toolbar-actions">
          <button type="button" className="btn btn-secondary" onClick={onAdd}>
            <Glyph name="plus" />
            Add meeting
          </button>
          {unscheduled > 0 && (
            <button type="button" className="btn btn-secondary" onClick={onAutoSchedule}>
              <NavIcon name="cal" size={16} />
              Auto-schedule {unscheduled}
            </button>
          )}
          {tentative > 0 && (
            <button type="button" className="btn btn-secondary" onClick={onConfirmAll}>
              <Glyph name="check" />
              Confirm {tentative} tentative
            </button>
          )}
          {dated > 0 && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => downloadFile(`${client || "meetings"} - schedule.ics`, toIcs(meetings, settings, client))}
            >
              <Glyph name="download" />
              Export .ics
            </button>
          )}
        </div>
      </div>

      {groups.map((g) => (
        <div key={g.id || "none"} className="sched-group">
          <div className="sched-group-head">
            <span>{g.label}</span>
            <span className="sched-count">{g.items.length}</span>
          </div>
          <ul className="sched-rows">
            {g.items.map((m) => {
              const warnings = warningsFor(m, meetings, settings);
              return (
                <li key={m.id} className="sched-row" data-status={m.status} data-type={m.type}>
                  <StatusPill meeting={m} onChange={(status) => onUpdate(m.id, { status })} />
                  <button type="button" className="sched-row-title" onClick={() => onOpen(m.id)} title="Open to preview and edit">
                    <span className="sched-dot" aria-hidden />
                    <span className="sched-row-name">{m.title || "Untitled meeting"}</span>
                    {m.origin === "ai" && (
                      <span className="sched-ai" title="Suggested">
                        <Glyph name="sparkles" size={12} />
                      </span>
                    )}
                  </button>
                  <select
                    className="sched-inline sched-inline-type"
                    aria-label="Meeting type"
                    value={m.type}
                    onChange={(e) => onUpdate(m.id, { type: e.target.value as MeetingType })}
                  >
                    {MEETING_TYPES.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                  <input
                    type="date"
                    className="sched-inline"
                    aria-label="Date"
                    value={m.date}
                    onChange={(e) => onUpdate(m.id, { date: e.target.value })}
                  />
                  <input
                    type="time"
                    className="sched-inline"
                    aria-label="Start time"
                    step={900}
                    value={m.time}
                    onChange={(e) => onUpdate(m.id, { time: e.target.value })}
                  />
                  <select
                    className="sched-inline"
                    aria-label="Length"
                    value={m.duration}
                    onChange={(e) => onUpdate(m.id, { duration: Number(e.target.value) })}
                  >
                    {[...new Set([...DURATIONS, m.duration])].sort((a, b) => a - b).map((d) => (
                      <option key={d} value={d}>
                        {durationLabel(d)}
                      </option>
                    ))}
                  </select>
                  <span className="sched-row-end">
                    {warnings.length > 0 && (
                      <span className="sched-warn" title={warnings.join("\n")} aria-label={warnings.join(". ")}>
                        <Glyph name="alert-triangle" size={15} />
                      </span>
                    )}
                    <button type="button" className="icon-btn" aria-label={`Open ${m.title}`} onClick={() => onOpen(m.id)}>
                      <Glyph name="arrow-right" size={15} />
                    </button>
                    <button
                      type="button"
                      className="icon-btn"
                      aria-label={`Delete ${m.title}`}
                      onClick={() => {
                        if (window.confirm(`Delete “${m.title || "this meeting"}”?`)) onRemove(m.id);
                      }}
                    >
                      <Glyph name="x" size={15} />
                    </button>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ))}

      {dated > 0 && (
        <button type="button" className="btn-link sched-to-calendar" onClick={onShowCalendar}>
          See them on the calendar
          <Glyph name="arrow-right" size={14} />
        </button>
      )}
    </section>
  );
}
