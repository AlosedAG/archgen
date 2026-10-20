"use client";

/** "How you'll meet": the dates, rhythm and defaults every meeting starts from. */

import { useId } from "react";

import {
  CADENCES,
  DAYS,
  DURATIONS,
  PLATFORMS,
  TIMEZONES,
  browserTimezone,
  durationLabel,
  type Cadence,
  type ScheduleSettings,
} from "@/lib/schedule-state";

export function PlanSetup({
  settings,
  onChange,
  children,
}: {
  settings: ScheduleSettings;
  onChange: (patch: Partial<ScheduleSettings>) => void;
  /** The Suggest button. */
  children: React.ReactNode;
}) {
  const id = useId();
  const tz = settings.timezone || browserTimezone();
  const zones = TIMEZONES.includes(tz) ? TIMEZONES : [tz, ...TIMEZONES];
  const toggleDay = (day: (typeof DAYS)[number]["id"]) =>
    onChange({
      preferredDays: settings.preferredDays.includes(day)
        ? settings.preferredDays.filter((d) => d !== day)
        : DAYS.map((d) => d.id).filter((d) => d === day || settings.preferredDays.includes(d)),
    });

  return (
    <section className="card sched-setup">
      <div className="heading-row">
        <div className="stack" style={{ gap: 4 }}>
          <h2 className="t-card-title">How you&apos;ll meet</h2>
          <p className="t-description">
            Set the rhythm once. Suggestions and Auto-schedule follow it, and every new meeting starts from these defaults.
          </p>
        </div>
      </div>

      <div className="sched-grid">
        <label className="field">
          <span className="field-label">First meeting from</span>
          <input type="date" className="input" value={settings.startDate} onChange={(e) => onChange({ startDate: e.target.value })} />
        </label>
        <label className="field">
          <span className="field-label">Target go-live</span>
          <input
            type="date"
            className="input"
            value={settings.goLiveDate}
            min={settings.startDate || undefined}
            onChange={(e) => onChange({ goLiveDate: e.target.value })}
          />
        </label>
        <label className="field">
          <span className="field-label">How often</span>
          <select className="select" value={settings.cadence} onChange={(e) => onChange({ cadence: e.target.value as Cadence })}>
            {CADENCES.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field-label">Usual time</span>
          <input type="time" className="input" step={900} value={settings.defaultTime} onChange={(e) => onChange({ defaultTime: e.target.value })} />
        </label>
        <label className="field">
          <span className="field-label">Usual length</span>
          <select className="select" value={settings.duration} onChange={(e) => onChange({ duration: Number(e.target.value) })}>
            {DURATIONS.map((d) => (
              <option key={d} value={d}>
                {durationLabel(d)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field-label">Time zone</span>
          <select className="select" value={tz} onChange={(e) => onChange({ timezone: e.target.value })}>
            {zones.map((z) => (
              <option key={z} value={z}>
                {z.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field-label">Where you meet</span>
          <select className="select" value={settings.platform} onChange={(e) => onChange({ platform: e.target.value })}>
            {PLATFORMS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label className="field sched-span-2">
          <span className="field-label">Default meeting link (optional)</span>
          <input
            type="url"
            className="input"
            placeholder="https://zoom.us/j/… — used for every new meeting"
            value={settings.defaultLink}
            onChange={(e) => onChange({ defaultLink: e.target.value })}
          />
        </label>
        <label className="field">
          <span className="field-label">How many meetings</span>
          <select
            className="select"
            value={settings.meetingCount ?? ""}
            onChange={(e) => onChange({ meetingCount: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">Let the suggestion decide</option>
            {[4, 6, 8, 10, 12, 16, 20].map((n) => (
              <option key={n} value={n}>
                About {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="field">
        <span className="field-label" id={`${id}-days`}>
          Days that work
        </span>
        <div className="choice-chips" role="group" aria-labelledby={`${id}-days`}>
          {DAYS.map((d) => {
            const on = settings.preferredDays.includes(d.id);
            return (
              <button key={d.id} type="button" className="choice-chip" role="checkbox" aria-checked={on} onClick={() => toggleDay(d.id)}>
                {d.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid-2">
        <label className="field">
          <span className="field-label">Who attends</span>
          <textarea
            className="textarea"
            placeholder="e.g. Client: sales director, marketing manager, ops lead. Us: solutions architect, PM."
            value={settings.attendees}
            onChange={(e) => onChange({ attendees: e.target.value })}
          />
        </label>
        <label className="field">
          <span className="field-label">Scheduling notes</span>
          <textarea
            className="textarea"
            placeholder="e.g. No meetings in the last week of the month (their close). Training must be in person. Keep sessions under an hour."
            value={settings.notes}
            onChange={(e) => onChange({ notes: e.target.value })}
          />
        </label>
      </div>

      <div className="sched-suggest">
        <p className="t-caption">
          Suggest meetings reads the discovery call, the Requirements Document, the Joint Evaluation Plan and the Tasks timeline, then
          drafts what each meeting needs to cover, prepare, review and explain. It only adds — nothing you typed is replaced.
        </p>
        {children}
      </div>
    </section>
  );
}
