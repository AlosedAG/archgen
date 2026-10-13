"use client";

/**
 * Pull (or re-pull) the project's read-only HubSpot snapshot. A new pull
 * clears results computed from the previous one. Explains what to do when
 * HubSpot isn't connected yet.
 */

import Link from "next/link";
import { useState } from "react";

import { ApiError, pullSnapshot } from "@/lib/api";
import type { ModuleStore } from "@/lib/module-state";
import type { PortalState } from "@/lib/portal-state";

import { Callout } from "../ui";

function pulledAt(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function SnapshotBar({ store }: { store: ModuleStore<PortalState> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; notConnected: boolean } | null>(null);
  const snapshot = store.state.snapshot;

  const pull = async () => {
    setBusy(true);
    setError(null);
    try {
      const fresh = await pullSnapshot();
      store.replace({ snapshot: fresh, findings: null, auditedAt: null, propertyAudit: null });
    } catch (e) {
      setError({
        message: e instanceof ApiError ? e.message : "Couldn't reach HubSpot.",
        notConnected: e instanceof ApiError && e.type?.endsWith("/hubspot-token-required") === true,
      });
    }
    setBusy(false);
  };

  return (
    <section className="snapshot-bar">
      <div className="stack" style={{ gap: 2 }}>
        <span className="field-label">HubSpot portal snapshot</span>
        <span className="t-caption">
          {snapshot
            ? `Pulled ${pulledAt(snapshot.pulled_at)} · ${(snapshot.object_schemas ?? []).length} objects, ${(snapshot.workflows ?? []).length} workflows`
            : "Read-only: properties, pipelines, workflows, owners and teams. Nothing in HubSpot changes."}
        </span>
      </div>
      <button type="button" className={snapshot ? "btn btn-secondary" : "btn btn-primary"} disabled={busy} onClick={() => void pull()}>
        {busy ? "Pulling from HubSpot…" : snapshot ? "Pull again" : "Pull from HubSpot"}
      </button>
      {error && (
        <div style={{ gridColumn: "1 / -1" }}>
          <Callout tone={error.notConnected ? "warning" : "error"} title={error.notConnected ? "HubSpot isn't connected" : "The pull didn't finish"}>
            {error.notConnected ? (
              <>
                Add your workspace&apos;s HubSpot private app token under{" "}
                <Link className="btn-link" href="/settings">
                  Setup &amp; API keys
                </Link>{" "}
                (read-only scopes), then pull again.
              </>
            ) : (
              error.message
            )}
          </Callout>
        </div>
      )}
    </section>
  );
}
