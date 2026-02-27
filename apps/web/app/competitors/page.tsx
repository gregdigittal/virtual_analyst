import { PublicHeader } from "@/components/PublicHeader";
import { PublicFooter } from "@/components/PublicFooter";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "How Virtual Analyst Compares",
  description: "See how Virtual Analyst compares to spreadsheets and enterprise FP&A tools.",
};

function CheckIcon() {
  return <span className="text-va-success" role="img" aria-label="Supported">&#10003;</span>;
}
function XIcon() {
  return <span className="text-va-danger" role="img" aria-label="Not supported">&#10007;</span>;
}
function PartialIcon() {
  return <span className="text-va-warning" role="img" aria-label="Partial support">~</span>;
}

interface ComparisonRow {
  feature: string;
  competitor: React.ReactNode;
  va: React.ReactNode;
}

function ComparisonTable({ title, description, rows, competitorLabel }: {
  title: string;
  description: string;
  rows: ComparisonRow[];
  competitorLabel: string;
}) {
  return (
    <section className="mt-12">
      <h2 className="font-brand text-xl font-bold text-va-text sm:text-2xl">{title}</h2>
      <p className="mt-2 text-va-text2">{description}</p>
      <div className="mt-6 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-va-border">
              <th className="py-3 pr-4 text-left font-medium text-va-text2">Feature</th>
              <th className="px-4 py-3 text-center font-medium text-va-text2">{competitorLabel}</th>
              <th className="px-4 py-3 text-center font-medium text-va-blue">Virtual Analyst</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.feature} className="border-b border-va-border/50">
                <td className="py-3 pr-4 text-va-text">{row.feature}</td>
                <td className="px-4 py-3 text-center">{row.competitor}</td>
                <td className="px-4 py-3 text-center">{row.va}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function ComparePage() {
  return (
    <div className="min-h-screen flex flex-col">
      <PublicHeader />

      <main className="flex-1">
        <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 sm:py-24">
          <h1 className="font-brand text-3xl font-bold text-va-text sm:text-4xl text-center">
            How Virtual Analyst Compares
          </h1>
          <p className="mt-4 text-center text-lg text-va-text2">
            Whether you are upgrading from spreadsheets or looking for a modern alternative to enterprise FP&amp;A tools.
          </p>

          <ComparisonTable
            title="vs. Spreadsheets"
            description="Excel and Google Sheets are flexible but lack the automation and rigor that financial modeling demands."
            competitorLabel="Excel / Sheets"
            rows={[
              { feature: "Monte Carlo simulation", competitor: <span className="text-va-text2">Manual VBA macros</span>, va: <><CheckIcon /> Built-in, one click</> },
              { feature: "Scenario comparison", competitor: <span className="text-va-text2">Copy worksheets</span>, va: <><CheckIcon /> Side-by-side diff</> },
              { feature: "Collaboration", competitor: <span className="text-va-text2">File sharing</span>, va: <><CheckIcon /> Real-time, versioned</> },
              { feature: "AI assistance", competitor: <><XIcon /> None</>, va: <><CheckIcon /> Industry detection, driver analysis</> },
              { feature: "Audit trail", competitor: <><XIcon /> None</>, va: <><CheckIcon /> Full version history</> },
              { feature: "Sensitivity analysis", competitor: <span className="text-va-text2">Manual data tables</span>, va: <><CheckIcon /> Tornado charts, heatmaps</> },
              { feature: "Board pack generation", competitor: <><XIcon /> Manual</>, va: <><CheckIcon /> Automated, drag-and-drop</> },
            ]}
          />

          <ComparisonTable
            title="vs. Enterprise FP&amp;A"
            description="Anaplan, Adaptive Planning, and Vena are powerful but come with enterprise complexity and cost."
            competitorLabel="Enterprise FP&amp;A"
            rows={[
              { feature: "Time to first model", competitor: <span className="text-va-text2">Weeks to months</span>, va: <><CheckIcon /> Minutes</> },
              { feature: "Pricing", competitor: <span className="text-va-text2">$50K-500K+/year</span>, va: <><CheckIcon /> Fraction of the cost</> },
              { feature: "AI-native", competitor: <><PartialIcon /> Bolt-on</>, va: <><CheckIcon /> Built from ground up</> },
              { feature: "Monte Carlo simulation", competitor: <><PartialIcon /> Limited or add-on</>, va: <><CheckIcon /> Core feature</> },
              { feature: "Template marketplace", competitor: <span className="text-va-text2">Vendor-locked</span>, va: <><CheckIcon /> Open, community-driven</> },
              { feature: "Implementation support", competitor: <span className="text-va-text2">Requires consultants</span>, va: <><CheckIcon /> Self-service with AI guidance</> },
            ]}
          />

          <div className="mt-16 text-center">
            <Link
              href="/signup"
              className="inline-flex items-center rounded-va-sm bg-va-blue px-6 py-3 text-base font-medium text-white hover:bg-va-blue/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight shadow-va-glow-blue"
            >
              Start your free trial
            </Link>
          </div>
        </div>
      </main>

      <PublicFooter />
    </div>
  );
}
