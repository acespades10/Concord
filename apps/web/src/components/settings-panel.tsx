"use client";
import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleCheck, FileUp, LockKeyhole, Play, Users } from "lucide-react";
import { api, type Project, type ProjectConfig, type User } from "@/lib/api";
import { ProjectForm } from "./project-form";
import { Button } from "./ui/button";
import { useNotice } from "./providers";
import { Dialog } from "./ui/dialog";

export function SettingsPanel({ project }: { project: Project }) {
  const client = useQueryClient(),
    notice = useNotice();
  const [importing, setImporting] = useState(false),
    [importError, setImportError] = useState(""),
    [archiveOpen, setArchiveOpen] = useState(false);
  const users = useQuery({
    queryKey: ["users"],
    queryFn: () => api<User[]>("/users"),
  });
  const members = useQuery({
    queryKey: ["members", project.id],
    queryFn: () => api<User[]>(`/projects/${project.id}/members`),
  });
  function refresh() {
    void client.invalidateQueries({ queryKey: ["project", project.id] });
    void client.invalidateQueries({ queryKey: ["projects"] });
    void client.invalidateQueries({ queryKey: ["members", project.id] });
  }
  const config = useMutation({
    mutationFn: (body: ProjectConfig) =>
      api(`/projects/${project.id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      notice("Configuration saved.");
      refresh();
    },
    onError: (e) => notice(e.message, true),
  });
  const state = useMutation({
    mutationFn: (state: string) =>
      api(`/projects/${project.id}/state`, {
        method: "POST",
        body: JSON.stringify({ state }),
      }),
    onSuccess: () => {
      setArchiveOpen(false);
      notice("Project state updated.");
      refresh();
    },
    onError: (e) => notice(e.message, true),
  });
  const membership = useMutation({
    mutationFn: (user_ids: string[]) =>
      api(`/projects/${project.id}/members`, {
        method: "PUT",
        body: JSON.stringify({ user_ids }),
      }),
    onSuccess: () => {
      notice("Team updated.");
      refresh();
    },
    onError: (e) => notice(e.message, true),
  });
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setImporting(true);
    setImportError("");
    try {
      const result = await api<{ imported: number }>(
        `/projects/${project.id}/imports`,
        { method: "POST", body: data },
      );
      notice(`${result.imported} items imported successfully.`);
      refresh();
    } catch (error) {
      setImportError((error as Error).message);
    } finally {
      setImporting(false);
    }
  }
  return (
    <div className="settings-grid">
      <section className="panel">
        <div className="panel-title">
          <h2>Project configuration</h2>
          {project.state !== "draft" && <LockKeyhole size={17} />}
        </div>
        {project.state === "draft" ? (
          <ProjectForm
            initial={project}
            onSave={(data) => config.mutate(data)}
            pending={config.isPending}
          />
        ) : (
          <>
            <p className="muted">
              Configuration was locked when this project was activated.
            </p>
            <dl className="config-list">
              <div>
                <dt>Mode</dt>
                <dd>{project.mode.toUpperCase()}</dd>
              </div>
              <div>
                <dt>Labels</dt>
                <dd>{project.labels.join(", ") || "A, B, TIE"}</dd>
              </div>
              <div>
                <dt>Raters per item</dt>
                <dd>{project.target_raters}</dd>
              </div>
              <div>
                <dt>Consensus threshold</dt>
                <dd>{Math.round(project.review_threshold * 100)}%</dd>
              </div>
            </dl>
          </>
        )}
      </section>
      <div className="settings-stack">
        <section className="panel">
          <div className="panel-title">
            <h2>Your annotation team</h2>
            <Users size={18} />
          </div>
          <p className="muted">
            Add at least {project.target_raters} annotators before activation.
          </p>
          {users.error || members.error ? (
            <p role="alert">Could not load the team. Reload to try again.</p>
          ) : !users.data || !members.data ? (
            <p role="status">Loading team…</p>
          ) : (
            <form
              key={members.data
                .map((m) => m.id)
                .sort()
                .join()}
              onSubmit={(event) => {
                event.preventDefault();
                membership.mutate(
                  new FormData(event.currentTarget)
                    .getAll("member")
                    .map(String),
                );
              }}
            >
              <fieldset
                disabled={
                  membership.isPending ||
                  ["completed", "archived"].includes(project.state)
                }
                className="member-list"
              >
                <legend className="sr-only">Project members</legend>
                {users.data
                  .filter((u) => u.role === "annotator")
                  .map((user) => (
                    <label className="member-option" key={user.id}>
                      <input
                        name="member"
                        value={user.id}
                        type="checkbox"
                        defaultChecked={members.data?.some(
                          (m) => m.id === user.id,
                        )}
                      />
                      <span className="avatar avatar-small">
                        {user.name[0]}
                      </span>
                      <span>
                        {user.name}
                        <small>{user.email}</small>
                      </span>
                    </label>
                  ))}
                <Button
                  variant="outline"
                  type="submit"
                  disabled={membership.isPending}
                >
                  Save team
                </Button>
              </fieldset>
            </form>
          )}
        </section>
        {project.state === "draft" && (
          <section className="panel">
            <div className="panel-title">
              <h2>Bring your data</h2>
              <FileUp size={18} />
            </div>
            <p className="muted">
              UTF-8 JSONL or CSV · up to 10 MiB / 10,000 rows. Imports are
              atomic.
            </p>
            <p className="form-hint">
              Required fields:{" "}
              <code>
                external_id,{" "}
                {project.mode === "rating"
                  ? "prompt, response"
                  : project.mode === "ner"
                    ? "text"
                    : "prompt, response_a, response_b"}
              </code>
              . Extra fields become metadata.
            </p>
            <form onSubmit={upload} className="upload-form">
              <label>
                Dataset file
                <input type="file" name="file" accept=".jsonl,.csv" required />
              </label>
              {importError && (
                <pre className="form-error import-error" role="alert">
                  {importError}
                </pre>
              )}
              <Button type="submit" variant="outline" disabled={importing}>
                <FileUp size={16} />
                {importing ? "Validating…" : "Validate & import"}
              </Button>
            </form>
          </section>
        )}
        <section className="panel">
          <div className="panel-title">
            <h2>Project lifecycle</h2>
            <span className={`state-badge state-${project.state}`}>
              {project.state}
            </span>
          </div>
          <p className="muted">
            {project.state === "draft"
              ? "Ready to begin? Activation locks the annotation rules and opens the queue."
              : project.state === "active"
                ? "Complete the project when every item reaches its target. Review and export remain available."
                : project.state === "completed"
                  ? "All annotation work is complete. You can still resolve disagreements and export."
                  : "This project is archived. You can browse quality reports and export its data."}
          </p>
          <div className="button-row">
            {project.state === "draft" && (
              <Button
                disabled={state.isPending}
                onClick={() => state.mutate("active")}
              >
                <Play size={16} />
                Activate project
              </Button>
            )}
            {project.state === "active" && (
              <Button
                disabled={state.isPending}
                onClick={() => state.mutate("completed")}
              >
                <CircleCheck size={16} />
                Mark completed
              </Button>
            )}
            {project.state !== "archived" && (
              <Button variant="ghost" onClick={() => setArchiveOpen(true)}>
                Archive
              </Button>
            )}
          </div>
        </section>
      </div>
      <Dialog
        open={archiveOpen}
        onOpenChange={setArchiveOpen}
        title="Archive this project?"
        description="Archiving permanently closes annotation and adjudication. Reports and exports stay available."
      >
        <div className="button-row">
          <Button variant="outline" onClick={() => setArchiveOpen(false)}>
            Keep project
          </Button>
          <Button
            variant="danger"
            disabled={state.isPending}
            onClick={() => state.mutate("archived")}
          >
            Archive project
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
