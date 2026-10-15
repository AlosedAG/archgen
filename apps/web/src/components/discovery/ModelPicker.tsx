"use client";

/**
 * Which AI model drafts the document: "Automatic" (the most accurate one
 * that's available, falling back down the list) or one to try first. The
 * choice is remembered in this browser. Hidden when only one model exists.
 */

import { useEffect, useId, useState } from "react";

import { getAiModels, type AiModels } from "@/lib/api";

const STORAGE_KEY = "archscope.aiModel";
let cached: Promise<AiModels> | null = null;

function readChoice(): string {
  try {
    return window.localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

/** The available models and the chosen one ("" = automatic). */
export function useAiModel() {
  const [models, setModels] = useState<NonNullable<AiModels["models"]>>([]);
  const [model, setModelState] = useState("");

  useEffect(() => {
    cached ??= getAiModels().catch(() => ({ provider: "none", models: [] }) as AiModels);
    void cached.then((r) => {
      setModels(r.models ?? []);
      const saved = readChoice();
      setModelState((r.models ?? []).some((m) => m.id === saved) ? saved : "");
    });
  }, []);

  const setModel = (id: string) => {
    setModelState(id);
    try {
      window.localStorage.setItem(STORAGE_KEY, id);
    } catch {
      // Remembering the choice is a convenience only.
    }
  };

  // The last model in the list is the lightest / least busy one.
  const lightest = models.length > 1 ? models[models.length - 1] : undefined;
  return { models, model, setModel, lightest };
}

export function ModelPicker({
  models,
  value,
  onChange,
  disabled,
}: {
  models: NonNullable<AiModels["models"]>;
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
}) {
  const id = useId();
  if (models.length < 2) return null;
  return (
    <label className="model-picker" htmlFor={id}>
      <span className="field-label">AI model</span>
      <select id={id} className="input" value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        <option value="">Automatic — most accurate available</option>
        {models.map((m) => (
          <option key={m.id} value={m.id}>
            {m.label}
            {m.note ? ` · ${m.note}` : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
