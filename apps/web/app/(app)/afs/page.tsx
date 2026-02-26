"use client";

import Link from "next/link";
import { VAButton, VACard } from "@/components/ui";

export default function AFSPage() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Annual Financial Statements
        </h1>
        <p className="mt-1 text-sm text-va-text2">
          AI-powered financial statement generation with IFRS/GAAP compliance.
        </p>
      </div>

      <VACard className="p-8 text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-va-blue/10">
          <svg width={28} height={28} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="text-va-blue">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
        </div>
        <h2 className="text-lg font-medium text-va-text">Coming Soon</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-va-text2">
          Upload trial balances and prior-year statements, then use AI to
          generate complete financial statement packages with framework-compliant
          disclosures.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <Link href="/excel-import">
            <VAButton variant="secondary">Import Excel model</VAButton>
          </Link>
          <Link href="/marketplace">
            <VAButton variant="primary">Browse templates</VAButton>
          </Link>
        </div>
      </VACard>

      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {[
          {
            title: "Framework Engine",
            desc: "IFRS, IFRS for SMEs, US GAAP, and SA Companies Act support with versioned disclosure checklists.",
          },
          {
            title: "AI Disclosure Drafter",
            desc: "Natural language instructions generate compliant disclosures using RAG over accounting standards.",
          },
          {
            title: "Statement Generator",
            desc: "PDF, DOCX, and iXBRL output with branding, comparatives, and automatic cross-references.",
          },
        ].map((f) => (
          <VACard key={f.title} className="p-4">
            <h3 className="text-sm font-medium text-va-text">{f.title}</h3>
            <p className="mt-1 text-xs text-va-text2">{f.desc}</p>
          </VACard>
        ))}
      </div>
    </main>
  );
}
