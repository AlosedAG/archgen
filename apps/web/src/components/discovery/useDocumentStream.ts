"use client";

import { useCallback, useRef, useState } from "react";

import { ApiError, streamDocument } from "@/lib/api";

export type StreamError = { message: string; /** The API isn't configured for AI drafting (no key). */ noKey: boolean };

/**
 * Runs an AI document stream: text accumulates as it arrives, and on
 * success the finished document is handed to `onDone` to keep.
 */
export function useDocumentStream(kind: "business-analysis" | "client-explainer", onDone: (text: string) => void) {
  const [text, setText] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<StreamError | null>(null);
  const abort = useRef<AbortController | null>(null);

  const start = useCallback(
    async (body: unknown) => {
      abort.current?.abort();
      const controller = new AbortController();
      abort.current = controller;
      setText("");
      setError(null);
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
        );
        onDone(full);
      } catch (e) {
        if ((e as Error).name !== "AbortError") {
          setError({
            message: e instanceof ApiError ? e.message : "The document couldn't be generated. Try again.",
            noKey: e instanceof ApiError && e.status === 503,
          });
        }
      } finally {
        setStreaming(false);
      }
    },
    [kind, onDone],
  );

  return { text, streaming, error, start };
}
