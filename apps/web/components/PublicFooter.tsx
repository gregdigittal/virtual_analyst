import Image from "next/image";
import Link from "next/link";

export function PublicFooter() {
  return (
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
          <Link
            href="/competitors"
            className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded-va-xs"
          >
            Compare
          </Link>
        </nav>
        <p className="text-xs text-va-muted">
          &copy; {new Date().getFullYear()} Virtual Analyst. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
