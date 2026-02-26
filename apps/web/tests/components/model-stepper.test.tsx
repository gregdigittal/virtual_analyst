import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ModelStepper, type StepStates } from "../../components/ModelStepper";

// Mock next/link to render a plain <a> tag
vi.mock("next/link", () => ({
  __esModule: true,
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [k: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const ALL_LABELS = [
  "Start",
  "Company",
  "Historical",
  "Assumptions",
  "Correlations",
  "Run",
  "Review",
];

describe("ModelStepper", () => {
  it("renders all 7 step labels", () => {
    render(<ModelStepper steps={{}} />);
    for (const label of ALL_LABELS) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("marks completed steps with done state via data-state attribute", () => {
    const steps: StepStates = {
      start: "done",
      company: "done",
      historical: "current",
    };
    render(<ModelStepper steps={steps} />);

    const startStep = screen.getByText("Start").closest("[data-step]")!;
    expect(startStep).toHaveAttribute("data-state", "done");

    const companyStep = screen.getByText("Company").closest("[data-step]")!;
    expect(companyStep).toHaveAttribute("data-state", "done");

    const historicalStep = screen
      .getByText("Historical")
      .closest("[data-step]")!;
    expect(historicalStep).toHaveAttribute("data-state", "current");
  });

  it("marks locked steps", () => {
    const steps: StepStates = {
      start: "done",
      company: "current",
      historical: "pending",
      assumptions: "locked",
      correlations: "locked",
      run: "locked",
      review: "locked",
    };
    render(<ModelStepper steps={steps} />);

    const assumptionsStep = screen
      .getByText("Assumptions")
      .closest("[data-step]")!;
    expect(assumptionsStep).toHaveAttribute("data-state", "locked");

    const reviewStep = screen.getByText("Review").closest("[data-step]")!;
    expect(reviewStep).toHaveAttribute("data-state", "locked");
  });

  it("renders clickable links for done/current steps when baselineId provided", () => {
    const steps: StepStates = {
      start: "done",
      company: "done",
      historical: "current",
      assumptions: "pending",
    };
    render(<ModelStepper steps={steps} baselineId="abc-123" />);

    // Done steps should be links
    const startLink = screen.getByText("Start").closest("a");
    expect(startLink).not.toBeNull();
    expect(startLink).toHaveAttribute("href", "/baselines/abc-123");

    const companyLink = screen.getByText("Company").closest("a");
    expect(companyLink).not.toBeNull();
    expect(companyLink).toHaveAttribute("href", "/baselines/abc-123");

    // Current step should also be a link
    const historicalLink = screen.getByText("Historical").closest("a");
    expect(historicalLink).not.toBeNull();
    expect(historicalLink).toHaveAttribute(
      "href",
      "/documents?baseline=abc-123",
    );
  });

  it("renders non-clickable elements for pending/locked steps", () => {
    const steps: StepStates = {
      start: "done",
      company: "current",
      historical: "pending",
      assumptions: "locked",
    };
    render(<ModelStepper steps={steps} baselineId="abc-123" />);

    // Pending step should NOT be a link
    const historicalLink = screen.getByText("Historical").closest("a");
    expect(historicalLink).toBeNull();

    // Locked step should NOT be a link
    const assumptionsLink = screen.getByText("Assumptions").closest("a");
    expect(assumptionsLink).toBeNull();
  });

  it("sets aria-label on each step with state information", () => {
    render(
      <ModelStepper
        steps={{ start: "done", company: "current", historical: "pending", assumptions: "locked" }}
        baselineId="b-1"
      />
    );
    expect(screen.getByLabelText(/Step 1: Start \(done\)/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Step 2: Company \(current\)/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Step 3: Historical \(pending\)/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Step 4: Assumptions \(locked\)/)).toBeInTheDocument();
  });

  it("sets aria-current='step' on current step link", () => {
    render(
      <ModelStepper
        steps={{ start: "done", company: "current" }}
        baselineId="b-1"
      />
    );
    const companyLink = screen.getByRole("link", { name: /Company/ });
    expect(companyLink).toHaveAttribute("aria-current", "step");
  });
});
