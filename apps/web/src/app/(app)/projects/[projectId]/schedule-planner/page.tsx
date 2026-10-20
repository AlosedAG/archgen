"use client";

/**
 * Schedule Planner — plan the client meetings, then run them from a calendar.
 *
 * 1. Plan: how you'll meet (dates, cadence, days, time, platform, link…),
 *    then add meetings or let "Suggest meetings" draft the series from the
 *    discovery call, the documents and the project timeline. Each meeting
 *    gets a date and time — picked, or placed by "Auto-schedule".
 * 2. Calendar: the month with every meeting; hover a day to see and adjust
 *    its meetings, drag one to another day, open one to preview, edit,
 *    get suggested content, copy the invite or download it (.ics).
 */

import { useCallback, useMemo, useState } from "react";

import { useAppSession } from "@/components/AppSession";
import { AssistButton } from "@/components/AssistButton";
import { ProjectHeader } from "@/components/project/ProjectHeader";
import { SaveBanner } from "@/components/project/SaveBanner";
import { MeetingDrawer } from "@/components/schedule/MeetingDrawer";
import { MeetingList } from "@/components/schedule/MeetingList";
import { MonthCalendar } from "@/components/schedule/MonthCalendar";
import { PlanSetup } from "@/components/schedule/PlanSetup";
import { Callout, TabPanel, Tabs } from "@/components/ui";
import { assistSchedule, getModuleState, type AssistContext } from "@/lib/api";
import { projectContext } from "@/lib/assist";
import { useModuleState } from "@/lib/module-state";
import {
  autoSchedule,
  fromSuggestion,
  newMeeting,
  normalizeSchedule,
  settingsPayload,
  stubs,
  type Meeting,
  type ScheduleSettings,
  type ScheduleState,
} from "@/lib/schedule-state";
import { STAGES, normalizeTasks } from "@/lib/tasks-state";

type Tab = "plan" | "calendar";

/** The usual project context, plus the timeline from Tasks & progress (stage dates and open tasks). */
async function scheduleContext(projectId: string, clientName: string): Promise<AssistContext> {
  const [context, tasksRaw] = await Promise.all([
    projectContext(projectId, clientName),
    getModuleState(projectId, "tasks").then((s) => (s.data && Object.keys(s.data).length ? s.data : null)),
  ]);
  if (tasksRaw) {
    const tasks = normalizeTasks(tasksRaw);
    const timeline = STAGES.map((st) => {
      const meta = tasks.stages[st.id];
      const open = tasks.tasks.filter((t) => t.stage === st.id && !t.done).map((t) => t.title);
      return {
        Stage: st.name,
        Started: meta.startedOn ?? "",
        Finished: meta.finishedOn ?? "",
        "Open tasks": open.slice(0, 12).join("; "),
      };
    }).filter((r) => r.Started || r.Finished || r["Open tasks"]);
    if (timeline.length) context.documents = { ...context.documents, "Project timeline (Tasks & progress)": { Stages: timeline } };
  }
  return context;
}

