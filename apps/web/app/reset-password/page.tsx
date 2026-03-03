"use client";

import { VAButton, VAInput } from "@/components/ui";
import { createClient } from "@/lib/supabase/client";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function ResetPasswordPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

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
      const { error: err } = await supabase.auth.updateUser({ password });
      if (err) {
        setError(err.message);
        return;
      }
      setSuccess(true);
    } finally {
      setLoading(false);
    }
  }

  if (success) {
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
              Password updated
            </h1>
            <p className="mt-2 text-sm text-va-text2">
              Your password has been successfully reset. You can now sign in with
              your new password.
            </p>
            <VAButton
              type="button"
              variant="primary"
              className="mt-6 w-full"
              onClick={() => {
                router.push("/baselines");
                router.refresh();
              }}
            >
              Continue to dashboard
            </VAButton>
          </div>
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
            Set a new password
          </h1>
          <p className="text-sm text-va-text2">
            Choose a strong password for your account.
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
              htmlFor="password"
              className="mb-1 block text-sm font-medium text-va-text"
            >
              New password
            </label>
            <VAInput
              id="password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
            <p className="mt-1 text-xs text-va-text2">
              At least 8 characters
            </p>
          </div>
          <div>
            <label
              htmlFor="confirmPassword"
              className="mb-1 block text-sm font-medium text-va-text"
            >
              Confirm new password
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
            {loading ? "Updating password…" : "Update password"}
          </VAButton>
        </form>
        <p className="text-center text-sm text-va-text2">
          <Link
            href="/login"
            className="text-va-blue hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded-va-xs"
          >
            Back to sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
