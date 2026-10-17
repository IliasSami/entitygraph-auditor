import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { GateSummary } from "@/components/report/gate-summary";
import { NORTHWIND_REPORT } from "@/lib/mock/northwind";
import type { AuditReport } from "@/lib/types";

function renderGate(report: AuditReport) {
  return render(
    <GateSummary
      report={report}
      onExport={() => {}}
      exporting={false}
      onOpenRecommendations={() => {}}
    />,
  );
}

describe("Gate summary issues", () => {
  it("renders plain-string gate issues", () => {
    const report: AuditReport = {
      ...NORTHWIND_REPORT,
      gate: {
        status: "fail",
        critical_issues: ["Missing canonical entity statement"],
        noncritical_issues: ["Consider adding a sameAs link"],
      },
    };

    renderGate(report);

    expect(screen.getByText("Missing canonical entity statement")).toBeInTheDocument();
    expect(screen.getByText("Consider adding a sameAs link")).toBeInTheDocument();
  });

  it("renders structured GateIssue objects (the real API shape) without crashing", () => {
    const report: AuditReport = {
      ...NORTHWIND_REPORT,
      gate: {
        status: "fail",
        critical_issues: [
          {
            category: "compliance",
            severity: "critical",
            message: "Prohibited term detected: Banned term 'guaranteed #1' used",
          },
        ],
        noncritical_issues: [
          {
            category: "brand",
            severity: "warning",
            title: "Off-brand talent language",
            message: "Banned term 'rockstar' used",
          },
        ],
      },
    };

    renderGate(report);

    expect(
      screen.getByText("Prohibited term detected: Banned term 'guaranteed #1' used"),
    ).toBeInTheDocument();
    // A structured issue with a title prefers the title.
    expect(screen.getByText("Off-brand talent language")).toBeInTheDocument();
  });
});
