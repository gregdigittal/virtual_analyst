import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatMessage } from "@/components/excel-import/ChatMessage";

describe("ChatMessage", () => {
  it("renders assistant message with 'Assistant' aria-label", () => {
    render(<ChatMessage role="assistant" text="Hello from AI" />);

    expect(screen.getByText("Hello from AI")).toBeInTheDocument();
    expect(screen.getByLabelText("Assistant")).toBeInTheDocument();
  });

  it("renders user message with 'You' aria-label", () => {
    render(<ChatMessage role="user" text="Hello from me" />);

    expect(screen.getByText("Hello from me")).toBeInTheDocument();
    expect(screen.getByLabelText("You")).toBeInTheDocument();
  });

  it("renders status message with text-va-text2 class", () => {
    render(<ChatMessage role="status" text="Processing file..." />);

    const statusEl = screen.getByText("Processing file...");
    expect(statusEl).toBeInTheDocument();
    expect(statusEl.closest("div")).toHaveClass("text-va-text2");
  });
});
