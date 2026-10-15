"use client";

import { Callout } from "../ui";
import type { StreamError } from "./useDocumentStream";

/**
 * Drafting failed: the "no API key" warning from the design, or the error
 * itself — with a one-click retry on a lighter model when the AI was busy.
 */
export function StreamErrorCallout({
  error,
  lighter,
  onRetryWith,
}: {
  error: StreamError;
  lighter?: { id: string; label: string };
  onRetryWith?: (modelId: string) => void;
}) {
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
      {error.busy && lighter && onRetryWith && (
        <div className="row" style={{ marginTop: 10 }}>
          <button type="button" className="btn btn-secondary" onClick={() => onRetryWith(lighter.id)}>
            Try with {lighter.label}
          </button>
          <span className="t-caption">A lighter model that&apos;s usually available — or choose another in the AI model menu.</span>
        </div>
      )}
    </Callout>
  );
}
