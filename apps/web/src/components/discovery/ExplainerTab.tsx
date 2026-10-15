"use client";

/** Tab 2 — a plain-language explainer of the HubSpot hubs the client needs, to share with them. */

import { motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";

import { suggestModules, type HubSpotModule } from "@/lib/api";
import type { DiscoveryStore } from "@/lib/discovery-state";

import { CheckMark, Icon, type IconName } from "../ui";
import { DocumentResult } from "./DocumentResult";
import { ModelPicker, useAiModel } from "./ModelPicker";
import { StreamErrorCallout } from "./StreamErrorCallout";
import { useDocumentStream } from "./useDocumentStream";
import { fadeInUp, lift, press, staggerTiming } from "@/lib/motion";

const HUBS: { id: HubSpotModule; icon: IconName; blurb: string }[] = [
  { id: "Marketing Hub", icon: "megaphone", blurb: "Turn interest into the right conversations." },
  { id: "Sales Hub", icon: "handshake", blurb: "Give every enquiry a clear next step." },
  { id: "Service Hub", icon: "headset", blurb: "Support customers consistently, wherever they reach you." },
  { id: "Operations Hub", icon: "workflow", blurb: "Keep systems connected and data dependable." },
  { id: "Content Hub (CMS)", icon: "panels-top-left", blurb: "Create and manage your website content." },
  { id: "Commerce Hub", icon: "credit-card", blurb: "Simplify quotes, billing, and payments." },
];

export function ExplainerTab({ store }: { store: DiscoveryStore }) {
  const { state, update } = store;
  const onDone = useCallback((text: string) => update({ ceOutput: text }), [update]);
  const stream = useDocumentStream("client-explainer", onDone);
  const ai = useAiModel();
  const [recommended, setRecommended] = useState<HubSpotModule[]>([]);
  const selected = state.ceModules;

  // Hubs the business analysis recommends, read from its "Recommended HubSpot Modules" section.
  useEffect(() => {
    if (!state.baOutput) {
      setRecommended([]);
      return;
    }
    let cancelled = false;
    suggestModules(state.baOutput)
      .then((modules) => !cancelled && setRecommended(modules))
      .catch(() => !cancelled && setRecommended([]));
    return () => {
      cancelled = true;
    };
  }, [state.baOutput]);

  return (
    <>
      <div className="stack" style={{ gap: 24 }}>
        <div className="heading-row">
          <h2 className="t-section">Choose the hubs to explain</h2>
          {recommended.length > 0 && (
            <span className="badge badge-keep">{recommended.length} recommended by business analysis</span>
          )}
        </div>
        <p className="t-description">
          Create a plain-language introduction for your client. Focus on the hubs that support their goals, not every
          feature.
        </p>
      </div>

      <div className="hub-grid" role="group" aria-label="HubSpot hubs to explain">
        {HUBS.map((hub, i) => {
          const on = selected.includes(hub.id);
          return (
            <motion.button
              key={hub.id}
              type="button"
              className="hub-card"
              aria-pressed={on}
              variants={fadeInUp}
              initial="hidden"
              animate="visible"
              transition={{ delay: i * staggerTiming.cards }}
              whileHover={lift}
              whileTap={press}
              onClick={() => update({ ceModules: on ? selected.filter((m) => m !== hub.id) : [...selected, hub.id] })}
            >
              <Icon name={hub.icon} />
              <span className="hub-name">
                <CheckMark checked={on} />
                {hub.id}
              </span>
              <span className="hub-blurb">{hub.blurb}</span>
              {recommended.includes(hub.id) && <span className="badge badge-keep">Recommended</span>}
            </motion.button>
          );
        })}
      </div>

      <div className="row-between">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={recommended.length === 0}
          title={recommended.length === 0 ? "Generate the business analysis first" : undefined}
          onClick={() => update({ ceModules: recommended })}
        >
          Use the hubs recommended in the business analysis
        </button>
        <motion.button
          type="button"
          className={stream.streaming ? "btn btn-primary btn-busy" : "btn btn-primary"}
          disabled={selected.length === 0 || stream.streaming}
          onClick={() => stream.start({ modules: selected, business_type: state.businessType }, ai.model)}
        >
          {!stream.streaming && <Icon name="sparkles" />}
          {stream.streaming ? "Generating…" : "Generate client explainer"}
        </motion.button>
        <ModelPicker models={ai.models} value={ai.model} onChange={ai.setModel} disabled={stream.streaming} />
      </div>
      {stream.error && (
        <StreamErrorCallout
          error={stream.error}
          lighter={ai.lightest}
          onRetryWith={(id) => {
            ai.setModel(id);
            void stream.start({ modules: selected, business_type: state.businessType }, id);
          }}
        />
      )}

      <DocumentResult
        markdown={stream.streaming ? stream.text : state.ceOutput}
        streaming={stream.streaming}
        onEdit={(ceOutput) => update({ ceOutput })}
        title="Your HubSpot Options, Explained"
        eyebrow="Client-facing / Plain-language guide"
        status={{ label: "Ready for your review", tone: "success" }}
        clientName={state.clientName}
        fileSuffix="hubspot_explainer"
        projectId={store.projectId}
        documentType="Discovery Client Explainer"
        progress={{ sections: Math.max(selected.length, 1), startedAt: stream.startedAt, status: stream.status }}
      />
    </>
  );
}
