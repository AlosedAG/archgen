"use client";

/**
 * Hubzy's help panel (the mockup's chat panel, without free typing): pick a
 * question and he answers from the workspace's Hubzy Answers table. Questions
 * for the current page come first, then the general ones. It opens next to
 * Hubzy wherever he is, takes focus when it opens, and Esc closes it.
 */

import { motion } from "framer-motion";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties, type Dispatch, type RefObject, type SetStateAction } from "react";

import { Glyph } from "@/components/icons";
import { listHubzyTopics, type HubzyTopic } from "@/lib/api";
import { springs } from "@/lib/motion";

import { HUBZY_PANEL as P } from "./config";
import { ORIGIN, placeBubble, type Side } from "./HubzyBubble";

export type HubzyLine = { id: number; from: "hubzy" | "me"; text: string };

// The last answers loaded, so the panel opens instantly next time (it still refreshes).
let cached: HubzyTopic[] | null = null;

/** The key a topic's `page` is matched against: the last part of the URL ("" on a project's root). */
export function pageKey(pathname: string): string {
  const parts = pathname.split("/").filter(Boolean);
  if (parts[0] === "projects" && parts.length === 2) return "";
  return parts.at(-1) ?? "";
}

const between = ([min, max]: readonly [number, number]) => min + Math.random() * (max - min);

