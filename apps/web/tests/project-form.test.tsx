import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ProjectForm } from "@/components/project-form";
import { Dialog } from "@/components/ui/dialog";

it("collects configured labels and target without exposing implementation fields", () => {
  const save = vi.fn();
  render(<ProjectForm onSave={save} pending={false} />);
  fireEvent.change(screen.getByLabelText("Project name"), {
    target: { value: "Quality" },
  });
  fireEvent.change(screen.getByLabelText(/Rating labels/), {
    target: { value: "Bad, Good" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create project" }));
  expect(save).toHaveBeenCalledWith(
    expect.objectContaining({
      name: "Quality",
      labels: ["Bad", "Good"],
      target_raters: 3,
      review_threshold: 0.8,
    }),
  );
});

it("gives a modal an accessible title, description and close control", () => {
  const close = vi.fn();
  render(
    <Dialog
      open
      onOpenChange={close}
      title="New project"
      description="Start with clear guidelines."
    >
      <p>Project form</p>
    </Dialog>,
  );
  expect(
    screen.getByRole("dialog", { name: "New project" }),
  ).toHaveAccessibleDescription("Start with clear guidelines.");
  fireEvent.click(screen.getByRole("button", { name: "Close dialog" }));
  expect(close).toHaveBeenCalledWith(false);
});
