import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/audits/new",
}));

import NewAuditPage from "@/app/audits/new/page";

function renderWithQuery(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("New-audit wizard step navigation", () => {
  it("starts on step 1 with Back disabled", async () => {
    renderWithQuery(<NewAuditPage />);

    expect(await screen.findByTestId("wizard-step")).toHaveAttribute("data-step", "1");
    expect(screen.getByText("Step 1 of 5")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /back/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /next/i })).toBeEnabled();
  });

  it("blocks moving forward until step 1 is valid", async () => {
    const user = userEvent.setup();
    renderWithQuery(<NewAuditPage />);

    await screen.findByTestId("wizard-step");
    await user.click(screen.getByRole("button", { name: /next/i }));

    // Validation messages appear and the step does not advance.
    expect(await screen.findByText(/choose a project/i)).toBeInTheDocument();
    expect(screen.getByTestId("wizard-step")).toHaveAttribute("data-step", "1");
  });

  it("advances to step 2 once a project and page type are chosen, then returns with Back", async () => {
    const user = userEvent.setup();
    renderWithQuery(<NewAuditPage />);

    await screen.findByTestId("wizard-step");

    await user.selectOptions(await screen.findByLabelText(/^project$/i), "proj-northwind");
    await user.selectOptions(screen.getByLabelText(/page type/i), "local_service");
    await user.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() =>
      expect(screen.getByTestId("wizard-step")).toHaveAttribute("data-step", "2"),
    );
    expect(screen.getByText("Step 2 of 5")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /back/i }));
    await waitFor(() =>
      expect(screen.getByTestId("wizard-step")).toHaveAttribute("data-step", "1"),
    );
  });
});