export default function SchedulePlannerPage() {
  const { project } = useAppSession();
  const projectId = project?.id ?? "";
  const client = project?.client_name || project?.name || "";
  const store = useModuleState<ScheduleState>(projectId, "schedule", normalizeSchedule);
  const { state, change, loaded } = store;
  const [tab, setTab] = useState<Tab>("plan");
  const [openId, setOpenId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const updateSettings = useCallback(
    (patch: Partial<ScheduleSettings>) => change((s) => ({ ...s, settings: { ...s.settings, ...patch } })),
    [change],
  );
  const updateMeeting = useCallback(
    (id: string, patch: Partial<Meeting>) =>
      change((s) => ({ ...s, meetings: s.meetings.map((m) => (m.id === id ? { ...m, ...patch } : m)) })),
    [change],
  );
  const removeMeeting = useCallback(
    (id: string) => {
      change((s) => ({ ...s, meetings: s.meetings.filter((m) => m.id !== id) }));
      setOpenId((cur) => (cur === id ? null : cur));
    },
    [change],
  );
  const addMeeting = useCallback(
    (patch: Partial<Meeting> = {}) => {
      const m = newMeeting({ title: "New meeting", ...patch }, state.settings);
      change((s) => ({ ...s, meetings: [...s.meetings, m] }));
      setOpenId(m.id);
    },
    [change, state.settings],
  );

  const suggest = async (): Promise<string> => {
    const context = await scheduleContext(projectId, client);
    const res = await assistSchedule(context, settingsPayload(state.settings), stubs(state.meetings));
    if (!res.meetings.length) return "Nothing new to add — every suggested meeting is already on the plan.";
    const added = res.meetings.map((m) => fromSuggestion(m, state.settings));
    change((s) => ({ ...s, meetings: [...s.meetings, ...added] }));
    return `Added ${added.length} suggested meeting${added.length === 1 ? "" : "s"} (${res.model}). Review them, then pick dates or use Auto-schedule.`;
  };

  const runAutoSchedule = () => {
    const { meetings, placed } = autoSchedule(state.meetings, state.settings);
    change((s) => ({ ...s, meetings }));
    setNotice(
      placed
        ? `Placed ${placed} meeting${placed === 1 ? "" : "s"} on the calendar as tentative. Move any of them, then confirm.`
        : "Every meeting already has a date.",
    );
  };

  const stats = useMemo(() => {
    const live = state.meetings.filter((m) => m.status !== "cancelled");
    return {
      total: live.length,
      unscheduled: live.filter((m) => !m.date && m.status !== "done").length,
      confirmed: live.filter((m) => m.status === "confirmed").length,
      done: live.filter((m) => m.status === "done").length,
    };
  }, [state.meetings]);

  const open = state.meetings.find((m) => m.id === openId) ?? null;

  return (
    <>
      <ProjectHeader
        eyebrow="STEP 5 / DELIVER"
        title="Schedule Planner"
        description="Plan the client meetings — what each one covers and when — then run them from the calendar."
        meta={
          stats.total > 0 && (
            <>
              <span className="status-chip">{stats.total} meetings</span>
              {stats.unscheduled > 0 && <span className="status-chip status-chip-warn">{stats.unscheduled} need a date</span>}
              {stats.done > 0 && <span className="status-chip status-chip-success">{stats.done} done</span>}
            </>
          )
        }
      />
      <div className="page-content">
        <SaveBanner store={store} />
        {!loaded ? (
          <div className="skeleton" style={{ height: 240 }} />
        ) : (
          <>
            <Tabs<Tab>
              tabs={[
                { id: "plan", label: "1 · Plan meetings" },
                { id: "calendar", label: `2 · Calendar${stats.total ? ` (${stats.total})` : ""}` },
              ]}
              active={tab}
              onChange={setTab}
              layoutId="schedule-tabs"
              variant="primary"
              label="Schedule Planner"
            />
            <TabPanel panelKey={tab} id="schedule-tabs">
              {tab === "plan" ? (
                <>
                  <PlanSetup settings={state.settings} onChange={updateSettings}>
                    <AssistButton label="Suggest meetings" variant="primary" run={suggest} />
                  </PlanSetup>
                  {notice && (
                    <Callout tone="success" title={notice} />
                  )}
                  <MeetingList
                    meetings={state.meetings}
                    settings={state.settings}
                    client={client}
                    onOpen={setOpenId}
                    onUpdate={updateMeeting}
                    onRemove={removeMeeting}
                    onAdd={() => addMeeting()}
                    onAutoSchedule={runAutoSchedule}
                    onConfirmAll={() =>
                      change((s) => ({
                        ...s,
                        meetings: s.meetings.map((m) => (m.date && m.status === "tentative" ? { ...m, status: "confirmed" } : m)),
                      }))
                    }
                    onShowCalendar={() => setTab("calendar")}
                  />
                </>
              ) : (
                <MonthCalendar
                  meetings={state.meetings}
                  settings={state.settings}
                  onOpen={setOpenId}
                  onUpdate={updateMeeting}
                  onAdd={(date) => addMeeting({ date })}
                  onAutoSchedule={runAutoSchedule}
                />
              )}
            </TabPanel>
          </>
        )}
      </div>
      <MeetingDrawer
        meeting={open}
        meetings={state.meetings}
        settings={state.settings}
        client={client}
        onClose={() => setOpenId(null)}
        onUpdate={updateMeeting}
        onRemove={removeMeeting}
        onNavigate={setOpenId}
        context={() => scheduleContext(projectId, client)}
      />
    </>
  );
}
