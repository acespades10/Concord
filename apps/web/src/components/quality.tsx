"use client";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  CheckCheck,
  CircleHelp,
  Layers,
  ShieldAlert,
  Users,
} from "lucide-react";
import { api, type Metrics, type Project } from "@/lib/api";
import { percent } from "@/lib/utils";
import { ErrorState, Loading } from "./auth";
import { Stat } from "./stat-card";

export function useLiveMetrics(projectId: string) {
  const client = useQueryClient();
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    const events = new EventSource(`/api/v1/projects/${projectId}/events`);
    events.onopen = () => setConnected(true);
    events.onerror = () => setConnected(false);
    events.addEventListener("revision", () => {
      void client.invalidateQueries({ queryKey: ["metrics", projectId] });
      void client.invalidateQueries({ queryKey: ["review", projectId] });
      void client.invalidateQueries({ queryKey: ["project", projectId] });
      void client.invalidateQueries({ queryKey: ["projects"] });
    });
    events.addEventListener("expired", () => {
      events.close();
      setConnected(false);
      void client.invalidateQueries({ queryKey: ["session"] });
    });
    return () => events.close();
  }, [client, projectId]);
  const query = useQuery({
    queryKey: ["metrics", projectId],
    queryFn: () => api<Metrics>(`/projects/${projectId}/metrics`),
    refetchInterval: connected ? false : 10000,
  });
  return { ...query, connected };
}

