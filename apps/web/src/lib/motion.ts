/**
 * Motion tokens: every duration, easing curve, spring and reusable variant
 * the app animates with. Components import from here instead of writing
 * their own numbers, so the feel stays consistent and is tuned in one place.
 *
 * Reference feel: quick and subtle (Linear, Attio). Animate transform and
 * opacity only. Reduced motion: <MotionConfig reducedMotion="user"> (in
 * Providers) drops transform animation app-wide; components that do more
 * than that use `useReducedMotion()` with the `reduced` variants below.
 */

import { useReducedMotion, type Transition, type Variants } from "framer-motion";

/** Seconds. */
export const duration = {
  instant: 0,
  fast: 0.15,
  base: 0.2,
  slow: 0.3,
} as const;

/** The shared easing curve: a quick start that settles softly. */
export const ease = [0.2, 0.7, 0.2, 1] as const;

/** Small distances (px) for enter / exit offsets — enough to read as movement, never more. */
export const offset = {
  page: 6,
  item: 8,
} as const;

/** Tweens built from the tokens. */
export const tween = {
  fast: { duration: duration.fast, ease } satisfies Transition,
  base: { duration: duration.base, ease } satisfies Transition,
  slow: { duration: duration.slow, ease } satisfies Transition,
} as const;

/** Physical springs for things that follow the pointer or slide between positions (tab indicators, nav highlight). */
export const springs = {
  snappy: { type: "spring", stiffness: 500, damping: 38 } satisfies Transition,
  gentle: { type: "spring", stiffness: 300, damping: 30 } satisfies Transition,
} as const;

// ---- Reusable variants ("hidden" -> "visible", optional "exit") --------------

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: tween.base },
  exit: { opacity: 0, transition: tween.fast },
};

export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: offset.item },
  visible: { opacity: 1, y: 0, transition: tween.base },
  exit: { opacity: 0, y: offset.item / 2, transition: tween.fast },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  visible: { opacity: 1, scale: 1, transition: tween.base },
  exit: { opacity: 0, scale: 0.98, transition: tween.fast },
};

/** Parent for staggered children (each child uses fadeInUp or similar). */
export const stagger = (each = 0.04, delayChildren = 0): Variants => ({
  hidden: {},
  visible: { transition: { staggerChildren: each, delayChildren } },
});

/** A page arriving after navigation: a short fade with a slight rise. */
export const pageEnter: Variants = {
  hidden: { opacity: 0, y: offset.page },
  visible: { opacity: 1, y: 0, transition: tween.slow },
};

// ---- Micro-interactions (Phase 2) -------------------------------------------------

/** Small things popping in and out (tokens in a multiselect, a chip's check mark). */
export const pop: Variants = {
  hidden: { opacity: 0, scale: 0.85 },
  visible: { opacity: 1, scale: 1, transition: springs.snappy },
  exit: { opacity: 0, scale: 0.85, transition: tween.fast },
};

/** Press feedback for motion buttons (plain `.btn`s get the same from CSS). */
export const press = { scale: 0.97 } as const;

/** Hover lift for clickable cards. */
export const lift = { y: -2 } as const;

/** Content that opens and closes in place (accordions, "Other — specify", "Why we ask"). */
export const collapse: Variants = {
  closed: { height: 0, opacity: 0, transition: tween.fast },
  open: { height: "auto", opacity: 1, transition: tween.base },
};

/** Dropdown lists and popovers: a short drop from above. */
export const dropdown: Variants = {
  hidden: { opacity: 0, y: -4 },
  visible: { opacity: 1, y: 0, transition: { duration: duration.fast * 0.8, ease } },
  exit: { opacity: 0, y: -4, transition: { duration: duration.fast * 0.6, ease } },
};

/** Tab panels swapping in place. */
export const panelSwap: Variants = {
  hidden: { opacity: 0, y: offset.page },
  visible: { opacity: 1, y: 0, transition: { duration: duration.fast, ease } },
  exit: { opacity: 0, y: -offset.page / 2, transition: { duration: duration.fast * 0.7, ease } },
};

/** Rows inserted into a live list (follow-ups, required tasks): slide in from the left. */
export const insertRow: Variants = {
  hidden: { opacity: 0, x: -offset.item },
  visible: { opacity: 1, x: 0, transition: springs.snappy },
  exit: { opacity: 0, x: -offset.item, transition: tween.fast },
};

/** Something new to notice (a revealed follow-up, a new task): a brief warm tint that fades. */
export const highlight = {
  from: "rgba(247, 121, 29, 0.14)",
  to: "rgba(247, 121, 29, 0)",
  transition: { duration: 1.1, ease: "easeOut" } satisfies Transition,
} as const;

/** Stagger timings: one orchestrated entrance per screen, so keep them short. */
export const staggerTiming = {
  cards: 0.04,
  rows: 0.025,
  /** Lists longer than this appear together — a long cascade reads as slow. */
  maxStaggered: 12,
} as const;

/**
 * Stagger variants for a list of `count` items: no cascade for long lists,
 * and none at all under reduced motion (items then simply fade in together).
 * Children of a staggered list must not set their own variant labels for
 * initial / animate / exit, or they stop inheriting the parent's state —
 * pass objects (e.g. `exit={{ ... }}`) instead.
 */
export function useStagger(count: number, each: number = staggerTiming.cards, delayChildren = 0): Variants {
  const reduce = useReducedMotion();
  return stagger(reduce || count > staggerTiming.maxStaggered ? 0 : each, reduce ? 0 : delayChildren);
}

/** Reduced-motion stand-ins: opacity only, and quicker. */
export const reduced = {
  pageEnter: {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { duration: duration.fast } },
  } satisfies Variants,
} as const;
