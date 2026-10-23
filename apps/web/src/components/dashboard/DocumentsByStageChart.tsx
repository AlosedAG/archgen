"use client";

/**
 * Documents by stage: two capsule bars per stage, Generated (coral) and
 * Outstanding (blue-grey), each standing in a full-height hatched "ghost"
 * track. Bars grow from the baseline; hovering or focusing a stage shows its
 * numbers. The legend names both series, so colour is never the only cue.
 */

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";
import { useState } from "react";

import type { ProjectDashboard } from "@/lib/api";

type Stage = ProjectDashboard["documents_by_stage"][number];

const SERIES = [
  { key: "generated", label: "Generated" },
  { key: "outstanding", label: "Outstanding" },
] as const;

// The shortest a non-zero bar gets (% of the track), so it still reads as a capsule.
const MIN_BAR = 12;

export function DocumentsByStageChart({ stages, seeAllHref }: { stages: Stage[]; seeAllHref: string }) {
  const reduce = useReducedMotion();
  const [active, setActive] = useState<string | null>(null);
  const max = Math.max(1, ...stages.flatMap((s) => [s.generated, s.outstanding]));
  const height = (v: number) => (v > 0 ? Math.max(MIN_BAR, (v / max) * 100) : 0);

  return (
    <section className="db-panel db-soft" aria-labelledby="dbs-title">
      <div className="db-panel-head">
        <h3 id="dbs-title">Documents by stage</h3>
        <Link href={seeAllHref} className="db-seeall">
          See all
        </Link>
      </div>
      <div className="dbs-legend">
        {SERIES.map((s) => (
          <span key={s.key} className="dbs-chip">
            <span className={`dbs-swatch dbs-swatch-${s.key}`} aria-hidden />
            {s.label}
          </span>
        ))}
      </div>
      <div className="dbs-chart" role="group" aria-label="Documents by stage: generated and outstanding per stage">
        {stages.map((s, i) => (
          <div
            key={s.stage}
            className="dbs-stage"
            tabIndex={0}
            aria-label={`${s.stage}: ${s.generated} generated, ${s.outstanding} outstanding`}
            onMouseEnter={() => setActive(s.stage)}
            onMouseLeave={() => setActive((a) => (a === s.stage ? null : a))}
            onFocus={() => setActive(s.stage)}
            onBlur={() => setActive((a) => (a === s.stage ? null : a))}
          >
            <div className="dbs-pair" aria-hidden>
              {SERIES.map((series, j) => {
                const h = height(s[series.key]);
                return (
                  <div key={series.key} className="dbs-track">
                    {h > 0 && (
                      <motion.div
                        className={`dbs-bar dbs-bar-${series.key}`}
                        initial={{ height: reduce ? `${h}%` : "0%" }}
                        animate={{ height: `${h}%` }}
                        transition={reduce ? { duration: 0 } : { duration: 0.7, delay: 0.15 + i * 0.06 + j * 0.05, ease: [0.2, 0.8, 0.2, 1] }}
                      />
                    )}
                  </div>
                );
              })}
            </div>
            <span className="dbs-x" aria-hidden>
              {s.stage}
            </span>
            {active === s.stage && (
              <div className="dbs-tip" role="tooltip">
                <b>{s.stage}</b>
                {SERIES.map((series) => (
                  <span key={series.key}>
                    <span className={`dbs-swatch dbs-swatch-${series.key}`} aria-hidden />
                    {series.label} <b>{s[series.key]}</b>
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
