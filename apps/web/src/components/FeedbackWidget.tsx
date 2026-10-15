"use client";

/**
 * The floating "Feedback" button on every signed-in page: pick Bug / Idea /
 * Question, describe it, attach screenshots (the + button, or paste), and
 * send — it's emailed to the app owner with the page, project and sender
 * filled in automatically.
 */

import { AnimatePresence, motion } from "framer-motion";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ApiError, sendFeedback, type FeedbackRequest } from "@/lib/api";

import { useAppSession } from "./AppSession";
import { spring } from "./ui";

type Kind = FeedbackRequest["kind"];
type Shot = { file: File; url: string };
type Sent = { kind: Kind; text: string; shots: number; reply: string; ok: boolean };

const KINDS: { id: Kind; label: string; placeholder: string }[] = [
  { id: "bug", label: "Bug", placeholder: "What happened, and what did you expect?" },
  { id: "idea", label: "Idea", placeholder: "What would make this better?" },
  { id: "question", label: "Question", placeholder: "What would you like to know?" },
];
const MAX_SHOTS = 5;
const MAX_SHOT_BYTES = 4 * 1024 * 1024;
const MAX_TOTAL_BYTES = 6 * 1024 * 1024;

function toBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] ?? "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function pageTitle(): string {
  return document.querySelector(".page-header h1")?.textContent?.trim() ?? document.title;
}

export function FeedbackWidget() {
  const { project } = useAppSession();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<Kind>("bug");
  const [text, setText] = useState("");
  const [shots, setShots] = useState<Shot[]>([]);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [sent, setSent] = useState<Sent[]>([]);
  const [page, setPage] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const textArea = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (open) {
      setPage(pageTitle());
      textArea.current?.focus();
    }
  }, [open, pathname]);

  // Free preview URLs when the widget goes away (removed shots are freed as they go).
  const shotsRef = useRef(shots);
  shotsRef.current = shots;
  useEffect(() => () => shotsRef.current.forEach((s) => URL.revokeObjectURL(s.url)), []);

  const addFiles = (files: File[]) => {
    setProblem(null);
    const images = files.filter((f) => f.type.startsWith("image/"));
    if (images.length < files.length) setProblem("Only images (screenshots) can be attached.");
    const next = [...shots];
    for (const file of images) {
      if (next.length >= MAX_SHOTS) {
        setProblem(`Up to ${MAX_SHOTS} screenshots per message.`);
        break;
      }
      if (file.size > MAX_SHOT_BYTES) {
        setProblem(`"${file.name}" is larger than 4 MB.`);
        continue;
      }
      next.push({ file, url: URL.createObjectURL(file) });
    }
    if (next.reduce((n, s) => n + s.file.size, 0) > MAX_TOTAL_BYTES) {
      setProblem("The screenshots add up to more than 6 MB. Remove one or send smaller ones.");
      return;
    }
    setShots(next);
  };

  const send = async () => {
    if (!text.trim() && !shots.length) return;
    setBusy(true);
    setProblem(null);
    const entry = { kind, text: text.trim(), shots: shots.length };
    try {
      const attachments = await Promise.all(
        shots.map(async (s) => ({ filename: s.file.name || "screenshot.png", content_type: s.file.type || "image/png", data: await toBase64(s.file) })),
      );
      const result = await sendFeedback({
        kind,
        message: text.trim(),
        page: page || pageTitle(),
        path: pathname,
        project_name: project ? project.client_name || project.name : "",
        attachments,
      });
      setSent((list) => [...list, { ...entry, reply: result.message, ok: true }]);
      setText("");
      shots.forEach((s) => URL.revokeObjectURL(s.url));
      setShots([]);
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Couldn't send it. Check your connection and try again.";
      setSent((list) => [...list, { ...entry, reply: message, ok: false }]);
    }
    setBusy(false);
  };

  const current = KINDS.find((k) => k.id === kind) ?? KINDS[0];
  return (
    <>
      <motion.button
        type="button"
        className="feedback-fab"
        aria-expanded={open}
        aria-controls="feedback-panel"
        onClick={() => setOpen((o) => !o)}
        whileTap={{ scale: 0.95 }}
      >
        {open ? "Close" : "Feedback"}
      </motion.button>
      <AnimatePresence>
        {open && (
          <motion.section
            id="feedback-panel"
            className="feedback-panel"
            role="dialog"
            aria-label="Send feedback"
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={spring}
            onKeyDown={(e) => {
              if (e.key === "Escape") setOpen(false);
            }}
          >
            <h2 className="feedback-title">Something not working? Have an idea?</h2>
            <p className="t-caption">
              Tell us what happened and attach screenshots with the + button (or paste them). It goes straight to Aylin — we add the
              page you&apos;re on{page ? ` (${page})` : ""} automatically.
            </p>
            <div className="feedback-kinds" role="radiogroup" aria-label="Kind of feedback">
              {KINDS.map((k) => (
                <button key={k.id} type="button" role="radio" aria-checked={kind === k.id} className="feedback-kind" onClick={() => setKind(k.id)}>
                  {k.label}
                </button>
              ))}
            </div>

            {sent.length > 0 && (
              <div className="feedback-log" aria-live="polite">
                {sent.map((s, i) => (
                  <div key={i} className="stack" style={{ gap: 6 }}>
                    <div className="feedback-bubble">
                      <b>{KINDS.find((k) => k.id === s.kind)?.label}</b> · {s.text || "(screenshot only)"}
                      {s.shots > 0 && <span className="t-caption"> · {s.shots} screenshot{s.shots === 1 ? "" : "s"}</span>}
                    </div>
                    <div className={s.ok ? "feedback-reply" : "feedback-reply feedback-reply-error"}>{s.reply}</div>
                  </div>
                ))}
              </div>
            )}

            {shots.length > 0 && (
              <div className="feedback-shots">
                {shots.map((s, i) => (
                  <div key={s.url} className="feedback-shot">
                    {/* eslint-disable-next-line @next/next/no-img-element -- a local preview of the user's own file */}
                    <img src={s.url} alt={`Screenshot ${i + 1}: ${s.file.name}`} />
                    <button type="button" aria-label={`Remove ${s.file.name}`} onClick={() => {
                        URL.revokeObjectURL(s.url);
                        setShots(shots.filter((x) => x !== s));
                      }}>
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
            {problem && <p className="feedback-problem">{problem}</p>}

            <form
              className="feedback-compose"
              onSubmit={(e) => {
                e.preventDefault();
                void send();
              }}
            >
              <button type="button" className="feedback-attach" aria-label="Attach screenshots" title="Attach screenshots" onClick={() => fileInput.current?.click()}>
                +
              </button>
              <input
                ref={fileInput}
                type="file"
                accept="image/*"
                multiple
                hidden
                onChange={(e) => {
                  addFiles([...(e.target.files ?? [])]);
                  e.target.value = "";
                }}
              />
              <textarea
                ref={textArea}
                rows={3}
                placeholder={current?.placeholder}
                aria-label="Your feedback"
                value={text}
                maxLength={5000}
                onChange={(e) => setText(e.target.value)}
                onPaste={(e) => {
                  const files = [...e.clipboardData.files];
                  if (files.length) {
                    e.preventDefault();
                    addFiles(files);
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void send();
                }}
              />
              <button type="submit" className="feedback-send" disabled={busy || (!text.trim() && !shots.length)} aria-label="Send feedback">
                {busy ? "…" : "↑"}
              </button>
            </form>
          </motion.section>
        )}
      </AnimatePresence>
    </>
  );
}
