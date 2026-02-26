"use client";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type MessageRole = "assistant" | "user" | "status";

export interface ChatMessageProps {
  role: MessageRole;
  text: string;
}

/* ------------------------------------------------------------------ */
/*  Avatar                                                             */
/* ------------------------------------------------------------------ */

function Avatar({ role }: { role: "assistant" | "user" }) {
  if (role === "assistant") {
    return (
      <div
        className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-va-blue/20 text-xs font-semibold text-va-blue"
        aria-label="Assistant"
      >
        AI
      </div>
    );
  }
  return (
    <div
      className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-va-surface text-xs font-semibold text-va-text2"
      aria-label="You"
    >
      U
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  ChatMessage                                                        */
/* ------------------------------------------------------------------ */

export function ChatMessage({ role, text }: ChatMessageProps) {
  /* Status messages: plain italic, no bubble */
  if (role === "status") {
    return (
      <div className="px-4 py-1.5 text-center text-sm italic text-va-text2">
        {text}
      </div>
    );
  }

  const isUser = role === "user";

  return (
    <div
      className={`flex items-start gap-2 px-3 py-2 ${
        isUser ? "flex-row-reverse" : "flex-row"
      }`}
    >
      <Avatar role={role} />
      <div
        className={`max-w-[80%] rounded-va-sm px-3 py-2 text-sm ${
          isUser
            ? "bg-va-panel text-va-text"
            : "bg-va-blue/10 text-va-text"
        }`}
      >
        {text}
      </div>
    </div>
  );
}
