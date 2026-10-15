"use client";

/**
 * A "Fill from earlier steps" / "Suggest" button: runs a suggestion (which
 * fills blanks only), then says what changed or why it couldn't.
 */

import { useState } from "react";

import { ApiError } from "@/lib/api";

import { Glyph } from "./icons";
import { Callout } from "./ui";

export function AssistButton({
  label,
  run,
  disabled,
  variant = "secondary",
}: {
  label: string;
  /** Does the work; resolves to the message shown afterwards. */
  run: () => Promise<string>;
  disabled?: boolean;
  variant?: "primary" | "secondary";
}) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ tone: "success" | "info" | "error"; text: string } | null>(null);

  const go = async () => {
    setBusy(true);
    setResult(null);
    try {
      const text = await run();
      setResult({ tone: text.startsWith("Nothing") ? "info" : "success", text });
    } catch (e) {
      setResult({ tone: "error", text: e instanceof ApiError ? e.message : "The suggestions didn't arrive. Try again." });
    }
    setBusy(false);
  };

  return (
    <div className="stack" style={{ gap: 8 }}>
      <button
        type="button"
        className={`btn btn-${variant}${busy ? " btn-busy" : ""}`}
        style={{ width: "fit-content" }}
        disabled={busy || disabled}
        onClick={() => void go()}
      >
        <Glyph name="sparkles" />
        {busy ? "Reading earlier steps…" : label}
      </button>
      {result && <Callout tone={result.tone} title={result.tone === "error" ? "No suggestions" : result.text}>{result.tone === "error" ? result.text : undefined}</Callout>}
    </div>
  );
}
