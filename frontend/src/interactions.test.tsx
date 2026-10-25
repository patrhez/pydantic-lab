// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ApprovalCard } from "./components/Chat";
import { activeRun, canSend, Session } from "./types";

afterEach(cleanup);
const approval = {
  id: "approval1",
  call_id: "call1",
  tool: "write_file",
  arguments: { path: "main.py" },
  status: "pending",
  reason: "Default approval",
  setup: false,
};
test("approval arrival preserves composer focus and never submits a decision", () => {
  const decide = vi.fn();
  const view = render(
    <textarea aria-label="Composer" defaultValue="Work in progress" />,
  );
  screen.getByLabelText("Composer").focus();
  view.rerender(
    <>
      <textarea aria-label="Composer" defaultValue="Work in progress" />
      <ApprovalCard approval={approval} onDecide={decide} />
    </>,
  );
  expect(document.activeElement).toBe(screen.getByLabelText("Composer"));
  fireEvent.keyDown(document.activeElement!, { key: "Enter" });
  expect(decide).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Allow Once" }));
  expect(decide).toHaveBeenCalledWith(approval, true);
});
test("expired approval has no executable controls", () => {
  render(
    <ApprovalCard
      approval={{
        ...approval,
        status: "expired",
        reason: "Steer changed the plan",
      }}
      onDecide={vi.fn()}
    />,
  );
  expect(screen.queryByRole("button", { name: "Allow Once" })).toBeNull();
  expect(screen.getByText("Steer changed the plan")).toBeTruthy();
});
test("provisioning and unknown states block chat, while stopped queues accept input", () => {
  for (const status of ["provisioning", "outcome_unknown", "deleting"])
    expect(canSend({ status } as Session)).toBe(false);
  expect(canSend({ status: "stopped", initialized: true } as Session)).toBe(true);
  expect(
    activeRun({
      runs: [
        { status: "queued" },
        { status: "awaiting_approval", id: "active" },
      ],
    } as Session)?.id,
  ).toBe("active");
});
