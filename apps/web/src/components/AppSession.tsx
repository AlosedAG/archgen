"use client";

/**
 * The signed-in session for every page under (app): loads the current
 * user, sends signed-out visitors to /login (and back afterwards), and
 * shares the user and the project being worked on with the shell.
 */

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { ApiError, getMe, setUnauthorizedHandler, signOut as apiSignOut, WAKING, type Me, type Project } from "@/lib/api";

import { Callout } from "./ui";

const SLOW_AFTER_MS = 3_000;

type AppSession = {
  me: Me;
  signOut: () => Promise<void>;
  /** Reload the signed-in user (e.g. after changing your name). */
  refreshMe: () => Promise<void>;
  /** The project the current page belongs to (set by project pages), or null. */
  project: Project | null;
  setProject: (project: Project | null) => void;
};

const Context = createContext<AppSession | null>(null);

export function useAppSession(): AppSession {
  const session = useContext(Context);
  if (!session) throw new Error("useAppSession must be used inside <AppSessionProvider>");
  return session;
}

/** Same as useAppSession but returns null outside the provider (e.g. on /login). */
export function useOptionalAppSession(): AppSession | null {
  return useContext(Context);
}

export function AppSessionProvider({ children, fallback }: { children: React.ReactNode; fallback: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);

  const toLogin = useCallback(() => {
    router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [router, pathname]);

  // After a few seconds without an answer the server is probably waking up (free hosting sleeps when idle).
  const [slow, setSlow] = useState(false);

  const load = useCallback(() => {
    setError(null);
    setSlow(false);
    const timer = window.setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    getMe()
      .then(setMe)
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 401) toLogin();
        else if (e instanceof ApiError && (e.status === undefined || WAKING.has(e.status)))
          setError("The server didn't wake up in time. It usually takes about a minute after a quiet spell — try again.");
        else setError(e instanceof ApiError ? e.message : "Couldn't load your account.");
      })
      .finally(() => window.clearTimeout(timer));
  }, [toLogin]);

  useEffect(() => {
    setUnauthorizedHandler(toLogin);
    load();
    return () => setUnauthorizedHandler(null);
    // Only on first load; later 401s are handled by the unauthorized handler.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const signOut = useCallback(async () => {
    await apiSignOut().catch(() => undefined);
    router.replace("/login");
  }, [router]);

  const refreshMe = useCallback(async () => setMe(await getMe()), []);

  const value = useMemo(() => (me ? { me, signOut, refreshMe, project, setProject } : null), [me, signOut, refreshMe, project]);

  if (error) {
    return (
      <div className="centered-page">
        <div className="stack" style={{ gap: 12, maxWidth: 440 }}>
          <Callout tone="error" title="Couldn't reach The Hub Zone">
            {error}
          </Callout>
          <button type="button" className="btn btn-primary" style={{ width: "fit-content" }} onClick={load}>
            Try again
          </button>
        </div>
      </div>
    );
  }
  if (!value) {
    return (
      <>
        {slow && (
          <div className="waking-banner" role="status">
            <span className="waking-dot" aria-hidden />
            Starting the server — this takes about a minute after a quiet spell.
          </div>
        )}
        {fallback}
      </>
    );
  }
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
