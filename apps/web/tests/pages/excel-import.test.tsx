import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockPush, mockGetAuthContext, mockApi } from "./setup";

import { ToastProvider } from "@/components/ui";

/* ------------------------------------------------------------------ */
/*  Mock the useAgentStream hook                                       */
/* ------------------------------------------------------------------ */

const mockStartStream = vi.fn();
const mockAnswerQuestion = vi.fn();
const mockProcessEvent = vi.fn();

const defaultStreamReturn = {
  messages: [],
  currentStep: "upload" as const,
  isComplete: false,
  isPaused: false,
  pendingQuestion: null,
  classification: null,
  mapping: null,
  error: null,
  startStream: mockStartStream,
  answerQuestion: mockAnswerQuestion,
  processEvent: mockProcessEvent,
};

vi.mock("@/hooks/useAgentStream", () => ({
  useAgentStream: () => defaultStreamReturn,
}));

/* ------------------------------------------------------------------ */
/*  Add excelIngestion methods to mockApi                              */
/* ------------------------------------------------------------------ */

(mockApi as Record<string, unknown>).excelIngestion = {
  getUploadStreamUrl: vi.fn(() => "http://localhost:8000/api/v1/excel-ingestion/upload-stream"),
  getAnswerStreamUrl: vi.fn(() => "http://localhost:8000/api/v1/excel-ingestion/test-id/answer-stream"),
  createDraft: vi.fn(async () => ({ draft_session_id: "draft-123" })),
};

/* ------------------------------------------------------------------ */
/*  Import the page under test (must come after mocks)                 */
/* ------------------------------------------------------------------ */

import ExcelImportPage from "@/app/(app)/excel-import/page";

function renderPage() {
  return render(
    <ToastProvider>
      <ExcelImportPage />
    </ToastProvider>,
  );
}

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe("ExcelImportPage", () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockGetAuthContext.mockClear();
    mockStartStream.mockClear();
    mockAnswerQuestion.mockClear();
    mockProcessEvent.mockClear();
    mockGetAuthContext.mockResolvedValue({
      tenantId: "tenant-test",
      userId: "user-test",
      accessToken: "mock-token",
      tenantIdIsFallback: false,
    });
  });

  it("renders upload step initially with drop zone", async () => {
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText(/drop your file here/i),
      ).toBeInTheDocument();
    });
  });

  it("renders the import stepper with 4 steps", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Upload")).toBeInTheDocument();
      expect(screen.getByText("Classify")).toBeInTheDocument();
      expect(screen.getByText("Map")).toBeInTheDocument();
      expect(screen.getByText("Review")).toBeInTheDocument();
    });
  });

  it("renders the page heading", async () => {
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /import excel model/i }),
      ).toBeInTheDocument();
    });
  });

  it("shows a file input for .xlsx files", async () => {
    renderPage();
    await waitFor(() => {
      const input = screen.getByLabelText(/select excel file/i);
      expect(input).toBeInTheDocument();
      expect(input).toHaveAttribute("accept", ".xlsx");
    });
  });
});
