"use client";

/**
 * Dragging Hubzy around: pointer events (mouse, pen and touch alike), kept
 * inside the viewport, remembered in localStorage. A drag never ends in a
 * click, and the arrow keys move him too when he has focus.
 */

import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type MouseEvent, type PointerEvent, type RefObject } from "react";

import { HUBZY_DRAG as D } from "./config";

export type HubzyPosition = { x: number; y: number };

function readSaved(): HubzyPosition | null {
  try {
    const saved = JSON.parse(localStorage.getItem(D.storageKey) ?? "null");
    if (typeof saved?.x === "number" && typeof saved?.y === "number") return { x: saved.x, y: saved.y };
  } catch {
    // Storage blocked or garbage: fall back to the default corner.
  }
  return null;
}

function save(pos: HubzyPosition): void {
  try {
    localStorage.setItem(D.storageKey, JSON.stringify(pos));
  } catch {
    // Not remembered this time; he still moves.
  }
}

export function useHubzyDrag(dock: RefObject<HTMLElement | null>) {
  /** Top-left corner in viewport pixels; null = the default bottom-right corner (CSS). */
  const [pos, setPos] = useState<HubzyPosition | null>(null);
  const [dragging, setDragging] = useState(false);
  const latest = useRef<HubzyPosition | null>(null);
  const drag = useRef<{ id: number; dx: number; dy: number; sx: number; sy: number; moved: boolean } | null>(null);
  const justDragged = useRef(false);

  const clamp = useCallback(
    (p: HubzyPosition): HubzyPosition => {
      const box = dock.current?.getBoundingClientRect();
      const w = box?.width ?? 78;
      const h = box?.height ?? 90;
      return {
        x: Math.round(Math.min(Math.max(D.margin, p.x), window.innerWidth - w - D.margin)),
        y: Math.round(Math.min(Math.max(D.margin, p.y), window.innerHeight - h - D.margin)),
      };
    },
    [dock],
  );

  const place = useCallback(
    (p: HubzyPosition) => {
      const next = clamp(p);
      latest.current = next;
      setPos(next);
    },
    [clamp],
  );

  // Restore where he was left, and keep him on screen when the window shrinks.
  useEffect(() => {
    const saved = readSaved();
    if (saved) place(saved);
    const onResize = () => {
      if (latest.current) place(latest.current);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [place]);

  const onPointerDown = (e: PointerEvent<HTMLElement>) => {
    if (e.button !== 0) return;
    const box = dock.current?.getBoundingClientRect();
    if (!box) return;
    drag.current = { id: e.pointerId, dx: e.clientX - box.left, dy: e.clientY - box.top, sx: e.clientX, sy: e.clientY, moved: false };
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: PointerEvent<HTMLElement>) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    if (!d.moved) {
      if (Math.hypot(e.clientX - d.sx, e.clientY - d.sy) < D.threshold) return;
      d.moved = true;
      setDragging(true);
    }
    place({ x: e.clientX - d.dx, y: e.clientY - d.dy });
  };

  const onPointerUp = (e: PointerEvent<HTMLElement>) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    drag.current = null;
    if (!d.moved) return;
    setDragging(false);
    if (latest.current) save(latest.current);
    // Swallow the click that follows this pointerup (if the browser sends one).
    justDragged.current = true;
    window.setTimeout(() => (justDragged.current = false), 0);
  };

  const onClickCapture = (e: MouseEvent<HTMLElement>) => {
    if (!justDragged.current) return;
    justDragged.current = false;
    e.preventDefault();
    e.stopPropagation();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLElement>) => {
    const step = e.shiftKey ? D.keyStep * 4 : D.keyStep;
    const move = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
    const box = dock.current?.getBoundingClientRect();
    if (!move || !box) return;
    e.preventDefault();
    place({ x: box.left + move[0]!, y: box.top + move[1]! });
    if (latest.current) save(latest.current);
  };

  return {
    pos,
    dragging,
    handlers: { onPointerDown, onPointerMove, onPointerUp, onPointerCancel: onPointerUp, onClickCapture, onKeyDown },
  };
}
