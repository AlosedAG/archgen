"use client";

/**
 * A workspace tracker (first version of a Service / Marketing / Data /
 * Developers page): headline figures from the rows, then the rows as an
 * editable table, autosaved for the whole workspace.
 */

import { SaveBanner } from "@/components/project/SaveBanner";
import { EditableTable, type Row } from "@/components/project/EditableTable";
import { Stats } from "@/components/project/Stats";
import { Callout } from "@/components/ui";
import { useModuleState } from "@/lib/module-state";
import type { Tool } from "@/lib/tools";

type TrackerState = { rows: Row[] };
const plural = (noun: string) => (/[^aeiou]y$/.test(noun) ? `${noun.slice(0, -1)}ies` : `${noun}s`);
const normalize = (raw: unknown): TrackerState => {
  const rows = (raw as Partial<TrackerState> | null)?.rows;
  return { rows: Array.isArray(rows) ? rows : [] };
};

export function TrackerTool({ tool }: { tool: Tool }) {
  const store = useModuleState<TrackerState>("", tool.slug, normalize, { workspace: true });
  const columns = tool.columns ?? [];

  if (!store.loaded) {
    return store.status === "error" ? (
      <Callout tone="error" title="Couldn't load this page">
        {store.error}
      </Callout>
    ) : (
      <div className="skeleton" style={{ height: 280 }} aria-busy="true" />
    );
  }
  const rows = store.state.rows;
  return (
    <>
      <SaveBanner store={store} scope="your workspace" />
      {tool.stats && <Stats items={tool.stats.map((s): [string, string | number] => [s.label, s.value(rows)])} />}
      {rows.length === 0 && (
        <Callout tone="info" title={`No ${plural(tool.noun ?? "row")} yet`}>
          Add the first one below. Everything here is saved for your whole workspace as you type.
        </Callout>
      )}
      <EditableTable
        label={tool.title}
        columns={columns}
        rows={rows}
        onChange={(next) => store.update({ rows: next })}
        addLabel={`+ Add ${tool.noun ?? "row"}`}
      />
    </>
  );
}
