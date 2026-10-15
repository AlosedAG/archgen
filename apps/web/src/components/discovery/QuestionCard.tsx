"use client";

/**
 * One discovery question: its input (token multiselect / dropdown / radio
 * list / text), the "Other — specify" field, a shorthand notes line and the
 * follow-up flag — then the follow-ups its answer revealed, in a ruled
 * group beneath it. Follow-ups revealed by a follow-up render as compact
 * "Revealed by …" fields, per the design.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useId, useRef, useState } from "react";

import type { FollowUpQuestion, Question } from "@/lib/api";
import { getAnswer, type Answer, type DiscoveryStore } from "@/lib/discovery-state";

import { Reveal } from "../ui";
import { collapse, dropdown, fadeInUp, highlight, insertRow, pop, press, staggerTiming, tween } from "@/lib/motion";
import { Glyph } from "@/components/icons";

export type QuestionContext = {
  store: DiscoveryStore;
  otherOption: string;
  /** Question id -> follow-ups revealed under it. */
  followUps: Record<string, FollowUpQuestion[]>;
  /** Follow-up id -> the options that revealed it. */
  revealedBy: Record<string, string[]>;
};

export function QuestionBlock({
  section,
  question,
  ctx,
  depth = 0,
}: {
  section: string;
  question: Question;
  ctx: QuestionContext;
  /** 0 = question bank, 1 = follow-up, 2+ = follow-up of a follow-up. */
  depth?: number;
}) {
  const revealed = ctx.followUps[question.id] ?? [];
  return (
    <motion.div className="question-block" variants={depth === 0 ? fadeInUp : undefined}>
      {depth >= 2 ? (
        <ChainedField section={section} question={question} ctx={ctx} />
      ) : (
        <QuestionCard section={section} question={question} ctx={ctx} isFollowUp={depth === 1} />
      )}
      <AnimatePresence initial={false}>
        {revealed.length > 0 && (
          <motion.div
            key="follow-ups"
            className={depth === 0 ? "follow-ups" : undefined}
            style={{ overflow: "hidden", display: "grid", gap: 12 }}
            variants={collapse}
            initial="closed"
            animate="open"
            exit="closed"
          >
            <AnimatePresence initial={false}>
              {revealed.map((followUp, i) => (
                <motion.div
                  key={followUp.id}
                  variants={insertRow}
                  initial="hidden"
                  animate="visible"
                  exit="exit"
                  transition={{ delay: i * staggerTiming.cards }}
                >
                  <QuestionBlock section={followUp.home_section} question={followUp} ctx={ctx} depth={depth + 1} />
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function QuestionCard({
  section,
  question,
  ctx,
  isFollowUp,
}: {
  section: string;
  question: Question;
  ctx: QuestionContext;
  isFollowUp: boolean;
}) {
  const { store, otherOption } = ctx;
  const answer = getAnswer(store.state, section, question.id);
  const set = (patch: Partial<Answer>) => store.setAnswer(section, question.id, patch);
  const labelId = useId();
  const isChoice = question.input !== "text";

  return (
    <motion.div
      className={isFollowUp ? "question-card is-follow-up" : "question-card"}
      data-flagged={answer.flagged}
      initial={isFollowUp ? { boxShadow: `0 0 0 4px ${highlight.from}` } : false}
      animate={{ boxShadow: `0 0 0 0 ${highlight.to}` }}
      transition={highlight.transition}
    >
      {isFollowUp && <span className="badge badge-follow-up"><Glyph name="corner-down-right" size={12} />Follow-up</span>}
      <p className="question-title" id={labelId}>
        {question.label}
        {question.hint && (
          <span className="question-hint" title={question.hint} aria-label={`Hint: ${question.hint}`}>
            ?
          </span>
        )}
      </p>
      <AnswerInput question={question} answer={answer} set={set} otherOption={otherOption} labelId={labelId} />
      {isChoice && (
        <>
          <Reveal show={answer.selected.includes(otherOption)}>
            <label className="field">
              <span className="field-label">Other — specify</span>
              <input
                className="input"
                placeholder="What did they say?"
                value={answer.other}
                onChange={(e) => set({ other: e.target.value })}
              />
            </label>
          </Reveal>
        </>
      )}
      <div className="note-row">
        {isChoice ? (
          <input
            className="notes-input"
            aria-label={`Notes — ${question.label}`}
            placeholder="Shorthand notes…"
            value={answer.notes}
            onChange={(e) => set({ notes: e.target.value })}
          />
        ) : (
          <span className="note-row-spacer" />
        )}
        <FlagButton flagged={answer.flagged} onChange={(flagged) => set({ flagged })} label={question.label} />
      </div>
    </motion.div>
  );
}

/** A follow-up revealed by another follow-up: badge, label and input, no card. */
function ChainedField({ section, question, ctx }: { section: string; question: Question; ctx: QuestionContext }) {
  const answer = getAnswer(ctx.store.state, section, question.id);
  const labelId = useId();
  const by = ctx.revealedBy[question.id] ?? [];
  return (
    <div className="chained">
      <span className="badge badge-follow-up"><Glyph name="corner-down-right" size={12} />Revealed by {by.length ? by.join(", ") : "your answer"}</span>
      <p className="field-label" id={labelId}>
        {question.label}
      </p>
      <AnswerInput
        question={question}
        answer={answer}
        set={(patch) => ctx.store.setAnswer(section, question.id, patch)}
        otherOption={ctx.otherOption}
        labelId={labelId}
      />
    </div>
  );
}

function AnswerInput({
  question,
  answer,
  set,
  otherOption,
  labelId,
}: {
  question: Question;
  answer: Answer;
  set: (patch: Partial<Answer>) => void;
  otherOption: string;
  labelId: string;
}) {
  const choices = [...(question.options ?? []), otherOption];
  // The design labels the "Other (specify)" chip just "Other".
  const chipLabel = (option: string) => (option === otherOption ? "Other" : option);
  if (question.input === "multiselect" || question.input === "radio") {
    const multiple = question.input === "multiselect";
    return (
      <ChoiceChips
        choices={choices}
        selected={answer.selected}
        multiple={multiple}
        labelId={labelId}
        chipLabel={chipLabel}
        onChange={(selected) => set({ selected })}
      />
    );
  }
  if (question.input === "select") {
    return (
      <select
        className="select select-soft"
        aria-labelledby={labelId}
        value={answer.selected[0] ?? ""}
        onChange={(e) => set({ selected: e.target.value ? [e.target.value] : [] })}
        style={answer.selected[0] ? undefined : { color: "var(--text-muted)" }}
      >
        <option value="">Choose one</option>
        {choices.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    );
  }
  return (
    <input
      className="input input-soft"
      aria-labelledby={labelId}
      placeholder="Capture an answer…"
      value={answer.notes}
      onChange={(e) => set({ notes: e.target.value })}
    />
  );
}

/** The design's follow-up flag: an outlined "Flag" button that turns orange ("Flagged") when on. */
function FlagButton({ flagged, onChange, label }: { flagged: boolean; onChange: (flagged: boolean) => void; label: string }) {
  return (
    <motion.button
      type="button"
      className="flag-button"
      whileTap={press}
      aria-pressed={flagged}
      aria-label={flagged ? `Flagged for follow-up: ${label}` : `Flag for follow-up: ${label}`}
      onClick={() => onChange(!flagged)}
    >
      {flagged ? "Flagged" : "Flag"}
    </motion.button>
  );
}

/**
 * Answer choices as chips: every option visible, selected ones filled with a
 * check. ``multiple`` = pick any number; otherwise picking one replaces the
 * other and picking it again clears it.
 */
export function ChoiceChips({
  choices,
  selected,
  multiple,
  labelId,
  chipLabel = (o) => o,
  onChange,
}: {
  choices: string[];
  selected: string[];
  multiple: boolean;
  labelId: string;
  chipLabel?: (option: string) => string;
  onChange: (selected: string[]) => void;
}) {
  const toggle = (option: string) => {
    const on = selected.includes(option);
    if (multiple) onChange(on ? selected.filter((s) => s !== option) : [...selected, option]);
    else onChange(on ? [] : [option]);
  };
  return (
    <div className="choice-chips" role={multiple ? "group" : "radiogroup"} aria-labelledby={labelId}>
      {choices.map((option) => {
        const on = selected.includes(option);
        return (
          <motion.button
            key={option}
            type="button"
            className="choice-chip"
            role={multiple ? "checkbox" : "radio"}
            aria-checked={on}
            onClick={() => toggle(option)}
            whileTap={press}
            animate={{ scale: on ? [1, 1.04, 1] : 1 }}
            transition={tween.base}
          >
            <AnimatePresence initial={false}>
              {on && (
                <motion.span
                  className="choice-chip-check"
                  // 12px glyph + 5px gap; width animates so the label slides over instead of jumping.
                  initial={{ width: 0, opacity: 0, scale: 0.85 }}
                  animate={{ width: 17, opacity: 1, scale: 1 }}
                  exit={{ width: 0, opacity: 0, scale: 0.85 }}
                  transition={tween.fast}
                >
                  <Glyph name="check" size={12} />
                </motion.span>
              )}
            </AnimatePresence>
            {chipLabel(option)}
          </motion.button>
        );
      })}
    </div>
  );
}

/**
 * Multiselect as removable tokens in a bordered box; clicking it opens a
 * filterable list of the remaining options. Keyboard: type to filter,
 * Up/Down to move, Enter to add, Backspace to remove the last token, Esc to close.
 * With ``allowCustom``, typed text that matches no option can be added as its own item.
 */
export function TokenSelect({
  choices,
  selected,
  onChange,
  labelId,
  tokenLabel,
  allowCustom = false,
  placeholder,
}: {
  choices: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  labelId: string;
  tokenLabel?: (option: string) => string;
  allowCustom?: boolean;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const listId = useId();
  const typed = query.trim();
  const matches = choices.filter((c) => !selected.includes(c) && c.toLowerCase().includes(typed.toLowerCase()));
  const isNew = allowCustom && typed !== "" && ![...choices, ...selected].some((c) => c.toLowerCase() === typed.toLowerCase());
  // The "Add …" entry is the last option, so Enter still picks the first match.
  const remaining = isNew ? [...matches, typed] : matches;

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  // The list fades out after closing; a click landing on it meanwhile must not pick anything.
  const openRef = useRef(open);
  openRef.current = open;

  /** Keyboard picks keep the list open for the next one; a mouse pick closes it, so a
   *  following click can't land on whichever option slid under the pointer. */
  const add = (option: string, keepOpen: boolean) => {
    onChange([...selected, option]);
    setQuery("");
    setActive(0);
    setOpen(keepOpen);
    input.current?.focus();
  };

  return (
    <div className="token-field" ref={root}>
      <div
        className="token-box"
        data-open={open}
        onClick={() => {
          setOpen(true);
          input.current?.focus();
        }}
      >
        <AnimatePresence initial={false}>
          {selected.map((option) => (
            <motion.span
              key={option}
              className="token"
              layout
              variants={pop}
              initial="hidden"
              animate="visible"
              exit="exit"
            >
              {tokenLabel ? tokenLabel(option) : option}
              <button
                type="button"
                className="token-remove"
                aria-label={`Remove ${option}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onChange(selected.filter((s) => s !== option));
                }}
              >
                <Glyph name="x" size={12} />
              </button>
            </motion.span>
          ))}
        </AnimatePresence>
        <input
          ref={input}
          className="token-search"
          role="combobox"
          aria-labelledby={labelId}
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          placeholder={selected.length ? "" : (placeholder ?? (allowCustom ? "Select or type to add your own" : "Select all that apply"))}
          value={query}
          onFocus={() => setOpen(true)}
          onBlur={(e) => {
            if (!root.current?.contains(e.relatedTarget as Node | null)) setOpen(false);
          }}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
            setOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setOpen(true);
              setActive((i) => Math.min(i + 1, remaining.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((i) => Math.max(i - 1, 0));
            } else if (e.key === "Enter") {
              const option = remaining[active];
              if (open && option) {
                e.preventDefault();
                add(option, true);
              }
            } else if (e.key === "Backspace" && !query && selected.length) {
              onChange(selected.slice(0, -1));
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
        />
      </div>
      <AnimatePresence>
        {open && (
          <motion.ul
            id={listId}
            role="listbox"
            className="option-list"
            variants={dropdown}
            initial="hidden"
            animate="visible"
            exit="exit"
          >
            {remaining.length === 0 ? (
              <li className="option-empty">
                {selected.length >= choices.length && !typed ? "Everything is selected." : allowCustom ? "Type to add your own." : "No matches."}
              </li>
            ) : (
              remaining.map((option, i) => (
                <li
                  key={option}
                  role="option"
                  aria-selected={i === active}
                  className="option"
                  data-active={i === active}
                  onMouseEnter={() => setActive(i)}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    if (openRef.current) add(option, false);
                  }}
                >
                  {isNew && i === remaining.length - 1 ? (
                    <>
                      <Glyph name="plus" size={14} /> Add &ldquo;{option}&rdquo;
                    </>
                  ) : (
                    option
                  )}
                </li>
              ))
            )}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
