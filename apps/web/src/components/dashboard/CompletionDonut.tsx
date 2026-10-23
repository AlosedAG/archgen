"use client";

/**
 * "Project completed": three nested rings (Scoped, In progress, Outstanding)
 * that sweep in when the dashboard opens, with a legend that carries the
 * numbers, and the portal health score underneath.
 */

import { motion, useReducedMotion } from "framer-motion";

import type { ProjectDashboard } from "@/lib/api";

const RINGS = [
  { key: "scoped", label: "Scoped", color: "#5B53E8", r: 80 },
  { key: "in_progress", label: "In progress", color: "#FF6B4A", r: 62 },
  { key: "outstanding", label: "Outstanding", color: "#5B83E8", r: 44 },
] as const;

export function CompletionDonut({ data }: { data: ProjectDashboard }) {
  const reduce = useReducedMotion();
  const c = data.completion;
  const health = data.insight.health;
  return (
    <section className="db-hero-side db-soft" aria-labelledby="dbc-title">
      <div className="db-panel-head">
        <h3 id="dbc-title">Project completed</h3>
        <span className="db-muted">
          {data.documents} doc{data.documents === 1 ? "" : "s"}
        </span>
      </div>
      <div className="dbc-wrap">
        <ul className="dbc-legend" aria-label={`Of ${c.deliverables} deliverables`}>
          {RINGS.map((ring) => (
            <li key={ring.key}>
              <span className="dbc-dot" style={{ background: ring.color }} aria-hidden />
              <span>
                <span className="dbc-name">{ring.label}</span>
                <b>{c[ring.key]}%</b>
              </span>
            </li>
          ))}
        </ul>
        <svg className="dbc-donut" viewBox="0 0 200 200" aria-hidden>
          <g transform="rotate(-90 100 100)">
            {RINGS.map((ring, i) => {
              const length = 2 * Math.PI * ring.r;
              const shown = Math.min(100, Math.max(0, c[ring.key])) / 100;
              return (
                <g key={ring.key}>
                  <circle cx="100" cy="100" r={ring.r} fill="none" stroke="var(--line)" strokeWidth="13" />
                  {shown > 0 && (
                    <motion.circle
                      cx="100"
                      cy="100"
                      r={ring.r}
                      fill="none"
                      stroke={ring.color}
                      strokeWidth="13"
                      strokeLinecap="round"
                      strokeDasharray={length}
                      initial={{ strokeDashoffset: reduce ? length * (1 - shown) : length }}
                      animate={{ strokeDashoffset: length * (1 - shown) }}
                      transition={reduce ? { duration: 0 } : { duration: 0.9, delay: 0.1 + i * 0.12, ease: [0.2, 0.8, 0.2, 1] }}
                    />
                  )}
                </g>
              );
            })}
          </g>
        </svg>
      </div>
      <p className="dbc-health">
        Portal health{" "}
        {health.score === null ? (
          <span>not audited yet</span>
        ) : (
          <>
            <b>{health.score}</b>/100
          </>
        )}
      </p>
    </section>
  );
}
