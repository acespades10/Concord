"use client";
import { useState } from "react";
import {
  Braces,
  Database,
  Download,
  FileArchive,
  ShieldCheck,
} from "lucide-react";
import type { Project } from "@/lib/api";
import { Button } from "./ui/button";
import { useNotice } from "./providers";

export function ExportPanel({ project }: { project: Project }) {
  const [format, setFormat] = useState("jsonl"),
    [selection, setSelection] = useState("both"),
    [include, setInclude] = useState(false),
    [busy, setBusy] = useState(false);
  const notice = useNotice();
  async function download() {
    setBusy(true);
    try {
      const response = await fetch(
        `/api/v1/projects/${project.id}/exports?format=${format}&selection=${selection}&include_unresolved=${include}`,
        { credentials: "same-origin" },
      );
      if (!response.ok)
        throw new Error("Export failed. Refresh your session and try again.");
      const blob = await response.blob(),
        url = URL.createObjectURL(blob),
        link = document.createElement("a");
      link.href = url;
      link.download =
        response.headers
          .get("Content-Disposition")
          ?.match(/filename="([^"]+)"/)?.[1] || "concord-export.zip";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      notice("Your export is ready. Check your downloads.");
    } catch (error) {
      notice((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="export-layout">
      <section className="panel export-panel">
        <span className="eyebrow">FROM HUMAN INSIGHT TO YOUR NEXT MODEL</span>
        <h2>Good data, ready to go.</h2>
        <p className="muted">
          Take your annotations and resolved decisions into your next workflow.
        </p>
        <fieldset>
          <legend>Choose a format</legend>
          <div className="export-formats">
            {[
              {
                id: "jsonl",
                title: "JSONL",
                detail: "Simple, line by line",
                Icon: Braces,
              },
              {
                id: "parquet",
                title: "Parquet",
                detail: "Efficient and typed",
                Icon: Database,
              },
              {
                id: "huggingface",
                title: "Hugging Face",
                detail: "DatasetDict archive",
                Icon: FileArchive,
              },
            ].map(({ id, title, detail, Icon }) => (
              <label
                key={id}
                className={`format-card ${format === id ? "selected" : ""}`}
              >
                <input
                  type="radio"
                  name="format"
                  checked={format === id}
                  onChange={() => setFormat(id)}
                />
                <Icon size={24} />
                <strong>{title}</strong>
                <small>{detail}</small>
              </label>
            ))}
          </div>
        </fieldset>
        <label>
          What should we include?
          <select
            value={selection}
            onChange={(e) => setSelection(e.target.value)}
          >
            <option value="both">Raw annotations + consensus</option>
            <option value="annotations">Raw submitted annotations only</option>
            <option value="consensus">Consensus only</option>
          </select>
        </label>
        <label className="check-label">
          <input
            type="checkbox"
            checked={include}
            onChange={(e) => setInclude(e.target.checked)}
            disabled={selection === "annotations"}
          />
          Include unresolved items in consensus
        </label>
        <p className="form-hint">
          Consensus contains resolved items by default. Draft annotations are
          never exported.
        </p>
        <Button disabled={busy} onClick={() => void download()}>
          <Download size={17} />
          {busy ? "Preparing your export…" : "Download dataset"}
        </Button>
      </section>
      <aside className="export-note">
        <span className="art-icon sage">
          <ShieldCheck size={24} />
        </span>
        <h3>A little context goes a long way.</h3>
        <p>
          Every export includes a versioned manifest and your project
          configuration.
        </p>
        <ul>
          <li>Stable, pseudonymous annotator identities</li>
          <li>Original Unicode text and NER offsets</li>
          <li>Canonical A/B response identities</li>
          <li>Deterministic item and annotator ordering</li>
          <li>Reviewer decisions and rationale</li>
        </ul>
        <small>
          JSONL starts with a manifest record. Parquet stores it in schema
          metadata. Archives include manifest.json.
        </small>
      </aside>
    </div>
  );
}
