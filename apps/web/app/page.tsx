import { createClient } from "@/lib/supabase/server";
import Link from "next/link";
import { redirect } from "next/navigation";

export default async function HomePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (user) {
    redirect("/baselines");
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-start gap-6 px-6 py-16">
      <div className="space-y-3">
        <p className="font-brand text-sm uppercase tracking-widest text-va-text2">
          Virtual Analyst
        </p>
        <h1 className="font-brand text-4xl font-semibold tracking-tight text-va-text">
          Deterministic financial modeling with an LLM-assisted draft layer.
        </h1>
        <p className="text-lg text-va-text2">
          This environment is ready for hosted testing and continuous delivery.
        </p>
      </div>
      <div className="flex flex-col gap-4">
        <Link
          href="/login"
          className="inline-flex items-center rounded-va-sm bg-va-blue px-4 py-2 font-medium text-va-text hover:bg-va-blue/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight shadow-va-glow-blue"
        >
          Sign in
        </Link>
        <div className="rounded-va-lg border border-va-border bg-va-panel/80 p-4 text-sm text-va-text">
          API health: <span className="font-mono font-medium">/api/v1/health/live</span>
        </div>
      </div>
    </main>
  );
}
