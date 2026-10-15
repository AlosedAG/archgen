"use client";

/**
 * Your account: display name, password, and the other browsers signed in
 * to it. Workspace-wide keys live on the Setup page.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAppSession } from "@/components/AppSession";
import { PageHeader } from "@/components/PageHeader";
import { Callout } from "@/components/ui";
import { ApiError, changePassword, getAccount, getAuthConfig, signOutOtherBrowsers, updateAccount, type Account } from "@/lib/api";

const ROLE_LABEL: Record<string, string> = { owner: "Owner", admin: "Admin", member: "Member" };

type Notice = { tone: "success" | "error"; text: string } | null;

function message(e: unknown, fallback: string): string {
  return e instanceof ApiError ? e.message : fallback;
}

function Profile({ account, onSaved }: { account: Account; onSaved: (a: Account) => Promise<void> }) {
  const [name, setName] = useState(account.name);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const changed = name.trim() !== account.name && name.trim() !== "";

  return (
    <section className="card stack" style={{ gap: 16 }}>
      <h2 className="t-card-title">Profile</h2>
      <form
        className="stack"
        style={{ gap: 12 }}
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setNotice(null);
          try {
            await onSaved(await updateAccount(name));
            setNotice({ tone: "success", text: "Name updated" });
          } catch (err) {
            setNotice({ tone: "error", text: message(err, "Couldn't save your name.") });
          }
          setBusy(false);
        }}
      >
        <div className="grid-2">
          <label className="field">
            <span className="field-label">Display name</span>
            <input className="input" value={name} maxLength={200} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field">
            <span className="field-label">Email</span>
            <input className="input" value={account.email} readOnly disabled />
          </label>
        </div>
        <dl className="account-facts">
          <div>
            <dt>Workspace</dt>
            <dd>{account.workspace_name}</dd>
          </div>
          <div>
            <dt>Role</dt>
            <dd>{ROLE_LABEL[account.role] ?? account.role}</dd>
          </div>
          <div>
            <dt>Member since</dt>
            <dd>{new Date(account.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}</dd>
          </div>
        </dl>
        <button type="submit" className="btn btn-primary" style={{ width: "fit-content" }} disabled={!changed || busy}>
          {busy ? "Saving…" : "Save"}
        </button>
      </form>
      {notice && <Callout tone={notice.tone} title={notice.tone === "success" ? notice.text : "That didn't work"}>{notice.tone === "error" ? notice.text : undefined}</Callout>}
    </section>
  );
}

function Password({ account, minLength, onSaved }: { account: Account; minLength: number; onSaved: (a: Account) => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const mismatch = confirm !== "" && confirm !== next;
  const ready = next.length >= minLength && next === confirm && (!account.has_password || current !== "");

  return (
    <section className="card stack" style={{ gap: 16 }}>
      <h2 className="t-card-title">{account.has_password ? "Change password" : "Set a password"}</h2>
      <form
        className="stack"
        style={{ gap: 12 }}
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setNotice(null);
          try {
            onSaved(await changePassword(current, next));
            setCurrent("");
            setNext("");
            setConfirm("");
            setNotice({ tone: "success", text: "Password changed. Your other browsers were signed out." });
          } catch (err) {
            setNotice({ tone: "error", text: message(err, "Couldn't change your password.") });
          }
          setBusy(false);
        }}
      >
        <div className="grid-3">
          {account.has_password && (
            <label className="field">
              <span className="field-label">Current password</span>
              <input className="input" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
            </label>
          )}
          <label className="field">
            <span className="field-label">New password</span>
            <input className="input" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
            <span className="t-caption">At least {minLength} characters</span>
          </label>
          <label className="field">
            <span className="field-label">Confirm new password</span>
            <input className="input" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} aria-invalid={mismatch} />
            {mismatch && <span className="t-caption field-error">Doesn&apos;t match</span>}
          </label>
        </div>
        <button type="submit" className="btn btn-primary" style={{ width: "fit-content" }} disabled={!ready || busy}>
          {busy ? "Saving…" : account.has_password ? "Change password" : "Set password"}
        </button>
      </form>
      {notice && <Callout tone={notice.tone} title={notice.tone === "success" ? notice.text : "That didn't work"}>{notice.tone === "error" ? notice.text : undefined}</Callout>}
    </section>
  );
}

function Sessions({ account, onChanged }: { account: Account; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const others = account.other_sessions;
  return (
    <section className="card stack" style={{ gap: 12 }}>
      <h2 className="t-card-title">Signed-in browsers</h2>
      <p className="t-description">
        {others === 0 ? "Only this browser is signed in." : `${others} other browser${others === 1 ? " is" : "s are"} signed in to your account.`}
        {account.last_login_at && ` Last sign-in ${new Date(account.last_login_at).toLocaleString()}.`}
      </p>
      {others > 0 && (
        <button
          type="button"
          className="btn btn-secondary"
          style={{ width: "fit-content" }}
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setNotice(null);
            try {
              const { signed_out } = await signOutOtherBrowsers();
              setNotice({ tone: "success", text: `Signed out ${signed_out} other browser${signed_out === 1 ? "" : "s"}` });
              onChanged();
            } catch (err) {
              setNotice({ tone: "error", text: message(err, "Couldn't sign out the other browsers.") });
            }
            setBusy(false);
          }}
        >
          {busy ? "Signing out…" : "Sign out other browsers"}
        </button>
      )}
      {notice && <Callout tone={notice.tone} title={notice.tone === "success" ? notice.text : "That didn't work"}>{notice.tone === "error" ? notice.text : undefined}</Callout>}
    </section>
  );
}

export default function AccountPage() {
  const { me, refreshMe, setProject } = useAppSession();
  const [account, setAccount] = useState<Account | null>(null);
  const [minLength, setMinLength] = useState(10);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    getAccount()
      .then(setAccount)
      .catch((e: unknown) => setError(message(e, "Couldn't load your account.")));

  useEffect(() => {
    setProject(null);
    void load();
    getAuthConfig()
      .then((c) => setMinLength(c.min_password_length))
      .catch(() => undefined);
  }, [setProject]);

  return (
    <>
      <PageHeader eyebrow="ACCOUNT" breadcrumb={`${me.workspace_name}  /  ${me.name || me.email}`} title="Profile & account" />
      <div className="page-content" style={{ maxWidth: 880 }}>
        {error && <Callout tone="error" title="Can't load your account">{error}</Callout>}
        {!account ? (
          !error && <div className="skeleton" style={{ height: 240 }} aria-busy="true" />
        ) : (
          <>
            <Profile
              account={account}
              onSaved={async (a) => {
                setAccount(a);
                await refreshMe();
              }}
            />
            <Password account={account} minLength={minLength} onSaved={setAccount} />
            <Sessions account={account} onChanged={() => void load()} />
            {me.is_admin && (
              <p className="t-caption">
                HubSpot and AI keys are shared by the whole workspace: <Link className="btn-link" href="/settings">Setup &amp; API keys</Link>
              </p>
            )}
          </>
        )}
      </div>
    </>
  );
}
