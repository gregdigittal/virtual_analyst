"use client";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface AgentQuestion {
  id: string;
  text: string;
  options: string[];
  context?: string;
}

export interface QuestionCardProps {
  question: AgentQuestion;
  onAnswer: (questionId: string, answer: string) => void;
  disabled?: boolean;
}

/* ------------------------------------------------------------------ */
/*  QuestionCard                                                       */
/* ------------------------------------------------------------------ */

export function QuestionCard({ question, onAnswer, disabled }: QuestionCardProps) {
  return (
    <div className="rounded-va-sm border border-va-blue/30 bg-va-blue/5 p-4">
      <p className="text-sm font-medium text-va-text">{question.text}</p>

      {question.context && (
        <p className="mt-1 text-xs text-va-text2">{question.context}</p>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        {question.options.map((option) => (
          <button
            key={option}
            type="button"
            disabled={disabled}
            onClick={() => onAnswer(question.id, option)}
            className="rounded-va-xs border border-va-border bg-va-panel px-3 py-1.5 text-sm text-va-text transition hover:border-va-blue hover:text-va-blue disabled:opacity-50 disabled:hover:border-va-border disabled:hover:text-va-text"
          >
            {option}
          </button>
        ))}
      </div>
    </div>
  );
}
