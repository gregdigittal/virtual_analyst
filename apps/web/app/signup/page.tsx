"use client";

import { VAButton, VAInput } from "@/components/ui";
import { getAppBaseUrl } from "@/lib/app-url";
import { createClient } from "@/lib/supabase/client";
import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

function SignUpForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/baselines";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [emailSent, setEmailSent] = useState(false);

  async function handleOAuth(provider: "google" | "azure") {
    setError(null);
    setLoading(true);
    try {
      const supabase = createClient();
      const baseUrl = getAppBaseUrl();
      const redirectTo = `${baseUrl}/auth/callback${next && next !== "/baselines" ? `?next=${encodeURIComponent(next)}` : ""}`;
      const { error: err } = await supabase.auth.signInWithOAuth({
        provider: provider === "azure" ? "azure" : "google",
        options: { redirectTo },
      });
      if (err) {
        setError(err.message);
        return;
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    try {
      const supabase = createClient();
      const { data, error: err } = await supabase.auth.signUp({
        email,
        password,
        options: { emailRedirectTo: `${getAppBaseUrl()}/auth/callback${next ? `?next=${encodeURIComponent(next)}` : ""}` },
      });

      if (err) {
        setError(err.message);
        return;
      }

      if (data?.user && !data.user.identities?.length) {
        setError("An account with this email may already exist. Try signing in.");
        return;
      }

      setEmailSent(true);
    } finally {
      setLoading(false);
    }
  }

  if (emailSent) {
    return (
      <main className="mx-auto flex min-h-screen flex-col justify-center px-6 py-12">
        <div className="mx-auto w-full max-w-md space-y-8 text-center">
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
          <div className="rounded-va-lg border border-va-border bg-va-panel/80 p-6">
            <h1 className="font-brand text-xl font-semibold text-va-text">
              Check your email
            </h1>
            <p className="mt-2 text-sm text-va-text2">
              We sent a confirmation link to <strong className="text-va-text">{email}</strong>. Click the link to activate your account, then sign in.
            </p>
            <VAButton
              type="button"
              variant="secondary"
              className="mt-6 w-full"
              onClick={() => router.push("/login")}
            >
              Go to sign in
            </VAButton>
          </div>
          <p className="text-sm text-va-text2">
            Didn’t receive the email? Check spam or{" "}
            <button
              type="button"
              className="text-va-blue hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded-va-xs"
              onClick={() => setEmailSent(false)}
            >
              try again
            </button>
            .
          </p>
        </div>
      </main>
    );
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
          <h1 className="font-brand text-xl font-semibold text-va-text">
            Create your account
          </h1>
          <p className="text-sm text-va-text2">
            Start your free trial. No credit card required.
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <VAButton
            type="button"
            variant="secondary"
            disabled={loading}
            className="w-full"
            onClick={() => handleOAuth("google")}
          >
            Continue with Google
          </VAButton>
          <VAButton
            type="button"
            variant="secondary"
            disabled={loading}
            className="w-full"
            onClick={() => handleOAuth("azure")}
          >
            Continue with Microsoft
          </VAButton>
        </div>
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t border-va-border" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-va-midnight px-2 text-va-text2">Or</span>
          </div>
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
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              aria-describedby={error ? "password-requirement" : undefined}
            />
            <p id="password-requirement" className="mt-1 text-xs text-va-text2">
              At least 8 characters
            </p>
          </div>
          <div>
            <label
              htmlFor="confirmPassword"
              className="mb-1 block text-sm font-medium text-va-text"
            >
              Confirm password
            </label>
            <VAInput
              id="confirmPassword"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={8}
            />
          </div>
          <VAButton
            type="submit"
            variant="primary"
            disabled={loading}
            className="w-full"
          >
            {loading ? "Creating account…" : "Create account"}
          </VAButton>
        </form>
        <p className="text-center text-sm text-va-text2">
          Already have an account?{" "}
          <Link
            href={`/login${next && next !== "/baselines" ? `?next=${encodeURIComponent(next)}` : ""}`}
            className="text-va-blue hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded-va-xs"
          >
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}

export default function SignUpPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center">
          <p className="text-va-text2">Loading…</p>
        </main>
      }
    >
      <SignUpForm />
    </Suspense>
  );
}
