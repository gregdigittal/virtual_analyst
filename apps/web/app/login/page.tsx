"use client";

import { VAButton, VAInput } from "@/components/ui";
import { createClient } from "@/lib/supabase/client";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/baselines";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const supabase = createClient();
      const { error: err } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (err) {
        setError(err.message);
        return;
      }
      router.push(next);
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen flex-col justify-center px-6 py-12">
      <div className="mx-auto w-full max-w-md space-y-8">
        <div className="flex justify-center">
          <Image
            src="/va-wordmark.svg"
            alt="Virtual Analyst"
            width={400}
            height={107}
            className="h-auto w-full max-w-[320px]"
            priority
          />
        </div>
        <div className="space-y-2 text-center">
          <p className="text-sm text-va-text2">
            Use your email and password to continue.
          </p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div
              className="rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
              role="alert"
            >
              {error}
            </div>
          )}
          <div>
            <label
              htmlFor="email"
              className="mb-1 block text-sm font-medium text-va-text"
            >
              Email
            </label>
            <VAInput
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label
              htmlFor="password"
              className="mb-1 block text-sm font-medium text-va-text"
            >
              Password
            </label>
            <VAInput
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <VAButton
            type="submit"
            variant="primary"
            disabled={loading}
            className="w-full"
          >
            {loading ? "Signing in…" : "Sign in"}
          </VAButton>
        </form>
        <p className="text-center text-sm text-va-text2">
          No account? Sign up is via Supabase Dashboard or API.
        </p>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center">
          <p className="text-va-text2">Loading…</p>
        </main>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
