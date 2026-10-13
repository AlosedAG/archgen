"use client";

/**
 * Sign in, create an account, or reset a password. New accounts and
 * resets are confirmed with a 6-digit code sent by email; afterwards the
 * user is signed in and returned to the page that asked.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Callout } from "@/components/ui";
import {
  ApiError,
  confirmPasswordReset,
  getAuthConfig,
  getMe,
  requestPasswordReset,
  resendSignUpCode,
  signIn,
  signUp,
  verifySignUp,
  type AuthConfig,
} from "@/lib/api";

type Mode = "sign-in" | "sign-up" | "verify" | "forgot" | "reset";

function safeNext(next: string | null): string {
  // Only same-site paths, never "//evil.com" or absolute URLs.
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/projects";
}

const TITLES: Record<Mode, string> = {
  "sign-in": "Sign in",
  "sign-up": "Create your account",
  verify: "Check your email",
  forgot: "Reset your password",
  reset: "Choose a new password",
};

function AuthForms() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [mode, setMode] = useState<Mode>("sign-in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);
  const minLength = config?.min_password_length ?? 10;

  useEffect(() => {
    getMe()
      .then(() => router.replace(next))
      .catch(() => undefined);
    getAuthConfig()
      .then(setConfig)
      .catch(() => undefined);
  }, [router, next]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  const go = (m: Mode) => {
    setMode(m);
    setError(null);
    setNotice(null);
    setCode("");
  };

  const run = async (work: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await work();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    }
    setBusy(false);
  };

  const passwordProblem =
    password.length > 0 && password.length < minLength
      ? `Use at least ${minLength} characters.`
      : confirm && confirm !== password
        ? "The passwords don't match."
        : null;

  return (
    <div className="login-page">
      <motion.div className="login-card" layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        <div className="login-brand">
          <span className="wordmark-name">ArchitectureScope</span>
          <span className="wordmark-tagline">SOLUTIONS ARCHITECT WORKSPACE</span>
        </div>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={mode}
            className="stack"
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -12 }}
            transition={{ duration: 0.18 }}
          >
            <h1 className="t-section">{TITLES[mode]}</h1>

            {mode === "sign-in" && (
              <form
                className="stack"
                onSubmit={(e) => {
                  e.preventDefault();
                  void run(async () => {
                    await signIn(email, password);
                    router.replace(next);
                  });
                }}
              >
                <EmailField value={email} onChange={setEmail} />
                <PasswordField label="Password" value={password} onChange={setPassword} autoComplete="current-password" />
                {error && <Callout tone="error" title="Couldn't sign you in">{error}</Callout>}
                <button type="submit" className="btn btn-primary" disabled={busy}>
                  {busy ? "Signing in…" : "Sign in"}
                </button>
                <div className="row-between">
                  {config?.password_reset && (
                    <button type="button" className="btn-link" onClick={() => go("forgot")}>
                      Forgot password?
                    </button>
                  )}
                  {config?.signup && (
                    <button type="button" className="btn-link" onClick={() => go("sign-up")}>
                      Create an account
                    </button>
                  )}
                </div>
              </form>
            )}

            {mode === "sign-up" && (
              <form
                className="stack"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (passwordProblem) return;
                  void run(async () => {
                    await signUp(name, email, password);
                    setCooldown(60);
                    go("verify");
                  });
                }}
              >
                <label className="field">
                  <span className="field-label">Your name</span>
                  <input className="input" autoComplete="name" required value={name} onChange={(e) => setName(e.target.value)} />
                </label>
                <EmailField value={email} onChange={setEmail} />
                <PasswordField label="Password" value={password} onChange={setPassword} autoComplete="new-password" hint={`At least ${minLength} characters.`} />
                <PasswordField label="Repeat password" value={confirm} onChange={setConfirm} autoComplete="new-password" />
                {passwordProblem && <p className="t-caption" style={{ color: "var(--status-risk-text)" }}>{passwordProblem}</p>}
                {error && <Callout tone="error" title="Couldn't create the account">{error}</Callout>}
                <button type="submit" className="btn btn-primary" disabled={busy || Boolean(passwordProblem) || !confirm}>
                  {busy ? "Sending code…" : "Create account"}
                </button>
                <button type="button" className="btn-link" onClick={() => go("sign-in")}>
                  I already have an account
                </button>
              </form>
            )}

            {(mode === "verify" || mode === "reset") && (
              <form
                className="stack"
                onSubmit={(e) => {
                  e.preventDefault();
                  void run(async () => {
                    if (mode === "verify") await verifySignUp(email, code);
                    else await confirmPasswordReset(email, code, password);
                    router.replace(next);
                  });
                }}
              >
                <p className="flagged-line">
                  We sent a 6-digit code to <strong>{email}</strong>. It expires in 15 minutes.
                </p>
                {config?.email_delivery === "outbox" && (
                  <Callout tone="info" title="Local development">
                    No mail server is configured, so the code is printed in the API console and saved under
                    var/outbox instead of being emailed.
                  </Callout>
                )}
                <label className="field">
                  <span className="field-label">Verification code</span>
                  <input
                    className="input code-input"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    required
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  />
                </label>
                {mode === "reset" && (
                  <>
                    <PasswordField label="New password" value={password} onChange={setPassword} autoComplete="new-password" hint={`At least ${minLength} characters.`} />
                    <PasswordField label="Repeat new password" value={confirm} onChange={setConfirm} autoComplete="new-password" />
                    {passwordProblem && <p className="t-caption" style={{ color: "var(--status-risk-text)" }}>{passwordProblem}</p>}
                  </>
                )}
                {notice && <Callout tone="success" title="Sent">{notice}</Callout>}
                {error && <Callout tone="error" title="That didn't work">{error}</Callout>}
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={busy || code.length !== 6 || (mode === "reset" && (Boolean(passwordProblem) || !confirm))}
                >
                  {busy ? "Checking…" : mode === "verify" ? "Confirm and sign in" : "Set password and sign in"}
                </button>
                <div className="row-between">
                  <button
                    type="button"
                    className="btn-link"
                    disabled={cooldown > 0 || busy}
                    onClick={() =>
                      void run(async () => {
                        if (mode === "verify") await resendSignUpCode(email);
                        else await requestPasswordReset(email);
                        setCooldown(60);
                        setNotice("A new code is on its way.");
                      })
                    }
                  >
                    {cooldown > 0 ? `Send a new code (${cooldown}s)` : "Send a new code"}
                  </button>
                  <button type="button" className="btn-link" onClick={() => go(mode === "verify" ? "sign-up" : "forgot")}>
                    Use a different email
                  </button>
                </div>
              </form>
            )}

            {mode === "forgot" && (
              <form
                className="stack"
                onSubmit={(e) => {
                  e.preventDefault();
                  void run(async () => {
                    await requestPasswordReset(email);
                    setPassword("");
                    setConfirm("");
                    setCooldown(60);
                    go("reset");
                  });
                }}
              >
                <p className="flagged-line">Enter your account email and we&apos;ll send you a code to set a new password.</p>
                <EmailField value={email} onChange={setEmail} />
                {error && <Callout tone="error" title="That didn't work">{error}</Callout>}
                <button type="submit" className="btn btn-primary" disabled={busy}>
                  {busy ? "Sending…" : "Send code"}
                </button>
                <button type="button" className="btn-link" onClick={() => go("sign-in")}>
                  Back to sign in
                </button>
              </form>
            )}
          </motion.div>
        </AnimatePresence>
      </motion.div>
      <span className="badge badge-connection">● Read-only HubSpot connection</span>
    </div>
  );
}

function EmailField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <label className="field">
      <span className="field-label">Email</span>
      <input className="input" type="email" autoComplete="username" required value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

function PasswordField({
  label,
  value,
  onChange,
  autoComplete,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete: string;
  hint?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <label className="field">
      <span className="field-label row-between">
        {label}
        <button type="button" className="btn-link" style={{ fontSize: 12 }} onClick={() => setShow((s) => !s)}>
          {show ? "Hide" : "Show"}
        </button>
      </span>
      <input
        className="input"
        type={show ? "text" : "password"}
        autoComplete={autoComplete}
        required
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {hint && <span className="t-caption">{hint}</span>}
    </label>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <AuthForms />
    </Suspense>
  );
}
