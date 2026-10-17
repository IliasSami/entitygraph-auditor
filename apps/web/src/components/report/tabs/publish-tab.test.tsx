import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { PublishTab } from "@/components/report/tabs/publish-tab";
import { NORTHWIND_REPORT } from "@/lib/mock/northwind";

/**
 * The publish/export tab must be derived entirely from the audit report. It used
 * to hard-code a sample brand (Fernhill Bookkeeping / fernhillcfo.com), a
 * $349/month offer, a fabricated rating, an invented author and a fake CMS
 * webhook state. This test pins the honest behaviour: real report data in,
 * explicit "not configured" states out, and none of the old sample strings.
 */
describe("PublishTab honesty", () => {
  it("derives previews, schema and the gate from the report", () => {
    render(<PublishTab report={NORTHWIND_REPORT} />);
    const text = document.body.textContent ?? "";

    // Real data from the report is surfaced.
    expect(text).toContain("Northwind Roofing");
    expect(text).toMatch(/publication gate:/i);
    expect(text).toContain("contact_phone"); // a real non-critical gate issue
    expect(text).toContain("Schema Generator");
  });

  it("never renders the retired hard-coded sample specifics", () => {
    render(<PublishTab report={NORTHWIND_REPORT} />);
    const text = document.body.textContent ?? "";

    const leaked = [
      "Fernhill",
      "fernhillcfo.com",
      "$349",
      "Dana Reyes",
      "Draft #884",
      "24 reviews",
      "★★★★★",
      "QuickBooks Online",
      "1 override",
      "88%",
    ];
    for (const needle of leaked) {
      expect(text).not.toContain(needle);
    }
  });

  it("reports publish destinations as not configured instead of faking a connection", () => {
    render(<PublishTab report={NORTHWIND_REPORT} />);
    const text = document.body.textContent ?? "";

    expect(text).toMatch(/no cms or webhook destination is configured/i);
    expect(text).not.toMatch(/wordpress rest connected/i);
    expect(text).not.toMatch(/webhook active/i);
  });

  it("renders an unevaluated gate as not evaluated, not as unresolved issues", () => {
    const report: typeof NORTHWIND_REPORT = {
      ...NORTHWIND_REPORT,
      gate: { status: "not_configured", critical_issues: [], noncritical_issues: [] },
    };
    render(<PublishTab report={report} />);
    const text = document.body.textContent ?? "";

    // No brand pack configured means the gate was never evaluated — it is not a
    // failure and must not be surfaced as unresolved gate issues.
    expect(text).toMatch(/gate was not evaluated/i);
    expect(text).not.toMatch(/unresolved gate issues/i);
    expect(text).toMatch(/publication gate:/i);
  });

  it("flags a failed gate as unresolved issues", () => {
    const report: typeof NORTHWIND_REPORT = {
      ...NORTHWIND_REPORT,
      gate: {
        status: "fail",
        critical_issues: ["An unverified high-stakes claim must be removed."],
        noncritical_issues: [],
      },
    };
    render(<PublishTab report={report} />);
    const text = document.body.textContent ?? "";

    expect(text).toMatch(/unresolved gate issues/i);
    expect(text).toMatch(/unverified high-stakes claim/i);
  });
});
