"use client";

/**
 * The signed-in session for every page under (app): loads the current
 * user, sends signed-out visitors to /login (and back afterwards), and
 * shares the user and the project being worked on with the shell.
 */

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { ApiError, getMe, setUnauthorizedHandler, signOut as apiSignOut, type Me, type Project } from "@/lib/api";

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

  useEffect(() => {
    setUnauthorizedHandler(toLogin);
    getMe()
      .then(setMe)
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 401) toLogin();
        else setError(e instanceof ApiError ? e.message : "Couldn't load your account.");
      });
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
        <div className="callout callout-error">
          <p className="callout-title">!&nbsp;&nbsp;Something went wrong</p>
          <div className="callout-body">{error}</div>
        </div>
      </div>
    );
  }
  if (!value) return <>{fallback}</>;
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
