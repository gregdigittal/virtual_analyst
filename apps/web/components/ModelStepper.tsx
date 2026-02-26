"use client";

import Link from "next/link";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type StepState = "done" | "current" | "pending" | "locked";

export interface StepStates {
  start?: StepState;
  company?: StepState;
  historical?: StepState;
  assumptions?: StepState;
  correlations?: StepState;
  run?: StepState;
  review?: StepState;
}

export interface ModelStepperProps {
  steps: StepStates;
  baselineId?: string;
}

/* ------------------------------------------------------------------ */
/*  Step metadata                                                      */
/* ------------------------------------------------------------------ */

type StepId = keyof StepStates;

interface StepDef {
  id: StepId;
  label: string;
  href: (baselineId: string) => string;
}

const STEPS: StepDef[] = [
  { id: "start", label: "Start", href: (id) => `/baselines/${id}` },
  { id: "company", label: "Company", href: (id) => `/baselines/${id}` },
  {
    id: "historical",
    label: "Historical",
    href: (id) => `/documents?baseline=${id}`,
  },
  {
    id: "assumptions",
    label: "Assumptions",
    href: (id) => `/drafts?baseline=${id}`,
  },
  {
    id: "correlations",
    label: "Correlations",
    href: (id) => `/drafts?baseline=${id}&tab=correlations`,
  },
  { id: "run", label: "Run", href: (id) => `/baselines/${id}` },
  { id: "review", label: "Review", href: (id) => `/runs?baseline=${id}` },
];

/* ------------------------------------------------------------------ */
/*  Icons                                                              */
/* ------------------------------------------------------------------ */

function CheckIcon() {
  return (
    <svg
      className="h-4 w-4"
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M3 8.5l3.5 3.5 6.5-7"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg
      className="h-3.5 w-3.5"
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      <rect
        x="3"
        y="7"
        width="10"
        height="7"
        rx="1.5"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M5 7V5a3 3 0 0 1 6 0v2"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Per-state styling                                                  */
/* ------------------------------------------------------------------ */

const circleClass: Record<StepState, string> = {
  done: "bg-va-success text-white",
  current: "border-2 border-va-blue text-va-blue bg-transparent",
  pending: "border-2 border-va-border text-va-text2 bg-transparent",
  locked: "border-2 border-va-border/50 text-va-text2/50 bg-transparent",
};

const labelClass: Record<StepState, string> = {
  done: "text-va-success font-medium",
  current: "text-va-blue font-medium",
  pending: "text-va-text2",
  locked: "text-va-text2/50",
};

/* ------------------------------------------------------------------ */
/*  Circle content                                                     */
/* ------------------------------------------------------------------ */

function CircleContent({
  state,
  index,
}: {
  state: StepState;
  index: number;
}) {
  switch (state) {
    case "done":
      return <CheckIcon />;
    case "current":
      return (
        <span className="block h-2.5 w-2.5 rounded-full bg-va-blue" />
      );
    case "locked":
      return <LockIcon />;
    default:
      return <span className="text-xs font-semibold">{index + 1}</span>;
  }
}

/* ------------------------------------------------------------------ */
/*  Connector                                                          */
/* ------------------------------------------------------------------ */

function Connector({ active }: { active: boolean }) {
  return (
    <div
      className={`mx-1 h-0.5 flex-1 rounded-full ${
        active ? "bg-va-blue" : "bg-va-border"
      }`}
      aria-hidden="true"
    />
  );
}

/* ------------------------------------------------------------------ */
/*  ModelStepper                                                       */
/* ------------------------------------------------------------------ */

export function ModelStepper({ steps, baselineId }: ModelStepperProps) {
  return (
    <nav aria-label="Model progress" className="w-full">
      <ol className="flex items-center">
        {STEPS.map((def, idx) => {
          const state: StepState = steps[def.id] ?? "pending";
          const isClickable =
            (state === "done" || state === "current") && !!baselineId;

          const stepContent = (
            <div className="flex flex-col items-center gap-1.5">
              {/* Circle */}
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full ${circleClass[state]}`}
              >
                <CircleContent state={state} index={idx} />
              </div>
              {/* Label */}
              <span className={`text-xs ${labelClass[state]}`}>
                {def.label}
              </span>
            </div>
          );

          return (
            <li
              key={def.id}
              className={`flex items-center ${
                idx < STEPS.length - 1 ? "flex-1" : ""
              }`}
            >
              <div data-step={def.id} data-state={state}>
                {isClickable ? (
                  <Link
                    href={def.href(baselineId)}
                    className="focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue rounded-va-sm"
                  >
                    {stepContent}
                  </Link>
                ) : (
                  stepContent
                )}
              </div>
              {idx < STEPS.length - 1 && (
                <Connector
                  active={state === "done" || state === "current"}
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
