import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

describe("logger", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "info").mockImplementation(() => {});
    vi.spyOn(console, "debug").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("logger.error calls console.error", async () => {
    const { logger } = await import("@/lib/logger");
    logger.error("test error");
    expect(console.error).toHaveBeenCalledWith(
      expect.stringContaining("test error")
    );
  });

  it("logger.warn calls console.warn", async () => {
    const { logger } = await import("@/lib/logger");
    logger.warn("test warning");
    expect(console.warn).toHaveBeenCalledWith(
      expect.stringContaining("test warning")
    );
  });

  it("logger.info calls console.info", async () => {
    const { logger } = await import("@/lib/logger");
    logger.info("test info");
    expect(console.info).toHaveBeenCalledWith(
      expect.stringContaining("test info")
    );
  });

  it("logger.error includes error object when provided", async () => {
    const { logger } = await import("@/lib/logger");
    const err = new Error("boom");
    logger.error("something failed", {}, err);
    expect(console.error).toHaveBeenCalledWith(
      expect.stringContaining("something failed"),
      expect.anything(),
      err
    );
  });
});
