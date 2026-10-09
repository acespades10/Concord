"use client";
import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownUp,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  CircleCheck,
  FolderOpen,
  GitCompareArrows,
  Plus,
  Search,
  Shapes,
  Sparkles,
  Tag,
  Users,
} from "lucide-react";
import { api, type Project, type ProjectConfig } from "@/lib/api";
import { modeNames, percent } from "@/lib/utils";
import { ErrorState, Loading, useUser } from "@/components/auth";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ProjectForm } from "@/components/project-form";
import { useNotice } from "@/components/providers";
import { Stat } from "@/components/stat-card";

const modeIcons = { rating: Tag, ner: Shapes, ab: GitCompareArrows };
export default function ProjectsPage() {
  const user = useUser(),
    client = useQueryClient(),
    notice = useNotice();
  const [search, setSearch] = useState(""),
    [filter, setFilter] = useState("all"),
    [open, setOpen] = useState(false),
    [sort, setSort] = useState(false);
  const query = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Project[]>("/projects"),
  });
  const create = useMutation({
    mutationFn: (data: ProjectConfig) =>
      api<Project>("/projects", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => {
      setOpen(false);
      void client.invalidateQueries({ queryKey: ["projects"] });
      notice("Project created. Add your team and import items to get started.");
    },
    onError: (error) => notice(error.message, true),
  });
  if (query.isPending) return <Loading />;
  if (query.error)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  const projects = query.data,
    isAnnotator = user.role === "annotator";
  const total = projects.reduce((sum, p) => sum + p.item_count, 0),
    submitted = projects.reduce(
      (sum, p) =>
        sum + (isAnnotator ? p.my_submission_count : p.submission_count),
      0,
    ),
    expected = projects.reduce(
      (sum, p) => sum + p.item_count * (isAnnotator ? 1 : p.target_raters),
      0,
    );
  const visible = projects
    .filter(
      (p) =>
        (filter === "all" || p.state === filter) &&
        `${p.name} ${p.description}`
          .toLowerCase()
          .includes(search.toLowerCase()),
    )
    .sort((a, b) => (sort ? a.name.localeCompare(b.name) : 0));
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">A SHARED SPACE FOR BETTER DATA</div>
          <h1>
            Your workspace<span className="heading-dot">.</span>
          </h1>
          <p>A little human judgment. A meaningful difference.</p>
        </div>
        {user.role === "admin" && (
          <Button onClick={() => setOpen(true)}>
            <Plus size={17} />
            New project
          </Button>
        )}
      </div>
      <section className="hero-banner">
        <div>
          <span className="hero-kicker">
            <span className="status-dot" /> QUALITY IS A TEAM EFFORT
          </span>
          <h2>
            Great models start
            <br />
            with <em>good agreement.</em>
          </h2>
          <p>
            Bring your team’s judgment together.
            <br />
            Label thoughtfully, measure clearly, move forward.
          </p>
          <Link href={isAnnotator ? "#project-list" : "/quality"}>
            {" "}
            {isAnnotator
              ? "Find your next assignment"
              : "Explore your quality overview"}
            <ArrowUpRight size={16} />
          </Link>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="orbital orbital-a" />
          <div className="orbital orbital-b" />
          <div className="orbital orbital-c" />
          <span className="hero-star">✳</span>
          <div className="floating-tag tag-left">
            <span className="mini-avatar">S</span>Human insight
            <span className="small-check">
              <Check size={12} />
            </span>
          </div>
          <div className="agreement-tile">
            <div className="tile-mark">
              <span />
              <span />
              <span />
            </div>
            <strong>On the same page.</strong>
            <span>Better together, by design.</span>
            <div className="tile-avatars">
              <i>S</i>
              <i>T</i>
              <i>C</i>
              <span>+ you</span>
            </div>
          </div>
          <div className="floating-tag tag-right">
            <span className="small-check">
              <Check size={12} />
            </span>
            Every perspective counts
          </div>
          <span className="art-dot art-dot-one" />
          <span className="art-dot art-dot-two" />
        </div>
      </section>
      <section className="stats-grid" aria-label="Workspace statistics">
        <Stat
          label="Active projects"
          value={projects
            .filter((p) => p.state === "active")
            .length.toString()
            .padStart(2, "0")}
          detail={`${projects.length} projects in your workspace`}
          icon={<FolderOpen size={19} />}
          tone="lavender"
        />
        <Stat
          label="Items in the workspace"
          value={total.toLocaleString()}
          detail="Across all annotation modes"
          icon={<Tag size={19} />}
          tone="peach"
        />
        <Stat
          label={isAnnotator ? "Your annotations" : "Submitted annotations"}
          value={submitted.toLocaleString()}
          detail={`${expected.toLocaleString()} ${isAnnotator ? "possible items" : "annotations at target coverage"}`}
          icon={<Users size={19} />}
          tone="blue"
        />
        <Stat
          label={isAnnotator ? "Your progress" : "Completion coverage"}
          value={percent(expected ? submitted / expected : 0)}
          detail="One thoughtful label at a time"
          icon={<CircleCheck size={19} />}
          tone="sage"
        />
      </section>
      <section id="project-list">
        <div className="section-heading">
          <div>
            <h2>
              Your projects{" "}
              <span className="count-pill">{projects.length}</span>
            </h2>
            <p>Pick up where you left off, or start something new.</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setSort(!sort)}>
            <ArrowDownUp size={14} />
            {sort ? "Name A–Z" : "Date created"}
          </Button>
        </div>
        <div className="project-toolbar">
          <div className="filter-tabs" aria-label="Filter projects">
            {["all", "active", "draft", "completed", "archived"].map(
              (state) => (
                <button
                  key={state}
                  onClick={() => setFilter(state)}
                  aria-pressed={filter === state}
                  className={filter === state ? "selected" : ""}
                >
                  {state === "all"
                    ? "All projects"
                    : state[0].toUpperCase() + state.slice(1)}
                </button>
              ),
            )}
          </div>
          <label className="search-field">
            <Search size={16} />
            <input
              aria-label="Search projects"
              placeholder="Search projects…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
        </div>
        <div className="project-grid">
          {visible.map((project) => {
            const Icon = modeIcons[project.mode],
              progress =
                (isAnnotator
                  ? project.my_submission_count
                  : project.submission_count) /
                (project.item_count *
                  (isAnnotator ? 1 : project.target_raters) || 1);
            return (
              <Link
                key={project.id}
                href={`/projects/${project.id}`}
                className={`project-card mode-${project.mode}`}
              >
                <div className="card-top">
                  <span
                    className={`project-icon ${project.mode === "rating" ? "lavender" : project.mode === "ner" ? "peach" : "blue"}`}
                  >
                    <Icon size={22} />
                  </span>
                  <span className={`state-badge state-${project.state}`}>
                    <span />
                    {project.state}
                  </span>
                </div>
                <span className="card-mode">{modeNames[project.mode]}</span>
                <h3>
                  {project.name}
                  <ArrowUpRight size={18} />
                </h3>
                <p>{project.description}</p>
                <div className="card-progress-label">
                  <span>{project.item_count} items</span>
                  <strong>{percent(progress)} complete</strong>
                </div>
                <div className="progress-track">
                  <div style={{ width: percent(progress) }} />
                </div>
                <div className="card-bottom">
                  <span className="member-dots">
                    {Array.from(
                      { length: Math.min(project.member_count, 3) },
                      (_, i) => (
                        <i key={i} aria-hidden="true">
                          <Users size={10} />
                        </i>
                      ),
                    )}
                    <span>{project.member_count} annotators</span>
                  </span>
                  <ChevronRight size={17} />
                </div>
              </Link>
            );
          })}
        </div>
        {!visible.length && (
          <div className="empty-state">
            <FolderOpen size={30} />
            <h3>No projects here yet</h3>
            <p>
              {search
                ? "Try another search or filter."
                : "Create a project to bring your data and team together."}
            </p>
          </div>
        )}
      </section>
      <div className="workspace-tip">
        <span className="tip-icon">
          <Sparkles size={19} />
        </span>
        <div>
          <strong>A shared standard makes all the difference.</strong>
          <p>
            Clear guidelines help your team make consistent, confident
            decisions.
          </p>
        </div>
        <Link href="/guide">
          Read the field guide
          <ArrowRight size={16} />
        </Link>
      </div>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Make room for better data"
        description="Set up a project for your team. You can fine-tune it before activation."
      >
        <ProjectForm
          onSave={(data) => create.mutate(data)}
          pending={create.isPending}
        />
      </Dialog>
    </>
  );
}
