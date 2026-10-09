"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCheck, ChevronDown, ShieldCheck } from "lucide-react";
import { api, type Payload, type Project, type ReviewItem } from "@/lib/api";
import { percent } from "@/lib/utils";
import { ErrorState, Loading } from "./auth";
import { PayloadEditor, validPayload } from "./annotation-editor";
import { Button } from "./ui/button";
import { useNotice } from "./providers";

export function ReviewPanel({ project }: { project: Project }) {
  const [all, setAll] = useState(false);
  const query = useQuery({
    queryKey: ["review", project.id, all],
    queryFn: () =>
      api<ReviewItem[]>(`/projects/${project.id}/review?all_items=${all}`),
    refetchInterval: 10000,
  });
  return (
    <>
      <div className="section-heading">
        <div>
          <h2>A second look, a clearer answer.</h2>
          <p>Compare perspectives and record a reasoned final decision.</p>
        </div>
        <label className="check-label">
          <input
            type="checkbox"
            checked={all}
            onChange={(e) => setAll(e.target.checked)}
          />
          Show all items
        </label>
      </div>
      {query.isPending ? (
        <Loading label="Finding items to review…" />
      ) : query.error ? (
        <ErrorState error={query.error} />
      ) : query.data.length ? (
        <div className="review-list">
          {query.data.map((item) => (
            <ReviewCard key={item.item.id} project={project} entry={item} />
          ))}
        </div>
      ) : (
        <div className="empty-state panel">
          <CheckCheck size={36} />
          <h2>You’re on the same page.</h2>
          <p>No unresolved, fully rated items need review right now.</p>
        </div>
      )}
    </>
  );
}

function ReviewCard({
  project,
  entry,
}: {
  project: Project;
  entry: ReviewItem;
}) {
  const [open, setOpen] = useState(false),
    [payload, setPayload] = useState<Payload>(
      (entry.adjudication?.payload ||
        entry.agreement.payload ||
        entry.annotations[0]?.payload ||
        (project.mode === "ner"
          ? { spans: [] }
          : project.mode === "ab"
            ? { choice: "TIE", note: "" }
            : { label: "", note: "" })) as Payload,
    ),
    [rationale, setRationale] = useState(
      String(entry.adjudication?.rationale || ""),
    );
  const notice = useNotice(),
    client = useQueryClient();
  const save = useMutation({
    mutationFn: () =>
      api(`/projects/${project.id}/items/${entry.item.id}/adjudication`, {
        method: "PUT",
        body: JSON.stringify({ mode: project.mode, payload, rationale }),
      }),
    onSuccess: () => {
      notice(
        "Final decision saved. Metrics and consensus exports are updated.",
      );
      void client.invalidateQueries({ queryKey: ["review", project.id] });
      void client.invalidateQueries({ queryKey: ["metrics", project.id] });
    },
    onError: (error) => notice(error.message, true),
  });
  return (
    <article className="review-card panel">
      <button
        className="review-card-toggle"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <div>
          <code>{entry.item.external_id}</code>
          <p>{entry.item.content.prompt || entry.item.content.text}</p>
        </div>
        <span
          className={`state-badge ${entry.agreement.resolved ? "state-completed" : "state-review"}`}
        >
          {entry.agreement.resolved
            ? "Resolved"
            : `${percent(entry.agreement.vote_share)} agreement`}
        </span>
        <ChevronDown size={18} className={open ? "rotated" : ""} />
      </button>
      {open && (
        <div className="review-card-body">
          <div className="submission-comparison">
            {entry.annotations.map((annotation, i) => (
              <section key={i}>
                <span className="eyebrow">{annotation.annotator}</span>
                {"spans" in annotation.payload ? (
                  <ul>
                    {(
                      annotation.payload.spans as {
                        text: string;
                        label: string;
                      }[]
                    ).map((span, n) => (
                      <li key={n}>
                        <strong>{span.text}</strong>{" "}
                        <span className="muted">{span.label}</span>
                      </li>
                    ))}
                    {!(annotation.payload.spans as unknown[]).length && (
                      <li>No entities</li>
                    )}
                  </ul>
                ) : (
                  <>
                    <strong className="vote-label">
                      {String(
                        annotation.payload.label || annotation.payload.choice,
                      )}
                    </strong>
                    <p>{String(annotation.payload.note || "No note added.")}</p>
                  </>
                )}
              </section>
            ))}
          </div>
          {entry.agreement.submitted < project.target_raters ? (
            <p className="metric-note">
              Waiting for all required raters before adjudication.
            </p>
          ) : (
            <>
              <h3 className="decision-title">
                <ShieldCheck size={19} />
                Your final decision
              </h3>
              <PayloadEditor
                project={project}
                item={entry.item}
                payload={payload}
                onChange={setPayload}
                disabled={save.isPending || project.state === "archived"}
                canonical
              />
              <label className="note-field">
                Rationale
                <textarea
                  minLength={3}
                  maxLength={4000}
                  rows={3}
                  value={rationale}
                  onChange={(e) => setRationale(e.target.value)}
                  placeholder="Explain how you resolved the disagreement…"
                />
              </label>
              {entry.adjudication && (
                <p className="muted">
                  Previously reviewed by {String(entry.adjudication.reviewer)}.
                </p>
              )}
              <Button
                disabled={
                  save.isPending ||
                  rationale.trim().length < 3 ||
                  !validPayload(payload) ||
                  project.state === "archived"
                }
                onClick={() => save.mutate()}
              >
                {save.isPending ? "Saving…" : "Save final decision"}
                <CheckCheck size={16} />
              </Button>
            </>
          )}
        </div>
      )}
    </article>
  );
}
