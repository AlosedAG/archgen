/**
 * The project's internal task tracker (saved as the "tasks" module state):
 * follow-up tasks grouped by engagement stage, each with its source, a
 * timestamped check, notes and attached documents; and per stage an owner
 * and start / finish dates that fill in from the tasks.
 */

export const STAGES = [
  { id: "discover", name: "Discover" },
  { id: "assess", name: "Assess current portal" },
  { id: "design", name: "Design" },
  { id: "propose", name: "Propose" },
  { id: "build", name: "Build" },
  { id: "launch", name: "Test & launch" },
] as const;

export type StageId = (typeof STAGES)[number]["id"];
export type TaskOrigin = "manual" | "ai" | "required" | "build";
export type TaskAttachment = { documentId: string; filename: string };

export type ProjectTask = {
  id: string;
  stage: StageId;
  title: string;
  /** Why the task exists and where it came from ("Source details"). */
  source: string;
  origin: TaskOrigin;
  done: boolean;
  /** ISO time it was checked, and by whom. */
  doneAt: string | null;
  doneBy: string | null;
  notes: string;
  attachments: TaskAttachment[];
  createdAt: string;
};

export type StageMeta = {
  ownerId: string | null;
  /** ISO dates (yyyy-mm-dd). Filled automatically, editable. */
  startedOn: string | null;
  finishedOn: string | null;
};

export type TasksState = { tasks: ProjectTask[]; stages: Record<StageId, StageMeta> };

export type StageStatus = "Not started" | "In progress" | "Done";

const EMPTY_STAGE: StageMeta = { ownerId: null, startedOn: null, finishedOn: null };

export function normalizeTasks(raw: unknown): TasksState {
  const s = (typeof raw === "object" && raw ? raw : {}) as Partial<TasksState>;
  const stages = Object.fromEntries(STAGES.map(({ id }) => [id, { ...EMPTY_STAGE, ...(s.stages?.[id] ?? {}) }])) as Record<StageId, StageMeta>;
  const valid = new Set<string>(STAGES.map((st) => st.id));
  const tasks = (s.tasks ?? [])
    .filter((t) => t && valid.has(t.stage))
    .map((t) => {
      const defaults: Omit<ProjectTask, "id" | "stage" | "title"> = {
        source: "",
        origin: "manual",
        done: false,
        doneAt: null,
        doneBy: null,
        notes: "",
        attachments: [],
        createdAt: "",
      };
      return { ...defaults, ...(t as Partial<ProjectTask>) } as ProjectTask;
    });
  return { tasks, stages };
}

export const today = () => new Date().toISOString().slice(0, 10);

export function newTaskId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `t-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** Comparable form of a title, so near-identical tasks aren't added twice. */
export const titleKey = (title: string) => title.toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, " ").replace(/\s+/g, " ").trim();

export function stageTasks(state: TasksState, stage: StageId): ProjectTask[] {
  return state.tasks.filter((t) => t.stage === stage);
}

export function stageStatus(state: TasksState, stage: StageId): StageStatus {
  const tasks = stageTasks(state, stage);
  const done = tasks.filter((t) => t.done).length;
  if ((tasks.length > 0 && done === tasks.length) || (tasks.length === 0 && state.stages[stage].finishedOn)) return "Done";
  if (done > 0 || state.stages[stage].startedOn) return "In progress";
  return "Not started";
}

export function progress(tasks: ProjectTask[]): { done: number; total: number; pct: number } {
  const done = tasks.filter((t) => t.done).length;
  return { done, total: tasks.length, pct: tasks.length ? Math.round((done / tasks.length) * 100) : 0 };
}

/**
 * Keep each stage's dates in step with its tasks: a stage starts the day its
 * first task is checked, finishes the day its last one is, and reopens if a
 * task is unchecked or added. Dates someone set by hand are kept unless the
 * stage reopens.
 */
export function syncStageDates(state: TasksState): TasksState {
  const stages = { ...state.stages };
  for (const { id } of STAGES) {
    const tasks = stageTasks(state, id);
    const meta = { ...stages[id] };
    const checked = tasks.filter((t) => t.done && t.doneAt).map((t) => t.doneAt!.slice(0, 10)).sort();
    if (!meta.startedOn && checked.length) meta.startedOn = checked[0]!;
    const allDone = tasks.length > 0 && tasks.every((t) => t.done);
    if (allDone && !meta.finishedOn) meta.finishedOn = checked.at(-1) ?? today();
    if (tasks.length > 0 && !allDone && meta.finishedOn) meta.finishedOn = null;
    stages[id] = meta;
  }
  return { ...state, stages };
}
