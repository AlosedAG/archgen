"use client";

/**
 * Ambient HubSpot facts: every 60–120s (random), if you've been idle for a
 * while, aren't typing, and nothing else is open, Hubzy offers a fact. Facts
 * come from a shuffled queue kept in localStorage, so none repeats until
 * every one has been shown, across reloads too.
 */

import { useEffect, useRef } from "react";

import { HUBZY_FACT_TIMING as F, HUBZY_FACTS } from "./config";

const between = ([min, max]: readonly [number, number]) => min + Math.random() * (max - min);

const TEXT_FIELD =
  'textarea, select, [contenteditable=""], [contenteditable="true"], ' +
  "input:not([type=button]):not([type=checkbox]):not([type=radio]):not([type=submit]):not([type=reset]):not([type=range]):not([type=file]):not([type=color])";

/** Is the user in a text field right now? */
function isTyping(): boolean {
  const el = document.activeElement;
  return el instanceof HTMLElement && el.matches(TEXT_FIELD);
}

function shuffled(items: string[]): string[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j]!, out[i]!];
  }
  return out;
}

/** The next fact, taken from the remembered queue (refilled and reshuffled when empty). */
function nextFact(): string | null {
  if (!HUBZY_FACTS.length) return null;
  let queue: string[] = [];
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(F.storageKey) ?? "[]");
    // Keep only facts that are still in the list (it may have been edited).
    if (Array.isArray(saved)) queue = saved.filter((f): f is string => typeof f === "string" && HUBZY_FACTS.includes(f));
  } catch {
    // Storage blocked: a fresh shuffle each time is fine.
  }
  if (!queue.length) queue = shuffled(HUBZY_FACTS);
  const [fact, ...rest] = queue;
  try {
    localStorage.setItem(F.storageKey, JSON.stringify(rest));
  } catch {
    // Not remembered; a later reload may repeat one. Harmless.
  }
  return fact ?? null;
}

/** How long a fact stays up: longer facts get a little longer. */
export function factShowFor(fact: string): number {
  const { base, perChar, min, max } = F.showFor;
  return Math.min(max, Math.max(min, base + fact.length * perChar));
}

/**
 * Calls `speak(fact)` when it's a good moment. `canSpeak` is false while a
 * bubble or the help panel is open.
 */
export function useHubzyFacts(canSpeak: boolean, speak: (fact: string) => void): void {
  const ready = useRef(canSpeak);
  const say = useRef(speak);
  useEffect(() => {
    ready.current = canSpeak;
    say.current = speak;
  });

  useEffect(() => {
    let lastActive = performance.now();
    let nextAt = lastActive + between(F.every);
    const active = () => {
      lastActive = performance.now();
    };
    const onVisible = () => {
      if (!document.hidden) active(); // coming back to the tab counts as activity
    };
    const events = ["keydown", "pointerdown", "wheel", "touchstart", "scroll"] as const;
    events.forEach((name) => window.addEventListener(name, active, { passive: true, capture: true }));
    document.addEventListener("visibilitychange", onVisible);

    const timer = window.setInterval(() => {
      const now = performance.now();
      if (now < nextAt || now - lastActive < F.idleFor) return;
      if (document.hidden || isTyping() || !ready.current) return;
      const fact = nextFact();
      if (fact) say.current(fact);
      nextAt = now + between(F.every);
    }, F.checkEvery);

    return () => {
      window.clearInterval(timer);
      events.forEach((name) => window.removeEventListener(name, active, { capture: true }));
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);
}
