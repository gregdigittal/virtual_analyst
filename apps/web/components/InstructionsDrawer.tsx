"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getInstructionsForPath, type InstructionSection } from "@/lib/instructions-config";

// ─── Icons ────────────────────────────────────────

function BookIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
    </svg>
  );
}

function CloseIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function ArrowRightIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

function CheckCircleIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}

function LightbulbIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <line x1="9" y1="18" x2="15" y2="18" /><line x1="10" y1="22" x2="14" y2="22" />
      <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14" />
    </svg>
  );
}

// ─── Instructions Button (floating) ──────────────

export function InstructionsButton() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const instructions = getInstructionsForPath(pathname);

  // Close drawer on route change
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open]);

  // Don't render button if no instructions available for this page
  if (!instructions) return null;

  return (
    <>
      {/* Floating Instructions Button */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2 rounded-full bg-va-blue px-4 py-2.5 text-sm font-medium text-white shadow-lg shadow-va-blue/25 transition-all hover:bg-va-blue/90 hover:shadow-va-blue/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
        aria-label="Page instructions"
      >
        <BookIcon className="h-4 w-4" />
        <span className="hidden sm:inline">Instructions</span>
      </button>

      {/* Drawer Overlay */}
      {open && (
        <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="Page instructions">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />

          {/* Drawer Panel */}
          <div className="relative w-full max-w-md animate-slide-in-right overflow-y-auto bg-va-panel border-l border-va-border shadow-2xl">
            <InstructionsContent
              instructions={instructions}
              onClose={() => setOpen(false)}
            />
          </div>
        </div>
      )}
    </>
  );
}

// ─── Instructions Content ────────────────────────

function InstructionsContent({
  instructions,
  onClose,
}: {
  instructions: InstructionSection;
  onClose: () => void;
}) {
  return (
    <div className="flex flex-col">
      {/* Header */}
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-va-border bg-va-panel/95 backdrop-blur px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-va-xs bg-va-blue/15 text-va-blue">
            <BookIcon className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-va-text">
              {instructions.title}
            </h2>
            <span className="text-xs text-va-text2">Chapter {instructions.chapter}</span>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-va-xs p-1.5 text-va-text2 hover:bg-white/5 hover:text-va-text transition focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue"
          aria-label="Close instructions"
        >
          <CloseIcon className="h-5 w-5" />
        </button>
      </div>

      <div className="px-5 py-5 space-y-6">
        {/* Overview */}
        <section>
          <p className="text-sm leading-relaxed text-va-text2">
            {instructions.overview}
          </p>
        </section>

        {/* Prerequisites */}
        {instructions.prerequisites.length > 0 && (
          <section>
            <h3 className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-va-warning">
              Prerequisites
            </h3>
            <div className="space-y-1.5">
              {instructions.prerequisites.map((pre) => (
                <Link
                  key={pre.href}
                  href={pre.href}
                  onClick={onClose}
                  className="flex items-center gap-2 rounded-va-xs border border-va-warning/20 bg-va-warning/5 px-3 py-2 text-sm text-va-warning hover:bg-va-warning/10 transition"
                >
                  <ArrowRightIcon className="h-3.5 w-3.5 shrink-0" />
                  {pre.label}
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* Step-by-step Guide */}
        <section>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-va-text2">
            How to use this page
          </h3>
          <ol className="space-y-2.5">
            {instructions.steps.map((step, i) => (
              <li key={i} className="flex gap-3">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-va-blue/15 text-[10px] font-bold text-va-blue">
                  {i + 1}
                </span>
                <span className="text-sm leading-relaxed text-va-text">
                  {step}
                </span>
              </li>
            ))}
          </ol>
        </section>

        {/* Tips */}
        {instructions.tips && instructions.tips.length > 0 && (
          <section>
            <h3 className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-va-text2">
              Tips
            </h3>
            <div className="space-y-2">
              {instructions.tips.map((tip, i) => (
                <div
                  key={i}
                  className="flex gap-2.5 rounded-va-xs border border-va-blue/15 bg-va-blue/5 px-3 py-2"
                >
                  <LightbulbIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-va-blue" />
                  <span className="text-sm text-va-text2">{tip}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Related Pages */}
        {instructions.relatedPages.length > 0 && (
          <section>
            <h3 className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-va-text2">
              Related Pages
            </h3>
            <div className="flex flex-wrap gap-2">
              {instructions.relatedPages.map((page) => (
                <Link
                  key={page.href}
                  href={page.href}
                  onClick={onClose}
                  className="inline-flex items-center gap-1.5 rounded-full border border-va-border bg-white/5 px-3 py-1 text-xs font-medium text-va-text2 hover:border-va-blue/40 hover:text-va-blue transition"
                >
                  {page.label}
                  <ArrowRightIcon className="h-3 w-3" />
                </Link>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
