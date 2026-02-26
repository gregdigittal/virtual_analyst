"use client";

import { VAInput } from "./VAInput";
import { VASelect } from "./VASelect";

interface FilterConfig {
  key: string;
  label: string;
  options: { value: string; label: string }[];
}

interface VAListToolbarProps {
  searchValue: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  filters?: FilterConfig[];
  filterValues?: Record<string, string>;
  onFilterChange?: (key: string, value: string) => void;
  onClearFilters?: () => void;
  className?: string;
}

export function VAListToolbar({
  searchValue,
  onSearchChange,
  searchPlaceholder = "Search...",
  filters,
  filterValues = {},
  onFilterChange,
  onClearFilters,
  className = "",
}: VAListToolbarProps) {
  const hasActiveFilters = Object.values(filterValues).some((v) => v !== "");

  return (
    <div className={`mb-4 flex flex-wrap items-center gap-3 ${className}`}>
      <div className="relative flex-1 min-w-[200px]">
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
          <svg
            className="h-4 w-4 text-va-muted"
            width={16}
            height={16}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </div>
        <VAInput
          value={searchValue}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder={searchPlaceholder}
          className="pl-9"
        />
      </div>
      {filters?.map((f) => (
        <VASelect
          key={f.key}
          value={filterValues[f.key] ?? ""}
          onChange={(e) => onFilterChange?.(f.key, e.target.value)}
        >
          <option value="">{f.label}</option>
          {f.options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </VASelect>
      ))}
      {hasActiveFilters && onClearFilters && (
        <button
          type="button"
          onClick={onClearFilters}
          className="text-sm text-va-blue hover:text-va-blue/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue rounded-va-xs px-2 py-1"
        >
          Clear filters
        </button>
      )}
    </div>
  );
}
