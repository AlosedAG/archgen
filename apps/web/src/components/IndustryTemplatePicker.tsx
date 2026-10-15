"use client";

/**
 * Pick an industry (and optionally a company size) and apply its template.
 * Templates only fill blanks; the caller's ``apply`` does the work and
 * returns the message to show.
 */

import { useEffect, useState } from "react";

import { ApiError, listIndustryTemplates, type IndustryTemplates } from "@/lib/api";

import { Glyph } from "./icons";
import { Callout } from "./ui";

export function IndustryTemplatePicker({
  apply,
  disabled,
}: {
  apply: (industry: string, size: string | null) => Promise<string>;
  disabled?: boolean;
}) {
  const [templates, setTemplates] = useState<IndustryTemplates | null>(null);
  const [industry, setIndustry] = useState("");
  const [size, setSize] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ tone: "success" | "info" | "error"; text: string } | null>(null);

  useEffect(() => {
    listIndustryTemplates()
      .then(setTemplates)
      .catch(() => setTemplates(null));
  }, []);

  if (!templates) return null;
  const chosen = templates.industries.find((i) => i.id === industry);

  const run = async () => {
    setBusy(true);
    setResult(null);
    try {
      const text = await apply(industry, size || null);
      setResult({ tone: text.startsWith("Nothing") ? "info" : "success", text });
    } catch (e) {
      setResult({ tone: "error", text: e instanceof ApiError ? e.message : "The template wasn't applied. Try again." });
    }
    setBusy(false);
  };

  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="template-picker">
        <label className="field">
          <span className="field-label">Industry template</span>
          <select className="input" value={industry} onChange={(e) => setIndustry(e.target.value)}>
            <option value="">Choose an industry</option>
            {templates.industries.map((i) => (
              <option key={i.id} value={i.id}>
                {i.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field-label">Company size</span>
          <select className="input" value={size} onChange={(e) => setSize(e.target.value)}>
            <option value="">Any size</option>
            {templates.sizes.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn btn-secondary" disabled={!industry || busy || disabled} onClick={() => void run()}>
          <Glyph name="layers" />
          {busy ? "Applying…" : "Apply template"}
        </button>
      </div>
      {chosen && !result && <span className="t-caption">{chosen.description}</span>}
      {result && (
        <Callout tone={result.tone} title={result.tone === "error" ? "Template not applied" : result.text}>
          {result.tone === "error" ? result.text : undefined}
        </Callout>
      )}
    </div>
  );
}
