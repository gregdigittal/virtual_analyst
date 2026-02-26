import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuestionCard, type AgentQuestion } from "@/components/excel-import/QuestionCard";

const sampleQuestion: AgentQuestion = {
  id: "q-1",
  text: "What type of entity is this?",
  options: ["SaaS Company", "Manufacturing", "Retail"],
  context: "We detected multiple revenue streams.",
};

describe("QuestionCard", () => {
  it("renders question text", () => {
    render(<QuestionCard question={sampleQuestion} onAnswer={vi.fn()} />);

    expect(screen.getByText("What type of entity is this?")).toBeInTheDocument();
  });

  it("renders all option buttons", () => {
    render(<QuestionCard question={sampleQuestion} onAnswer={vi.fn()} />);

    expect(screen.getByRole("button", { name: "SaaS Company" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Manufacturing" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retail" })).toBeInTheDocument();
  });

  it("calls onAnswer(questionId, selectedOption) on click", async () => {
    const user = userEvent.setup();
    const onAnswer = vi.fn();
    render(<QuestionCard question={sampleQuestion} onAnswer={onAnswer} />);

    await user.click(screen.getByRole("button", { name: "Manufacturing" }));

    expect(onAnswer).toHaveBeenCalledWith("q-1", "Manufacturing");
  });

  it("disables buttons when disabled=true", () => {
    render(<QuestionCard question={sampleQuestion} onAnswer={vi.fn()} disabled />);

    const buttons = screen.getAllByRole("button");
    for (const btn of buttons) {
      expect(btn).toBeDisabled();
    }
  });
});
