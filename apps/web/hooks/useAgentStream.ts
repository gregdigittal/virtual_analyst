"use client";

import { useCallback, useRef, useState } from "react";
import type { ImportStep } from "@/components/excel-import/ImportStepper";
import type { ThreadMessage } from "@/components/excel-import/ChatThread";
import type { AgentQuestion } from "@/components/excel-import/QuestionCard";

/* ------------------------------------------------------------------ */
/*  SSE event types (from backend)                                     */
/* ------------------------------------------------------------------ */

export type SSEEvent =
  | { type: "message"; role: "assistant"; text: string }
  | { type: "status"; step?: string; message: string }
  | { type: "classification"; sheets: unknown[]; model_summary: object }
  | { type: "mapping"; [key: string]: unknown }
  | { type: "question"; id: string; text: string; options: string[]; context?: string }
  | { type: "complete"; mapping: object; classification: object; unmapped: unknown[] }
  | { type: "error"; message: string; recoverable: boolean };

/* ------------------------------------------------------------------ */
/*  Return interface                                                    */
/* ------------------------------------------------------------------ */

export interface UseAgentStreamReturn {
  messages: ThreadMessage[];
  currentStep: ImportStep;
  isComplete: boolean;
  isPaused: boolean;
  pendingQuestion: AgentQuestion | null;
  classification: object | null;
  mapping: object | null;
  error: string | null;
  startStream: (ingestionId: string, url: string) => void;
  answerQuestion: (questionId: string, answer: string) => void;
  processEvent: (data: Record<string, unknown>) => void;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

let _nextId = 0;
function nextMsgId(): string {
  return `msg-${++_nextId}`;
}

/* ------------------------------------------------------------------ */
/*  Hook                                                               */
/* ------------------------------------------------------------------ */

export function useAgentStream(): UseAgentStreamReturn {
  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [currentStep, setCurrentStep] = useState<ImportStep>("upload");
  const [isComplete, setIsComplete] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState<AgentQuestion | null>(null);
  const [classification, setClassification] = useState<object | null>(null);
  const [mapping, setMapping] = useState<object | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Track active stream metadata (ingestionId + url) for potential reconnection
  const streamRef = useRef<{ ingestionId: string; url: string } | null>(null);

  /* ---------------------------------------------------------------- */
  /*  processEvent — feed a parsed SSE event into state                */
  /* ---------------------------------------------------------------- */

  const processEvent = useCallback((data: Record<string, unknown>) => {
    const eventType = data.type as string | undefined;

    switch (eventType) {
      case "message": {
        const text = (data.text as string) ?? "";
        setMessages((prev) => [
          ...prev,
          { id: nextMsgId(), role: "assistant", text },
        ]);
        break;
      }

      case "status": {
        const statusMsg = (data.message as string) ?? "";
        setMessages((prev) => [
          ...prev,
          { id: nextMsgId(), role: "status", text: statusMsg },
        ]);
        if (data.step) {
          setCurrentStep(data.step as ImportStep);
        }
        break;
      }

      case "classification": {
        setClassification(data as object);
        setCurrentStep("classify");
        break;
      }

      case "mapping": {
        setMapping(data as object);
        setCurrentStep("map");
        break;
      }

      case "question": {
        const question: AgentQuestion = {
          id: data.id as string,
          text: data.text as string,
          options: data.options as string[],
          ...(data.context != null && { context: data.context as string }),
        };
        setPendingQuestion(question);
        setIsPaused(true);
        break;
      }

      case "complete": {
        if (data.mapping) setMapping(data.mapping as object);
        if (data.classification) setClassification(data.classification as object);
        setIsComplete(true);
        setCurrentStep("review");
        break;
      }

      case "error": {
        const errMsg = (data.message as string) ?? "Unknown error";
        setError(errMsg);
        break;
      }

      default:
        // Unknown event type — ignore silently
        break;
    }
  }, []);

  /* ---------------------------------------------------------------- */
  /*  startStream — record the stream target for the caller            */
  /* ---------------------------------------------------------------- */

  const startStream = useCallback((ingestionId: string, url: string) => {
    streamRef.current = { ingestionId, url };
    // Reset state for a new stream
    setMessages([]);
    setCurrentStep("upload");
    setIsComplete(false);
    setIsPaused(false);
    setPendingQuestion(null);
    setClassification(null);
    setMapping(null);
    setError(null);
  }, []);

  /* ---------------------------------------------------------------- */
  /*  answerQuestion — clear pending question and resume               */
  /* ---------------------------------------------------------------- */

  const answerQuestion = useCallback(
    (questionId: string, answer: string) => {
      setPendingQuestion(null);
      setIsPaused(false);
      setMessages((prev) => [
        ...prev,
        { id: nextMsgId(), role: "user", text: answer },
      ]);
    },
    []
  );

  return {
    messages,
    currentStep,
    isComplete,
    isPaused,
    pendingQuestion,
    classification,
    mapping,
    error,
    startStream,
    answerQuestion,
    processEvent,
  };
}
