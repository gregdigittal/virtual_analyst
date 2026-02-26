import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "How Virtual Analyst Compares",
  description:
    "See how Virtual Analyst stacks up against spreadsheets and enterprise FP&A tools for financial modeling.",
};

/* ------------------------------------------------------------------ */
/*  Indicator icons                                                    */
/* ------------------------------------------------------------------ */

function CheckIcon() {
  return (
    <svg
      className="h-5 w-5 text-va-success"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-label="Strength"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg
      className="h-5 w-5 text-va-danger"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-label="Weakness"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function TildeIcon() {
  return (
    <span className="inline-flex h-5 w-5 items-center justify-center text-va-warning font-bold text-lg" aria-label="Partial">
      ~
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Indicator helper                                                   */
/* ------------------------------------------------------------------ */

type Indicator = "check" | "x" | "partial";

function IndicatorIcon({ type }: { type: Indicator }) {
  switch (type) {
    case "check":
      return <CheckIcon />;
    case "x":
      return <XIcon />;
    case "partial":
      return <TildeIcon />;
  }
}

/* ------------------------------------------------------------------ */
/*  ComparisonTable                                                    */
/* ------------------------------------------------------------------ */

interface ComparisonRow {
  feature: string;
  competitor: string;
  competitorIndicator: Indicator;
  va: string;
  vaIndicator: Indicator;
}

function ComparisonTable({
  title,
  description,
  rows,
  competitorLabel,
}: {
  title: string;
  description: string;
  rows: ComparisonRow[];
  competitorLabel: string;
}) {
  return (
    <div className="rounded-va-lg border border-va-border bg-va-panel/80 overflow-hidden">
      <div className="px-6 py-5 border-b border-va-border">
        <h2 className="font-brand text-xl font-bold text-va-text">{title}</h2>
        <p className="mt-1 text-sm text-va-text2">{description}</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[600px] text-sm">
          <thead>
            <tr className="border-b border-va-border bg-va-midnight/50">
              <th className="px-6 py-3 text-left font-medium text-va-text2">Feature</th>
              <th className="px-6 py-3 text-left font-medium text-va-text2">{competitorLabel}</th>
              <th className="px-6 py-3 text-left font-medium text-va-text2">Virtual Analyst</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={row.feature}
                className={
                  i % 2 === 0
                    ? "border-b border-va-border/50"
                    : "border-b border-va-border/50 bg-va-surface/30"
                }
              >
                <td className="px-6 py-3 font-medium text-va-text">{row.feature}</td>
                <td className="px-6 py-3 text-va-text2">
                  <span className="flex items-center gap-2">
                    <IndicatorIcon type={row.competitorIndicator} />
                    {row.competitor}
                  </span>
                </td>
                <td className="px-6 py-3 text-va-text">
                  <span className="flex items-center gap-2">
                    <IndicatorIcon type={row.vaIndicator} />
                    {row.va}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Data                                                               */
/* ------------------------------------------------------------------ */

const spreadsheetRows: ComparisonRow[] = [
  {
    feature: "Monte Carlo simulation",
    competitor: "Manual VBA macros",
    competitorIndicator: "x",
    va: "Built-in, one click",
    vaIndicator: "check",
  },
  {
    feature: "Scenario comparison",
    competitor: "Copy worksheets",
    competitorIndicator: "x",
    va: "Side-by-side diff",
    vaIndicator: "check",
  },
  {
    feature: "Collaboration",
    competitor: "File sharing",
    competitorIndicator: "partial",
    va: "Real-time, versioned",
    vaIndicator: "check",
  },
  {
    feature: "AI assistance",
    competitor: "None",
    competitorIndicator: "x",
    va: "Industry detection, driver analysis",
    vaIndicator: "check",
  },
  {
    feature: "Audit trail",
    competitor: "None",
    competitorIndicator: "x",
    va: "Full version history",
    vaIndicator: "check",
  },
  {
    feature: "Sensitivity analysis",
    competitor: "Manual data tables",
    competitorIndicator: "partial",
    va: "Tornado charts, heatmaps",
    vaIndicator: "check",
  },
  {
    feature: "Board pack generation",
    competitor: "Manual",
    competitorIndicator: "x",
    va: "Automated, drag-and-drop",
    vaIndicator: "check",
  },
];

const enterpriseRows: ComparisonRow[] = [
  {
    feature: "Time to first model",
    competitor: "Weeks to months",
    competitorIndicator: "x",
    va: "Minutes",
    vaIndicator: "check",
  },
  {
    feature: "Pricing",
    competitor: "$50K-500K+/year",
    competitorIndicator: "x",
    va: "Fraction of the cost",
    vaIndicator: "check",
  },
  {
    feature: "AI-native",
    competitor: "Bolt-on",
    competitorIndicator: "partial",
    va: "Built from ground up",
    vaIndicator: "check",
  },
  {
    feature: "Monte Carlo",
    competitor: "Limited or add-on",
    competitorIndicator: "partial",
    va: "Core feature",
    vaIndicator: "check",
  },
  {
    feature: "Template marketplace",
    competitor: "Vendor-locked",
    competitorIndicator: "x",
    va: "Open, community-driven",
    vaIndicator: "check",
  },
  {
    feature: "Implementation support",
    competitor: "Requires consultants",
    competitorIndicator: "x",
    va: "Self-service with AI guidance",
    vaIndicator: "check",
  },
];

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function CompareLandingPage() {
  return (
    <div className="min-h-screen flex flex-col bg-va-midnight">
      {/* Header — matches landing page */}
      <header className="sticky top-0 z-50 border-b border-va-border bg-va-midnight/95 backdrop-blur supports-[backdrop-filter]:bg-va-midnight/80">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link
            href="/"
            className="flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded-va-xs"
            aria-label="Virtual Analyst home"
          >
            <Image
              src="/va-icon.svg"
              alt=""
              width={32}
              height={32}
              className="h-8 w-8"
            />
            <span className="font-brand text-lg font-semibold text-va-text">
              Virtual Analyst
            </span>
          </Link>
          <nav className="flex items-center gap-3" aria-label="Main navigation">
            <Link
              href="/login"
              className="rounded-va-xs px-3 py-2 text-sm font-medium text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="inline-flex items-center rounded-va-sm bg-va-blue px-4 py-2 text-sm font-medium text-white hover:bg-va-blue/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight shadow-va-glow-blue"
            >
              Get started
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        {/* Page heading */}
        <section className="border-b border-va-border bg-gradient-to-b from-va-panel/50 to-va-midnight py-16 sm:py-24">
          <div className="mx-auto max-w-4xl px-4 text-center sm:px-6">
            <h1 className="font-brand text-3xl font-bold tracking-tight text-va-text sm:text-4xl md:text-5xl">
              How Virtual Analyst Compares
            </h1>
            <p className="mt-4 text-lg text-va-text2">
              Whether you&apos;re outgrowing spreadsheets or looking for a leaner alternative to enterprise FP&amp;A, see how we stack up.
            </p>
          </div>
        </section>

        {/* Comparison tables */}
        <section className="py-16 sm:py-24">
          <div className="mx-auto max-w-5xl space-y-12 px-4 sm:px-6">
            <ComparisonTable
              title="vs. Spreadsheets"
              description="Excel and Google Sheets are flexible, but financial modeling demands more."
              competitorLabel="Excel / Sheets"
              rows={spreadsheetRows}
            />

            <ComparisonTable
              title="vs. Enterprise FP&A"
              description="Legacy platforms are powerful but come with heavyweight implementations and price tags."
              competitorLabel="Enterprise FP&A"
              rows={enterpriseRows}
            />
          </div>
        </section>

        {/* CTA */}
        <section className="border-t border-va-border bg-va-midnight py-16 sm:py-24">
          <div className="mx-auto max-w-3xl px-4 text-center sm:px-6">
            <h2 className="font-brand text-2xl font-bold text-va-text sm:text-3xl">
              Ready to see the difference?
            </h2>
            <p className="mt-4 text-va-text2">
              Create your free account and build your first model in minutes.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/signup"
                className="inline-flex items-center rounded-va-sm bg-va-blue px-6 py-3 text-base font-medium text-white hover:bg-va-blue/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight shadow-va-glow-blue"
              >
                Get started free
              </Link>
              <Link
                href="/"
                className="inline-flex items-center rounded-va-sm border border-va-border bg-transparent px-6 py-3 text-base font-medium text-va-text hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
              >
                Back to home
              </Link>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-va-border bg-va-ink py-8">
          <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6">
            <div className="flex items-center gap-2">
              <Image src="/va-icon.svg" alt="" width={24} height={24} className="h-6 w-6" />
              <span className="font-brand text-sm font-medium text-va-text2">Virtual Analyst</span>
            </div>
            <nav className="flex items-center gap-6" aria-label="Footer navigation">
              <Link
                href="/login"
                className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded-va-xs"
              >
                Sign in
              </Link>
              <Link
                href="/signup"
                className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded-va-xs"
              >
                Sign up
              </Link>
              <Link
                href="/compare"
                className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded-va-xs"
              >
                Compare
              </Link>
            </nav>
            <p className="text-xs text-va-muted">
              &copy; {new Date().getFullYear()} Virtual Analyst. All rights reserved.
            </p>
          </div>
        </footer>
      </main>
    </div>
  );
}
