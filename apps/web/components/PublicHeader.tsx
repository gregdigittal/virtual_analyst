import Image from "next/image";
import Link from "next/link";

export function PublicHeader() {
  return (
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
  );
}
