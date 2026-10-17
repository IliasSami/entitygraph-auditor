import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RecommendationCard } from "@/components/report/tabs/recommendations-tab";
import { NORTHWIND_REPORT } from "@/lib/mock/northwind";
import type { Finding } from "@/lib/types";

const WITH_FULL_CONTEXT = NORTHWIND_REPORT.recommendations[0];

function renderCard(finding: Finding) {
  return render(
    <ul>
      <RecommendationCard recommendation={finding} />
    </ul>,
  );
}

describe("RecommendationCard", () => {
  it("renders what, where, why, how and a verification condition", () => {
    expect(WITH_FULL_CONTEXT.how?.verification_condition).toBeTruthy();
    renderCard(WITH_FULL_CONTEXT);

    const card = screen.getByTestId("recommendation-card");

    // What — always present.
    expect(card).toHaveTextContent(/what:/i);
    expect(card).toHaveTextContent(WITH_FULL_CONTEXT.what);

    // Where — names the section the writer must edit.
    const where = screen.getByTestId("rec-where");
    expect(where).toHaveTextContent(WITH_FULL_CONTEXT.where!.section_id!);

    // Why — cites the rule/entity that triggered the finding.
    const why = screen.getByTestId("rec-why");
    expect(why).toHaveTextContent(WITH_FULL_CONTEXT.why!.rule_id!);

    // How — a concrete suggested rewrite the writer can adopt.
    const how = screen.getByTestId("rec-how");
    expect(how).toHaveTextContent(/suggested rewrite/i);

    // Verification — the condition that must hold before the fix counts as done.
    const verification = screen.getByTestId("rec-verification");
    expect(verification).toHaveTextContent(WITH_FULL_CONTEXT.how!.verification_condition!);
  });

  it("says so explicitly when no verification condition was recorded", () => {
    const withoutVerification: Finding = {
      ...WITH_FULL_CONTEXT,
      finding_id: "fnd-no-verification",
      how: { suggested_rewrite: "Rewrite the sentence.", implementation_steps: [] },
    };
    renderCard(withoutVerification);

    expect(screen.getByTestId("rec-verification-none")).toHaveTextContent(
      /no verification condition was recorded/i,
    );
    expect(screen.queryByTestId("rec-verification")).not.toBeInTheDocument();
  });
});
