/**
 * Structured logger for the Virtual Analyst frontend.
 *
 * In development: writes to the browser/Node console.
 * In production: writes to the console AND optionally forwards to a remote
 * endpoint via NEXT_PUBLIC_LOG_ENDPOINT (fire-and-forget, never blocks the UI).
 *
 * To integrate a third-party service (e.g. Sentry, Datadog RUM):
 *   1. Install the SDK: npm install @sentry/nextjs
 *   2. Replace the _sendRemote call below with the SDK's capture method.
 *   3. Remove NEXT_PUBLIC_LOG_ENDPOINT once the SDK handles transport.
 */

export type LogLevel = "debug" | "info" | "warn" | "error";

export interface LogEntry {
  level: LogLevel;
  message: string;
  context?: Record<string, unknown>;
  error?: Error;
  timestamp: string;
}

const isDev = process.env.NODE_ENV === "development";
const remoteEndpoint = process.env.NEXT_PUBLIC_LOG_ENDPOINT ?? null;

function _sendRemote(entry: LogEntry): void {
  if (!remoteEndpoint) return;
  fetch(remoteEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...entry,
      error: entry.error
        ? { message: entry.error.message, stack: entry.error.stack }
        : undefined,
    }),
    keepalive: true,
  }).catch(() => {
    // Intentionally silenced — logging infrastructure failure must not surface to users.
  });
}

function _log(
  level: LogLevel,
  message: string,
  context?: Record<string, unknown>,
  error?: Error
): void {
  const entry: LogEntry = { level, message, context, error, timestamp: new Date().toISOString() };

  const consoleArgs: unknown[] = [`[${level.toUpperCase()}] ${message}`];
  // Always include context when explicitly passed (even empty {}) so error is always the 3rd arg.
  if (context !== undefined) consoleArgs.push(context);
  if (error) consoleArgs.push(error);

  switch (level) {
    case "debug":
      if (isDev) console.debug(...consoleArgs);
      break;
    case "info":
      console.info(...consoleArgs);
      break;
    case "warn":
      console.warn(...consoleArgs);
      break;
    case "error":
      console.error(...consoleArgs);
      break;
  }

  if (!isDev) {
    _sendRemote(entry);
  }
}

export const logger = {
  debug: (message: string, context?: Record<string, unknown>) =>
    _log("debug", message, context),
  info: (message: string, context?: Record<string, unknown>) =>
    _log("info", message, context),
  warn: (message: string, context?: Record<string, unknown>, error?: Error) =>
    _log("warn", message, context, error),
  error: (message: string, context?: Record<string, unknown>, error?: Error) =>
    _log("error", message, context, error),
};
