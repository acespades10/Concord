"use client";
import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  CheckCheck,
  Clock3,
  FileCheck2,
  ShieldCheck,
} from "lucide-react";
import { api, type Assignment, type Project } from "@/lib/api";
import { modeNames } from "@/lib/utils";
import { ErrorState, Loading, useUser } from "@/components/auth";
import { Button } from "@/components/ui/button";
import { AnnotationEditor } from "@/components/annotation-editor";
import { QualityPanel } from "@/components/quality";
import { ReviewPanel } from "@/components/review-panel";
import { ExportPanel } from "@/components/export-panel";
import { SettingsPanel } from "@/components/settings-panel";
import { useNotice } from "@/components/providers";

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>(),
    user = useUser();
  const [tab, setTab] = useState(
    user.role === "annotator" ? "annotate" : "quality",
  );
  const query = useQuery({
    queryKey: ["project", id],
    queryFn: () => api<Project>(`/projects/${id}`),
  });
  if (query.isPending) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const project = query.data,
    tabs =
      user.role === "annotator"
        ? [["annotate", "Annotate"]]
        : [
            ["quality", "Quality & agreement"],
            ["review", "Review queue"],
            ["exports", "Export dataset"],
            ...(user.role === "admin" ? [["settings", "Project setup"]] : []),
          ];
  return (
    <>
      <Link className="back-link" href="/projects">
        <ArrowLeft size={15} />
        All projects
      </Link>
      <div className="page-heading project-page-heading">
        <div>
          <div className="eyebrow">{modeNames[project.mode].toUpperCase()}</div>
          <h1>{project.name}</h1>
          <p>{project.description}</p>
        </div>
        <span className={`state-badge state-${project.state}`}>
          <span />
          {project.state}
        </span>
      </div>
      <div className="project-meta">
        <span>
          <FileCheck2 size={15} />
          {project.item_count} items
        </span>
        <span>
          <ShieldCheck size={15} />
          {project.target_raters} raters per item
        </span>
        <span>
          <Clock3 size={15} />
          15-minute renewable claims
        </span>
      </div>
      <div className="detail-tabs" role="tablist" aria-label="Project sections">
        {tabs.map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            aria-controls={`panel-${id}`}
            id={`tab-${id}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "annotate" && user.role === "annotator" && (
          <WorkQueue project={project} />
        )}
        {tab === "quality" && user.role !== "annotator" && (
          <QualityPanel project={project} />
        )}
        {tab === "review" && user.role !== "annotator" && (
          <ReviewPanel project={project} />
        )}
        {tab === "exports" && user.role !== "annotator" && (
          <ExportPanel project={project} />
        )}
        {tab === "settings" && user.role === "admin" && (
          <SettingsPanel project={project} />
        )}
      </div>
    </>
  );
}

function WorkQueue({ project }: { project: Project }) {
  const client = useQueryClient(),
    notice = useNotice();
  const [started, setStarted] = useState(false);
  const query = useQuery({
    queryKey: ["assignment", project.id],
    queryFn: () =>
      api<Assignment | null>(`/projects/${project.id}/assignments/current`),
    staleTime: 0,
    refetchOnWindowFocus: false,
  });
  const next = useMutation({
    mutationFn: () =>
      api<Assignment | null>(`/projects/${project.id}/assignments/next`, {
        method: "POST",
      }),
    onSuccess: (assignment) => {
      setStarted(true);
      client.setQueryData(["assignment", project.id], assignment);
      void client.invalidateQueries({ queryKey: ["project", project.id] });
      void client.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (e) => notice(e.message, true),
  });
  async function resetSkipped() {
    try {
      await api(`/projects/${project.id}/assignments/reset-skipped`, {
        method: "POST",
      });
      next.mutate();
    } catch (error) {
      notice((error as Error).message, true);
    }
  }
  if (project.state !== "active")
    return (
      <div className="empty-state panel">
        <CheckCheck size={32} />
        <h2>This queue is {project.state}.</h2>
        <p>Annotation opens when an administrator activates the project.</p>
      </div>
    );
  if (query.isPending || query.isFetching || next.isPending)
    return <Loading label="Finding your next item…" />;
  if (query.error)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  return query.data ? (
    <AnnotationEditor
      key={`${query.data.id}-${query.data.expires_at}`}
      project={project}
      assignment={query.data}
      onDone={() => next.mutate()}
    />
  ) : (
    <div className="empty-state panel">
      <span className="empty-illustration">
        <CheckCheck size={38} />
      </span>
      <h2>
        {started ? "You’re all caught up." : "A fresh perspective starts here."}
      </h2>
      <p>
        {started
          ? "No items are available for you right now. Other claims may still be in progress."
          : "You’ll receive one item at a time. Your drafts save as you work."}
      </p>
      <div className="button-row">
        <Button disabled={next.isPending} onClick={() => next.mutate()}>
          {started ? "Check for more work" : "Start annotating"}
          <ArrowRight size={16} />
        </Button>
        {started && (
          <Button variant="outline" onClick={() => void resetSkipped()}>
            Revisit skipped items
          </Button>
        )}
      </div>
    </div>
  );
}
