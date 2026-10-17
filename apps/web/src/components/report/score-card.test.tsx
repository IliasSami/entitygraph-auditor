import { useState } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ScoreCard, ScoreDrawer } from "@/components/report/score-card";
import { NORTHWIND_REPORT } from "@/lib/mock/northwind";
import type { ComponentScore } from "@/lib/types";

const EOS = NORTHWIND_REPORT.scores.EOS;

function Harness() {
  const [open, setOpen] = useState<ComponentScore | null>(null);
  return (
    <>
      <ScoreCard score={EOS} onSelect={setOpen} />
      <ScoreDrawer score={open} onOpenChange={setOpen} />
    </>
  );
}

describe("Score card drawer", () => {
  it("opens the rubric drawer with sub-scores, lost-point reasons and the heuristic disclaimer", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    expect(screen.queryByTestId("score-drawer")).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: /open rubric detail for entity optimization score/i }),
    );

    const drawer = await screen.findByTestId("score-drawer");
    expect(drawer).toBeInTheDocument();

    // The rubric heading and the component sub-scores are rendered.
    expect(screen.getByText(/rubric sub-scores/i)).toBeInTheDocument();
    for (const label of Object.keys(EOS.sub_scores)) {
      const pretty = label
        .split(/[_\s]+/)
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
      expect(screen.getByText(pretty)).toBeInTheDocument();
    }

    // "Why points were lost" explains the deduction rather than just a number.
    expect(screen.getByText(/why points were lost/i)).toBeInTheDocument();
    expect(screen.getByText(EOS.lost_points_reasons[0])).toBeInTheDocument();

    // Every score surface carries the internal-heuristic disclaimer.
    expect(screen.getByText(/internal editorial heuristic/i)).toBeInTheDocument();
  });
});
