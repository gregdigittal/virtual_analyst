import { createClient } from "@/lib/supabase/server";
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
      {/* Header */}
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
        {/* Hero */}
        <section className="relative overflow-hidden border-b border-va-border bg-gradient-to-b from-va-panel/50 to-va-midnight">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
            <div className="mx-auto max-w-3xl text-center">
              <p className="font-brand text-sm uppercase tracking-widest text-va-blue">
                Financial modeling, augmented
              </p>
              <h1 className="mt-4 font-brand text-4xl font-bold tracking-tight text-va-text sm:text-5xl md:text-6xl">
                Build better models in less time
              </h1>
              <p className="mt-6 text-lg leading-relaxed text-va-text2 sm:text-xl">
                Virtual Analyst combines LLM-assisted draft generation, Monte Carlo simulation, and valuation in one platform—so your team can focus on decisions, not spreadsheets.
              </p>
              <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
                <Link
                  href="/signup"
                  className="inline-flex w-full items-center justify-center rounded-va-sm bg-va-blue px-6 py-3 text-base font-medium text-white hover:bg-va-blue/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight shadow-va-glow-blue sm:w-auto"
                >
                  Start free trial
                </Link>
                <Link
                  href="/login"
                  className="inline-flex w-full items-center justify-center rounded-va-sm border border-va-border bg-transparent px-6 py-3 text-base font-medium text-va-text hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight sm:w-auto"
                >
                  Sign in
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* Value props */}
        <section className="border-b border-va-border bg-va-midnight py-16 sm:py-24" aria-labelledby="value-heading">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <h2 id="value-heading" className="sr-only">
              Why Virtual Analyst
            </h2>
            <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-va-lg border border-va-border bg-va-panel/80 p-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-va-sm bg-va-blue/20 text-va-blue" aria-hidden>
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <h3 className="mt-4 font-brand text-lg font-semibold text-va-text">
                  LLM-assisted drafts
                </h3>
                <p className="mt-2 text-sm text-va-text2">
                  Generate assumption sets and evidence-backed drafts from your baselines so you start from a solid first version, not a blank sheet.
                </p>
              </div>
              <div className="rounded-va-lg border border-va-border bg-va-panel/80 p-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-va-sm bg-va-violet/20 text-va-violet" aria-hidden>
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <h3 className="mt-4 font-brand text-lg font-semibold text-va-text">
                  Monte Carlo & valuation
                </h3>
                <p className="mt-2 text-sm text-va-text2">
                  Run simulations and DCF-style valuation in-app. Compare scenarios, track covenants, and share results with stakeholders.
                </p>
              </div>
              <div className="rounded-va-lg border border-va-border bg-va-panel/80 p-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-va-sm bg-va-success/20 text-va-success" aria-hidden>
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
                <h3 className="mt-4 font-brand text-lg font-semibold text-va-text">
                  Built for teams
                </h3>
                <p className="mt-2 text-sm text-va-text2">
                  Role-based access, document attachments, comments, and activity feeds. Keep everyone aligned on the same model and narrative.
                </p>
              </div>
              <div className="rounded-va-lg border border-va-border bg-va-panel/80 p-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-va-sm bg-va-magenta/20 text-va-magenta" aria-hidden>
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                </div>
                <h3 className="mt-4 font-brand text-lg font-semibold text-va-text">
                  Audit-ready
                </h3>
                <p className="mt-2 text-sm text-va-text2">
                  Append-only audit log, covenant tracking, and integrations that fit into your existing control environment.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Feature highlights */}
        <section className="border-b border-va-border bg-va-panel/30 py-16 sm:py-24" aria-labelledby="features-heading">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <h2 id="features-heading" className="font-brand text-2xl font-bold text-va-text sm:text-3xl text-center">
              One platform for the full workflow
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-center text-va-text2">
              From baseline models and scenarios to runs, memos, and stakeholder-ready outputs.
            </p>
            <ul className="mx-auto mt-12 grid max-w-4xl gap-4 sm:grid-cols-2" role="list">
              <li className="flex gap-3 rounded-va-lg border border-va-border bg-va-midnight/80 px-4 py-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-va-blue/20 text-va-blue text-xs font-medium" aria-hidden>1</span>
                <span className="text-va-text">Baselines & scenarios</span>
              </li>
              <li className="flex gap-3 rounded-va-lg border border-va-border bg-va-midnight/80 px-4 py-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-va-blue/20 text-va-blue text-xs font-medium" aria-hidden>2</span>
                <span className="text-va-text">LLM-assisted draft generation</span>
              </li>
              <li className="flex gap-3 rounded-va-lg border border-va-border bg-va-midnight/80 px-4 py-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-va-blue/20 text-va-blue text-xs font-medium" aria-hidden>3</span>
                <span className="text-va-text">Monte Carlo simulation & valuation</span>
              </li>
              <li className="flex gap-3 rounded-va-lg border border-va-border bg-va-midnight/80 px-4 py-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-va-blue/20 text-va-blue text-xs font-medium" aria-hidden>4</span>
                <span className="text-va-text">Memos, attachments & comments</span>
              </li>
            </ul>
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
            </nav>
            <p className="text-xs text-va-muted">
              © {new Date().getFullYear()} Virtual Analyst. All rights reserved.
            </p>
          </div>
        </footer>
      </main>
    </div>
  );
}
