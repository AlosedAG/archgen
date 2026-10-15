"use client";

/**
 * Progress while an AI document is drafted: a filling bar with a
 * percentage, what's happening now ("Writing section 3 of 8: Current
 * State — Data"), which model is drafting (or that a busy one is being
 * retried / replaced), and the time elapsed.
 *
 * The model doesn't report progress, so it's estimated: before any text
 * arrives the bar creeps up while the model reads and plans (up to ~35%);
 * after that it follows the sections written against the sections the
 * document is expected to have.
 */

import { motion } from "framer-motion";
import { useEffect, useState } from "react";

const THINKING_SHARE = 35;
const CHARS_PER_SECTION = 1200;

function elapsedLabel(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function estimateProgress(text: string, sections: number, elapsedSeconds: number) {
  const headings = [...text.matchAll(/^##\s+(.+)$/gm)].map((m) => m[1]?.trim() ?? "");
  if (!text.trim()) {
    const pct = 4 + (THINKING_SHARE - 4) * (1 - Math.exp(-elapsedSeconds / 30));
    return { pct, stage: elapsedSeconds < 3 ? "Sending your notes…" : "Reading your notes and planning the document…", current: "" };
  }
  const total = Math.max(sections, headings.length, 1);
  const lastStart = text.lastIndexOf(`## ${headings.at(-1) ?? ""}`);
  const partial = headings.length ? Math.min(1, (text.length - Math.max(lastStart, 0)) / CHARS_PER_SECTION) : 0;
  const done = Math.max(headings.length - 1, 0) + partial;
  const pct = THINKING_SHARE + (98 - THINKING_SHARE) * Math.min(1, done / total);
  return {
    pct,
    stage: headings.length ? `Writing section ${Math.min(headings.length, total)} of ${total}` : "Starting to write…",
    current: headings.at(-1) ?? "",
  };
}

export function DraftProgress({ text, sections, startedAt, status }: { text: string; sections: number; startedAt: number; status: string | null }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(timer);
  }, []);
  const elapsed = Math.max(0, Math.round((now - startedAt) / 1000));
  const { pct, stage, current } = estimateProgress(text, sections, elapsed);
  const rounded = Math.round(pct);

  return (
    <div className="draft-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={rounded} aria-valuetext={`${rounded}% — ${stage}`}>
      <div className="draft-progress-head">
        <span className="draft-progress-stage">
          {stage}
          {current && <span className="draft-progress-section">: {current}</span>}
        </span>
        <span className="draft-progress-pct">{rounded}%</span>
      </div>
      <div className="draft-progress-track">
        <motion.div className="draft-progress-fill" initial={{ width: "2%" }} animate={{ width: `${pct}%` }} transition={{ duration: 0.6, ease: "easeOut" }} />
      </div>
      <div className="draft-progress-foot">
        <span>{status ?? "Connecting to the AI model…"}</span>
        <span>{elapsedLabel(elapsed)} elapsed · usually 1–2 minutes</span>
      </div>
    </div>
  );
}