const explanations: Record<string, string> = {
  no_fully_rated_items: "Waiting for fully rated items",
  zero_expected_disagreement: "Undefined: only one effective category",
  no_shared_labels: "No shared labels yet",
};
export function QualityPanel({ project }: { project: Project }) {
  const query = useLiveMetrics(project.id);
  if (query.isPending) return <Loading label="Measuring agreement…" />;
  if (query.error) return <ErrorState error={query.error} />;
  const m = query.data,
    people = Object.entries(m.annotators),
    maximum = Math.max(...Object.values(m.distribution), 1);
  return (
    <>
      <div className="quality-heading">
        <span
          className={`live-indicator ${query.connected ? "connected" : ""}`}
        >
          <span />
          {query.connected
            ? "Live updates connected"
            : "Checking for updates every 10 seconds"}
        </span>
        <span className="muted">Revision {m.revision}</span>
      </div>
      <div className="stats-grid">
        <Stat
          label="Completion coverage"
          value={percent(m.coverage)}
          detail={`${m.submissions} of ${m.expected_submissions} annotations`}
          icon={<Layers size={18} />}
          tone="lavender"
        />
        <Stat
          label="Fleiss’ kappa"
          value={m.fleiss.value === null ? "—" : m.fleiss.value.toFixed(3)}
          detail={
            m.fleiss.reason
              ? explanations[m.fleiss.reason] || m.fleiss.reason
              : `${m.fleiss.n} complete ${project.mode === "ner" ? "tokens" : "items"}`
          }
          icon={<Activity size={18} />}
          tone="blue"
        />
        <Stat
          label="Resolved items"
          value={String(m.resolved)}
          detail={`${m.total_items} items in this project`}
          icon={<CheckCheck size={18} />}
          tone="sage"
        />
        <Stat
          label="Needs a human review"
          value={String(m.unresolved)}
          detail={`Automatic threshold: ${percent(project.review_threshold)}`}
          icon={<ShieldAlert size={18} />}
          tone="peach"
        />
      </div>
      <div className="quality-grid">
        <section className="panel">
          <div className="panel-title">
            <h2>Label distribution</h2>
            <span className="subtle-icon">
              <Layers size={17} />
            </span>
          </div>
          <p className="muted">
            {project.mode === "ner"
              ? "Entity spans across submitted annotations."
              : "Canonical labels across submitted annotations."}
          </p>
          <div className="distribution">
            {Object.entries(m.distribution).map(([label, count], index) => (
              <div className="distribution-row" key={label}>
                <div>
                  <span>{label}</span>
                  <strong>{count}</strong>
                </div>
                <div className="distribution-track">
                  <span
                    className={`chart-color-${index % 4}`}
                    style={{ width: percent(count / maximum) }}
                  />
                </div>
              </div>
            ))}
            {!Object.keys(m.distribution).length && (
              <p className="empty-small">
                Your first submission starts the story.
              </p>
            )}
          </div>
        </section>
        <section className="panel">
          <div className="panel-title">
            <h2>Pairwise agreement</h2>
            <Users size={17} />
          </div>
          <p className="muted">
            Cohen’s kappa ·{" "}
            {project.mode === "ner"
              ? "shared token BIO labels"
              : "shared categorical items"}
          </p>
          {people.length ? (
            <div className="table-scroll">
              <table className="matrix">
                <thead>
                  <tr>
                    <th scope="col">Annotator</th>
                    {people.map(([id, name]) => (
                      <th key={id} scope="col" title={name}>
                        {name.split(" ")[0]}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {people.map(([id, name]) => (
                    <tr key={id}>
                      <th scope="row">{name.split(" ")[0]}</th>
                      {people.map(([other]) => {
                        const pair = m.pairs.find(
                          (p) =>
                            (p.left === id && p.right === other) ||
                            (p.right === id && p.left === other),
                        );
                        return (
                          <td
                            key={other}
                            className={
                              id === other
                                ? "matrix-diagonal"
                                : pair?.kappa.value != null &&
                                    pair.kappa.value > 0.6
                                  ? "matrix-good"
                                  : "matrix-neutral"
                            }
                            title={
                              pair?.kappa.reason
                                ? explanations[pair.kappa.reason]
                                : `${pair?.shared_items || 0} shared items`
                            }
                          >
                            {id === other
                              ? "—"
                              : pair?.kappa.value == null
                                ? "N/A"
                                : pair.kappa.value.toFixed(2)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="empty-small">
              Pairwise scores appear after two annotators submit.
            </p>
          )}
          {project.mode === "ner" && (
            <div className="f1-list">
              {m.pairs.map((pair) => (
                <p key={`${pair.left}-${pair.right}`}>
                  <span>
                    {m.annotators[pair.left]?.split(" ")[0]} ×{" "}
                    {m.annotators[pair.right]?.split(" ")[0]}
                  </span>
                  <strong>
                    Span F1{" "}
                    {pair.span_f1 == null ? "N/A" : pair.span_f1.toFixed(3)}
                  </strong>
                </p>
              ))}
            </div>
          )}
        </section>
      </div>
      <div className="metric-note">
        <CircleHelp size={17} />
        <p>
          Kappa adjusts agreement for chance. A one-category dataset has an
          undefined kappa, even when every rater agrees.{" "}
          {project.mode === "ner"
            ? "NER uses BIO token labels for kappa and exact boundaries plus entity type for span F1."
            : "Fleiss’ kappa includes only items with all required raters; the configured scale uses unweighted categorical agreement."}
        </p>
      </div>
      <section className="panel item-agreement">
        <div className="panel-title">
          <h2>Item-level agreement</h2>
          <span className="count-pill">{m.total_items}</span>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Item</th>
                <th>Raters</th>
                <th>Vote share</th>
                <th>Resolution</th>
              </tr>
            </thead>
            <tbody>
              {m.items.map((item) => (
                <tr key={item.item_id}>
                  <td>
                    <code>{item.external_id}</code>
                  </td>
                  <td>
                    {item.submitted} / {project.target_raters}
                  </td>
                  <td>
                    {item.submitted < project.target_raters
                      ? "—"
                      : percent(item.vote_share)}
                  </td>
                  <td>
                    <span
                      className={`state-badge ${item.resolved ? "state-completed" : item.reason === "awaiting_raters" ? "state-draft" : "state-review"}`}
                    >
                      {item.adjudicated
                        ? "Adjudicated"
                        : item.resolved
                          ? "Consensus"
                          : item.reason === "awaiting_raters"
                            ? "Awaiting raters"
                            : "Needs review"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
