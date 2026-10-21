"use client";

/**
 * Hubzy's idle life: blinks at random intervals (sometimes a double), glances
 * left / right / toward the cursor, and pulls a small expression now and then.
 * Every timer is randomised and pauses while the tab is hidden. Under
 * reduced motion he still blinks (and bobs gently, in CSS) but doesn't glance
 * around or pull expressions.
 */

import { useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState, type RefObject } from "react";

import { EXPRESSIONS, HUBZY_TIMING as T, LOOK_RANGE, type HubzyExpression } from "./config";
import type { HubzyFace } from "./HubzyArt";

const between = ([min, max]: readonly [number, number]) => min + Math.random() * (max - min);
const pick = <V,>(items: readonly V[]): V => items[Math.floor(Math.random() * items.length)]!;
const CENTER = { x: 0, y: 0 };

/** A setTimeout chain that waits while the page is hidden instead of piling up. */
function loop(step: () => number, firstDelay: number, timers: Set<number>): void {
  const run = (delay: number) => {
    const id = window.setTimeout(() => {
      timers.delete(id);
      if (document.hidden) return run(1000);
      run(step());
    }, delay);
    timers.add(id);
  };
  run(firstDelay);
}

export function useHubzyLife(anchor: RefObject<HTMLElement | null>): HubzyFace {
  const reduce = useReducedMotion();
  const [blinking, setBlinking] = useState(false);
  const [look, setLook] = useState(CENTER);
  const [expression, setExpression] = useState<HubzyExpression | null>(null);
  const cursor = useRef<{ x: number; y: number; at: number } | null>(null);

  // Remember where the pointer was last seen (no re-render on every move).
  useEffect(() => {
    if (reduce) return;
    const onMove = (e: PointerEvent) => {
      cursor.current = { x: e.clientX, y: e.clientY, at: performance.now() };
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, [reduce]);

  useEffect(() => {
    if (reduce) {
      setLook(CENTER);
      setExpression(null);
    }
    const timers = new Set<number>();
    const later = (fn: () => void, ms: number) => {
      const id = window.setTimeout(() => {
        timers.delete(id);
        fn();
      }, ms);
      timers.add(id);
    };

    // Blinks: random gaps, the occasional quick double.
    loop(
      () => {
        setBlinking(true);
        later(() => setBlinking(false), T.blinkLength);
        if (Math.random() < T.doubleBlinkChance) {
          later(() => setBlinking(true), T.blinkLength * 2);
          later(() => setBlinking(false), T.blinkLength * 3);
        }
        return between(T.blinkEvery);
      },
      between(T.blinkEvery),
      timers,
    );
    if (reduce) return () => timers.forEach((id) => window.clearTimeout(id));

    // Glances: toward a recently-moved cursor, otherwise a casual left / right / up.
    loop(
      () => {
        const box = anchor.current?.getBoundingClientRect();
        const c = cursor.current;
        let target: { x: number; y: number };
        if (box && c && performance.now() - c.at < T.cursorFreshFor) {
          const dx = c.x - (box.left + box.width / 2);
          const dy = c.y - (box.top + box.height * 0.45);
          const len = Math.hypot(dx, dy) || 1;
          target = { x: (dx / len) * LOOK_RANGE.x, y: (dy / len) * LOOK_RANGE.y };
        } else {
          target = pick([
            { x: -LOOK_RANGE.x, y: 0 },
            { x: LOOK_RANGE.x, y: 0 },
            { x: -LOOK_RANGE.x * 0.7, y: -LOOK_RANGE.y * 0.6 },
            { x: LOOK_RANGE.x * 0.7, y: -LOOK_RANGE.y * 0.6 },
          ]);
        }
        setLook(target);
        later(() => setLook(CENTER), between(T.glanceHold));
        return between(T.glanceEvery);
      },
      between(T.glanceEvery),
      timers,
    );

    // Expressions: one small thing at a time, then back to neutral.
    loop(
      () => {
        const next = pick(EXPRESSIONS);
        setExpression(next);
        later(() => setExpression(null), T.expressionLength[next]);
        return between(T.expressionEvery);
      },
      between(T.expressionEvery),
      timers,
    );

    return () => timers.forEach((id) => window.clearTimeout(id));
  }, [reduce, anchor]);

  return { blinking, look, expression };
}
