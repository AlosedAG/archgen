"use client";

/**
 * A "type the name to confirm" dialog for deletions that can't be undone, as
 * GitHub does for repositories. Rendered into <body>, so cards with stretched
 * links or transforms underneath can't intercept its clicks or clip it.
 * Escape and the backdrop cancel; Enter confirms once the name matches.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { Callout } from "@/components/ui";

export function ConfirmDeleteDialog({
  open,
  name,
  what,
  details,
  busy,
  error,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  /** What the user must type, exactly. */
  name: string;
  /** "project", "folder"…: used in the title and button. */
  what: string;
  /** What else goes with it, shown under the title. */
  details: React.ReactNode;
  busy: boolean;
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [typed, setTyped] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const titleId = useId();
  const matches = typed.trim() === name.trim();

  useEffect(() => {
    if (!open) return;
    setTyped("");
    const t = setTimeout(() => input.current?.focus(), 30);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(t);
      window.removeEventListener("keydown", onKey);
    };
    // Re-arm only when the dialog opens or the busy state changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, busy]);

  if (typeof document === "undefined") return null;
  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="drawer-backdrop"
            onClick={() => !busy && onCancel()}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.16 }}
          />
          <div className="confirm-wrap">
            <motion.form
              className="confirm-dialog"
              role="alertdialog"
              aria-modal="true"
              aria-labelledby={titleId}
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={{ duration: 0.18, ease: [0.2, 0.7, 0.2, 1] }}
              onSubmit={(e) => {
                e.preventDefault();
                if (matches && !busy) onConfirm();
              }}
            >
              <h2 id={titleId} className="confirm-title">
                Delete “{name}”?
              </h2>
              <div className="confirm-warning">{details} This can&apos;t be undone.</div>
              <label className="field">
                <span className="field-label">
                  To confirm, type <b className="confirm-name">{name}</b>
                </span>
                <input
                  ref={input}
                  className="input"
                  value={typed}
                  onChange={(e) => setTyped(e.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                  disabled={busy}
                  aria-invalid={typed !== "" && !matches}
                />
              </label>
              {error && (
                <Callout tone="error" title="That didn't work">
                  {error}
                </Callout>
              )}
              <div className="confirm-actions">
                <button type="button" className="btn btn-secondary" disabled={busy} onClick={onCancel}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-danger" disabled={!matches || busy}>
                  {busy ? "Deleting…" : `Delete this ${what}`}
                </button>
              </div>
            </motion.form>
          </div>
        </>
      )}
    </AnimatePresence>,
    document.body,
  );
}
