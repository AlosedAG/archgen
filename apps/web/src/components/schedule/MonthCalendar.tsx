"use client";

/**
 * The month view: every dated meeting on its day. Hover (or focus) a day
 * to see its meetings in detail and adjust the time, length or link in
 * place; click one to open it; drag one to another day to move it. Meetings
 * still without a date wait in a tray beside the month — drag them on.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { NavIcon } from "../NavIcons";
import { Glyph } from "../icons";
import {
  DURATIONS,
  addDays,
  durationLabel,
  isoDay,
  parseDay,
  prettyDate,
  prettyTime,
  safeUrl,
  timeRange,
  todayIso,
  warningsFor,
  type Meeting,
  type ScheduleSettings,
} from "@/lib/schedule-state";

import { TypeTag } from "./MeetingList";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DRAG_TYPE = "application/x-hubzone-meeting";
const CLOSE_DELAY_MS = 140;

function firstOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1, 12);
}

/** The month to open on: the next upcoming meeting's, else the start date's, else this month. */
function initialMonth(meetings: Meeting[], settings: ScheduleSettings): Date {
  const today = todayIso();
  const upcoming = meetings
    .filter((m) => m.date && m.date >= today && m.status !== "cancelled")
    .map((m) => m.date)
    .sort()[0];
  return firstOfMonth(parseDay(upcoming ?? settings.startDate) ?? new Date());
}

const byTime = (a: Meeting, b: Meeting) => (a.time || "99").localeCompare(b.time || "99");

