"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Project } from "@/lib/api";
import { ErrorState, Loading, RoleGate, useUser } from "@/components/auth";
import { QualityPanel } from "@/components/quality";

export default function QualityPage() {
  const user = useUser(),
    [selected, setSelected] = useState("");
  const query = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Project[]>("/projects"),
    enabled: user.role !== "annotator",
  });
  const project = query.data?.find((p) => p.id === selected) || query.data?.[0];
  return (
    <RoleGate roles={["admin", "reviewer"]}>
      <div className="page-heading">
        <div>
          <span className="eyebrow">CONFIDENCE, WITH THE NUMBERS TO MATCH</span>
          <h1>
            Quality overview<span className="heading-dot">.</span>
          </h1>
          <p>See where perspectives align, and where a closer look can help.</p>
        </div>
      </div>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} />
      ) : project ? (
        <>
          <label className="project-select">
            Project
            <select
              value={project.id}
              onChange={(e) => setSelected(e.target.value)}
            >
              {query.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <QualityPanel key={project.id} project={project} />
        </>
      ) : (
        <div className="empty-state">
          Create your first project to start measuring agreement.
        </div>
      )}
    </RoleGate>
  );
}
