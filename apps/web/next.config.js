const { withSentryConfig } = require("@sentry/nextjs");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
};

module.exports = withSentryConfig(nextConfig, {
  // Suppress source map upload (no auth token configured)
  silent: true,
  disableServerWebpackPlugin: true,
  disableClientWebpackPlugin: true,
});
