"use client";

/** The user guide: quick start, the process, every page, and troubleshooting. */

import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { useAppSession } from "@/components/AppSession";
import { TabPanel, Tabs } from "@/components/ui";
import { GUIDE_PAGES, PROCESS, QUICK_START, TROUBLESHOOTING } from "@/lib/guide";

type TabId = "start" | "pages" | "help";

export default function GuidePage() {
  const { me } = useAppSession();
  const [tab, setTab] = useState<TabId>("start");
  const steps = [...new Set(GUIDE_PAGES.map((p) => p.step))];

  return (
    <>
      <PageHeader
        eyebrow="START HERE"
        breadcrumb={me.workspace_name}
        title="User guide"
        description="How to use ArchitectureScope, step by step. Every page also has its own short guide at the bottom of the sidebar."
      />
      <div className="page-content">
        <Tabs<TabId>
          label="User guide"
          layoutId="guide-tabs"
          variant="secondary"
          tabs={[
            { id: "start", label: "Start here" },
            { id: "pages", label: "Page by page" },
            { id: "help", label: "Troubleshooting" },
          ]}
          active={tab}
          onChange={setTab}
        />
        <TabPanel panelKey={tab} id="guide-tabs">
          {tab === "start" && (
            <div className="stack" style={{ gap: 24 }}>
              <section className="stack" style={{ gap: 10 }}>
                <h2 className="t-section">Quick start</h2>
                <ol className="guide-list">
                  {QUICK_START.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ol>
              </section>
              <section className="stack" style={{ gap: 10 }}>
                <h2 className="t-section">The process, step by step</h2>
                <div className="grid-2">
                  {PROCESS.map((p) => (
                    <div key={p.step} className="card stack" style={{ gap: 6 }}>
                      <span className="t-card-title">{p.step}</span>
                      <span className="t-description">{p.text}</span>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}
          {tab === "pages" && (
            <div className="stack" style={{ gap: 24 }}>
              {steps.map((step) => (
                <section key={step} className="stack" style={{ gap: 10 }}>
                  <h2 className="t-section">{step}</h2>
                  {GUIDE_PAGES.filter((p) => p.step === step).map((p) => (
                    <div key={p.key} className="card stack" style={{ gap: 6 }}>
                      <span className="t-card-title">{p.title}</span>
                      <span className="t-description">{p.summary}</span>
                      <ul className="guide-list">
                        {p.steps.map((s) => (
                          <li key={s}>{s}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </section>
              ))}
            </div>
          )}
          {tab === "help" && (
            <div className="stack" style={{ gap: 12 }}>
              {TROUBLESHOOTING.map((t) => (
                <div key={t.problem} className="card stack" style={{ gap: 4 }}>
                  <span className="t-card-title">{t.problem}</span>
                  <span className="t-description">{t.fix}</span>
                </div>
              ))}
            </div>
          )}
        </TabPanel>
      </div>
    </>
  );
}
