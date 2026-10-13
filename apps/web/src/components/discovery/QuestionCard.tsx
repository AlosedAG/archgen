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

import { Checkbox, Reveal, spring } from "../ui";

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
  const showOptions = depth === 0 && question.input !== "text";
  return (
    <div className="question-block">
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
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.2, 0.8, 0.2, 1] }}
          >
            <AnimatePresence initial={false}>
              {revealed.map((followUp, i) => (
                <motion.div
                  key={followUp.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0, transition: { delay: 0.06 * i, ...spring } }}
                  exit={{ opacity: 0, x: -10, transition: { duration: 0.15 } }}
                >
                  <QuestionBlock section={followUp.home_section} question={followUp} ctx={ctx} depth={depth + 1} />
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
      {showOptions && (
        <p className="options-caption">Options: {[...(question.options ?? []), ctx.otherOption].join(" · ")}</p>
      )}
    </div>
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
      initial={isFollowUp ? { boxShadow: "0 0 0 4px rgba(247,121,29,0.28)" } : false}
      animate={{ boxShadow: "0 0 0 0 rgba(247,121,29,0)" }}
      transition={{ duration: 1.1, ease: "easeOut" }}
    >
      {isFollowUp && <span className="badge badge-follow-up">↳ Follow-up</span>}
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
          <input
            className="notes-input"
            aria-label={`Notes — ${question.label}`}
            placeholder="Shorthand notes…"
            value={answer.notes}
            onChange={(e) => set({ notes: e.target.value })}
          />
        </>
      )}
      <Checkbox checked={answer.flagged} onChange={(flagged) => set({ flagged })}>
        Flag for follow-up
      </Checkbox>
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
      <span className="badge badge-follow-up">↳ Revealed by {by.length ? by.join(", ") : "your answer"}</span>
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
  if (question.input === "multiselect") {
    return (
      <TokenSelect
        choices={choices}
        selected={answer.selected}
        onChange={(selected) => set({ selected })}
        labelId={labelId}
        // The design labels the "Other (specify)" token just "Other".
        tokenLabel={(option) => (option === otherOption ? "Other" : option)}
      />
    );
  }
  if (question.input === "select") {
    return (
      <select
        className="select"
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
  if (question.input === "radio") {
    return (
      <div className="radio-list" role="radiogroup" aria-labelledby={labelId}>
        {choices.map((option) => {
          const on = answer.selected[0] === option;
          return (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={on}
              className="radio"
              onClick={() => set({ selected: on ? [] : [option] })}
            >
              <span className="radio-dot">
                <AnimatePresence>
                  {on && (
                    <motion.span
                      className="radio-dot-fill"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      exit={{ scale: 0 }}
                      transition={spring}
                    />
                  )}
                </AnimatePresence>
              </span>
              {option}
            </button>
          );
        })}
      </div>
    );
  }
  return (
    <input
      className="input"
      aria-labelledby={labelId}
      placeholder="Shorthand is fine"
      value={answer.notes}
      onChange={(e) => set({ notes: e.target.value })}
    />
  );
}

/**
 * Multiselect as removable tokens in a bordered box; clicking it opens a
 * filterable list of the remaining options. Keyboard: type to filter,
 * ↑/↓ to move, Enter to add, Backspace to remove the last token, Esc to close.
 */
export function TokenSelect({
  choices,
  selected,
  onChange,
  labelId,
  tokenLabel,
}: {
  choices: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  labelId: string;
  tokenLabel?: (option: string) => string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const listId = useId();
  const remaining = choices.filter((c) => !selected.includes(c) && c.toLowerCase().includes(query.trim().toLowerCase()));

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const add = (option: string) => {
    onChange([...selected, option]);
    setQuery("");
    setActive(0);
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
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.85 }}
              transition={spring}
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
                ×
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
          placeholder={selected.length ? "" : "Select all that apply"}
          value={query}
          onFocus={() => setOpen(true)}
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
                add(option);
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
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.12 }}
          >
            {remaining.length === 0 ? (
              <li className="option-empty">{selected.length === choices.length ? "Everything is selected." : "No matches."}</li>
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
                    add(option);
                  }}
                >
                  {option}
                </li>
              ))
            )}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
