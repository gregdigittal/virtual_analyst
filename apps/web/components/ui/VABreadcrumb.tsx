"use client";

import Link from "next/link";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface VABreadcrumbProps {
  items: BreadcrumbItem[];
  className?: string;
}

export function VABreadcrumb({ items, className = "" }: VABreadcrumbProps) {
  return (
    <nav aria-label="Breadcrumb" className={className}>
      <ol className="flex items-center gap-1.5 text-sm">
        {items.map((item, i) => (
          <li key={i} className="flex items-center gap-1.5">
            {i > 0 && (
              <span className="text-va-muted" aria-hidden="true">/</span>
            )}
            {item.href && i < items.length - 1 ? (
              <Link
                href={item.href}
                className="text-va-text2 hover:text-va-text transition-colors"
              >
                {item.label}
              </Link>
            ) : (
              <span
                className="text-va-text font-medium"
                aria-current={i === items.length - 1 ? "page" : undefined}
              >
                {item.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
