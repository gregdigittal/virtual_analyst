/**
 * Base URL for the app, used for OAuth redirects and email links.
 * In production, set NEXT_PUBLIC_APP_URL so SSO redirects to the correct domain
 * (e.g. https://yourapp.com) instead of relying on request origin.
 */
export function getAppBaseUrl(): string {
  if (typeof window !== "undefined") {
    const envUrl = process.env.NEXT_PUBLIC_APP_URL;
    if (envUrl) return envUrl.replace(/\/$/, "");
    return window.location.origin;
  }
  return process.env.NEXT_PUBLIC_APP_URL ?? "";
}
