import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { GateBadge } from "@/components/status";
import { GATE_STATUSES, GATE_STATUS_LABELS, type GateStatus } from "@/lib/types";

describe("GateBadge variants", () => {
  it("labels every gate status with text, never colour alone", () => {
    for (const status of GATE_STATUSES as readonly GateStatus[]) {
      const { unmount } = render(<GateBadge status={status} />);
      expect(screen.getByTestId("gate-badge")).toHaveTextContent(GATE_STATUS_LABELS[status]);
      unmount();
    }
  });

  it("renders a distinct 'Not assessed' label when the gate is unknown", () => {
    render(<GateBadge status={null} />);
    const badge = screen.getByTestId("gate-badge");
    expect(badge).toHaveTextContent("Not assessed");
    expect(badge).not.toHaveTextContent(GATE_STATUS_LABELS.pass);
  });

  it("carries a text label for pass and fail so the tone is never the only signal", () => {
    const { unmount } = render(<GateBadge status="pass" />);
    expect(screen.getByTestId("gate-badge")).toHaveTextContent("Pass");
    unmount();

    render(<GateBadge status="fail" />);
    expect(screen.getByTestId("gate-badge")).toHaveTextContent(/fail/i);
  });
});
