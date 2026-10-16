"use client";

/**
 * Tasks & progress: the team's internal tracker for one project. Follow-up
 * tasks grouped by engagement stage — each with its source, a timestamped
 * check, notes and attached documents — plus per-stage owners, start /
 * finish dates and progress, and a progress report for the client.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { useAppSession } from "@/components/AppSession";
import { AssistButton } from "@/components/AssistButton";
import { Glyph } from "@/components/icons";
import { ProjectHeader } from "@/components/project/ProjectHeader";
import { SaveBanner } from "@/components/project/SaveBanner";
import { Callout, Checkbox, CheckMark, ExportFooter, Icon, Reveal } from "@/components/ui";
import {
  ApiError,
  assistProjectTasks,
  downloadDocument,
  evaluateNotes,
  exportMarkdown,
  fileStub,
  getModuleState,
  listMembers,
  saveToLibrary,
  textFile,
  type LibraryDocument,
  type Member,
} from "@/lib/api";
import { projectContext } from "@/lib/assist";
import { normalizeState as normalizeDiscovery } from "@/lib/discovery-state";
import { insertRow, springs, tween } from "@/lib/motion";
import { useModuleState } from "@/lib/module-state";
import {
  newTaskId,
  normalizeTasks,
  progress,
  STAGES,
  stageStatus,
  stageTasks,
  syncStageDates,
  titleKey,
  today,
  type ProjectTask,
  type StageId,
  type StageStatus,
  type TasksState,
} from "@/lib/tasks-state";

const STATUS_CHIP: Record<StageStatus, string> = {
  "Not started": "status-chip status-chip-neutral",
  "In progress": "status-chip",
  Done: "status-chip status-chip-success",
};

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function day(date: string | null): string {
  return date ? new Date(`${date}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "—";
}

/** A thin bar that fills to `pct` (transform only, so it stays smooth). */
function ProgressBar({ pct, label }: { pct: number; label: string }) {
  return (
    <div className="track-progress" role="progressbar" aria-label={label} aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <motion.span className="track-progress-fill" initial={false} animate={{ scaleX: pct / 100 }} transition={tween.slow} />
    </div>
  );
}

// ---- One task -----------------------------------------------------------------------

function TaskRow({
  task,
  projectId,
  onChange,
  onDelete,
  onToggle,
}: {
  task: ProjectTask;
  projectId: string;
  onChange: (patch: Partial<ProjectTask>) => void;
  onDelete: () => void;
  onToggle: () => void;
}) {
  const [open, setOpen] = useState<"source" | "notes" | null>(null);
  const [uploading, setUploading] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    setProblem(null);
    try {
      const added = [];
      for (const f of Array.from(files)) {
        const saved = await saveToLibrary(projectId, "Task attachment", { blob: f, filename: f.name }, `${task.title} — ${f.name}`);
        added.push({ documentId: saved.id, filename: saved.filename });
      }
      onChange({ attachments: [...task.attachments, ...added] });
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : "The file wasn't uploaded.");
    }
    setUploading(false);
  };

  return (
    <motion.li className="track-task" data-done={task.done} layout variants={insertRow} initial="hidden" animate="visible" exit="exit" transition={{ layout: springs.snappy }}>
      <div className="track-task-main">
        <button type="button" className="track-check" role="checkbox" aria-checked={task.done} aria-label={`Done: ${task.title}`} onClick={onToggle}>
          <CheckMark checked={task.done} />
        </button>
        <div className="track-task-body">
          <span className="track-task-title">{task.title}</span>
          {task.done && task.doneAt && (
            <span className="track-task-stamp">
              Checked {when(task.doneAt)}
              {task.doneBy ? ` by ${task.doneBy}` : ""}
            </span>
          )}
          <div className="track-task-links">
            {task.source && (
              <button type="button" className="task-source-toggle" aria-expanded={open === "source"} onClick={() => setOpen(open === "source" ? null : "source")}>
                Source details
              </button>
            )}
            <button type="button" className="task-source-toggle" aria-expanded={open === "notes"} onClick={() => setOpen(open === "notes" ? null : "notes")}>
              {task.notes.trim() ? "Notes (1)" : "Add notes"}
            </button>
            <button type="button" className="task-source-toggle" disabled={uploading} onClick={() => file.current?.click()}>
              {uploading ? "Uploading…" : "Attach file"}
            </button>
            <input ref={file} type="file" multiple hidden onChange={(e) => void upload(e.target.files).then(() => (e.target.value = ""))} />
          </div>
          {task.attachments.length > 0 && (
            <div className="track-files">
              {task.attachments.map((a) => (
                <span key={a.documentId} className="track-file">
                  <button
                    type="button"
                    className="btn-link"
                    title="Download"
                    onClick={() =>
                      downloadDocument(projectId, { id: a.documentId, filename: a.filename } as LibraryDocument).catch((e: unknown) =>
                        setProblem(e instanceof ApiError ? e.message : "Download failed."),
                      )
                    }
                  >
                    <Glyph name="file" size={14} />
                    {a.filename}
                  </button>
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label={`Remove ${a.filename} from this task`}
                    title="Remove from this task (the file stays in the Project Library)"
                    onClick={() => onChange({ attachments: task.attachments.filter((x) => x.documentId !== a.documentId) })}
                  >
                    <Glyph name="x" size={12} />
                  </button>
                </span>
              ))}
            </div>
          )}
          <Reveal show={open === "source"}>
            <p className="task-reason track-detail">{task.source}</p>
          </Reveal>
          <Reveal show={open === "notes"}>
            <textarea
              className="textarea track-detail"
              rows={3}
              placeholder="Decisions, who said what, links, next steps…"
              value={task.notes}
              onChange={(e) => onChange({ notes: e.target.value })}
            />
          </Reveal>
          {problem && <Callout tone="error" title="That didn't work">{problem}</Callout>}
        </div>
        <button
          type="button"
          className="icon-btn"
          aria-label={`Delete task ${task.title}`}
          onClick={() => {
            if (window.confirm(`Delete "${task.title}"? Its notes go too; attached files stay in the Project Library.`)) onDelete();
          }}
        >
          <Glyph name="x" size={14} />
        </button>
      </div>
    </motion.li>
  );
}

