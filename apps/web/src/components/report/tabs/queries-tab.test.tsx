import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FanoutProvenanceSummary } from "@/components/report/tabs/queries-tab";
import type { FanoutQuery } from "@/lib/types";

function query(id: string, origin: FanoutQuery["origin"], source: FanoutQuery["source"]): FanoutQuery {
  return {
    query_id: id,
    query_text: `query ${id}`,
    origin,
    source,
    intent: "informational",
    importance: 2,
    answer_shape: "definition",
    scope: "this_page",
  };
}

const FIXTURE: FanoutQuery[] = [
  query("q-1", "observed", "gsc"),
  query("q-2", "observed", "gsc"),
  query("q-3", "simulated", "generated_hypothesis"),
  query("q-4", "simulated", "generated_hypothesis"),
  query("q-5", "simulated", "generated_hypothesis"),
];

describe("Fanout provenance summary", () => {
  it("counts observed and simulated queries separately and never merges them", () => {
    render(<FanoutProvenanceSummary fanout={FIXTURE} />);

    const summary = screen.getByTestId("fanout-provenance-summary");
    expect(summary).toBeInTheDocument();
    expect(screen.getByTestId("observed-count")).toHaveTextContent("2 observed");
    expect(screen.getByTestId("simulated-count")).toHaveTextContent("3 simulated");
    expect(summary).toHaveTextContent("of 5 total queries");
  });

  it("reports zero observed queries when the query set is entirely simulated", () => {
    const simulatedOnly = FIXTURE.filter((q) => q.origin === "simulated");
    render(<FanoutProvenanceSummary fanout={simulatedOnly} />);

    expect(screen.getByTestId("observed-count")).toHaveTextContent("0 observed");
    expect(screen.getByTestId("simulated-count")).toHaveTextContent("3 simulated");
  });
});
