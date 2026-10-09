"use client";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  CircleCheck,
  Clock3,
  Save,
  SkipForward,
  X,
} from "lucide-react";
import {
  api,
  type Assignment,
  type Payload,
  type Project,
  type SaveResult,
  type Span,
} from "@/lib/api";
import { Button } from "./ui/button";
import { useNotice } from "./providers";

function emptyPayload(mode: Project["mode"]): Payload {
  return mode === "rating"
    ? { label: "", note: "" }
    : mode === "ab"
      ? { choice: "TIE", note: "" }
      : { spans: [] };
}
export function validPayload(payload: Payload) {
  return !("label" in payload) || Boolean(payload.label);
}

export function NerEditor({
  text,
  tokens,
  labels,
  spans,
  onChange,
  disabled = false,
}: {
  text: string;
  tokens: Assignment["item"]["tokens"];
  labels: string[];
  spans: Span[];
  onChange: (spans: Span[]) => void;
  disabled?: boolean;
}) {
  const [entity, setEntity] = useState(labels[0]),
    [anchor, setAnchor] = useState<number | null>(null),
    [error, setError] = useState("");
  function choose(index: number) {
    if (anchor === null) {
      setAnchor(index);
      setError("");
      return;
    }
    const start = tokens[Math.min(anchor, index)].start,
      end = tokens[Math.max(anchor, index)].end;
    if (spans.some((s) => start < s.end && end > s.start)) {
      setError(
        "This selection overlaps an existing entity. Remove that entity first.",
      );
      setAnchor(null);
      return;
    }
    onChange(
      [
        ...spans,
        {
          start,
          end,
          label: entity,
          text: Array.from(text).slice(start, end).join(""),
        },
      ].sort((a, b) => a.start - b.start),
    );
    setAnchor(null);
  }
  return (
    <div className="ner-editor">
      <div className="entity-types" role="group" aria-label="Entity type">
        {labels.map((label, i) => (
          <button
            disabled={disabled}
            className={`entity-chip entity-color-${i % 5} ${entity === label ? "selected" : ""}`}
            aria-pressed={entity === label}
            key={label}
            onClick={() => setEntity(label)}
          >
            <span />
            {label}
          </button>
        ))}
      </div>
      <p className="form-hint">
        Choose a type, then select the first and last token. Select a token
        twice for a single-token entity. All offsets use Unicode code points.
      </p>
      <div className="token-canvas" role="group" aria-label="Text tokens">
        {tokens.map((token, index) => {
          const span = spans.find(
            (s) => token.start >= s.start && token.end <= s.end,
          );
          const gap = Array.from(text)
            .slice(index ? tokens[index - 1].end : 0, token.start)
            .join("");
          return (
            <span key={`${token.start}-${token.end}`}>
              {gap}
              <button
                type="button"
                disabled={disabled}
                aria-label={`${token.text}, token ${index + 1}${span ? `, ${span.label}` : ""}`}
                aria-pressed={anchor === index}
                className={`token ${anchor === index ? "token-anchor" : ""} ${span ? `entity-color-${labels.indexOf(span.label) % 5} token-marked` : ""}`}
                onClick={() => choose(index)}
              >
                {token.text}
                {span && token.start === span.start && (
                  <small>{span.label}</small>
                )}
              </button>
            </span>
          );
        })}
      </div>
      {anchor !== null && (
        <div className="selection-hint" role="status">
          Select the last token to complete the entity.
          <Button variant="ghost" size="sm" onClick={() => setAnchor(null)}>
            Cancel selection
          </Button>
        </div>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="span-list">
        <span className="eyebrow">{spans.length} ENTITIES MARKED</span>
        {spans.length === 0 && (
          <p className="muted">
            No entities yet. An empty annotation is valid when no entities are
            present.
          </p>
        )}
        {spans.map((span, i) => (
          <div className="span-row" key={`${span.start}-${span.end}`}>
            <span
              className={`entity-chip entity-color-${labels.indexOf(span.label) % 5}`}
            >
              {span.label}
            </span>
            <strong>{span.text}</strong>
            <code>
              {span.start}–{span.end}
            </code>
            <button
              type="button"
              className="icon-button"
              aria-label={`Remove ${span.text}`}
              disabled={disabled}
              onClick={() => onChange(spans.filter((_, j) => i !== j))}
            >
              <X size={15} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export function PayloadEditor({
  project,
  item,
  payload,
  onChange,
  disabled = false,
  canonical = false,
}: {
  project: Project;
  item: Assignment["item"];
  payload: Payload;
  onChange: (value: Payload) => void;
  disabled?: boolean;
  canonical?: boolean;
}) {
  return (
    <div className="payload-editor">
      {project.mode === "ner" && "spans" in payload ? (
        <NerEditor
          text={item.content.text}
          tokens={item.tokens}
          labels={project.labels}
          spans={payload.spans}
          onChange={(spans) => onChange({ spans })}
          disabled={disabled}
        />
      ) : (
        <>
          <div className="prompt-box">
            <span className="eyebrow">PROMPT</span>
            <p>{item.content.prompt}</p>
          </div>
          {project.mode === "rating" && "label" in payload ? (
            <>
              <div className="response-box">
                <span className="eyebrow">RESPONSE TO EVALUATE</span>
                <p>{item.content.response}</p>
              </div>
              <fieldset disabled={disabled}>
                <legend>How would you rate this response?</legend>
                <div className="rating-options">
                  {project.labels.map((label, i) => (
                    <label
                      className={
                        payload.label === label
                          ? "rating-option selected"
                          : "rating-option"
                      }
                      key={label}
                    >
                      <input
                        type="radio"
                        name="rating"
                        value={label}
                        checked={payload.label === label}
                        onChange={() => onChange({ ...payload, label })}
                      />
                      <span className="rating-number">{i + 1}</span>
                      <strong>{label}</strong>
                      {payload.label === label && <Check size={17} />}
                    </label>
                  ))}
                </div>
              </fieldset>
            </>
          ) : "choice" in payload ? (
            <>
              <div className="ab-responses">
                {["A", "B"].map((side) => (
                  <div
                    className={`response-box ${payload.choice === side ? "chosen-response" : ""}`}
                    key={side}
                  >
                    <span className="response-letter">{side}</span>
                    <span className="eyebrow">
                      {canonical ? "CANONICAL RESPONSE" : "ANONYMOUS RESPONSE"}{" "}
                      {side}
                    </span>
                    <p>
                      {item.content[side === "A" ? "response_a" : "response_b"]}
                    </p>
                  </div>
                ))}
              </div>
              <fieldset disabled={disabled}>
                <legend>Which response is better?</legend>
                <div className="choice-options">
                  {(["A", "TIE", "B"] as const).map((choice) => (
                    <label
                      className={
                        payload.choice === choice
                          ? "choice-option selected"
                          : "choice-option"
                      }
                      key={choice}
                    >
                      <input
                        type="radio"
                        name="choice"
                        value={choice}
                        checked={payload.choice === choice}
                        onChange={() => onChange({ ...payload, choice })}
                      />
                      {choice === "TIE"
                        ? "Equally good / Tie"
                        : `Prefer ${choice}`}
                    </label>
                  ))}
                </div>
              </fieldset>
            </>
          ) : null}
          {"note" in payload && (
            <label className="note-field">
              Your note <span className="muted">(optional)</span>
              <textarea
                disabled={disabled}
                rows={2}
                maxLength={2000}
                value={payload.note || ""}
                onChange={(e) => onChange({ ...payload, note: e.target.value })}
                placeholder="What informed your decision?"
              />
            </label>
          )}
        </>
      )}
    </div>
  );
}

export function AnnotationEditor({
  project,
  assignment,
  onDone,
}: {
  project: Project;
  assignment: Assignment;
  onDone: () => void;
}) {
  const [payload, setPayload] = useState<Payload>(
      assignment.draft || emptyPayload(project.mode),
    ),
    [status, setStatus] = useState("Drafts save automatically"),
    [busy, setBusy] = useState(false),
    [blocked, setBlocked] = useState(false),
    [expires, setExpires] = useState(assignment.expires_at);
  const version = useRef(assignment.version),
    queue = useRef<Promise<void>>(Promise.resolve()),
    timer = useRef<ReturnType<typeof setTimeout> | null>(null),
    stopping = useRef(false),
    failed = useRef(false),
    lastSaved = useRef(JSON.stringify(assignment.draft));
  const notice = useNotice();
  const saveRef =
    useRef<(value: Payload, submit: boolean) => Promise<void>>(null);
  function persist(value: Payload, submit: boolean): Promise<void> {
    const operation = queue.current.then(async () => {
      if (failed.current)
        throw new Error("Reload the assignment before continuing.");
      if (!submit && JSON.stringify(value) === lastSaved.current) return;
      setStatus(submit ? "Submitting…" : "Saving draft…");
      try {
        const result = await api<SaveResult>(
          `/assignments/${assignment.id}/${submit ? "submit" : "draft"}`,
          {
            method: submit ? "POST" : "PUT",
            body: JSON.stringify({
              mode: project.mode,
              payload: value,
              version: version.current,
            }),
          },
        );
        version.current = result.version;
        lastSaved.current = JSON.stringify(value);
        setExpires(result.expires_at);
        setStatus(submit ? "Submitted" : "All changes saved");
      } catch (error) {
        failed.current = true;
        setBlocked(true);
        setStatus((error as Error).message);
        throw error;
      }
    });
    queue.current = operation.catch(() => {});
    return operation;
  }
  useEffect(() => {
    saveRef.current = persist;
  });
  useEffect(() => {
    if (stopping.current || failed.current || !validPayload(payload)) return;
    timer.current = setTimeout(() => {
      void saveRef.current?.(payload, false).catch(() => {});
    }, 800);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [payload]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (JSON.stringify(payload) !== lastSaved.current) event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [payload]);
  async function finish(skip: boolean) {
    stopping.current = true;
    if (timer.current) clearTimeout(timer.current);
    setBusy(true);
    try {
      if (skip) {
        await queue.current;
        await api(`/assignments/${assignment.id}/skip`, { method: "POST" });
      } else {
        await persist(payload, true);
      }
      notice(
        skip
          ? "Item skipped. You can revisit it from the empty queue."
          : "Annotation submitted. Thank you for your perspective.",
      );
      onDone();
    } catch (error) {
      notice((error as Error).message, true);
      stopping.current = false;
      setBusy(false);
    }
  }
  return (
    <div className="annotation-panel">
      <div className="panel-header">
        <span className="eyebrow">{assignment.item.external_id}</span>
        <span className="lease-label">
          <Clock3 size={14} />
          Claim until{" "}
          {new Date(expires * 1000).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
      <PayloadEditor
        project={project}
        item={assignment.item}
        payload={payload}
        onChange={setPayload}
        disabled={busy || blocked}
      />
      <div className="editor-footer">
        <span
          className={`save-state ${blocked ? "form-error" : ""}`}
          role="status"
        >
          {blocked ? (
            <Clock3 size={15} />
          ) : status === "All changes saved" ? (
            <CircleCheck size={15} />
          ) : (
            <Save size={15} />
          )}
          {status}
        </span>
        <div>
          {blocked ? (
            <Button onClick={() => window.location.reload()}>
              Reload assignment
            </Button>
          ) : (
            <>
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => void finish(true)}
              >
                <SkipForward size={15} />
                Skip item
              </Button>
              <Button
                disabled={busy || !validPayload(payload)}
                onClick={() => void finish(false)}
              >
                {busy ? "Working…" : "Submit & continue"}
                <ArrowRight size={16} />
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