// ---- One stage ------------------------------------------------------------------------

function StageSection({
  stage,
  state,
  members,
  hideDone,
  projectId,
  meName,
  mutate,
}: {
  stage: (typeof STAGES)[number];
  state: TasksState;
  members: Member[];
  hideDone: boolean;
  projectId: string;
  meName: string;
  mutate: (fn: (s: TasksState) => TasksState) => void;
}) {
  const tasks = stageTasks(state, stage.id);
  const meta = state.stages[stage.id];
  const status = stageStatus(state, stage.id);
  const { done, total, pct } = progress(tasks);
  const [open, setOpen] = useState(status !== "Done");
  const [draft, setDraft] = useState("");
  const shown = hideDone ? tasks.filter((t) => !t.done) : tasks;

  const setMeta = (patch: Partial<typeof meta>) => mutate((s) => ({ ...s, stages: { ...s.stages, [stage.id]: { ...s.stages[stage.id], ...patch } } }));
  const setTask = (id: string, patch: Partial<ProjectTask>) => mutate((s) => ({ ...s, tasks: s.tasks.map((t) => (t.id === id ? { ...t, ...patch } : t)) }));

  return (
    <section className="track-stage card" id={`stage-${stage.id}`}>
      <button type="button" className="track-stage-head" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <motion.span animate={{ rotate: open ? 90 : 0 }} transition={springs.snappy} style={{ display: "inline-flex" }}>
          <Icon name="chevron-right" />
        </motion.span>
        <span className="track-stage-name">{stage.name}</span>
        <span className={STATUS_CHIP[status]}>{status}</span>
        <span className="t-caption track-stage-count">
          {done} of {total} done
        </span>
        <span className="track-stage-bar">
          <ProgressBar pct={pct} label={`${stage.name} progress`} />
        </span>
      </button>
      <div className="track-stage-meta">
        <label className="field">
          <span className="field-label">In charge</span>
          <select className="input" value={meta.ownerId ?? ""} onChange={(e) => setMeta({ ownerId: e.target.value || null })}>
            <option value="">Nobody yet</option>
            {members.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field-label">Started</span>
          <input type="date" className="input" value={meta.startedOn ?? ""} onChange={(e) => setMeta({ startedOn: e.target.value || null })} />
        </label>
        <label className="field">
          <span className="field-label">Finished</span>
          <input type="date" className="input" value={meta.finishedOn ?? ""} onChange={(e) => setMeta({ finishedOn: e.target.value || null })} />
        </label>
      </div>
      <Reveal show={open}>
        <div className="stack" style={{ gap: 10, paddingTop: 4 }}>
          {shown.length > 0 ? (
            <ul className="track-tasks">
              <AnimatePresence initial={false}>
                {shown.map((t) => (
                  <TaskRow
                    key={t.id}
                    task={t}
                    projectId={projectId}
                    onChange={(patch) => setTask(t.id, patch)}
                    onDelete={() => mutate((s) => ({ ...s, tasks: s.tasks.filter((x) => x.id !== t.id) }))}
                    onToggle={() =>
                      setTask(t.id, t.done ? { done: false, doneAt: null, doneBy: null } : { done: true, doneAt: new Date().toISOString(), doneBy: meName })
                    }
                  />
                ))}
              </AnimatePresence>
            </ul>
          ) : (
            <p className="t-caption">{tasks.length ? "Everything here is done." : "No tasks yet."}</p>
          )}
          <form
            className="track-add"
            onSubmit={(e) => {
              e.preventDefault();
              const title = draft.trim();
              if (!title) return;
              mutate((s) => ({
                ...s,
                tasks: [
                  ...s.tasks,
                  { id: newTaskId(), stage: stage.id, title, source: "", origin: "manual", done: false, doneAt: null, doneBy: null, notes: "", attachments: [], createdAt: new Date().toISOString() },
                ],
              }));
              setDraft("");
            }}
          >
            <input className="input" placeholder={`Add a task to ${stage.name}…`} value={draft} onChange={(e) => setDraft(e.target.value)} />
            <button type="submit" className="btn btn-secondary" disabled={!draft.trim()}>
              <Glyph name="plus" /> Add
            </button>
          </form>
        </div>
      </Reveal>
    </section>
  );
}

// ---- Report --------------------------------------------------------------------------

function reportMarkdown(state: TasksState, client: string, members: Member[], withNotes: boolean): string {
  const owner = (id: string | null) => members.find((m) => m.id === id)?.name ?? "—";
  const all = progress(state.tasks);
  const lines = [
    `# Project progress — ${client}`,
    "",
    `Updated ${new Date().toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" })}`,
    "",
    `**Overall:** ${all.pct}% complete (${all.done} of ${all.total} tasks).`,
    "",
    "| Stage | In charge | Status | Started | Finished | Progress |",
    "| --- | --- | --- | --- | --- | --- |",
    ...STAGES.map(({ id, name }) => {
      const p = progress(stageTasks(state, id));
      const m = state.stages[id];
      return `| ${name} | ${owner(m.ownerId)} | ${stageStatus(state, id)} | ${day(m.startedOn)} | ${day(m.finishedOn)} | ${p.done} of ${p.total} (${p.pct}%) |`;
    }),
  ];
  for (const { id, name } of STAGES) {
    const tasks = stageTasks(state, id);
    if (!tasks.length) continue;
    lines.push("", `## ${name}`, "");
    for (const t of tasks) {
      lines.push(`- ${t.done ? "Done" : "Open"}: ${t.title}${t.done && t.doneAt ? ` (completed ${day(t.doneAt.slice(0, 10))})` : ""}`);
      if (withNotes && t.notes.trim()) lines.push(`  - Notes: ${t.notes.trim().replace(/\n+/g, " ")}`);
    }
  }
  return lines.join("\n");
}

// ---- Page ------------------------------------------------------------------------------

export default function TasksPage() {
  const { project, me } = useAppSession();
  const projectId = project?.id ?? "";
  const store = useModuleState<TasksState>(projectId, "tasks", normalizeTasks);
  const { state, change, loaded } = store;
  const [members, setMembers] = useState<Member[]>([]);
  const [hideDone, setHideDone] = useState(false);
  const [withNotes, setWithNotes] = useState(false);

  useEffect(() => {
    listMembers()
      .then(setMembers)
      .catch(() => undefined);
  }, []);

  if (!project) return null;
  const client = project.client_name || project.name;
  const mutate = (fn: (s: TasksState) => TasksState) => change((s) => syncStageDates(fn(s)));
  const all = progress(state.tasks);

  const addTasks = (incoming: Omit<ProjectTask, "id" | "createdAt" | "notes" | "attachments" | "doneBy" | "doneAt">[]) => {
    const have = new Set(state.tasks.map((t) => titleKey(t.title)));
    const fresh: ProjectTask[] = [];
    for (const t of incoming) {
      const key = titleKey(t.title);
      if (!key || have.has(key)) continue;
      have.add(key);
      const at = new Date().toISOString();
      fresh.push({ ...t, id: newTaskId(), notes: "", attachments: [], createdAt: at, doneAt: t.done ? at : null, doneBy: t.done ? "From discovery" : null });
    }
    if (fresh.length) {
      mutate((s) => {
        const existing = new Set(s.tasks.map((t) => titleKey(t.title)));
        return { ...s, tasks: [...s.tasks, ...fresh.filter((t) => !existing.has(titleKey(t.title)))] };
      });
    }
    return fresh.length;
  };

  const suggest = async () => {
    const result = await assistProjectTasks(
      await projectContext(project.id, client),
      state.tasks.map((t) => ({ stage: t.stage, title: t.title })),
    );
    const added = addTasks(result.tasks.map((t) => ({ stage: t.stage as StageId, title: t.title, source: t.source, origin: "ai", done: false })));
    return added ? `Added ${added} suggested task${added === 1 ? "" : "s"} across the stages. Review them below.` : "Nothing new to suggest: the list already covers what earlier steps mention.";
  };

  const pullFromDiscovery = async () => {
    const discovery = normalizeDiscovery((await getModuleState(project.id, "discovery")).data, client);
    const evaluation = await evaluateNotes({
      client_name: discovery.clientName,
      business_type: discovery.businessType,
      client_website: "",
      sections: discovery.sections,
      project_type: discovery.projectType,
      done_build_items: discovery.buildDone,
      stage_planner: discovery.stagePlanner,
    });
    const required = evaluation.tasks.map((f) => ({
      stage: "build" as StageId,
      title: f.task.label,
      source: `Required by the discovery answers — because: ${f.reasons.join(" · ")}${f.task.detail ? `. ${f.task.detail}` : ""}`,
      origin: "required" as const,
      done: discovery.tasksDone.includes(f.task.id),
    }));
    const build = evaluation.build_order.sections.flatMap((section) =>
      section.items.map((item) => ({
        stage: "build" as StageId,
        title: item.name,
        source: `Build order · ${section.title}${item.sources.length ? ` — from ${item.sources.join("; ")}` : ""}`,
        origin: "build" as const,
        done: item.done,
      })),
    );
    const added = addTasks([...required, ...build]);
    return added ? `Added ${added} task${added === 1 ? "" : "s"} from the discovery call's required tasks and build order (under Build).` : "Nothing new: those tasks are already on the list.";
  };

  return (
    <>
      <ProjectHeader
        eyebrow="PROJECT / TRACKING"
        title="Tasks & progress"
        meta={
          <>
            <span className="status-chip">
              {all.done} of {all.total} tasks done
            </span>
            <span className="status-chip status-chip-success">{all.pct}% complete</span>
          </>
        }
      />
      <div className="page-content">
        {!loaded ? (
          <div className="skeleton" style={{ height: 320 }} aria-busy="true" />
        ) : (
          <>
            <SaveBanner store={store} />

            <section className="card track-overview" aria-label="Progress by stage">
              <div className="row-between">
                <span className="t-card-title">Overall progress</span>
                <span className="t-caption">
                  {all.done} of {all.total} tasks · {all.pct}%
                </span>
              </div>
              <ProgressBar pct={all.pct} label="Overall progress" />
              <div className="track-stage-strip">
                {STAGES.map((s) => {
                  const p = progress(stageTasks(state, s.id));
                  const status = stageStatus(state, s.id);
                  const owner = members.find((m) => m.id === state.stages[s.id].ownerId)?.name;
                  return (
                    <a key={s.id} href={`#stage-${s.id}`} className="track-stage-tile" data-status={status}>
                      <span className="track-stage-tile-name">{s.name}</span>
                      <span className={STATUS_CHIP[status]}>{status}</span>
                      <ProgressBar pct={p.pct} label={`${s.name} progress`} />
                      <span className="t-caption">{owner ?? "Nobody in charge"}</span>
                      <span className="t-caption">
                        {state.stages[s.id].startedOn
                          ? `${day(state.stages[s.id].startedOn)} – ${state.stages[s.id].finishedOn ? day(state.stages[s.id].finishedOn) : "ongoing"}`
                          : "No dates yet"}
                      </span>
                    </a>
                  );
                })}
              </div>
            </section>

            <div className="track-actions">
              <AssistButton label="Suggest tasks with AI" run={suggest} />
              <AssistButton label="Pull from discovery" run={pullFromDiscovery} />
              <Checkbox checked={hideDone} onChange={setHideDone}>
                Hide completed tasks
              </Checkbox>
            </div>

            {state.tasks.length === 0 && (
              <Callout tone="info" title="No tasks yet">
                Suggest tasks with AI, pull the discovery call&apos;s required tasks and build order, or add your own under any stage.
              </Callout>
            )}

            {STAGES.map((s) => (
              <StageSection key={s.id} stage={s} state={state} members={members} hideDone={hideDone} projectId={project.id} meName={me.name || me.email} mutate={mutate} />
            ))}

            <section className="stack" style={{ gap: 12 }}>
              <h2 className="t-section">Progress report for the client</h2>
              <Checkbox checked={withNotes} onChange={setWithNotes}>
                Include task notes (they&apos;re internal; leave off for the client)
              </Checkbox>
              <ExportFooter
                library={{ projectId: project.id, documentType: "Progress Report", title: `Progress report — ${client}` }}
                actions={[
                  { label: ".docx", make: () => exportMarkdown(reportMarkdown(state, client, members, withNotes), `Progress report — ${client}`, "docx", fileStub(client, "progress_report")) },
                  { label: ".pdf", make: () => exportMarkdown(reportMarkdown(state, client, members, withNotes), `Progress report — ${client}`, "pdf", fileStub(client, "progress_report")) },
                  { label: ".md", make: () => textFile(reportMarkdown(state, client, members, withNotes), `${fileStub(client, "progress_report")}.md`, "text/markdown") },
                ]}
              />
            </section>
          </>
        )}
      </div>
    </>
  );
}
