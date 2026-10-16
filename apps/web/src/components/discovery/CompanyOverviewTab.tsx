"use client";

/**
 * Optional: a company overview read from the client's website by the AI —
 * name, type of business, summary, offerings, highlights, things to know and
 * questions to ask — to prepare for the call. Saved with the discovery notes
 * and shared with the other AI features as context.
 */

import { motion } from "framer-motion";
import { useState } from "react";

import { companyOverview, exportMarkdown, fileStub, textFile, type CompanyOverview } from "@/lib/api";
import type { DiscoveryStore } from "@/lib/discovery-state";
import { fadeInUp } from "@/lib/motion";

import { AssistButton } from "../AssistButton";
import { Callout, ExportFooter } from "../ui";

const LISTS: [keyof CompanyOverview, string][] = [
  ["offerings", "Products & services"],
  ["highlights", "Highlights"],
  ["things_to_know", "Things to know for the engagement"],
  ["questions_to_ask", "Questions to ask on the call"],
];

function toMarkdown(o: CompanyOverview, website: string): string {
  const lines = [`# ${o.name || "Company overview"}`, ""];
  if (o.type) lines.push(`**Type:** ${o.type}`, "");
  if (o.summary) lines.push(o.summary, "");
  if (o.audience) lines.push(`**Customers:** ${o.audience}`, "");
  if (o.locations) lines.push(`**Locations:** ${o.locations}`, "");
  for (const [key, title] of LISTS) {
    const items = (o[key] as string[] | undefined) ?? [];
    if (items.length) lines.push(`## ${title}`, "", ...items.map((i) => `- ${i}`), "");
  }
  lines.push(`Source: ${website}`);
  return lines.join("\n");
}

export function CompanyOverviewTab({ store }: { store: DiscoveryStore }) {
  const { state, update } = store;
  const saved = state.companyOverview;
  const website = state.clientWebsite.trim();
  const [applied, setApplied] = useState<string | null>(null);

  const generate = async () => {
    const result = await companyOverview(website, state.clientName, state.businessType);
    update({ companyOverview: { website: result.website, generatedAt: new Date().toISOString(), data: result.overview } });
    setApplied(null);
    return "Company overview ready. Review it below.";
  };

  const o = saved?.data;
  const canApply = o && ((o.type && o.type !== state.businessType) || (o.name && !state.clientName.trim()));

  return (
    <div className="stack" style={{ gap: 20 }}>
      {!website ? (
        <Callout tone="info" title="Add the client's website first">
          Type it in &ldquo;Client&apos;s website&rdquo; at the top of the page, then generate the overview here.
        </Callout>
      ) : (
        <div className="row" style={{ alignItems: "flex-start" }}>
          <AssistButton label={o ? "Regenerate from the website" : "Generate company overview"} variant={o ? "secondary" : "primary"} run={generate} />
          {saved && (
            <span className="t-caption" style={{ paddingTop: 10 }}>
              From {saved.website} · {new Date(saved.generatedAt).toLocaleString()}
            </span>
          )}
        </div>
      )}

      {o && (
        <motion.section className="card company-overview" variants={fadeInUp} initial="hidden" animate="visible">
          <div className="company-overview-head">
            <div className="stack" style={{ gap: 4 }}>
              <h2 className="t-section" style={{ margin: 0 }}>
                {o.name || state.clientName || "Company overview"}
              </h2>
              {o.type && <span className="status-chip">{o.type}</span>}
            </div>
            {canApply && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  update({
                    businessType: o.type || state.businessType,
                    clientName: state.clientName.trim() ? state.clientName : o.name || state.clientName,
                  });
                  setApplied("Business type (and client name, if it was blank) updated from the overview.");
                }}
              >
                Use for the client details
              </button>
            )}
          </div>
          {applied && <Callout tone="success" title={applied} />}
          {o.summary && <p className="company-overview-summary">{o.summary}</p>}
          {(o.audience || o.locations) && (
            <dl className="account-facts">
              {o.audience && (
                <div>
                  <dt>Customers</dt>
                  <dd>{o.audience}</dd>
                </div>
              )}
              {o.locations && (
                <div>
                  <dt>Locations</dt>
                  <dd>{o.locations}</dd>
                </div>
              )}
            </dl>
          )}
          <div className="company-overview-lists">
            {LISTS.map(([key, title]) => {
              const items = (o[key] as string[] | undefined) ?? [];
              if (!items.length) return null;
              return (
                <div key={key} className="company-overview-list">
                  <h3 className="t-card-title">{title}</h3>
                  <ul>
                    {items.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
          <ExportFooter
            library={{ projectId: store.projectId, documentType: "Company Overview", title: `Company overview — ${o.name || state.clientName}` }}
            actions={[
              { label: ".docx", make: () => exportMarkdown(toMarkdown(o, saved.website), `Company overview — ${o.name || state.clientName}`, "docx", fileStub(state.clientName, "company_overview")) },
              { label: ".md", make: () => textFile(toMarkdown(o, saved.website), `${fileStub(state.clientName, "company_overview")}.md`, "text/markdown") },
            ]}
          />
        </motion.section>
      )}
    </div>
  );
}
