"use client";

import { VACard } from "@/components/ui";
import Link from "next/link";

const settingsLinks = [
  { href: "/settings/billing", title: "Billing", description: "Plans, subscriptions, usage, and invoices." },
  { href: "/settings/integrations", title: "Integrations", description: "Connect Xero or QuickBooks and sync data." },
  { href: "/settings/audit", title: "Audit Log", description: "Search activity and export audit events." },
  { href: "/settings/currency", title: "Currency", description: "Base currency, FX rates, and conversions." },
  { href: "/settings/sso", title: "SSO / SAML", description: "Configure IdP metadata and SSO settings." },
  { href: "/settings/compliance", title: "Compliance", description: "GDPR exports and anonymization tools." },
  { href: "/settings/teams", title: "Teams", description: "Manage teams and members." },
];

export default function SettingsPage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Settings
        </h1>
        <p className="mt-1 text-sm text-va-text2">
          Configure account, integrations, billing, and compliance workflows.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {settingsLinks.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="rounded-va-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
          >
            <VACard className="h-full p-5 transition hover:bg-white/5">
              <h2 className="text-lg font-medium text-va-text">
                {item.title}
              </h2>
              <p className="mt-2 text-sm text-va-text2">
                {item.description}
              </p>
            </VACard>
          </Link>
        ))}
      </div>
    </main>
  );
}
