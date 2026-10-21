"use client";

/**
 * Hubzy's speech bubble: sits above him with its tail pointing at him, and
 * flips below or beside him when there's no room, always fully on screen.
 * It pops in from the tail. It never takes focus by itself and only covers
 * its own box.
 */

import { motion } from "framer-motion";
import { useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from "react";

import { springs } from "@/lib/motion";

import { HUBZY_BUBBLE as B } from "./config";

export type Side = "top" | "bottom" | "left" | "right";
type Placement = { side: Side; x: number; y: number; tail: number };

export function placeBubble(anchor: DOMRect, w: number, h: number): Placement {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const m = B.margin;
  const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), Math.max(lo, hi));
  const cx = anchor.left + anchor.width / 2;
  const cy = anchor.top + anchor.height / 2;

  let side: Side;
  if (anchor.top - B.gap - h >= m) side = "top";
  else if (anchor.bottom + B.gap + h <= vh - m) side = "bottom";
  else side = anchor.left - B.gap - w >= m ? "left" : "right";

  if (side === "top" || side === "bottom") {
    // Lean toward the middle of the screen so the bubble has room to grow.
    const preferred = cx > vw / 2 ? cx - w + B.tailInset * 2 : cx - B.tailInset * 2;
    const x = clamp(preferred, m, vw - w - m);
    const y = side === "top" ? anchor.top - B.gap - h : anchor.bottom + B.gap;
    return { side, x, y, tail: clamp(cx - x, B.tailInset, w - B.tailInset) };
  }
  const x = side === "left" ? anchor.left - B.gap - w : anchor.right + B.gap;
  const y = clamp(cy - h / 2, m, vh - h - m);
  return { side, x: clamp(x, m, vw - w - m), y, tail: clamp(cy - y, B.tailInset, h - B.tailInset) };
}

export const ORIGIN: Record<Side, (tail: number) => string> = {
  top: (t) => `${t}px 100%`,
  bottom: (t) => `${t}px 0`,
  left: (t) => `100% ${t}px`,
  right: (t) => `0 ${t}px`,
};

export function HubzyBubble({
  anchor,
  track,
  label,
  children,
  passive,
  onEscape,
}: {
  /** Hubzy's dock: the bubble points at it. */
  anchor: RefObject<HTMLElement | null>;
  /** Changes whenever Hubzy moves, so the bubble follows. */
  track: unknown;
  label: string;
  children: ReactNode;
  /** Ambient (a fact): clicks go straight through to the page underneath. */
  passive?: boolean;
  onEscape?: () => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [place, setPlace] = useState<Placement | null>(null);

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

  const style = {
    left: place?.x ?? 0,
    top: place?.y ?? 0,
    visibility: place ? undefined : "hidden",
    transformOrigin: place ? ORIGIN[place.side](place.tail) : undefined,
    "--hz-tail": `${place?.tail ?? 0}px`,
  } as CSSProperties;

  return (
    <motion.div
      ref={box}
      className="hubzy-say"
      role="region"
      aria-label={label}
      data-side={place?.side}
      data-passive={passive || undefined}
      style={style}
      initial={{ opacity: 0, scale: 0.5 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.7, transition: { duration: 0.14 } }}
      transition={{ ...springs.snappy, damping: 24 }}
      onKeyDown={(e) => {
        if (e.key === "Escape" && onEscape) {
          e.stopPropagation();
          onEscape();
        }
      }}
    >
      <span className="hubzy-say-tail" aria-hidden="true" />
      {children}
    </motion.div>
  );
}
