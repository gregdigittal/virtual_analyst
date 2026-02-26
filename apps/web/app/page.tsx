import { createClient } from "@/lib/supabase/server";
import { PublicFooter } from "@/components/PublicFooter";
import { PublicHeader } from "@/components/PublicHeader";
import Image from "next/image";
import Link from "next/link";
import { redirect } from "next/navigation";

export default async function LandingPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (user) {
    const params = await searchParams;
    const next = params?.next;
    const safeNext =
      next && next.startsWith("/") && !next.startsWith("//")
        ? next
        : "/baselines";
    redirect(safeNext);
  }

  return (
    <div className="min-h-screen flex flex-col">
      <PublicHeader />

      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden border-b border-va-border bg-gradient-to-b from-va-panel/50 to-va-midnight">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
            <div className="mx-auto max-w-3xl text-center">
              <Image
                src="/va-icon.svg"
                alt="Virtual Analyst logo"
                width={96}
                height={96}
                className="mx-auto h-20 w-20 sm:h-24 sm:w-24"
                priority
              />
              <h1 className="mt-6 font-brand text-4xl font-bold tracking-tight text-va-text sm:text-5xl md:text-6xl">
                One Platform for the Full Financial Modeling Workflow
              </h1>
              <p className="mt-6 text-lg leading-relaxed text-va-text2 sm:text-xl">
                From AFS upload to board pack — AI-powered modeling, Monte Carlo simulation, and automated reporting.
              </p>
              <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
                <Link
                  href="/signup"
                  className="inline-flex w-full items-center justify-center rounded-va-sm bg-va-blue px-6 py-3 text-base font-medium text-white hover:bg-va-blue/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight shadow-va-glow-blue sm:w-auto"
                >
                  Get started free
                </Link>
                <Link
                  href="#features"
                  className="inline-flex w-full items-center justify-center rounded-va-sm border border-va-border bg-transparent px-6 py-3 text-base font-medium text-va-text hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight sm:w-auto"
                >
                  See how it works &rarr;
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* Feature Showcase */}
        <section id="features" className="border-b border-va-border bg-va-midnight py-16 sm:py-24" aria-labelledby="features-heading">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <h2 id="features-heading" className="font-brand text-2xl font-bold text-va-text sm:text-3xl text-center">
              Four stages. One platform.
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-center text-va-text2">
              From AFS upload to board pack, every step of the financial modeling workflow lives in Virtual Analyst.
            </p>
            <div className="mt-12 grid gap-8 sm:grid-cols-2">
              {/* Setup */}
              <div className="rounded-va-lg border border-va-border bg-va-panel/80 p-6">
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-va-blue/20 text-va-blue font-brand text-lg font-bold" aria-hidden="true">1</span>
                  <h3 className="font-brand text-lg font-semibold text-va-text">Setup</h3>
                </div>
                <ul className="mt-4 space-y-2 text-sm text-va-text2">
                  <li className="flex items-start gap-2"><span className="text-va-blue" aria-hidden="true">&bull;</span>Import Excel workbooks</li>
                  <li className="flex items-start gap-2"><span className="text-va-blue" aria-hidden="true">&bull;</span>Upload annual financial statements</li>
                  <li className="flex items-start gap-2"><span className="text-va-blue" aria-hidden="true">&bull;</span>14+ industry templates</li>
                  <li className="flex items-start gap-2"><span className="text-va-blue" aria-hidden="true">&bull;</span>AI-powered industry detection</li>
                </ul>
              </div>
              {/* Configure */}
              <div className="rounded-va-lg border border-va-border bg-va-panel/80 p-6">
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-va-violet/20 text-va-violet font-brand text-lg font-bold" aria-hidden="true">2</span>
                  <h3 className="font-brand text-lg font-semibold text-va-text">Configure</h3>
                </div>
                <ul className="mt-4 space-y-2 text-sm text-va-text2">
                  <li className="flex items-start gap-2"><span className="text-va-violet" aria-hidden="true">&bull;</span>Assumption editor</li>
                  <li className="flex items-start gap-2"><span className="text-va-violet" aria-hidden="true">&bull;</span>AI driver detection</li>
                  <li className="flex items-start gap-2"><span className="text-va-violet" aria-hidden="true">&bull;</span>Scenario comparison</li>
                  <li className="flex items-start gap-2"><span className="text-va-violet" aria-hidden="true">&bull;</span>Correlation configuration</li>
                </ul>
              </div>
              {/* Analyze */}
              <div className="rounded-va-lg border border-va-border bg-va-panel/80 p-6">
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-va-success/20 text-va-success font-brand text-lg font-bold" aria-hidden="true">3</span>
                  <h3 className="font-brand text-lg font-semibold text-va-text">Analyze</h3>
                </div>
                <ul className="mt-4 space-y-2 text-sm text-va-text2">
                  <li className="flex items-start gap-2"><span className="text-va-success" aria-hidden="true">&bull;</span>Monte Carlo simulation</li>
                  <li className="flex items-start gap-2"><span className="text-va-success" aria-hidden="true">&bull;</span>Sensitivity analysis</li>
                  <li className="flex items-start gap-2"><span className="text-va-success" aria-hidden="true">&bull;</span>Budget tracking</li>
                  <li className="flex items-start gap-2"><span className="text-va-success" aria-hidden="true">&bull;</span>Covenant monitoring</li>
                </ul>
              </div>
              {/* Report */}
              <div className="rounded-va-lg border border-va-border bg-va-panel/80 p-6">
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-va-magenta/20 text-va-magenta font-brand text-lg font-bold" aria-hidden="true">4</span>
                  <h3 className="font-brand text-lg font-semibold text-va-text">Report</h3>
                </div>
                <ul className="mt-4 space-y-2 text-sm text-va-text2">
                  <li className="flex items-start gap-2"><span className="text-va-magenta" aria-hidden="true">&bull;</span>Board pack generation</li>
                  <li className="flex items-start gap-2"><span className="text-va-magenta" aria-hidden="true">&bull;</span>Investment memos</li>
                  <li className="flex items-start gap-2"><span className="text-va-magenta" aria-hidden="true">&bull;</span>Document management</li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="border-b border-va-border bg-va-midnight py-16 sm:py-24" aria-labelledby="cta-heading">
          <div className="mx-auto max-w-3xl px-4 text-center sm:px-6">
            <h2 id="cta-heading" className="font-brand text-2xl font-bold text-va-text sm:text-3xl">
              Ready to streamline your modeling?
            </h2>
            <p className="mt-4 text-va-text2">
              Create your account and connect your first baseline in minutes.
            </p>
            <div className="mt-8">
              <Link
                href="/signup"
                className="inline-flex items-center rounded-va-sm bg-va-blue px-6 py-3 text-base font-medium text-white hover:bg-va-blue/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight shadow-va-glow-blue"
              >
                Get started free
              </Link>
            </div>
          </div>
        </section>

        <PublicFooter />
      </main>
    </div>
  );
}
