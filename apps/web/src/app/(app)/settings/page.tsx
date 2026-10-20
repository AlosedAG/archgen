"use client";

/**
 * Setup & API keys: the workspace's HubSpot token and AI keys,
 * stored encrypted on the server. Values are write-only — the page only
 * ever shows whether a key is stored and its last 4 characters.
 */

import { useEffect, useState } from "react";

import { useAppSession } from "@/components/AppSession";
import { PageHeader } from "@/components/PageHeader";
import { Callout } from "@/components/ui";
import { ApiError, deleteSecret, listSecrets, setSecret, type SecretStatus } from "@/lib/api";

const HELP: Record<string, string> = {
  hubspot_token:
    "A HubSpot private app token with read-only scopes. The Hub Zone only reads from HubSpot — it never creates, edits or deletes anything.",
  gemini_api_key:
    "Google Gemini key for AI drafting (business analysis, client explainer) — free from aistudio.google.com/apikey. When set, drafting uses Gemini instead of Claude.",
  anthropic_api_key: "Claude key for AI drafting, used when no Gemini key is set. Starts with sk-ant-.",
};

export default function SettingsPage() {
  const { me } = useAppSession();
  const [secrets, setSecrets] = useState<SecretStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSecrets()
      .then(setSecrets)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Couldn't load settings."));
  }, []);

  return (
    <>
      <PageHeader
        eyebrow="START HERE / SETUP"
        breadcrumb={`${me.workspace_name}  /  ${me.name || me.email}`}
        title="Setup & API keys"
      />
      <div className="page-content">
        {!me.is_admin && (
          <Callout tone="info" title="Only admins can change keys">
            You can see what&apos;s connected; ask a workspace owner or admin to add or replace a key.
          </Callout>
        )}
        {error && <Callout tone="error" title="Something went wrong">{error}</Callout>}
        {secrets === null ? (
          <div className="skeleton" style={{ height: 200 }} aria-busy="true" />
        ) : (
          secrets.map((secret) => (
            <SecretRow
              key={secret.name}
              secret={secret}
              canEdit={me.is_admin}
              onChange={setSecrets}
              onError={setError}
            />
          ))
        )}
      </div>
    </>
  );
}

function SecretRow({
  secret,
  canEdit,
  onChange,
  onError,
}: {
  secret: SecretStatus;
  canEdit: boolean;
  onChange: (all: SecretStatus[]) => void;
  onError: (message: string | null) => void;
}) {
  const [value, setValue] = useState("");
  const [editing, setEditing] = useState(!secret.configured);
  const [busy, setBusy] = useState(false);

  return (
    <section className="secret-row" aria-label={secret.label}>
      <div className="heading-row">
        <h2 className="t-card-title">{secret.label}</h2>
        <span className={`badge ${secret.configured ? "badge-success" : "badge-neutral"}`}>
          {secret.configured ? "Connected" : "Not connected"}
        </span>
      </div>
      <p className="t-description">{HELP[secret.name]}</p>
      {secret.configured && !editing && (
        <p className="flagged-line">
          Stored key ending in <strong>…{secret.hint}</strong>
          {secret.updated_at && ` · updated ${new Date(secret.updated_at).toLocaleDateString()}`}
        </p>
      )}
      {canEdit &&
        (editing ? (
          <form
            className="inline-form"
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              onError(null);
              try {
                onChange(await setSecret(secret.name, value));
                setValue("");
                setEditing(false);
              } catch (err) {
                onError(err instanceof ApiError ? err.message : "Couldn't save the key.");
              }
              setBusy(false);
            }}
          >
            <label className="field">
              <span className="field-label">{secret.configured ? "Replace with" : "Key"}</span>
              <input
                className="input"
                type="password"
                autoComplete="off"
                spellCheck={false}
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            </label>
            <button type="submit" className="btn btn-primary" disabled={busy || value.trim().length < 8}>
              {busy ? "Saving…" : "Save key"}
            </button>
            {secret.configured && (
              <button type="button" className="btn-link" onClick={() => setEditing(false)}>
                Cancel
              </button>
            )}
          </form>
        ) : (
          <div className="row">
            <button type="button" className="btn btn-secondary" onClick={() => setEditing(true)}>
              Replace key
            </button>
            <button
              type="button"
              className="btn btn-danger"
              onClick={async () => {
                onError(null);
                try {
                  await deleteSecret(secret.name);
                  onChange(await listSecrets());
                  setEditing(true);
                } catch (err) {
                  onError(err instanceof ApiError ? err.message : "Couldn't remove the key.");
                }
              }}
            >
              Remove
            </button>
          </div>
        ))}
    </section>
  );
}
