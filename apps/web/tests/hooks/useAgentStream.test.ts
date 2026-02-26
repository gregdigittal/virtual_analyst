import { renderHook, act } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { useAgentStream } from "@/hooks/useAgentStream";

describe("useAgentStream", () => {
  it("starts with empty default state", () => {
    const { result } = renderHook(() => useAgentStream());

    expect(result.current.messages).toEqual([]);
    expect(result.current.currentStep).toBe("upload");
    expect(result.current.isComplete).toBe(false);
    expect(result.current.isPaused).toBe(false);
    expect(result.current.pendingQuestion).toBeNull();
    expect(result.current.classification).toBeNull();
    expect(result.current.mapping).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('processEvent("message") appends to messages', () => {
    const { result } = renderHook(() => useAgentStream());

    act(() => {
      result.current.processEvent({
        type: "message",
        role: "assistant",
        text: "Analyzing your spreadsheet...",
      });
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe("assistant");
    expect(result.current.messages[0].text).toBe(
      "Analyzing your spreadsheet..."
    );

    // Append a second message
    act(() => {
      result.current.processEvent({
        type: "message",
        role: "assistant",
        text: "Found 3 sheets.",
      });
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1].text).toBe("Found 3 sheets.");
  });

  it('processEvent("classification") sets classification and advances to "classify"', () => {
    const { result } = renderHook(() => useAgentStream());

    const classificationData = {
      type: "classification",
      sheets: [{ name: "Revenue" }, { name: "Costs" }],
      model_summary: { type: "saas", confidence: 0.95 },
    };

    act(() => {
      result.current.processEvent(classificationData);
    });

    expect(result.current.classification).toEqual(classificationData);
    expect(result.current.currentStep).toBe("classify");
  });

  it('processEvent("question") sets isPaused and pendingQuestion', () => {
    const { result } = renderHook(() => useAgentStream());

    act(() => {
      result.current.processEvent({
        type: "question",
        id: "q-1",
        text: "What currency are these figures in?",
        options: ["USD", "EUR", "GBP"],
        context: "Found mixed currency symbols",
      });
    });

    expect(result.current.isPaused).toBe(true);
    expect(result.current.pendingQuestion).toEqual({
      id: "q-1",
      text: "What currency are these figures in?",
      options: ["USD", "EUR", "GBP"],
      context: "Found mixed currency symbols",
    });

    // answerQuestion clears the pending question
    act(() => {
      result.current.answerQuestion("q-1", "USD");
    });

    expect(result.current.isPaused).toBe(false);
    expect(result.current.pendingQuestion).toBeNull();
    // User answer appended to messages
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe("user");
    expect(result.current.messages[0].text).toBe("USD");
  });

  it('processEvent("complete") sets isComplete and advances to "review"', () => {
    const { result } = renderHook(() => useAgentStream());

    const mappingData = { revenue: ["Sheet1!A1"] };
    const classificationData = { type: "saas" };

    act(() => {
      result.current.processEvent({
        type: "complete",
        mapping: mappingData,
        classification: classificationData,
        unmapped: ["Sheet2!B5"],
      });
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.currentStep).toBe("review");
    expect(result.current.mapping).toEqual(mappingData);
    expect(result.current.classification).toEqual(classificationData);
  });
});
