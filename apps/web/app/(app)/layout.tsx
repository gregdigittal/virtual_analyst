"use client";

import { useState } from "react";
import { VASidebar } from "@/components/VASidebar";

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden">
      <VASidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="flex-1 overflow-y-auto">
        <div className="sticky top-0 z-30 flex h-12 items-center border-b border-va-border bg-va-panel/95 px-4 md:hidden">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue rounded-va-xs p-1"
            aria-label="Open menu"
          >
            <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
