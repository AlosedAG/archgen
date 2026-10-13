"use client";

import { Callout } from "../ui";
import type { StreamError } from "./useDocumentStream";

/** Drafting failed: the "no API key" warning from the design, or the error itself. */
export function StreamErrorCallout({ error }: { error: StreamError }) {
  if (error.noKey) {
    return (
      <Callout tone="warning" title="No AI key connected">
        Drafting needs a Gemini or Anthropic API key for your workspace. An admin can add one under{" "}
        <a className="btn-link" href="/settings">
          Setup &amp; API keys
        </a>
        . You can keep taking notes, building checklists, and exporting meanwhile.
      </Callout>
    );
  }
  return (
    <Callout tone="error" title="The draft didn't finish">
      {error.message}
    </Callout>
  );
}