export function MonthCalendar({
  meetings,
  settings,
  onOpen,
  onUpdate,
  onAdd,
  onAutoSchedule,
}: {
  meetings: Meeting[];
  settings: ScheduleSettings;
  onOpen: (id: string) => void;
  onUpdate: (id: string, patch: Partial<Meeting>) => void;
  onAdd: (date: string) => void;
  onAutoSchedule: () => void;
}) {
  const [month, setMonth] = useState(() => initialMonth(meetings, settings));
  const [hoverDay, setHoverDay] = useState<string | null>(null);
  const [dropDay, setDropDay] = useState<string | null>(null);
  const closeTimer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(closeTimer.current), []);

  const today = todayIso();
  const byDay = useMemo(() => {
    const map = new Map<string, Meeting[]>();
    for (const m of meetings) {
      if (!m.date) continue;
      map.set(m.date, [...(map.get(m.date) ?? []), m]);
    }
    for (const list of map.values()) list.sort(byTime);
    return map;
  }, [meetings]);
  const tray = meetings.filter((m) => !m.date && m.status !== "cancelled" && m.status !== "done");

  // Six weeks from the Monday on or before the 1st.
  const offset = (month.getDay() + 6) % 7;
  const gridStart = addDays(month, -offset);
  const days = Array.from({ length: 42 }, (_, i) => addDays(gridStart, i));
  const inMonth = (d: Date) => d.getMonth() === month.getMonth();
  const monthMeetings = meetings
    .filter((m) => m.date && parseDay(m.date)?.getMonth() === month.getMonth() && parseDay(m.date)?.getFullYear() === month.getFullYear())
    .sort((a, b) => a.date.localeCompare(b.date) || byTime(a, b));

  const openDay = (day: string) => {
    window.clearTimeout(closeTimer.current);
    setHoverDay(day);
  };
  const closeDay = (day: string) => {
    window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setHoverDay((cur) => (cur === day ? null : cur)), CLOSE_DELAY_MS);
  };

  const drop = (e: React.DragEvent, day: string) => {
    e.preventDefault();
    setDropDay(null);
    const id = e.dataTransfer.getData(DRAG_TYPE);
    const m = meetings.find((x) => x.id === id);
    if (!m || m.date === day) return;
    onUpdate(id, { date: day, time: m.time || settings.defaultTime, status: m.status === "done" ? m.status : m.status === "confirmed" ? "confirmed" : "tentative" });
  };
  const dragProps = (m: Meeting) => ({
    draggable: true,
    onDragStart: (e: React.DragEvent) => {
      e.dataTransfer.setData(DRAG_TYPE, m.id);
      e.dataTransfer.effectAllowed = "move";
      setHoverDay(null);
    },
  });

  return (
    <div className="sched-cal-layout">
      <section className="card sched-cal">
        <div className="sched-cal-head">
          <h2 className="t-card-title">{month.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</h2>
          <div className="sched-cal-nav">
            <button type="button" className="icon-btn" aria-label="Previous month" onClick={() => setMonth((m) => new Date(m.getFullYear(), m.getMonth() - 1, 1, 12))}>
              <NavIcon name="chevron-right" size={16} className="flip" />
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setMonth(firstOfMonth(new Date()))}>
              Today
            </button>
            <button type="button" className="icon-btn" aria-label="Next month" onClick={() => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + 1, 1, 12))}>
              <NavIcon name="chevron-right" size={16} />
            </button>
          </div>
        </div>

        <div className="sched-cal-grid" role="grid" aria-label="Meetings by day">
          {WEEKDAYS.map((w) => (
            <div key={w} className="sched-cal-wd" role="columnheader">
              {w}
            </div>
          ))}
          {days.map((d, i) => {
            const iso = isoDay(d);
            const list = byDay.get(iso) ?? [];
            const open = hoverDay === iso;
            const col = i % 7;
            const markers = [iso === settings.startDate && "Start", iso === settings.goLiveDate && "Go-live"].filter(Boolean) as string[];
            return (
              <div
                key={iso}
                role="gridcell"
                className="sched-day"
                data-out={!inMonth(d) || undefined}
                data-today={iso === today || undefined}
                data-past={iso < today || undefined}
                data-drop={dropDay === iso || undefined}
                data-open={open || undefined}
                data-side={col >= 4 ? "left" : "right"}
                data-row={i >= 28 ? "bottom" : "top"}
                onMouseEnter={() => openDay(iso)}
                onMouseLeave={() => closeDay(iso)}
                onFocus={() => openDay(iso)}
                onBlur={(e) => {
                  if (!e.currentTarget.contains(e.relatedTarget as Node | null)) closeDay(iso);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Escape") setHoverDay(null);
                }}
                onDragOver={(e) => {
                  if (e.dataTransfer.types.includes(DRAG_TYPE)) {
                    e.preventDefault();
                    setDropDay(iso);
                  }
                }}
                onDragLeave={() => setDropDay((cur) => (cur === iso ? null : cur))}
                onDrop={(e) => drop(e, iso)}
              >
                <div className="sched-day-head">
                  <span className="sched-day-num">{d.getDate()}</span>
                  {markers.map((mk) => (
                    <span key={mk} className="sched-marker" data-kind={mk === "Go-live" ? "golive" : "start"}>
                      {mk}
                    </span>
                  ))}
                  <button type="button" className="sched-day-add" aria-label={`Add a meeting on ${prettyDate(iso)}`} onClick={() => onAdd(iso)}>
                    <Glyph name="plus" size={13} />
                  </button>
                </div>
                <div className="sched-chips">
                  {list.slice(0, 3).map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      className="sched-chip"
                      data-type={m.type}
                      data-status={m.status}
                      onClick={() => onOpen(m.id)}
                      {...dragProps(m)}
                    >
                      {m.time && <span className="sched-chip-time">{prettyTime(m.time)}</span>}
                      <span className="sched-chip-title">{m.title || "Untitled"}</span>
                    </button>
                  ))}
                  {list.length > 3 && <span className="sched-more">+{list.length - 3} more</span>}
                </div>

                {open && list.length > 0 && (
                  <div className="sched-pop" role="dialog" aria-label={`Meetings on ${prettyDate(iso)}`}>
                    <div className="sched-pop-head">
                      {prettyDate(iso, { weekday: "long", month: "long", day: "numeric" })}
                      <span className="t-caption">
                        {list.length} meeting{list.length === 1 ? "" : "s"}
                      </span>
                    </div>
                    {list.map((m) => {
                      const url = safeUrl(m.link);
                      const warnings = warningsFor(m, meetings, settings);
                      return (
                        <div key={m.id} className="sched-pop-item" data-type={m.type}>
                          <div className="sched-pop-title">
                            <span className="sched-dot" aria-hidden />
                            <b>{m.title || "Untitled meeting"}</b>
                          </div>
                          <div className="sched-pop-meta">
                            <TypeTag type={m.type} />
                            <span className="t-caption">{timeRange(m)}</span>
                            <span className="sched-status-text" data-status={m.status}>
                              {m.status}
                            </span>
                          </div>
                          {m.purpose && <p className="sched-pop-purpose">{m.purpose}</p>}
                          {warnings.map((w) => (
                            <p key={w} className="sched-pop-warn">
                              <Glyph name="alert-triangle" size={13} />
                              {w}
                            </p>
                          ))}
                          <div className="sched-pop-edit">
                            <label>
                              <span className="t-caption">Start</span>
                              <input type="time" className="sched-inline" step={900} value={m.time} onChange={(e) => onUpdate(m.id, { time: e.target.value })} />
                            </label>
                            <label>
                              <span className="t-caption">Length</span>
                              <select className="sched-inline" value={m.duration} onChange={(e) => onUpdate(m.id, { duration: Number(e.target.value) })}>
                                {[...new Set([...DURATIONS, m.duration])].sort((a, b) => a - b).map((n) => (
                                  <option key={n} value={n}>
                                    {durationLabel(n)}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label className="sched-pop-link">
                              <span className="t-caption">Link</span>
                              <input
                                type="url"
                                className="sched-inline"
                                placeholder="Meeting link"
                                value={m.link}
                                onChange={(e) => onUpdate(m.id, { link: e.target.value })}
                              />
                            </label>
                          </div>
                          <div className="row" style={{ gap: 8 }}>
                            <button type="button" className="btn btn-secondary btn-sm" onClick={() => onOpen(m.id)}>
                              Open details
                            </button>
                            {url && (
                              <a className="btn btn-secondary btn-sm" href={url} target="_blank" rel="noopener noreferrer">
                                <Glyph name="external-link" size={14} />
                                Join
                              </a>
                            )}
                            {m.status === "tentative" && (
                              <button type="button" className="btn-link" onClick={() => onUpdate(m.id, { status: "confirmed" })}>
                                Confirm
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <p className="t-caption sched-cal-hint">Hover a day to see and adjust its meetings · drag a meeting to move it · + adds one on that day.</p>
      </section>

      <aside className="sched-side">
        <section className="card sched-tray">
          <div className="row-between">
            <h3 className="t-card-title">Needs a date</h3>
            <span className="sched-count">{tray.length}</span>
          </div>
          {tray.length ? (
            <>
              <p className="t-caption">Drag onto a day, or place them all at your cadence.</p>
              <div className="sched-tray-list">
                {tray.map((m) => (
                  <button key={m.id} type="button" className="sched-chip" data-type={m.type} data-status="tentative" onClick={() => onOpen(m.id)} {...dragProps(m)}>
                    <span className="sched-chip-title">{m.title || "Untitled"}</span>
                  </button>
                ))}
              </div>
              <button type="button" className="btn btn-secondary btn-sm" onClick={onAutoSchedule}>
                <NavIcon name="cal" size={14} />
                Auto-schedule
              </button>
            </>
          ) : (
            <p className="t-caption">Every meeting has a date.</p>
          )}
        </section>

        <section className="card sched-agenda">
          <h3 className="t-card-title">This month</h3>
          {monthMeetings.length ? (
            <ul>
              {monthMeetings.map((m) => (
                <li key={m.id}>
                  <button type="button" className="sched-agenda-item" data-type={m.type} data-status={m.status} onClick={() => onOpen(m.id)}>
                    <span className="sched-agenda-date">
                      <b>{parseDay(m.date)?.getDate()}</b>
                      <span>{prettyDate(m.date, { weekday: "short" })}</span>
                    </span>
                    <span className="sched-agenda-text">
                      <span className="sched-agenda-title">{m.title || "Untitled meeting"}</span>
                      <span className="t-caption">{timeRange(m)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="t-caption">No meetings this month.</p>
          )}
        </section>
      </aside>
    </div>
  );
}
