import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useState } from "react";
import {
  AnnotationEditor,
  NerEditor,
  PayloadEditor,
} from "@/components/annotation-editor";
import type { Assignment, Project, Span } from "@/lib/api";
import { Providers } from "@/components/providers";

const project: Project = {
  id: "p",
  name: "Test",
  description: "",
  mode: "rating",
  ordered: false,
  labels: ["Bad", "Good"],
  target_raters: 3,
  review_threshold: 0.8,
  state: "active",
  metric_revision: 0,
  item_count: 1,
  submission_count: 0,
  my_submission_count: 0,
  member_count: 3,
};
const assignment: Assignment = {
  id: "a",
  project_id: "p",
  version: 0,
  expires_at: Date.now() / 1000 + 900,
  item: {
    id: "i",
    external_id: "one",
    content: { prompt: "Greet me", response: "Hello" },
    tokens: [],
  },
  draft: null,
};

describe("accessible annotation controls", () => {
  it("uses Unicode code point offsets and prevents overlapping spans", () => {
    const change = vi.fn();
    function Harness() {
      const [spans, setSpans] = useState<Span[]>([]);
      return (
        <NerEditor
          text="🌿 José"
          tokens={[
            { text: "🌿", start: 0, end: 1 },
            { text: "José", start: 2, end: 6 },
          ]}
          labels={["PERSON"]}
          spans={spans}
          onChange={(s) => {
            setSpans(s);
            change(s);
          }}
        />
      );
    }
    render(<Harness />);
    const token = screen.getByRole("button", { name: "José, token 2" });
    fireEvent.click(token);
    fireEvent.click(token);
    expect(change).toHaveBeenCalledWith([
      { start: 2, end: 6, label: "PERSON", text: "José" },
    ]);
    fireEvent.click(token);
    fireEvent.click(token);
    expect(screen.getByRole("alert")).toHaveTextContent("overlaps");
    fireEvent.click(screen.getByRole("button", { name: "Remove José" }));
    expect(change).toHaveBeenLastCalledWith([]);
  });

  it("offers an accessible configurable radio group", () => {
    const change = vi.fn();
    render(
      <PayloadEditor
        project={project}
        item={assignment.item}
        payload={{ label: "", note: "" }}
        onChange={change}
      />,
    );
    fireEvent.click(screen.getByRole("radio", { name: /Good/ }));
    expect(change).toHaveBeenCalledWith({ label: "Good", note: "" });
    expect(
      screen.getByRole("group", { name: "How would you rate this response?" }),
    ).toBeInTheDocument();
  });

  it("submits with the latest autosave version and locks on conflicts", async () => {
    const requests: { url: string; body: { version: number } }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, options: RequestInit) => {
        const body = JSON.parse(options.body as string);
        requests.push({ url, body });
        return new Response(
          JSON.stringify({
            version: requests.length,
            expires_at: Date.now() / 1000 + 900,
            status: url.endsWith("submit") ? "submitted" : "draft",
          }),
          { status: 200 },
        );
      }),
    );
    const done = vi.fn();
    render(
      <Providers>
        <AnnotationEditor
          project={project}
          assignment={assignment}
          onDone={done}
        />
      </Providers>,
    );
    expect(
      screen.getByRole("button", { name: /Submit & continue/ }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("radio", { name: /Good/ }));
    await waitFor(
      () =>
        expect(screen.getByRole("status")).toHaveTextContent(
          "All changes saved",
        ),
      { timeout: 2500 },
    );
    fireEvent.click(screen.getByRole("button", { name: /Submit & continue/ }));
    await waitFor(() => expect(done).toHaveBeenCalled());
    expect(requests.map((r) => r.body.version)).toEqual([0, 1]);
    vi.unstubAllGlobals();
  });

  it("disables editing after a stale draft conflict", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ detail: "Draft changed in another tab" }),
            { status: 409 },
          ),
      ),
    );
    render(
      <Providers>
        <AnnotationEditor
          project={project}
          assignment={assignment}
          onDone={() => {}}
        />
      </Providers>,
    );
    fireEvent.click(screen.getByRole("radio", { name: /Good/ }));
    await waitFor(
      () =>
        expect(
          screen.getByRole("button", { name: "Reload assignment" }),
        ).toBeVisible(),
      { timeout: 2500 },
    );
    expect(screen.getByRole("radio", { name: /Good/ })).toBeDisabled();
    vi.unstubAllGlobals();
  });
});
