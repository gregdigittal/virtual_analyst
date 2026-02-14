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
        <p className="text-sm uppercase tracking-widest text-muted-foreground">
          Virtual Analyst
        </p>
        <h1 className="text-4xl font-semibold tracking-tight">
          Deterministic financial modeling with an LLM-assisted draft layer.
        </h1>
        <p className="text-lg text-muted-foreground">
          This environment is ready for hosted testing and continuous delivery.
        </p>
      </div>
      <div className="flex flex-col gap-4">
        <Link
          href="/login"
          className="inline-flex items-center rounded-md bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700"
        >
          Sign in
        </Link>
        <div className="rounded-lg border border-border bg-card p-4 text-sm text-card-foreground">
          API health: <span className="font-medium">/api/v1/health/live</span>
        </div>
      </div>
    </main>
  );
}