/** The small Hubzy from the mockup's panel header. */
function HubzyMini() {
  return (
    <svg viewBox="0 0 40 44" fill="none" aria-hidden="true">
      <line x1="20" y1="11" x2="20" y2="5" stroke="#1A1B2E" strokeWidth="2" />
      <circle cx="20" cy="3.6" r="3.1" fill="#FF5A5F" stroke="#1A1B2E" strokeWidth="1.5" />
      <circle cx="20" cy="26" r="15" fill="#5B53E8" stroke="#1A1B2E" strokeWidth="2" />
      <path d="M30 17a15 15 0 0 1 3 10" stroke="#BFC7FF" strokeWidth="1.6" strokeLinecap="round" />
      <ellipse cx="13.5" cy="30" rx="3" ry="1.6" fill="#FF9DC0" />
      <ellipse cx="26.5" cy="30" rx="3" ry="1.6" fill="#FF9DC0" />
      <circle cx="15.5" cy="25" r="2.1" fill="#15162A" />
      <circle cx="14.8" cy="24.2" r=".7" fill="#fff" />
      <circle cx="24.5" cy="25" r="2.1" fill="#15162A" />
      <circle cx="23.8" cy="24.2" r=".7" fill="#fff" />
      <path d="M17 31q3 2.5 6 0" stroke="#15162A" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function HubzyPanel({
  anchor,
  track,
  name,
  lines,
  setLines,
  onTalk,
  onClose,
}: {
  /** Hubzy's dock: the panel opens next to it. */
  anchor: RefObject<HTMLElement | null>;
  /** Changes whenever Hubzy moves, so the panel follows. */
  track: unknown;
  /** The signed-in user's first name, for the hello. */
  name: string;
  /** The conversation, kept by Hubzy so it survives closing the panel. */
  lines: HubzyLine[];
  setLines: Dispatch<SetStateAction<HubzyLine[]>>;
  /** Move Hubzy's mouth for this long. */
  onTalk: (ms: number) => void;
  onClose: () => void;
}) {
  const page = pageKey(usePathname());
  const titleId = useId();
  const box = useRef<HTMLDivElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const [place, setPlace] = useState<{ side: Side; x: number; y: number; tail: number } | null>(null);
  const [topics, setTopics] = useState<HubzyTopic[] | null>(cached);
  const [status, setStatus] = useState<"loading" | "ready" | "error">(cached ? "ready" : "loading");
  const [typing, setTyping] = useState(false);
  const timers = useRef(new Set<number>());

  const later = useCallback((fn: () => void, ms: number) => {
    const id = window.setTimeout(() => {
      timers.current.delete(id);
      fn();
    }, ms);
    timers.current.add(id);
  }, []);
  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach((id) => window.clearTimeout(id));
  }, []);

  const say = useCallback(
    (from: HubzyLine["from"], text: string) => setLines((all) => [...all, { id: (all.at(-1)?.id ?? 0) + 1, from, text }]),
    [setLines],
  );

  // Load (or refresh) the answers; give up after a while so he can say so.
  const load = useCallback(() => {
    const abort = new AbortController();
    const timeout = window.setTimeout(() => abort.abort(), P.loadTimeout);
    if (!cached) setStatus("loading");
    listHubzyTopics(abort.signal)
      .then((fresh) => {
        cached = fresh;
        setTopics(fresh);
        setStatus("ready");
      })
      .catch(() => {
        if (!cached) setStatus("error");
      })
      .finally(() => window.clearTimeout(timeout));
    return () => abort.abort();
  }, []);
  useEffect(() => load(), [load]);

  // Say hello the first time the panel opens.
  useEffect(() => {
    if (lines.length) return;
    later(() => {
      say("hubzy", P.hello(name));
      onTalk(P.talkFor);
    }, P.helloDelay);
    // Only when the panel opens.
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Bring the newest message into view, from its first line if it's a long one.
  useEffect(() => {
    const el = log.current;
    const last = el?.lastElementChild;
    if (!el || !(last instanceof HTMLElement)) return;
    el.scrollTo({ top: Math.min(el.scrollHeight, last.offsetTop - el.offsetTop - 12) });
  }, [lines, typing, status]);

  // Focus moves into the panel once it's placed (it's hidden until then).
  const placed = place !== null;
  useEffect(() => {
    if (placed) box.current?.focus({ preventScroll: true });
  }, [placed]);

  // Esc closes it from anywhere (focus may sit on a button that just got disabled).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Sit next to Hubzy, on whichever side has room, and follow him.
  useLayoutEffect(() => {
    const update = () => {
      const a = anchor.current?.getBoundingClientRect();
      const b = box.current;
      if (a && b) setPlace(placeBubble(a, b.offsetWidth, b.offsetHeight));
    };
    update();
    const sized = new ResizeObserver(update);
    if (box.current) sized.observe(box.current);
    window.addEventListener("resize", update);
    return () => {
      sized.disconnect();
      window.removeEventListener("resize", update);
    };
  }, [anchor, track]);

  const ask = (topic: HubzyTopic) => {
    say("me", topic.question);
    setTyping(true);
    later(() => {
      setTyping(false);
      say("hubzy", topic.answer);
      onTalk(P.talkFor);
    }, between(P.typingFor));
  };

  const forPage = (topics ?? []).filter((t) => t.page && t.page === page);
  const general = (topics ?? []).filter((t) => !t.page);

  const style = {
    left: place?.x ?? 0,
    top: place?.y ?? 0,
    visibility: place ? undefined : "hidden",
    transformOrigin: place ? ORIGIN[place.side](place.tail) : undefined,
  } as CSSProperties;

  const group = (label: string, items: HubzyTopic[]) =>
    items.length > 0 && (
      <div className="hubzy-chip-group" role="group" aria-label={label}>
        <p className="hubzy-chip-label">{label}</p>
        {items.map((t) => (
          <button key={t.id} type="button" className="hubzy-chip" disabled={typing} onClick={() => ask(t)}>
            {t.question}
          </button>
        ))}
      </div>
    );

  return (
    <motion.div
      ref={box}
      className="hubzy-chat"
      role="dialog"
      aria-labelledby={titleId}
      tabIndex={-1}
      style={style}
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.92, transition: { duration: 0.16 } }}
      transition={{ ...springs.snappy, damping: 30 }}
    >
      <div className="hubzy-head">
        <span className="mini">
          <HubzyMini />
        </span>
        <h2 id={titleId}>Hubzy</h2>
        <button type="button" className="hubzy-x" aria-label="Close Hubzy" onClick={onClose}>
          <Glyph name="x" size={16} />
        </button>
      </div>
      <div className="hubzy-log" ref={log} aria-live="polite">
        {lines.map((line) => (
          <div key={line.id} className={`hubzy-row hubzy-in${line.from === "me" ? " me" : ""}`}>
            {line.from === "hubzy" && (
              <span className="pfp">
                <HubzyMini />
              </span>
            )}
            <div className="hubzy-bubble">{line.text}</div>
          </div>
        ))}
        {status === "error" && (
          <div className="hubzy-row hubzy-in">
            <span className="pfp">
              <HubzyMini />
            </span>
            <div className="hubzy-bubble">{P.unreachable}</div>
          </div>
        )}
        {status === "ready" && topics?.length === 0 && (
          <div className="hubzy-row hubzy-in">
            <span className="pfp">
              <HubzyMini />
            </span>
            <div className="hubzy-bubble">{P.empty}</div>
          </div>
        )}
        {typing && (
          <div className="hubzy-row hubzy-in">
            <span className="pfp">
              <HubzyMini />
            </span>
            <div className="hubzy-bubble" role="status" aria-label="Hubzy is typing">
              <span className="hubzy-dots" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
            </div>
          </div>
        )}
      </div>
      <div className="hubzy-chips">
        {status === "loading" && <p className="hubzy-chip-label">Loading questions…</p>}
        {status === "error" && (
          <button type="button" className="hubzy-chip" onClick={load}>
            {P.retry}
          </button>
        )}
        {status === "ready" && (
          <>
            {group(P.pageGroup, forPage)}
            {group(P.generalGroup, general)}
          </>
        )}
      </div>
    </motion.div>
  );
}
