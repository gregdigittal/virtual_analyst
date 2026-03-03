"use client";

import { VAButton, VAInput } from "@/components/ui";
import { getAppBaseUrl } from "@/lib/app-url";
import { createClient } from "@/lib/supabase/client";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [emailSent, setEmailSent] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const supabase = createClient();
      const baseUrl = getAppBaseUrl();
      const { error: err } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${baseUrl}/auth/callback?next=/reset-password`,
      });
      if (err) {
        setError(err.message);
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
              We sent a password reset link to{" "}
              <strong className="text-va-text">{email}</strong>. Click the link
              to set a new password.
            </p>
            <VAButton
              type="button"
              variant="secondary"
              className="mt-6 w-full"
              onClick={() => setEmailSent(false)}
            >
              Try a different email
            </VAButton>
          </div>
          <p className="text-sm text-va-text2">
            Remember your password?{" "}
            <Link
              href="/login"
              className="text-va-blue hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded-va-xs"
            >
              Sign in
            </Link>
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
            Reset your password
          </h1>
          <p className="text-sm text-va-text2">
            Enter your email and we&apos;ll send you a link to reset your
            password.
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
          <VAButton
            type="submit"
            variant="primary"
            disabled={loading}
            className="w-full"
          >
            {loading ? "Sending link…" : "Send reset link"}
          </VAButton>
        </form>
        <p className="text-center text-sm text-va-text2">
          Remember your password?{" "}
          <Link
            href="/login"
            className="text-va-blue hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded-va-xs"
          >
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
