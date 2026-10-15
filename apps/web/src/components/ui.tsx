"use client";

/** Shared UI primitives from the ArchScope component sheet, with motion built in. */

import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import { ApiError, downloadFile, saveToLibrary, type GeneratedFile } from "@/lib/api";
import { collapse, dropdown, fadeInUp, offset, panelSwap, press, springs, stagger, staggerTiming, tween } from "@/lib/motion";

import { Glyph } from "./icons";

// Motion presets come from the central tokens (lib/motion.ts).
export const spring = springs.snappy;
export const fade = tween.base;

// ---- Icons ------------------------------------------------------------------

/** The design's icons (exported from Figma into /public/icons), at their designed size. */
export type IconName =
  | "chevron-right"
  | "chevron-down"
  | "search"
  | "chevron-down-18"
  | "message-square"
  | "sparkles"
  | "rotate-ccw"
  | "megaphone"
  | "handshake"
  | "headset"
  | "workflow"
  | "panels-top-left"
  | "credit-card";

const ICON_SIZE: Partial<Record<IconName, number>> = {
  "chevron-down-18": 18,
  megaphone: 24,
  handshake: 24,
  headset: 24,
  workflow: 24,
  "panels-top-left": 24,
  "credit-card": 24,
};

export function Icon({ name }: { name: IconName }) {
  const size = ICON_SIZE[name] ?? 16;
  // eslint-disable-next-line @next/next/no-img-element -- static design SVGs at fixed size
  return <img src={`/icons/${name}.svg`} width={size} height={size} alt="" aria-hidden style={{ flex: "none" }} />;
}

// ---- Tabs -------------------------------------------------------------------

export type TabDef<T extends string> = { id: T; label: string };

/**
 * Accessible tab list. `primary` is the segmented control (active tab on a
 * white tile); `secondary` is the underlined row. The active marker slides
 * between tabs; `layoutId` must be unique per tab list on the page.
 */
