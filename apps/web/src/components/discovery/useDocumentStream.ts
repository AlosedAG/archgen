"use client";

import { useCallback, useRef, useState } from "react";

import { ApiError, streamDocument } from "@/lib/api";

export type StreamError = {
  message: string;
  /** The API isn't configured for AI drafting (no key). */
  noKey: boolean;
  /** The AI service was busy / out of free quota — worth trying another model. */
  busy: boolean;
};

/**
 * Runs an AI document stream: text accumulates as it arrives, and on
 * success the finished document is handed to `onDone` to keep.
 */
export function useDocumentStream(kind: "business-analysis" | "client-explainer", onDone: (text: string) => void) {
  const [text, setText] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<StreamError | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState(() => Date.now());
  const abort = useRef<AbortController | null>(null);

  const start = useCallback(
    async (body: unknown, model?: string) => {
      abort.current?.abort();
      const controller = new AbortController();
      abort.current = controller;
      setText("");
      setError(null);
      setStatus(null);
      setStartedAt(Date.now());
      setStreaming(true);
      let full = "";
      try {
        await streamDocument(
          kind,
          body,
          (chunk) => {
            full += chunk;
            setText(full);
          },
          controller.signal,
          setStatus,
          model || undefined,
        );
        onDone(full);
      } catch (e) {
        if ((e as Error).name !== "AbortError") {
          setError({
            message: e instanceof ApiError ? e.message : "The document couldn't be generated. Try again.",
            noKey: e instanceof ApiError && e.status === 503 && !(e.type ?? "").endsWith("/ai-busy"),
            busy: e instanceof ApiError && /\/ai-(busy|rate-limited)$/.test(e.type ?? ""),
          });
        }
      } finally {
        setStreaming(false);
      }
    },
    [kind, onDone],
  );

  return { text, streaming, error, start, status, startedAt };
}
