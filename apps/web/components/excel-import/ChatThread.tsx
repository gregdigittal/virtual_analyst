"use client";

import { useEffect, useRef } from "react";
import { ChatMessage, type MessageRole } from "./ChatMessage";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ThreadMessage {
  id: string;
  role: MessageRole;
  text: string;
}

export interface ChatThreadProps {
  messages: ThreadMessage[];
  children?: React.ReactNode; // Slot for QuestionCard
}

/* ------------------------------------------------------------------ */
/*  ChatThread                                                         */
/* ------------------------------------------------------------------ */

export function ChatThread({ messages, children }: ChatThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  /* Auto-scroll to bottom on new messages */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  return (
    <div className="flex h-full flex-col overflow-y-auto rounded-va-sm border border-va-border bg-va-midnight/50 p-2">
      {messages.map((msg) => (
        <ChatMessage key={msg.id} role={msg.role} text={msg.text} />
      ))}
      {children}
      <div ref={bottomRef} />
    </div>
  );
}