export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
  layoutId,
  variant,
  label,
}: {
  tabs: TabDef<T>[];
  active: T;
  onChange: (id: T) => void;
  layoutId: string;
  variant: "primary" | "secondary";
  label: string;
}) {
  const primary = variant === "primary";
  return (
    <div className={primary ? "tabs-primary" : "tabs-secondary"} role="tablist" aria-label={label}>
      {tabs.map((tab) => {
        const selected = tab.id === active;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={`panel-${layoutId}`}
            className={primary ? "tab-primary" : "tab-secondary"}
            onClick={() => onChange(tab.id)}
          >
            {selected && (
              <motion.span layoutId={layoutId} className={primary ? "tab-primary-bg" : "tab-underline"} transition={spring} />
            )}
            <span className="tab-label">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/** Cross-fades between tab panels when `panelKey` changes. */
export function TabPanel({ panelKey, id, children }: { panelKey: string; id: string; children: React.ReactNode }) {
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={panelKey}
        id={`panel-${id}`}
        role="tabpanel"
        className="stack"
        style={{ gap: 24 }}
        variants={panelSwap}
        initial="hidden"
        animate="visible"
        exit="exit"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

// ---- Checkbox ---------------------------------------------------------------

/** Checkbox whose tick draws itself in. */
export function Checkbox({
  checked,
  onChange,
  children,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children?: React.ReactNode;
}) {
  return (
    <label className="check" data-checked={checked}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <CheckMark checked={checked} />
      {children}
    </label>
  );
}

export function CheckMark({ checked }: { checked: boolean }) {
  return (
    <motion.span
      className="check-box"
      data-checked={checked}
      animate={{ scale: checked ? [1, 1.15, 1] : 1 }}
      transition={tween.base}
    >
      <svg width="10" height="10" viewBox="0 0 12 12" aria-hidden>
        <motion.path
          d="M2.5 6.2 5 8.6 9.6 3.4"
          fill="none"
          stroke="#fff"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={false}
          animate={{ pathLength: checked ? 1 : 0, opacity: checked ? 1 : 0 }}
          transition={tween.base}
        />
      </svg>
    </motion.span>
  );
}

// ---- Reveal / numbers ---------------------------------------------------------

/** Height + fade reveal for content that appears and disappears in place. */
export function Reveal({ show, children }: { show: boolean; children: React.ReactNode }) {
  return (
    <AnimatePresence initial={false}>
      {show && (
        <motion.div variants={collapse} initial="closed" animate="open" exit="closed" style={{ overflow: "hidden" }}>
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** A number that rolls when it changes. */
export function AnimatedNumber({ value }: { value: number }) {
  return (
    <AnimatePresence mode="popLayout" initial={false}>
      <motion.span
        key={value}
        initial={{ y: -offset.item, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: offset.item, opacity: 0 }}
        transition={spring}
        style={{ display: "inline-block" }}
      >
        {value}
      </motion.span>
    </AnimatePresence>
  );
}

// ---- Staggered entrance -------------------------------------------------------

/**
 * A list whose items rise in one after another the first time it renders
 * (each child must be a <StaggerItem>). Long lists appear together — a long
 * cascade reads as slow.
 */
export function StaggerList({
  as = "div",
  count,
  each = staggerTiming.cards,
  className,
  style,
  children,
}: {
  as?: "div" | "ul";
  count: number;
  each?: number;
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}) {
  const Component = as === "ul" ? motion.ul : motion.div;
  return (
    <Component
      className={className}
      style={style}
      variants={stagger(count > staggerTiming.maxStaggered ? 0 : each)}
      initial="hidden"
      animate="visible"
    >
      {children}
    </Component>
  );
}

export function StaggerItem({
  as = "div",
  className,
  children,
  ...rest
}: { as?: "div" | "li"; className?: string; children: React.ReactNode } & Omit<
  React.ComponentProps<typeof motion.div>,
  "variants" | "children" | "className"
>) {
  const Component = as === "li" ? motion.li : motion.div;
  return (
    <Component className={className} variants={fadeInUp} {...(rest as object)}>
      {children}
    </Component>
  );
}

// ---- Callout -----------------------------------------------------------------

const CALLOUT_GLYPH = { info: "info", warning: "alert-triangle", error: "alert-circle", success: "check-circle" } as const;

/** Tinted callout with a bold first line and an optional body. */
export function Callout({
  tone,
  title,
  children,
}: {
  tone: "info" | "warning" | "error" | "success";
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <motion.div
      className={`callout callout-${tone}`}
      role={tone === "error" ? "alert" : "status"}
      variants={dropdown}
      initial="hidden"
      animate="visible"
    >
      <p className="callout-title">
        <Glyph name={CALLOUT_GLYPH[tone]} />
        <span>{title}</span>
      </p>
      {children && <div className="callout-body">{children}</div>}
    </motion.div>
  );
}

// ---- Export footer -------------------------------------------------------------

export type ExportAction = {
  /** Button label, e.g. ".pdf". */
  label: string;
  /** Produce the file (downloaded on click, or saved to the library). */
  make: () => Promise<GeneratedFile> | GeneratedFile;
};

/**
 * The document export footer: outlined download buttons, the orange
 * "Save to Project Library" (every format, filed under the project), and
 * the "fully editable" caption. Failures show inline.
 */
export function ExportFooter({
  actions,
  library,
  divider = true,
}: {
  actions: ExportAction[];
  /** Where "Save to Project Library" files it; omit to hide the button. */
  library?: { projectId: string; documentType: string; title?: string };
  divider?: boolean;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<number | null>(null);

  const run = async (key: string, work: () => Promise<void>) => {
    setBusy(key);
    setError(null);
    try {
      await work();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That didn't work. Try again.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className={divider ? "export-footer" : "stack"} style={divider ? undefined : { gap: 12 }}>
      <div className="row-between">
        <div className="download-group">
          {actions.map((action) => (
            <motion.button
              key={action.label}
              type="button"
              className="btn btn-secondary"
              whileTap={press}
              disabled={busy !== null}
              onClick={() => run(action.label, async () => downloadFile(await action.make()))}
            >
              {busy === action.label ? "Preparing…" : <><Glyph name="download" /> {action.label}</>}
            </motion.button>
          ))}
        </div>
        {library && (
          <motion.button
            type="button"
            className="btn btn-primary"
            whileTap={press}
            disabled={busy !== null}
            onClick={() =>
              run("library", async () => {
                const files = await Promise.all(actions.map((a) => a.make()));
                for (const file of files) await saveToLibrary(library.projectId, library.documentType, file, library.title);
                setSaved(files.length);
              })
            }
          >
            {busy === "library" ? "Saving…" : "Save to Project Library"}
          </motion.button>
        )}
      </div>
      <p className="t-caption">Every format is fully editable afterward</p>
      {saved !== null && library && (
        <Callout tone="success" title={`Saved ${saved} file${saved === 1 ? "" : "s"} to the project library`}>
          Filed under {library.documentType}.{" "}
          <a className="btn-link" href={`/projects/${library.projectId}/library`}>
            View in Project Library <Glyph name="arrow-right" size={14} />
          </a>
        </Callout>
      )}
      {error && <Callout tone="error" title="That didn't finish">{error}</Callout>}
    </div>
  );
}
