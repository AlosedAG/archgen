"use client";

/**
 * The proposal builder's templates bar, always at the top: start from one
 * of the team's saved templates, save this proposal as a template for
 * similar clients, and manage (delete) templates. Templates keep nearly
 * everything; the client's details, dates and reference are cleared when
 * saving and the current ones kept when starting from one.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  applyProposalTemplate,
  deleteProposalTemplate,
  listProposalTemplates,
  saveProposalTemplate,
  type ProposalDocument,
  type ProposalTemplateSummary,
} from "@/lib/api";

import { Callout } from "../ui";

type Panel = null | "use" | "save" | "manage";

function describe(t: ProposalTemplateSummary): string {
  const parts = [`${t.requirement_count} requirement${t.requirement_count === 1 ? "" : "s"}`, `${t.scope_count} scope item${t.scope_count === 1 ? "" : "s"}`];
  if (t.created_by) parts.push(`saved by ${t.created_by}`);
  return parts.join(" · ");
}

/** Whether the proposal is still basically blank (nothing deal-specific typed yet). */
export function isFreshProposal(doc: ProposalDocument): boolean {
  const filled = (rows: Record<string, unknown>[] | undefined, key: string) => (rows ?? []).some((r) => String(r[key] ?? "").trim());
  return !filled(doc.requirements, "requirement") && !filled(doc.scope, "item") && !String(doc.problem_statement ?? "").trim();
}

