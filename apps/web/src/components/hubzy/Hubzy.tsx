"use client";

/**
 * Hubzy, The Hub Zone's assistant: mounted once in the app shell, present on
 * every signed-in page. He can be dragged anywhere (and stays where he was
 * left), greets you once per session in a speech bubble with a few quick
 * replies, and offers the odd HubSpot fact while you're idle. Clicking him
 * opens his help panel: questions to pick from, answered from the
 * workspace's Hubzy Answers table. Only Hubzy, his bubble and his panel take
 * pointer events (a fact bubble doesn't even do that); there is no overlay
 * over the page.
 */

import { AnimatePresence } from "framer-motion";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useAppSession } from "@/components/AppSession";

import { HUBZY_FACT_LABEL, HUBZY_FACT_TIMING, HUBZY_GREETING, HUBZY_TOUR, type HubzyAction, type HubzyReply } from "./config";
import { HubzyArt } from "./HubzyArt";
import { HubzyBubble } from "./HubzyBubble";
import { HubzyPanel, type HubzyLine } from "./HubzyPanel";
import { useHubzyDrag } from "./useHubzyDrag";
import { factShowFor, useHubzyFacts } from "./useHubzyFacts";
import { useHubzyLife } from "./useHubzyLife";

type Say = { id: string; text: string; replies?: HubzyReply[]; fact?: boolean };

const NEW_PROJECT_INPUT = "new-project-name";

/** First name from the account, or the friendly fallback. */
function firstName(name: string | null | undefined): string {
  return name?.trim().split(/\s+/)[0] || HUBZY_GREETING.fallbackName;
}

export function Hubzy() {
  const { me } = useAppSession();
  const router = useRouter();
  const pathname = usePathname();
  const self = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const face = useHubzyLife(self);
  const { pos, dragging, handlers } = useHubzyDrag(self);
  const [say, setSay] = useState<Say | null>(null);
  const [talking, setTalking] = useState(false);
  const [panel, setPanel] = useState(false);
  const [chat, setChat] = useState<HubzyLine[]>([]);
  const talkTimer = useRef<number | undefined>(undefined);

  /** Move his mouth for a while. */
  const talk = useCallback((ms: number) => {
    setTalking(true);
    window.clearTimeout(talkTimer.current);
    talkTimer.current = window.setTimeout(() => setTalking(false), ms);
  }, []);
  useEffect(() => () => window.clearTimeout(talkTimer.current), []);

  const greeting = useCallback(
    (): Say => ({ id: "greeting", text: HUBZY_GREETING.text(firstName(me.name)), replies: HUBZY_GREETING.replies }),
    [me.name],
  );

  // Greet once per browser session, shortly after the app loads.
  useEffect(() => {
    try {
      if (sessionStorage.getItem(HUBZY_GREETING.sessionKey)) return;
    } catch {
      // No session storage: greet anyway.
    }
    const timer = window.setTimeout(() => {
      setSay(greeting());
      try {
        sessionStorage.setItem(HUBZY_GREETING.sessionKey, "1");
      } catch {
        // He may greet again after a reload; harmless.
      }
    }, HUBZY_GREETING.delay);
    return () => window.clearTimeout(timer);
  }, [greeting]);

  /** Close the bubble; if focus was inside it, hand focus back to Hubzy. */
  const dismiss = useCallback(() => {
    const active = document.activeElement;
    if (active instanceof HTMLElement && active.closest(".hubzy-say")) button.current?.focus();
    setSay(null);
  }, []);

  // A fact pops up with a little chatter, then goes away on its own.
  useHubzyFacts(say === null && !panel, (fact) => {
    setSay({ id: `fact-${Date.now()}`, text: fact, fact: true });
    talk(HUBZY_FACT_TIMING.talkFor);
  });

  useEffect(() => {
    if (!say?.fact) return;
    const timer = window.setTimeout(() => setSay((now) => (now?.id === say.id ? null : now)), factShowFor(say.text));
    return () => window.clearTimeout(timer);
  }, [say]);

  const openPanel = () => {
    setSay(null);
    setPanel(true);
  };
  /** Close the panel and hand focus back to Hubzy. */
  const closePanel = useCallback(() => {
    setPanel(false);
    button.current?.focus();
  }, []);

  const startProject = () => {
    dismiss();
    if (pathname !== "/projects") router.push("/projects");
    // Focus the new-project field once the Projects page is on screen.
    const until = performance.now() + 5000;
    const tryFocus = () => {
      const input = document.getElementById(NEW_PROJECT_INPUT);
      if (input) input.focus();
      else if (performance.now() < until) window.setTimeout(tryFocus, 100);
    };
    tryFocus();
  };

  const act = (action: HubzyAction) => {
    if (action === "dismiss") dismiss();
    else if (action === "tour") setSay({ id: "tour", ...HUBZY_TOUR });
    else if (action === "start-project") startProject();
  };

  return (
    <>
      <div
        className="hubzy-dock"
        ref={self}
        data-dragging={dragging || undefined}
        style={pos ? { left: pos.x, top: pos.y, right: "auto", bottom: "auto" } : undefined}
      >
        <button
          ref={button}
          type="button"
          className="hubzy-figure"
          aria-label="Hubzy, your assistant. Press to ask him something; drag him, or use the arrow keys, to move him."
          aria-haspopup="dialog"
          aria-expanded={panel}
          onClick={() => (panel ? closePanel() : openPanel())}
          {...handlers}
          onKeyDown={(e) => {
            // With the panel open, its own Esc handler closes it.
            if (e.key === "Escape" && say && !panel) dismiss();
            else handlers.onKeyDown(e);
          }}
        >
          <HubzyArt face={{ ...face, talking }} />
        </button>
      </div>
      <AnimatePresence>
        {panel && (
          <HubzyPanel
            anchor={self}
            track={pos}
            name={firstName(me.name)}
            lines={chat}
            setLines={setChat}
            onTalk={talk}
            onClose={closePanel}
          />
        )}
      </AnimatePresence>
      <AnimatePresence>
        {say && !panel && (
          <HubzyBubble key={say.id} anchor={self} track={pos} label="Hubzy says" passive={say.fact} onEscape={dismiss}>
            {say.fact && <p className="hubzy-say-eyebrow">{HUBZY_FACT_LABEL}</p>}
            <p className="hubzy-say-text" aria-live="polite">
              {say.text}
            </p>
            {say.replies && (
              <div className="hubzy-replies">
                {say.replies.map((reply) => (
                  <button key={reply.label} type="button" className="hubzy-chip" onClick={() => act(reply.action)}>
                    {reply.label}
                  </button>
                ))}
              </div>
            )}
          </HubzyBubble>
        )}
      </AnimatePresence>
    </>
  );
}
