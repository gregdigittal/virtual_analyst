"use client";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type ImportStep = "upload" | "classify" | "map" | "review";

type StepState = "done" | "current" | "pending";

interface StepDef {
  id: ImportStep;
  label: string;
}

/* ------------------------------------------------------------------ */
/*  Step metadata                                                      */
/* ------------------------------------------------------------------ */

const STEPS: StepDef[] = [
  { id: "upload", label: "Upload" },
  { id: "classify", label: "Classify" },
  { id: "map", label: "Map" },
  { id: "review", label: "Review" },
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

/* ------------------------------------------------------------------ */
/*  Per-state styling                                                  */
/* ------------------------------------------------------------------ */

const circleClass: Record<StepState, string> = {
  done: "bg-va-success text-white",
  current: "border-2 border-va-blue text-va-blue bg-transparent",
  pending: "border-2 border-va-border text-va-text2 bg-transparent",
};

const labelClass: Record<StepState, string> = {
  done: "text-va-success font-medium",
  current: "text-va-blue font-medium",
  pending: "text-va-text2",
};

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
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function getState(stepIndex: number, currentIndex: number): StepState {
  if (stepIndex < currentIndex) return "done";
  if (stepIndex === currentIndex) return "current";
  return "pending";
}

/* ------------------------------------------------------------------ */
/*  ImportStepper                                                      */
/* ------------------------------------------------------------------ */

export function ImportStepper({ currentStep }: { currentStep: ImportStep }) {
  const currentIndex = STEPS.findIndex((s) => s.id === currentStep);

  return (
    <nav aria-label="Import progress" className="w-full">
      <ol className="flex items-center">
        {STEPS.map((def, idx) => {
          const state = getState(idx, currentIndex);

          return (
            <li
              key={def.id}
              className={`flex items-center ${
                idx < STEPS.length - 1 ? "flex-1" : ""
              }`}
            >
              <div
                data-step={def.id}
                data-state={state}
                aria-label={`Step ${idx + 1}: ${def.label} (${state})`}
              >
                <div className="flex flex-col items-center gap-1.5">
                  {/* Circle */}
                  <div
                    className={`flex h-8 w-8 items-center justify-center rounded-full ${circleClass[state]}`}
                  >
                    {state === "done" ? (
                      <CheckIcon />
                    ) : (
                      <span className="text-xs font-semibold">{idx + 1}</span>
                    )}
                  </div>
                  {/* Label */}
                  <span className={`text-xs ${labelClass[state]}`}>
                    {def.label}
                  </span>
                </div>
              </div>
              {idx < STEPS.length - 1 && (
                <Connector active={state === "done" || state === "current"} />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