export function ProposalTemplatesBar({
  doc,
  defaultName,
  onApplied,
}: {
  doc: ProposalDocument;
  defaultName: string;
  onApplied: (next: ProposalDocument, templateName: string) => void;
}) {
  const [templates, setTemplates] = useState<ProposalTemplateSummary[] | null>(null);
  const [panel, setPanel] = useState<Panel>(null);
  const [chosen, setChosen] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [clash, setClash] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  const load = useCallback(() => {
    listProposalTemplates()
      .then((list) => {
        setTemplates(list);
        setChosen((c) => c || list[0]?.id || "");
      })
      .catch(() => setTemplates([]));
  }, []);
  useEffect(load, [load]);

  const run = async (work: () => Promise<void>) => {
    setBusy(true);
    setMessage(null);
    try {
      await work();
    } catch (e) {
      setMessage({ tone: "error", text: e instanceof ApiError ? e.message : "That didn't work. Try again." });
    }
    setBusy(false);
  };

  const use = () =>
    run(async () => {
      const template = templates?.find((t) => t.id === chosen);
      if (!template) return;
      onApplied(await applyProposalTemplate(template.id, doc), template.name);
      setPanel(null);
      setMessage({ tone: "success", text: `Started from “${template.name}”. The client's details, dates and reference were kept — review and adjust the rest.` });
    });

  const save = (replace: boolean) =>
    run(async () => {
      try {
        const saved = await saveProposalTemplate({ name: name.trim(), description: description.trim(), proposal: doc, replace });
        setClash(false);
        setPanel(null);
        setMessage({ tone: "success", text: `Saved as template “${saved.name}”. Everyone in your workspace can now start a proposal from it.` });
        load();
      } catch (e) {
        if (e instanceof ApiError && e.status === 409) {
          setClash(true);
          return;
        }
        throw e;
      }
    });

  const remove = (t: ProposalTemplateSummary) =>
    run(async () => {
      await deleteProposalTemplate(t.id);
      setMessage({ tone: "success", text: `Deleted template “${t.name}”.` });
      if (chosen === t.id) setChosen("");
      load();
    });

  const count = templates?.length ?? 0;
  const fresh = isFreshProposal(doc);
  const toggle = (p: Panel) => {
    setMessage(null);
    setClash(false);
    if (p === "save" && panel !== "save") {
      setName(defaultName);
      setDescription("");
    }
    setPanel(panel === p ? null : p);
  };

  return (
    <section className={fresh && count > 0 ? "templates-bar templates-bar-highlight" : "templates-bar"} aria-label="Proposal templates">
      <div className="templates-bar-head">
        <div className="stack" style={{ gap: 2 }}>
          <span className="templates-bar-title">Templates</span>
          <span className="t-caption">
            {fresh && count > 0
              ? `New proposal? Start from one of your team's ${count} saved template${count === 1 ? "" : "s"} instead of filling everything in.`
              : count > 0
                ? `${count} saved template${count === 1 ? "" : "s"} in your workspace.`
                : "Save this proposal as a template to reuse it for a similar client."}
          </span>
        </div>
        <div className="row">
          <button type="button" className={fresh && count > 0 ? "btn btn-primary" : "btn btn-secondary"} disabled={!count} onClick={() => toggle("use")}>
            Start from a template
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => toggle("save")}>
            Save as template
          </button>
          {count > 0 && (
            <button type="button" className="btn-link" onClick={() => toggle("manage")}>
              Manage ({count})
            </button>
          )}
        </div>
      </div>

      <AnimatePresence initial={false}>
        {panel && (
          <motion.div
            key={panel}
            className="templates-panel"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
          >
            {panel === "use" && templates && (
              <div className="stack" style={{ gap: 10 }}>
                <div className="templates-list" role="radiogroup" aria-label="Choose a template">
                  {templates.map((t) => (
                    <label key={t.id} className="template-option" data-selected={chosen === t.id}>
                      <input type="radio" name="proposal-template" checked={chosen === t.id} onChange={() => setChosen(t.id)} />
                      <span className="stack" style={{ gap: 2 }}>
                        <b>{t.name}</b>
                        {t.description && <span className="t-description">{t.description}</span>}
                        <span className="t-caption">{describe(t)}</span>
                      </span>
                    </label>
                  ))}
                </div>
                <p className="t-caption">
                  {fresh
                    ? "The template fills in everything; this proposal's client details, dates and reference stay."
                    : "This replaces what's in this proposal now (client details, dates and reference stay). Save it as a template first if you want to keep it."}
                </p>
                <div className="row">
                  <button type="button" className="btn btn-primary" disabled={busy || !chosen} onClick={() => void use()}>
                    {busy ? "Applying…" : "Use this template"}
                  </button>
                  <button type="button" className="btn-link" onClick={() => setPanel(null)}>
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {panel === "save" && (
              <form
                className="stack"
                style={{ gap: 10 }}
                onSubmit={(e) => {
                  e.preventDefault();
                  void save(false);
                }}
              >
                <div className="grid-2">
                  <label className="field">
                    <span className="field-label">Template name</span>
                    <input className="input" required maxLength={200} placeholder="e.g. Dental clinic — multi-location" value={name} onChange={(e) => { setName(e.target.value); setClash(false); }} />
                  </label>
                  <label className="field">
                    <span className="field-label">When to use it (optional)</span>
                    <input className="input" maxLength={500} placeholder="e.g. Clinics with 3+ locations and online booking" value={description} onChange={(e) => setDescription(e.target.value)} />
                  </label>
                </div>
                <p className="t-caption">
                  Keeps everything you filled in — requirements, scope, team, pricing, schedule, risks, KPIs and texts. The client&apos;s contact details,
                  the dates, the reference number and the names of the client&apos;s people are left out.
                </p>
                {clash ? (
                  <Callout tone="warning" title={`A template named “${name.trim()}” already exists`}>
                    <div className="row" style={{ marginTop: 6 }}>
                      <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void save(true)}>
                        Replace it
                      </button>
                      <span className="t-caption">or change the name above.</span>
                    </div>
                  </Callout>
                ) : (
                  <div className="row">
                    <button type="submit" className="btn btn-primary" disabled={busy || !name.trim()}>
                      {busy ? "Saving…" : "Save template"}
                    </button>
                    <button type="button" className="btn-link" onClick={() => setPanel(null)}>
                      Cancel
                    </button>
                  </div>
                )}
              </form>
            )}

            {panel === "manage" && templates && (
              <div className="templates-list">
                {templates.map((t) => (
                  <div key={t.id} className="template-option">
                    <span className="stack" style={{ gap: 2, flex: 1 }}>
                      <b>{t.name}</b>
                      {t.description && <span className="t-description">{t.description}</span>}
                      <span className="t-caption">
                        {describe(t)} · updated {new Date(t.updated_at).toLocaleDateString()}
                      </span>
                    </span>
                    {t.can_delete ? (
                      <button
                        type="button"
                        className="btn-link btn-link-danger"
                        disabled={busy}
                        onClick={() => {
                          if (window.confirm(`Delete the template “${t.name}” for everyone in your workspace?`)) void remove(t);
                        }}
                      >
                        Delete
                      </button>
                    ) : (
                      <span className="t-caption" title="Only the person who saved it or an admin can delete it">
                        —
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {message && (
        <Callout tone={message.tone} title={message.tone === "success" ? "Done" : "That didn't work"}>
          {message.text}
        </Callout>
      )}
    </section>
  );
}
