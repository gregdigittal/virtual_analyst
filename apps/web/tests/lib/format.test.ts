import { describe, it, expect } from "vitest";
import { formatDate, formatDateTime } from "../../lib/format";

describe("formatDate", () => {
  it("returns em-dash for null", () => {
    expect(formatDate(null)).toBe("\u2014");
  });

  it("returns em-dash for undefined", () => {
    expect(formatDate(undefined)).toBe("\u2014");
  });

  it("returns em-dash for empty string", () => {
    expect(formatDate("")).toBe("\u2014");
  });

  it("returns a non-empty string for a valid ISO date", () => {
    const result = formatDate("2026-01-15");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
    expect(result).not.toBe("\u2014");
  });

  it("returns em-dash for an invalid date string", () => {
    expect(formatDate("not-a-date")).toBe("\u2014");
  });
});

describe("formatDateTime", () => {
  it("returns em-dash for null", () => {
    expect(formatDateTime(null)).toBe("\u2014");
  });

  it("returns em-dash for undefined", () => {
    expect(formatDateTime(undefined)).toBe("\u2014");
  });

  it("returns em-dash for empty string", () => {
    expect(formatDateTime("")).toBe("\u2014");
  });

  it("returns a non-empty string for a valid ISO datetime", () => {
    const result = formatDateTime("2026-01-15T10:30:00Z");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
    expect(result).not.toBe("\u2014");
  });

  it("returns em-dash for an invalid datetime string", () => {
    expect(formatDateTime("not-a-date")).toBe("\u2014");
  });
});
