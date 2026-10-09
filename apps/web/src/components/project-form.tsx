"use client";
import { useState, type FormEvent } from "react";
import { Button } from "./ui/button";
import type { ProjectConfig } from "@/lib/api";

export function ProjectForm({
  initial,
  onSave,
  pending,
}: {
  initial?: ProjectConfig;
  onSave: (data: ProjectConfig) => void;
  pending: boolean;
}) {
  const [mode, setMode] = useState<ProjectConfig["mode"]>(
    initial?.mode || "rating",
  );
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    onSave({
      name: String(data.get("name")),
      description: String(data.get("description")),
      mode,
      labels:
        mode === "ab"
          ? []
          : String(data.get("labels"))
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean),
      ordered: data.get("ordered") === "on",
      target_raters: Number(data.get("raters")),
      review_threshold: Number(data.get("threshold")) / 100,
    });
  }
  return (
    <form className="stack-form" onSubmit={submit}>
      <label>
        Project name
        <input
          name="name"
          minLength={2}
          maxLength={120}
          required
          placeholder="e.g. Response quality"
          defaultValue={initial?.name}
        />
      </label>
      <label>
        Description
        <textarea
          name="description"
          maxLength={2000}
          rows={2}
          placeholder="What are we looking for?"
          defaultValue={initial?.description}
        />
      </label>
      <label>
        Annotation mode
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as ProjectConfig["mode"])}
        >
          <option value="rating">Response rating</option>
          <option value="ner">Entity annotation (NER)</option>
          <option value="ab">Blinded A/B comparison</option>
        </select>
      </label>
      {mode !== "ab" && (
        <label>
          {mode === "ner" ? "Entity types" : "Rating labels"}
          <input
            name="labels"
            required
            placeholder={
              mode === "ner"
                ? "PERSON, ORG, LOCATION"
                : "Needs work, Acceptable, Excellent"
            }
            defaultValue={initial?.labels?.join(", ")}
          />
          <small>
            Separate labels with commas. Order matters for an ordered scale.
          </small>
        </label>
      )}
      {mode === "rating" && (
        <label className="check-label">
          <input
            type="checkbox"
            name="ordered"
            defaultChecked={initial?.ordered}
          />
          Use an ordered rating scale
        </label>
      )}
      <div className="form-grid">
        <label>
          Raters per item
          <input
            name="raters"
            type="number"
            min={2}
            max={20}
            defaultValue={initial?.target_raters || 3}
            required
          />
        </label>
        <label>
          Consensus threshold (%)
          <input
            name="threshold"
            type="number"
            min={50}
            max={100}
            step={1}
            defaultValue={Math.round((initial?.review_threshold || 0.8) * 100)}
            required
          />
        </label>
      </div>
      <p className="form-hint">
        Configuration locks when the project is activated.
      </p>
      <Button type="submit" disabled={pending}>
        {pending
          ? "Saving…"
          : initial
            ? "Save configuration"
            : "Create project"}
      </Button>
    </form>
  );
}
