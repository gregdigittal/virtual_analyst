"use client";

import { createClient } from "@/lib/supabase/client";
import Link from "next/link";
import { useRouter } from "next/navigation";

export function Nav() {
  const router = useRouter();

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
    router.refresh();
  }

  return (
    <nav className="border-b border-border bg-card">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-6">
          <Link
            href="/baselines"
            className="text-sm font-medium text-foreground hover:text-muted-foreground"
          >
            Baselines
          </Link>
          <Link
            href="/runs"
            className="text-sm font-medium text-foreground hover:text-muted-foreground"
          >
            Runs
          </Link>
          <Link
            href="/dashboard"
            className="text-sm font-medium text-foreground hover:text-muted-foreground"
          >
            Dashboard
          </Link>
        </div>
        <button
          type="button"
          onClick={handleSignOut}
          className="text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}
