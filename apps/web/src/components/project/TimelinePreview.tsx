"use client";

/**
 * The SOW's indicative schedule as a small Gantt chart: one bar per phase
 * over a week axis, the buffer / validation period in the accent colour.
 * The bars come from the API's analysis, so they match the PDF exactly.
 */

import type { ProposalAnalysis } from "@/lib/api";

export function TimelinePreview({ chart }: { chart: ProposalAnalysis["timeline"] }) {
  const total = Math.max(1, chart.total_weeks);
  if (!chart.bars.length) return null;
  const step = total <= 16 ? 1 : total <= 32 ? 2 : 4;
  const ticks = Array.from({ length: Math.ceil(total / step) }, (_, i) => 1 + i * step);
  return (
    <figure className="gantt" aria-label={`Indicative timeline: about ${total} weeks`}>
      <div className="gantt-row gantt-axis" aria-hidden>
        <span />
        <span className="gantt-track">
          {ticks.map((w) => (
            <span key={w} className="gantt-tick" style={{ left: `${((w - 1) / total) * 100}%` }}>
              W{w}
            </span>
          ))}
        </span>
      </div>
      {chart.bars.map((bar, i) => (
        <div key={`${bar.phase}-${i}`} className="gantt-row">
          <span className={`gantt-label${bar.buffer ? " gantt-label-buffer" : ""}`}>{bar.phase}</span>
          <span className="gantt-track">
            <span
              className={`gantt-bar${bar.buffer ? " gantt-bar-buffer" : ""}`}
              style={{ left: `${((bar.start - 1) / total) * 100}%`, width: `${(bar.weeks / total) * 100}%` }}
              title={`${bar.phase}: weeks ${bar.start}-${bar.start + bar.weeks - 1}`}
            >
              {bar.weeks} wk
            </span>
          </span>
        </div>
      ))}
      <figcaption className="t-caption">About {total} weeks from kickoff. Drawn the same way in the PDF.</figcaption>
    </figure>
  );
}
