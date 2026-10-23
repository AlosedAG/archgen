"use client";

/**
 * A project's home: its dashboard, on a soft lavender "board". The header
 * names the project, its client and stage, shows the team and a Continue
 * button into the tool to pick up from; below come the active workstreams
 * (Tasks-tracker stages in progress), how complete the deliverables are,
 * then the team's contribution, documents by stage and recent activity.
 * Every figure comes from useProjectDashboard (the project's saved work).
 */

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";
import { useParams } from "next/navigation";

import { useAppSession } from "@/components/AppSession";
import { CompletionDonut } from "@/components/dashboard/CompletionDonut";
import { DocumentsByStageChart } from "@/components/dashboard/DocumentsByStageChart";
import { NavIcon, type NavIconName } from "@/components/NavIcons";
import { Callout } from "@/components/ui";
import type { ProjectDashboard } from "@/lib/api";
import { avatarColor, initials } from "@/lib/avatars";
import { ago, useProjectDashboard } from "@/lib/project-dashboard";

type Person = ProjectDashboard["team"][number];

function Avatar({ person, className }: { person: Person; className: string }) {
  return (
    <span className={className} style={{ background: avatarColor(person.id ?? person.name) }} title={person.name} aria-hidden>
      {initials(person.name)}
    </span>
  );
}

const TINTS = ["db-w1", "db-w2", "db-w3"];

function Workstreams({ data, projectId }: { data: ProjectDashboard; projectId: string }) {
  const reduce = useReducedMotion();
  return (
    <section className="db-hero-main db-soft" aria-labelledby="dbw-title">
      <div className="db-panel-head">
        <h3 id="dbw-title">Active workstream</h3>
        <Link href={`/projects/${projectId}/tasks`} className="db-seeall">
          See all
        </Link>
      </div>
      {data.workstreams.length === 0 ? (
        <div className="db-empty">
          <p>No stage is in progress yet.</p>
          <p className="db-muted">
            Workstreams appear here once tasks in the <Link href={`/projects/${projectId}/tasks`}>Tasks tracker</Link> get ticked off.
          </p>
        </div>
      ) : (
        <ul className="db-work">
          {data.workstreams.map((w, i) => {
            const pct = w.total ? Math.round((w.done / w.total) * 100) : 0;
            return (
              <li key={w.stage} className={`db-wcard ${TINTS[i % TINTS.length]}`}>
                <span className="db-wchip">{w.stage}</span>
                <h4>{w.title}</h4>
                <span className="db-spacer" />
                {w.people.length > 0 && (
                  <span className="db-wavs" aria-label={`People: ${w.people.map((p) => p.name).join(", ")}`}>
                    {w.people.slice(0, 4).map((p) => (
                      <Avatar key={p.id ?? p.name} person={p} className="db-wav" />
                    ))}
                  </span>
                )}
                <span className="db-wprog">
                  <span
                    className="db-wtrack"
                    role="progressbar"
                    aria-label={`${w.stage} tasks done`}
                    aria-valuemin={0}
                    aria-valuemax={w.total}
                    aria-valuenow={w.done}
                  >
                    <motion.i
                      initial={{ width: reduce ? `${pct}%` : 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={reduce ? { duration: 0 } : { duration: 0.7, delay: 0.2 + i * 0.08, ease: [0.2, 0.8, 0.2, 1] }}
                    />
                  </span>
                  <span className="db-wct">
                    {w.done}/{w.total}
                  </span>
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function Team({ data }: { data: ProjectDashboard }) {
  return (
    <section className="db-panel db-soft" aria-labelledby="dbt-title">
      <div className="db-panel-head">
        <h3 id="dbt-title">Team contribution</h3>
      </div>
      {data.contributors.length === 0 ? (
        <p className="db-muted">Nobody has worked on this project yet.</p>
      ) : (
        <ol className="db-rank">
          {data.contributors.slice(0, 5).map((c) => (
            <li key={c.id}>
              <Avatar person={c} className="db-rank-av" />
              <span className="db-rank-name">
                <b>{c.name}</b>
                <span>{c.role}</span>
              </span>
              <span className="db-rank-pts">
                {c.documents}
                <small>doc{c.documents === 1 ? "" : "s"}</small>
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

const FEED_ICON: Record<ProjectDashboard["activity"][number]["kind"], NavIconName> = {
  document: "doc",
  task: "check",
  audit: "gauge",
  edit: "sliders",
};

function Activity({ data, projectId }: { data: ProjectDashboard; projectId: string }) {
  return (
    <section className="db-panel db-soft" aria-labelledby="dba-title">
      <div className="db-panel-head">
        <h3 id="dba-title">Recent activity</h3>
        <Link href={`/projects/${projectId}/library`} className="db-seeall">
          See all
        </Link>
      </div>
      {data.activity.length === 0 ? (
        <p className="db-muted">Nothing yet. Saved documents, ticked tasks and audits show up here.</p>
      ) : (
        <ul className="db-feed">
          {data.activity.map((a, i) => (
            <li key={`${a.kind}-${a.at}-${i}`}>
              <span className="db-feed-ic" aria-hidden>
                <NavIcon name={FEED_ICON[a.kind]} size={15} />
              </span>
              <span className="db-feed-t">
                <b>{a.title}</b>
                <span>
                  <time dateTime={a.at} title={new Date(a.at).toLocaleString()}>
                    {ago(a.at)}
                  </time>
                  {a.by ? ` · ${a.by}` : ""}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function ProjectDashboardPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { project } = useAppSession();
  const state = useProjectDashboard(projectId);

  const title = project ? project.client_name || project.name : "";
  const context = project ? (project.client_name && project.client_name !== project.name ? project.name : project.folder) : "";

  return (
    <div className="page-content db-page">
      <Link href="/projects" className="db-back">
        <NavIcon name="chevron-right" size={15} className="db-back-ic" />
        Back to Projects
      </Link>
      {state.status === "error" ? (
        <Callout tone="error" title="Couldn't load the dashboard">
          {state.message}{" "}
          <button type="button" className="btn-link" onClick={state.reload}>
            Try again
          </button>
        </Callout>
      ) : (
        <div className="db-board" aria-busy={state.status === "loading"}>
          <header className="db-board-head">
            <div>
              <h1>{title}</h1>
              <p className="db-board-sub">
                {[context, state.status === "ready" ? `${state.data.insight.stage} stage` : null].filter(Boolean).join(" · ") || " "}
              </p>
            </div>
            {state.status === "ready" && (
              <div className="db-board-right">
                <span className="db-team" aria-label={`Team: ${state.data.team.map((p) => p.name).join(", ")}`}>
                  {state.data.team.slice(0, 5).map((p) => (
                    <Avatar key={p.id ?? p.name} person={p} className="db-team-av" />
                  ))}
                </span>
                <Link href={`/projects/${projectId}/${state.data.continue_page}`} className="btn btn-primary db-pill-btn">
                  {state.data.continue_label}
                </Link>
              </div>
            )}
          </header>
          {state.status === "loading" ? (
            <div className="db-hero" aria-hidden>
              <div className="skeleton" style={{ height: 230, borderRadius: 20 }} />
              <div className="skeleton" style={{ height: 230, borderRadius: 20 }} />
            </div>
          ) : (
            <>
              <div className="db-hero">
                <Workstreams data={state.data} projectId={projectId} />
                <CompletionDonut data={state.data} />
              </div>
              <div className="db-trio">
                <Team data={state.data} />
                <DocumentsByStageChart stages={state.data.documents_by_stage} seeAllHref={`/projects/${projectId}/library`} />
                <Activity data={state.data} projectId={projectId} />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
