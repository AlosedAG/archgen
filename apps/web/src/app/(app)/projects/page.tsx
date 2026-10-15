"use client";

/**
 * The workspace's client projects: search and filter them, grouped by
 * folder; see who is in charge and who last edited each one; create, edit
 * (name, client, folder, person in charge) or delete them.
 */

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useAppSession } from "@/components/AppSession";
import { PageHeader } from "@/components/PageHeader";
import { Glyph } from "@/components/icons";
import { fadeInUp, lift, springs, tween, useStagger } from "@/lib/motion";
import { Callout } from "@/components/ui";
import { ApiError, createProject, deleteProject, listMembers, listProjects, updateProject, type Member, type Project } from "@/lib/api";

const NO_FOLDER = "\u0000none";

function when(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 24 * 60) return `${Math.round(minutes / 60)} h ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function initials(name: string): string {
  return name
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

function FolderInput({ value, onChange, folders, id }: { value: string; onChange: (v: string) => void; folders: string[]; id: string }) {
  return (
    <>
      <input className="input" list={id} placeholder="No folder" value={value} onChange={(e) => onChange(e.target.value)} />
      <datalist id={id}>
        {folders.map((f) => (
          <option key={f} value={f} />
        ))}
      </datalist>
    </>
  );
}

/** A folder's heading; a real folder can be renamed, which moves every project in it (archived ones too). */
function FolderHeading({ name, count, onRenamed }: { name: string; count: number; onRenamed: (from: string, to: string) => Promise<void> }) {
  const [draft, setDraft] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (draft !== null) {
    const next = draft.trim();
    return (
      <div className="stack" style={{ gap: 8 }}>
        <form
          className="folder-rename"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!next || next === name) return setDraft(null);
            setBusy(true);
            setError(null);
            try {
              await onRenamed(name, next);
              setDraft(null);
            } catch (err) {
              setError(err instanceof ApiError ? err.message : "Couldn't rename the folder.");
            }
            setBusy(false);
          }}
        >
          <Glyph name="folder" size={18} />
          <input className="input" aria-label="Folder name" autoFocus value={draft} maxLength={120} onChange={(e) => setDraft(e.target.value)} />
          <button type="submit" className="btn btn-primary" disabled={busy || !next}>
            {busy ? "Saving…" : "Rename"}
          </button>
          <button type="button" className="btn-link" disabled={busy} onClick={() => setDraft(null)}>
            Cancel
          </button>
        </form>
        {error && <Callout tone="error" title="That didn't work">{error}</Callout>}
      </div>
    );
  }
  return (
    <h2 className="folder-heading">
      <Glyph name={name ? "folder" : "file"} size={18} />
      {name || "No folder"} <span className="t-caption">({count})</span>
      {name && (
        <button type="button" className="icon-btn" aria-label={`Rename folder ${name}`} title="Rename folder" onClick={() => setDraft(name)}>
          <Glyph name="pencil" size={14} />
        </button>
      )}
    </h2>
  );
}

/** A folder's cards, rising in one after another when the list loads. */
function ProjectGrid({ count, children }: { count: number; children: React.ReactNode }) {
  return (
    <motion.div className="project-grid" variants={useStagger(count)} initial="hidden" animate="visible">
      {children}
    </motion.div>
  );
}

function ProjectCard({
  project,
  members,
  folders,
  onChanged,
  onDeleted,
}: {
  project: Project;
  members: Member[];
  folders: string[];
  onChanged: (p: Project) => void;
  onDeleted: (id: string) => void;
}) {
  const [mode, setMode] = useState<"view" | "edit" | "delete">("view");
  const [draft, setDraft] = useState({ name: "", client_name: "", folder: "", lead_user_id: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = () => {
    setDraft({ name: project.name, client_name: project.client_name, folder: project.folder ?? "", lead_user_id: project.lead?.id ?? "" });
    setError(null);
    setMode("edit");
  };

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      onChanged(
        await updateProject(project.id, {
          name: draft.name.trim(),
          client_name: draft.client_name.trim(),
          folder: draft.folder.trim(),
          lead_user_id: draft.lead_user_id || null,
        }),
      );
      setMode("view");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save the changes.");
    }
    setBusy(false);
  };

  const remove = async () => {
    setBusy(true);
    setError(null);
    try {
      await deleteProject(project.id);
      onDeleted(project.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't delete the project.");
      setBusy(false);
    }
  };

  const title = project.client_name || project.name;
  return (
    <motion.div
      layout
      className="project-card"
      variants={fadeInUp}
      exit={{ opacity: 0, scale: 0.98, transition: tween.fast }}
      whileHover={mode === "view" ? lift : undefined}
      transition={{ layout: springs.snappy }}
    >
      {mode === "edit" ? (
        <form
          className="stack"
          style={{ gap: 10 }}
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <label className="field">
            <span className="field-label">Project name</span>
            <input className="input" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} required />
          </label>
          <label className="field">
            <span className="field-label">Client name</span>
            <input className="input" value={draft.client_name} onChange={(e) => setDraft({ ...draft, client_name: e.target.value })} />
          </label>
          <label className="field">
            <span className="field-label">Folder</span>
            <FolderInput id={`folders-${project.id}`} value={draft.folder} onChange={(v) => setDraft({ ...draft, folder: v })} folders={folders} />
          </label>
          <label className="field">
            <span className="field-label">Person in charge</span>
            <select className="input" value={draft.lead_user_id} onChange={(e) => setDraft({ ...draft, lead_user_id: e.target.value })}>
              <option value="">Nobody yet</option>
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </label>
          <div className="row">
            <button type="submit" className="btn btn-primary" disabled={busy || !draft.name.trim()}>
              {busy ? "Saving…" : "Save"}
            </button>
            <button type="button" className="btn-link" onClick={() => setMode("view")} disabled={busy}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <>
          <Link href={`/projects/${project.id}/discovery`} className="project-card-link">
            <span className="project-card-name">{title}</span>
            {project.client_name && project.client_name !== project.name && <span className="t-description">{project.name}</span>}
            <span className="t-caption">
              {project.document_count ?? 0} saved document{project.document_count === 1 ? "" : "s"}
            </span>
          </Link>
          <div className="project-people">
            <span className="person-chip" title={project.lead ? `${project.lead.name} <${project.lead.email}>` : "Nobody is in charge yet"}>
              <span className="avatar" aria-hidden>
                {project.lead ? initials(project.lead.name) : "?"}
              </span>
              <span>
                <span className="person-chip-label">In charge</span>
                {project.lead?.name ?? "Nobody yet"}
              </span>
            </span>
            <span className="t-caption" title={new Date(project.updated_at).toLocaleString()}>
              Last edited {when(project.updated_at)}
              {project.last_edited_by ? ` by ${project.last_edited_by.name}` : ""}
            </span>
          </div>
          {mode === "delete" ? (
            <div className="project-confirm" role="alert">
              <span>
                Delete <b>{title}</b>
                {project.document_count ? ` and its ${project.document_count} saved document${project.document_count === 1 ? "" : "s"}` : ""}? This can&apos;t be undone.
              </span>
              <div className="row">
                <button type="button" className="btn btn-danger" disabled={busy} onClick={() => void remove()}>
                  {busy ? "Deleting…" : "Delete project"}
                </button>
                <button type="button" className="btn-link" disabled={busy} onClick={() => setMode("view")}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="project-actions">
              <button type="button" className="btn-link" onClick={startEdit}>
                Edit
              </button>
              {project.can_delete && (
                <button type="button" className="btn-link btn-link-danger" onClick={() => setMode("delete")}>
                  Delete
                </button>
              )}
            </div>
          )}
        </>
      )}
      {error && (
        <Callout tone="error" title="That didn't work">
          {error}
        </Callout>
      )}
    </motion.div>
  );
}

export default function ProjectsPage() {
  const router = useRouter();
  const { me, setProject } = useAppSession();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [name, setName] = useState("");
  const [folder, setFolder] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [folderFilter, setFolderFilter] = useState("");
  const [leadFilter, setLeadFilter] = useState("");

  useEffect(() => {
    setProject(null);
    listProjects()
      .then(setProjects)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Couldn't load projects."));
    listMembers()
      .then(setMembers)
      .catch(() => undefined);
  }, [setProject]);

  const folders = useMemo(
    () => [...new Set((projects ?? []).map((p) => p.folder ?? "").filter(Boolean))].sort((a, b) => a.localeCompare(b)),
    [projects],
  );

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (projects ?? []).filter((p) => {
      if (folderFilter === NO_FOLDER ? p.folder : folderFilter && p.folder !== folderFilter) return false;
      if (leadFilter && (p.lead?.id ?? "") !== leadFilter) return false;
      if (!q) return true;
      return [p.name, p.client_name, p.folder, p.lead?.name, p.last_edited_by?.name].some((v) => (v ?? "").toLowerCase().includes(q));
    });
  }, [projects, query, folderFilter, leadFilter]);

  // Grouped by folder (alphabetical), projects without a folder last.
  const groups = useMemo(() => {
    const map = new Map<string, Project[]>();
    for (const p of visible) map.set(p.folder ?? "", [...(map.get(p.folder ?? "") ?? []), p]);
    return [...map.entries()].sort(([a], [b]) => (a === "" ? 1 : b === "" ? -1 : a.localeCompare(b)));
  }, [visible]);

  const renameFolder = async (from: string, to: string) => {
    const inFolder = (await listProjects(true)).filter((p) => p.folder === from);
    const updated = await Promise.all(inFolder.map((p) => updateProject(p.id, { folder: to })));
    const byId = new Map(updated.map((p) => [p.id, p]));
    setProjects((list) => (list ?? []).map((p) => byId.get(p.id) ?? p));
    if (folderFilter === from) setFolderFilter(to);
  };

  const replace = (updated: Project) => setProjects((list) => (list ?? []).map((p) => (p.id === updated.id ? updated : p)));
  const filtered = Boolean(query.trim() || folderFilter || leadFilter);

  return (
    <>
      <PageHeader
        eyebrow="WORKSPACE / PROJECTS"
        breadcrumb={`${me.workspace_name}  /  ${me.name || me.email}`}
        title="Projects"
      />
      <div className="page-content">
        <form
          className="inline-form"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!name.trim()) return;
            setBusy(true);
            setError(null);
            try {
              const project = await createProject(name.trim(), { folder: folder.trim() });
              router.push(`/projects/${project.id}/discovery`);
            } catch (err) {
              setError(err instanceof ApiError ? err.message : "Couldn't create the project.");
              setBusy(false);
            }
          }}
        >
          <label className="field">
            <span className="field-label">New client / project</span>
            <input className="input" placeholder="e.g. Bright Smiles" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field" style={{ maxWidth: 260 }}>
            <span className="field-label">Folder (optional)</span>
            <FolderInput id="folders-new" value={folder} onChange={setFolder} folders={folders} />
          </label>
          <button type="submit" className="btn btn-primary" disabled={busy || !name.trim()}>
            {busy ? "Creating…" : "Create project"}
          </button>
        </form>
        {error && <Callout tone="error" title="Something went wrong">{error}</Callout>}

        {projects && projects.length > 0 && (
          <div className="project-toolbar" role="search">
            <input
              className="input"
              type="search"
              placeholder="Search projects, clients, folders or people…"
              aria-label="Search projects"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <select className="input" aria-label="Filter by folder" value={folderFilter} onChange={(e) => setFolderFilter(e.target.value)}>
              <option value="">All folders</option>
              {folders.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
              <option value={NO_FOLDER}>No folder</option>
            </select>
            <select className="input" aria-label="Filter by person in charge" value={leadFilter} onChange={(e) => setLeadFilter(e.target.value)}>
              <option value="">Anyone in charge</option>
              <option value={me.user_id}>Me</option>
              {members
                .filter((m) => m.id !== me.user_id)
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
            </select>
            {filtered && (
              <button
                type="button"
                className="btn-link"
                onClick={() => {
                  setQuery("");
                  setFolderFilter("");
                  setLeadFilter("");
                }}
              >
                Clear filters
              </button>
            )}
          </div>
        )}

        {projects === null ? (
          <div className="project-grid" aria-busy="true">
            <div className="skeleton" style={{ height: 150 }} />
            <div className="skeleton" style={{ height: 150 }} />
            <div className="skeleton" style={{ height: 150 }} />
          </div>
        ) : projects.length === 0 ? (
          <Callout tone="info" title="No projects yet">
            Create your first client project above to start a discovery call.
          </Callout>
        ) : visible.length === 0 ? (
          <Callout tone="info" title="No projects match">
            Try another search or clear the filters.
          </Callout>
        ) : (
          groups.map(([group, items]) => (
            <section key={group || "none"} className="stack" style={{ gap: 12 }}>
              {(folders.length > 0 || group) && (
                <FolderHeading name={group} count={items.length} onRenamed={renameFolder} />
              )}
              <ProjectGrid count={items.length}>
                <AnimatePresence>
                  {items.map((p) => (
                    <ProjectCard
                      key={p.id}
                      project={p}
                      members={members}
                      folders={folders}
                      onChanged={replace}
                      onDeleted={(id) => setProjects((list) => (list ?? []).filter((x) => x.id !== id))}
                    />
                  ))}
                </AnimatePresence>
              </ProjectGrid>
            </section>
          ))
        )}
      </div>
    </>
  );
}
