"use client";

/** "Saved · 10:42", "Saving…", or what went wrong (with a way out) — for any autosaved project module. */

import type { SaveStatus } from "@/lib/module-state";

import { Callout } from "../ui";

export function SaveBanner({
  store,
  scope = "this project",
}: {
  store: { status: SaveStatus; error: string | null; savedAt: Date | null; reload: () => Promise<void> | void };
  /** Where the changes are saved, e.g. "your workspace". */
  scope?: string;
}) {
  if (store.status === "conflict") {
    return (
      <Callout tone="warning" title="This was changed somewhere else">
        {store.error} Your latest edits here weren&apos;t saved.
        <div style={{ marginTop: 8 }}>
          <button type="button" className="btn btn-secondary" onClick={() => void store.reload()}>
            Reload the saved version
          </button>
        </div>
      </Callout>
    );
  }
  const label =
    store.status === "saving"
      ? "Saving…"
      : store.status === "error"
        ? `Couldn't save — retrying on your next change. ${store.error ?? ""}`
        : store.savedAt
          ? `Saved to ${scope} · ${store.savedAt.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`
          : `Changes save to ${scope} automatically`;
  return (
    <span className="save-indicator" role="status" aria-live="polite">
      <span className="save-dot" data-state={store.status} />
      {label}
    </span>
  );
}
